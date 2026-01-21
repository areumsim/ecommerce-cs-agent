from __future__ import annotations

import csv
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Generator

from .interfaces import CsvRepoConfig, Repository

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False


class FileLock:
    _locks: Dict[str, threading.Lock] = {}
    _global_lock = threading.Lock()
    
    @classmethod
    def get_lock(cls, path: str) -> threading.Lock:
        with cls._global_lock:
            if path not in cls._locks:
                cls._locks[path] = threading.Lock()
            return cls._locks[path]
    
    @classmethod
    @contextmanager
    def acquire(cls, path: str, timeout: float = 30.0) -> Generator[None, None, None]:
        lock = cls.get_lock(path)
        acquired = lock.acquire(timeout=timeout)
        if not acquired:
            raise TimeoutError(f"Could not acquire lock for {path}")
        try:
            yield
        finally:
            lock.release()


class CSVRepository(Repository):
    """Lightweight CSV-backed repository for PoC.

    - Keeps data in-memory after first load for quick lookups
    - Persists mutations by writing a new temp file and renaming (atomic-ish)
    - Supports simple equality-based filtering
    - JSON fields are transparently (de)serialized
    """

    def __init__(self, config: CsvRepoConfig):
        self.config = config
        self._fieldnames: Optional[List[str]] = None
        self._rows: List[Dict[str, Any]] = []
        self._index: Dict[str, int] = {}
        self._load()

    # ---------- public api ----------
    def get_by_id(self, _id: str) -> Optional[Dict[str, Any]]:
        idx = self._index.get(_id)
        if idx is None:
            return None
        return dict(self._rows[idx])

    def query(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not filters:
            return [dict(r) for r in self._rows]
        out: List[Dict[str, Any]] = []
        for r in self._rows:
            if all(str(r.get(k)) == str(v) for k, v in filters.items()):
                out.append(dict(r))
        return out

    def create(self, record: Dict[str, Any]) -> Dict[str, Any]:
        key = record.get(self.config.key_field)
        if not key:
            raise ValueError(f"Missing key_field: {self.config.key_field}")
        if key in self._index:
            raise ValueError(f"Duplicate key: {key}")
        row = self._serialize(dict(record))
        self._rows.append(row)
        self._index[key] = len(self._rows) - 1
        self._persist()
        return dict(row)

    def update(self, _id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        idx = self._index.get(_id)
        if idx is None:
            raise KeyError(_id)
        updated = dict(self._rows[idx])
        updated.update(patch)
        self._rows[idx] = self._serialize(updated)
        self._persist()
        return dict(self._rows[idx])

    def delete(self, _id: str) -> None:
        idx = self._index.pop(_id, None)
        if idx is None:
            return
        # remove and rebuild index for simplicity
        del self._rows[idx]
        self._rebuild_index()
        self._persist()

    # ---------- internals ----------
    def _path(self) -> str:
        return os.path.join(self.config.data_dir, self.config.filename)

    def _load(self) -> None:
        path = self._path()
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", newline="", encoding="utf-8") as f:
                pass
            self._rows = []
            self._index = {}
            return

        with FileLock.acquire(path):
            with open(path, "r", newline="", encoding="utf-8") as f:
                if HAS_FCNTL:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                reader = csv.DictReader(f)
                self._fieldnames = reader.fieldnames or []
                for row in reader:
                    self._rows.append(self._deserialize(dict(row)))
        self._rebuild_index()

    def _persist(self) -> None:
        path = self._path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fieldnames = self._fieldnames or self._infer_fieldnames()
        
        with FileLock.acquire(path):
            fd, tmp = tempfile.mkstemp(prefix="csvrepo_", dir=os.path.dirname(path))
            os.close(fd)
            try:
                with open(tmp, "w", newline="", encoding="utf-8") as f:
                    if HAS_FCNTL:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in self._rows:
                        writer.writerow(self._serialize_for_write(row, fieldnames))
                os.replace(tmp, path)
            finally:
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass

    def _rebuild_index(self) -> None:
        self._index = {}
        for i, r in enumerate(self._rows):
            key = r.get(self.config.key_field)
            if key:
                self._index[str(key)] = i

    def _infer_fieldnames(self) -> List[str]:
        names: List[str] = []
        for r in self._rows:
            for k in r.keys():
                if k not in names:
                    names.append(k)
        return names

    def _serialize(self, row: Dict[str, Any]) -> Dict[str, Any]:
        if self.config.json_fields:
            for jf in self.config.json_fields:
                if jf in row and not isinstance(row[jf], str):
                    row[jf] = json.dumps(row[jf], ensure_ascii=False)
        return row

    def _serialize_for_write(self, row: Dict[str, Any], fieldnames: List[str]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k in fieldnames:
            v = row.get(k)
            if self.config.json_fields and k in self.config.json_fields and not isinstance(v, str):
                out[k] = json.dumps(v, ensure_ascii=False)
            else:
                out[k] = v
        return out

    def _deserialize(self, row: Dict[str, Any]) -> Dict[str, Any]:
        if self.config.json_fields:
            for jf in self.config.json_fields:
                if jf in row and row[jf]:
                    try:
                        row[jf] = json.loads(row[jf])
                    except json.JSONDecodeError:
                        # leave as-is if malformed
                        pass
        return row

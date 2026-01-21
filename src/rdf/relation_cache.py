import time
from functools import lru_cache
from typing import Tuple

class RelationCache:
    def __init__(self, ttl: int = 60):
        self.ttl = ttl
        self._timestamps = {}

    def _is_valid(self, key):
        return key in self._timestamps and (time.time() - self._timestamps[key]) < self.ttl

    def get(self, key):
        if self._is_valid(key):
            return self._cache[key]
        return None

    def set(self, key, value):
        self._timestamps[key] = time.time()
        self._cache[key] = value

    _cache = {}

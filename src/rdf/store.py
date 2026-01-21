from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import logging
import base64
import os

import requests
import yaml

try:
    from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, XSD
    RDFLIB_AVAILABLE = True
except ImportError:
    RDFLIB_AVAILABLE = False
    Graph = None

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

logger = logging.getLogger(__name__)

ECOM = Namespace("http://example.org/ecommerce#") if RDFLIB_AVAILABLE else None
SCHEMA = Namespace("http://schema.org/") if RDFLIB_AVAILABLE else None

PREFIXES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX ecom: <http://example.org/ecommerce#>
PREFIX schema: <http://schema.org/>
"""


class UnifiedRDFStore:
    
    def __init__(self, persist_path: Optional[str] = None):
        if not RDFLIB_AVAILABLE:
            raise ImportError("rdflib not installed. Run: pip install rdflib")
        
        self.persist_path = persist_path
        self.graph = Graph()
        self._bind_namespaces()
        self._loaded = False
    
    def _bind_namespaces(self):
        self.graph.bind("ecom", ECOM)
        self.graph.bind("schema", SCHEMA)
        self.graph.bind("rdf", RDF)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("owl", OWL)
        self.graph.bind("xsd", XSD)
    
    def load_directory(self, directory: str) -> int:
        dir_path = Path(directory)
        if not dir_path.exists():
            logger.warning(f"Directory not found: {directory}")
            return 0
        
        count = 0
        for ttl_file in sorted(dir_path.glob("**/*.ttl")):
            try:
                self.graph.parse(ttl_file, format="turtle")
                logger.info(f"Loaded: {ttl_file.name}")
                count += 1
            except Exception as e:
                logger.error(f"Failed to load {ttl_file}: {e}")
        
        self._loaded = count > 0
        return count
    
    def load_file(self, filepath: str) -> bool:
        try:
            self.graph.parse(filepath, format="turtle")
            self._loaded = True
            return True
        except Exception as e:
            logger.error(f"Failed to load {filepath}: {e}")
            return False
    
    def query(self, sparql: str, include_prefixes: bool = True) -> List[Dict[str, Any]]:
        if include_prefixes and not sparql.strip().upper().startswith("PREFIX"):
            sparql = PREFIXES + sparql
        
        try:
            results = self.graph.query(sparql)
            if results.vars is None:
                return []
            
            return [
                {str(var): str(val) if val else None for var, val in zip(results.vars, row)}
                for row in results
            ]
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise
    
    def ask(self, sparql: str, include_prefixes: bool = True) -> bool:
        if include_prefixes and not sparql.strip().upper().startswith("PREFIX"):
            sparql = PREFIXES + sparql
        
        try:
            results = self.graph.query(sparql)
            return bool(results.askAnswer) if hasattr(results, 'askAnswer') else False
        except Exception as e:
            logger.error(f"ASK query failed: {e}")
            return False
    
    def update(self, sparql: str, include_prefixes: bool = True) -> bool:
        if include_prefixes and not sparql.strip().upper().startswith("PREFIX"):
            sparql = PREFIXES + sparql
        
        try:
            self.graph.update(sparql)
            return True
        except Exception as e:
            logger.error(f"Update failed: {e}")
            return False
    
    def add_triple(self, subject: str, predicate: str, obj: Any, obj_type: str = "uri"):
        s = URIRef(subject) if not subject.startswith("_:") else subject
        p = URIRef(predicate)
        
        if obj_type == "uri":
            o = URIRef(obj)
        elif obj_type == "literal":
            o = Literal(obj)
        elif obj_type == "int":
            o = Literal(obj, datatype=XSD.integer)
        elif obj_type == "float":
            o = Literal(obj, datatype=XSD.decimal)
        elif obj_type == "datetime":
            o = Literal(obj, datatype=XSD.dateTime)
        elif obj_type == "base64":
            o = Literal(obj, datatype=XSD.base64Binary)
        else:
            o = Literal(obj)
        
        self.graph.add((s, p, o))
    
    @staticmethod
    def encode_vector(vector: List[float]) -> str:
        if not NUMPY_AVAILABLE:
            raise ImportError("numpy not installed. Run: pip install numpy")
        arr = np.array(vector, dtype=np.float32)
        return base64.b64encode(arr.tobytes()).decode('ascii')
    
    @staticmethod
    def decode_vector(encoded: str) -> List[float]:
        if not NUMPY_AVAILABLE:
            raise ImportError("numpy not installed. Run: pip install numpy")
        data = base64.b64decode(encoded)
        return np.frombuffer(data, dtype=np.float32).tolist()
    
    def add_embedding(self, subject_uri: str, vector: List[float]):
        encoded = self.encode_vector(vector)
        self.add_triple(subject_uri, str(ECOM.embedding), encoded, "base64")
        self.add_triple(subject_uri, str(ECOM.embeddingDim), len(vector), "int")
    
    def get_embedding(self, subject_uri: str) -> Optional[List[float]]:
        query = f"""
            SELECT ?embedding
            WHERE {{
                <{subject_uri}> ecom:embedding ?embedding .
            }}
        """
        results = self.query(query)
        if results and results[0].get("embedding"):
            return self.decode_vector(results[0]["embedding"])
        return None
    
    def get_all_embeddings(self, type_filter: Optional[str] = None) -> List[Tuple[str, List[float]]]:
        type_clause = f"?s a <{type_filter}> ." if type_filter else ""
        query = f"""
            SELECT ?s ?embedding
            WHERE {{
                {type_clause}
                ?s ecom:embedding ?embedding .
            }}
        """
        results = self.query(query)
        embeddings = []
        for r in results:
            if r.get("embedding"):
                try:
                    vec = self.decode_vector(r["embedding"])
                    embeddings.append((r["s"], vec))
                except Exception:
                    continue
        return embeddings
    
    def vector_search(
        self, 
        query_vector: List[float], 
        type_filter: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Tuple[str, float]]:
        if not NUMPY_AVAILABLE:
            raise ImportError("numpy not installed. Run: pip install numpy")
        
        embeddings = self.get_all_embeddings(type_filter)
        if not embeddings:
            return []
        
        query_arr = np.array(query_vector, dtype=np.float32)
        query_norm = np.linalg.norm(query_arr)
        if query_norm == 0:
            return []
        query_arr = query_arr / query_norm
        
        similarities = []
        for uri, vec in embeddings:
            vec_arr = np.array(vec, dtype=np.float32)
            vec_norm = np.linalg.norm(vec_arr)
            if vec_norm == 0:
                continue
            vec_arr = vec_arr / vec_norm
            similarity = float(np.dot(query_arr, vec_arr))
            similarities.append((uri, similarity))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    def count_triples(self) -> int:
        return len(self.graph)
    
    def count_by_type(self, type_uri: str) -> int:
        query = f"""
            SELECT (COUNT(?s) as ?count)
            WHERE {{ ?s a <{type_uri}> . }}
        """
        results = self.query(query)
        return int(results[0]["count"]) if results else 0
    
    def save(self, filepath: Optional[str] = None) -> bool:
        path = filepath or self.persist_path
        if not path:
            logger.warning("No persist path specified")
            return False
        
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.graph.serialize(path, format="turtle")
            logger.info(f"Saved to: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save: {e}")
            return False
    
    def clear(self):
        self.graph = Graph()
        self._bind_namespaces()
        self._loaded = False
    
    @property
    def is_loaded(self) -> bool:
        return self._loaded
    
    @property
    def triple_count(self) -> int:
        return len(self.graph)


class FusekiStore:
    
    def __init__(self, endpoint: str, user: Optional[str] = None, password: Optional[str] = None):
        self.endpoint = endpoint.rstrip('/')
        self.sparql_endpoint = f"{self.endpoint}/sparql"
        self.update_endpoint = f"{self.endpoint}/update"
        self.data_endpoint = f"{self.endpoint}/data"
        self.auth = (user, password) if user and password else None
        self._loaded = True
    
    def query(self, sparql: str, include_prefixes: bool = True) -> List[Dict[str, Any]]:
        if include_prefixes and not sparql.strip().upper().startswith("PREFIX"):
            sparql = PREFIXES + sparql
        
        try:
            resp = requests.get(
                self.sparql_endpoint,
                params={"query": sparql},
                headers={"Accept": "application/json"},
                auth=self.auth,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            
            results = []
            for binding in data.get("results", {}).get("bindings", []):
                row = {}
                for var, val in binding.items():
                    row[var] = val.get("value") if val else None
                results.append(row)
            return results
        except Exception as e:
            logger.error(f"Fuseki query failed: {e}")
            raise
    
    def ask(self, sparql: str, include_prefixes: bool = True) -> bool:
        if include_prefixes and not sparql.strip().upper().startswith("PREFIX"):
            sparql = PREFIXES + sparql
        
        try:
            resp = requests.get(
                self.sparql_endpoint,
                params={"query": sparql},
                headers={"Accept": "application/json"},
                auth=self.auth,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json().get("boolean", False)
        except Exception as e:
            logger.error(f"Fuseki ASK query failed: {e}")
            return False
    
    def update(self, sparql: str, include_prefixes: bool = True) -> bool:
        if include_prefixes and not sparql.strip().upper().startswith("PREFIX"):
            sparql = PREFIXES + sparql
        
        try:
            resp = requests.post(
                self.update_endpoint,
                data={"update": sparql},
                auth=self.auth,
                timeout=30,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Fuseki update failed: {e}")
            return False
    
    def count_triples(self) -> int:
        results = self.query("SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }")
        return int(results[0]["count"]) if results else 0
    
    def count_by_type(self, type_uri: str) -> int:
        results = self.query(f"SELECT (COUNT(?s) as ?count) WHERE {{ ?s a <{type_uri}> . }}")
        return int(results[0]["count"]) if results else 0
    
    @staticmethod
    def encode_vector(vector: List[float]) -> str:
        if not NUMPY_AVAILABLE:
            raise ImportError("numpy not installed")
        arr = np.array(vector, dtype=np.float32)
        return base64.b64encode(arr.tobytes()).decode('ascii')
    
    @staticmethod
    def decode_vector(encoded: str) -> List[float]:
        if not NUMPY_AVAILABLE:
            raise ImportError("numpy not installed")
        data = base64.b64decode(encoded)
        return np.frombuffer(data, dtype=np.float32).tolist()
    
    def add_embedding(self, subject_uri: str, vector: List[float]) -> bool:
        """Add or update embedding for a subject in Fuseki."""
        encoded = self.encode_vector(vector)
        dim = len(vector)

        # Delete existing embedding first
        delete_query = f"""
        DELETE WHERE {{
            <{subject_uri}> ecom:embedding ?e .
        }}
        """
        self.update(delete_query)

        delete_dim_query = f"""
        DELETE WHERE {{
            <{subject_uri}> ecom:embeddingDim ?d .
        }}
        """
        self.update(delete_dim_query)

        # Insert new embedding
        insert_query = f"""
        INSERT DATA {{
            <{subject_uri}> ecom:embedding "{encoded}"^^xsd:base64Binary .
            <{subject_uri}> ecom:embeddingDim {dim} .
        }}
        """
        return self.update(insert_query)

    def get_embedding(self, subject_uri: str) -> Optional[List[float]]:
        results = self.query(f"SELECT ?embedding WHERE {{ <{subject_uri}> ecom:embedding ?embedding . }}")
        if results and results[0].get("embedding"):
            return self.decode_vector(results[0]["embedding"])
        return None
    
    def get_all_embeddings(self, type_filter: Optional[str] = None) -> List[Tuple[str, List[float]]]:
        type_clause = f"?s a <{type_filter}> ." if type_filter else ""
        results = self.query(f"SELECT ?s ?embedding WHERE {{ {type_clause} ?s ecom:embedding ?embedding . }}")
        embeddings = []
        for r in results:
            if r.get("embedding"):
                try:
                    vec = self.decode_vector(r["embedding"])
                    embeddings.append((r["s"], vec))
                except Exception:
                    continue
        return embeddings
    
    def vector_search(self, query_vector: List[float], type_filter: Optional[str] = None, top_k: int = 10) -> List[Tuple[str, float]]:
        if not NUMPY_AVAILABLE:
            raise ImportError("numpy not installed")
        
        embeddings = self.get_all_embeddings(type_filter)
        if not embeddings:
            return []
        
        query_arr = np.array(query_vector, dtype=np.float32)
        query_norm = np.linalg.norm(query_arr)
        if query_norm == 0:
            return []
        query_arr = query_arr / query_norm
        
        similarities = []
        for uri, vec in embeddings:
            vec_arr = np.array(vec, dtype=np.float32)
            vec_norm = np.linalg.norm(vec_arr)
            if vec_norm == 0:
                continue
            vec_arr = vec_arr / vec_norm
            similarity = float(np.dot(query_arr, vec_arr))
            similarities.append((uri, similarity))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    @property
    def is_loaded(self) -> bool:
        return self._loaded
    
    @property
    def triple_count(self) -> int:
        return self.count_triples()


def _load_rdf_config() -> Dict[str, Any]:
    config_path = Path(__file__).parent.parent.parent / "configs" / "rdf.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


_default_store = None


def get_store(ontology_dir: Optional[str] = None, auto_load: bool = True):
    global _default_store
    
    if _default_store is not None:
        return _default_store
    
    config = _load_rdf_config()
    backend = config.get("rdf", {}).get("backend", "rdflib")
    
    if backend == "fuseki":
        fuseki_cfg = config.get("fuseki", {})
        endpoint = os.environ.get("FUSEKI_ENDPOINT", fuseki_cfg.get("endpoint", "http://localhost:3030/ecommerce"))
        user = os.environ.get("FUSEKI_USER", fuseki_cfg.get("user"))
        password = os.environ.get("FUSEKI_PASSWORD", fuseki_cfg.get("password"))
        
        try:
            _default_store = FusekiStore(endpoint, user, password)
            test_count = _default_store.count_triples()
            logger.info(f"Connected to Fuseki: {endpoint} ({test_count} triples)")
        except Exception as e:
            logger.warning(f"Fuseki connection failed: {e}, falling back to RDFLib")
            backend = "rdflib"
    
    if backend == "rdflib":
        if not RDFLIB_AVAILABLE:
            raise ImportError("rdflib not installed")
        _default_store = UnifiedRDFStore()
        if auto_load:
            load_dir = ontology_dir or config.get("rdf", {}).get("ontology_dir")
            if not load_dir:
                load_dir = str(Path(__file__).parent.parent.parent / "ontology")
            if Path(load_dir).exists():
                _default_store.load_directory(load_dir)
    
    return _default_store


def reset_store():
    global _default_store
    _default_store = None

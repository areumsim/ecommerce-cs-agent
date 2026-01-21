"""RDF Store and Repository Tests.

Tests for the RDFLib-based unified store and repository.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import os


class TestUnifiedRDFStore:
    """Tests for UnifiedRDFStore class."""
    
    def test_store_initialization(self):
        """Test store initializes correctly."""
        from src.rdf.store import UnifiedRDFStore
        
        store = UnifiedRDFStore()
        assert store.graph is not None
        assert store.triple_count == 0
        assert not store.is_loaded
    
    def test_load_directory(self):
        """Test loading TTL files from directory."""
        from src.rdf.store import UnifiedRDFStore
        
        store = UnifiedRDFStore()
        
        # Load from ontology directory
        project_root = Path(__file__).parent.parent
        ontology_dir = project_root / "ontology"
        
        if ontology_dir.exists():
            count = store.load_directory(str(ontology_dir))
            assert count > 0
            assert store.is_loaded
            assert store.triple_count > 0
    
    def test_load_nonexistent_directory(self):
        """Test loading from non-existent directory."""
        from src.rdf.store import UnifiedRDFStore
        
        store = UnifiedRDFStore()
        count = store.load_directory("/nonexistent/path")
        assert count == 0
        assert not store.is_loaded
    
    def test_query_basic(self):
        """Test basic SPARQL query."""
        from src.rdf.store import UnifiedRDFStore, ECOM
        
        store = UnifiedRDFStore()
        
        # Add test data
        store.add_triple(
            f"{ECOM}test_product",
            f"{ECOM}productId",
            "TEST001",
            "string"
        )
        store.add_triple(
            f"{ECOM}test_product",
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
            f"{ECOM}Product",
            "uri"
        )
        
        # Query
        results = store.query("""
            SELECT ?id
            WHERE {
                ?product ecom:productId ?id .
            }
        """)
        
        assert len(results) == 1
        assert results[0]["id"] == "TEST001"
    
    def test_add_triple_types(self):
        """Test adding triples with different types."""
        from src.rdf.store import UnifiedRDFStore, ECOM
        
        store = UnifiedRDFStore()
        
        # String
        store.add_triple(f"{ECOM}test", f"{ECOM}name", "Test Name", "string")
        
        # Integer
        store.add_triple(f"{ECOM}test", f"{ECOM}count", 42, "int")
        
        # Float
        store.add_triple(f"{ECOM}test", f"{ECOM}price", 99.99, "float")
        
        # URI
        store.add_triple(f"{ECOM}test", f"{ECOM}category", f"{ECOM}electronics", "uri")
        
        assert store.triple_count == 4
    
    def test_vector_encoding_decoding(self):
        """Test vector encoding and decoding."""
        from src.rdf.store import UnifiedRDFStore
        
        original = [0.1, 0.2, 0.3, 0.4, 0.5]
        
        encoded = UnifiedRDFStore.encode_vector(original)
        assert isinstance(encoded, str)
        
        decoded = UnifiedRDFStore.decode_vector(encoded)
        assert len(decoded) == len(original)
        
        for o, d in zip(original, decoded):
            assert abs(o - d) < 0.0001
    
    def test_add_and_get_embedding(self):
        """Test adding and retrieving embeddings."""
        from src.rdf.store import UnifiedRDFStore, ECOM
        
        store = UnifiedRDFStore()
        
        subject = f"{ECOM}test_product"
        vector = [0.1, 0.2, 0.3, 0.4]
        
        store.add_embedding(subject, vector)
        
        retrieved = store.get_embedding(subject)
        assert retrieved is not None
        assert len(retrieved) == len(vector)
    
    def test_vector_search(self):
        """Test vector similarity search."""
        from src.rdf.store import UnifiedRDFStore, ECOM
        
        store = UnifiedRDFStore()
        
        # Add some embeddings
        store.add_embedding(f"{ECOM}product1", [1.0, 0.0, 0.0])
        store.add_embedding(f"{ECOM}product2", [0.9, 0.1, 0.0])
        store.add_embedding(f"{ECOM}product3", [0.0, 1.0, 0.0])
        
        # Search for vectors similar to [1.0, 0.0, 0.0]
        results = store.vector_search([1.0, 0.0, 0.0], top_k=2)
        
        assert len(results) == 2
        # product1 should be most similar (exact match)
        assert "product1" in results[0][0]
        assert results[0][1] > 0.99
    
    def test_count_by_type(self):
        """Test counting entities by type."""
        from src.rdf.store import UnifiedRDFStore, ECOM
        
        store = UnifiedRDFStore()
        
        # Add some customers
        for i in range(5):
            store.add_triple(
                f"{ECOM}customer_{i}",
                "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                f"{ECOM}Customer",
                "uri"
            )
        
        count = store.count_by_type(str(ECOM.Customer))
        assert count == 5
    
    def test_clear(self):
        """Test clearing the store."""
        from src.rdf.store import UnifiedRDFStore, ECOM
        
        store = UnifiedRDFStore()
        store.add_triple(f"{ECOM}test", f"{ECOM}name", "Test", "string")
        assert store.triple_count > 0
        
        store.clear()
        assert store.triple_count == 0
        assert not store.is_loaded
    
    def test_save_and_load(self):
        """Test saving and loading store."""
        from src.rdf.store import UnifiedRDFStore, ECOM
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.ttl")
            
            # Create and save
            store1 = UnifiedRDFStore(persist_path=filepath)
            store1.add_triple(f"{ECOM}test", f"{ECOM}name", "Test", "string")
            assert store1.save()
            
            # Load in new store
            store2 = UnifiedRDFStore()
            assert store2.load_file(filepath)
            assert store2.triple_count == store1.triple_count


class TestRDFRepository:
    """Tests for RDFRepository class."""
    
    @pytest.fixture
    def repo(self):
        """Create a repository with test data."""
        from src.rdf.store import UnifiedRDFStore, ECOM
        from src.rdf.repository import RDFRepository
        
        store = UnifiedRDFStore()
        
        # Add test customer
        store.add_triple(f"{ECOM}customer_test", "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", f"{ECOM}Customer", "uri")
        store.add_triple(f"{ECOM}customer_test", f"{ECOM}customerId", "user_test", "string")
        store.add_triple(f"{ECOM}customer_test", f"{ECOM}name", "테스트 고객", "string")
        store.add_triple(f"{ECOM}customer_test", f"{ECOM}email", "test@example.com", "string")
        store.add_triple(f"{ECOM}customer_test", f"{ECOM}membershipLevel", "gold", "string")
        
        # Add test product
        store.add_triple(f"{ECOM}product_test", "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", f"{ECOM}Product", "uri")
        store.add_triple(f"{ECOM}product_test", f"{ECOM}productId", "prod_test", "string")
        store.add_triple(f"{ECOM}product_test", f"{ECOM}title", "테스트 상품", "string")
        store.add_triple(f"{ECOM}product_test", f"{ECOM}brand", "TestBrand", "string")
        store.add_triple(f"{ECOM}product_test", f"{ECOM}price", 100.0, "float")
        
        return RDFRepository(store)
    
    def test_get_customer(self, repo):
        """Test getting customer by ID."""
        customer = repo.get_customer("user_test")
        
        assert customer is not None
        assert customer.customer_id == "user_test"
        assert customer.name == "테스트 고객"
        assert customer.email == "test@example.com"
        assert customer.membership_level == "gold"
    
    def test_get_customer_not_found(self, repo):
        """Test getting non-existent customer."""
        customer = repo.get_customer("nonexistent")
        assert customer is None
    
    def test_get_customers(self, repo):
        """Test getting all customers."""
        customers = repo.get_customers(limit=10)
        assert len(customers) >= 1
        assert any(c.customer_id == "user_test" for c in customers)
    
    def test_get_product(self, repo):
        """Test getting product by ID."""
        product = repo.get_product("prod_test")
        
        assert product is not None
        assert product.product_id == "prod_test"
        assert product.title == "테스트 상품"
        assert product.brand == "TestBrand"
        assert product.price == 100.0
    
    def test_get_product_not_found(self, repo):
        """Test getting non-existent product."""
        product = repo.get_product("nonexistent")
        assert product is None
    
    def test_get_products(self, repo):
        """Test getting all products."""
        products = repo.get_products(limit=10)
        assert len(products) >= 1
        assert any(p.product_id == "prod_test" for p in products)
    
    def test_count_customers(self, repo):
        """Test counting customers."""
        count = repo.count_customers()
        assert count >= 1
    
    def test_count_products(self, repo):
        """Test counting products."""
        count = repo.count_products()
        assert count >= 1


class TestGetStore:
    """Tests for get_store singleton."""
    
    def test_singleton(self):
        """Test that get_store returns same instance."""
        from src.rdf.store import get_store, _default_store
        
        # Reset singleton for clean test
        import src.rdf.store as store_module
        store_module._default_store = None
        
        store1 = get_store(auto_load=False)
        store2 = get_store(auto_load=False)
        
        assert store1 is store2
    
    def test_auto_load(self):
        """Test auto-loading ontology."""
        from src.rdf.store import get_store
        import src.rdf.store as store_module
        
        # Reset singleton
        store_module._default_store = None
        
        store = get_store(auto_load=True)
        
        # Should have loaded ontology if it exists
        project_root = Path(__file__).parent.parent
        if (project_root / "ontology").exists():
            assert store.triple_count > 0


class TestIntegration:
    """Integration tests using real ontology files."""
    
    @pytest.fixture
    def loaded_repo(self):
        """Create repository with loaded ontology."""
        from src.rdf.store import get_store
        from src.rdf.repository import RDFRepository
        import src.rdf.store as store_module
        
        # Reset and load
        store_module._default_store = None
        store = get_store(auto_load=True)
        
        return RDFRepository(store)
    
    @pytest.mark.skipif(
        not Path(__file__).parent.parent.joinpath("ontology/instances").exists(),
        reason="Ontology files not present"
    )
    def test_collaborative_recommendations(self, loaded_repo):
        """Test collaborative filtering recommendations."""
        # Get a customer
        customers = loaded_repo.get_customers(limit=1)
        if not customers:
            pytest.skip("No customers in ontology")
        
        customer_id = customers[0].customer_id
        
        # Get recommendations (may be empty if no purchase overlap)
        recs = loaded_repo.get_collaborative_recommendations(customer_id, limit=5)
        
        # Just verify it doesn't error
        assert isinstance(recs, list)
    
    @pytest.mark.skipif(
        not Path(__file__).parent.parent.joinpath("ontology/instances").exists(),
        reason="Ontology files not present"
    )
    def test_similar_products(self, loaded_repo):
        """Test similar products query."""
        # Get a product
        products = loaded_repo.get_products(limit=1)
        if not products:
            pytest.skip("No products in ontology")
        
        product_id = products[0].product_id
        
        # Get similar products
        similar = loaded_repo.get_similar_products(product_id, limit=5)
        
        # Just verify it doesn't error
        assert isinstance(similar, list)

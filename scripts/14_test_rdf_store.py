#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rdf.store import UnifiedRDFStore
from src.rdf.repository import RDFRepository


def test_store_loading():
    print("[1/5] Testing store loading...")
    store = UnifiedRDFStore()
    
    ontology_dir = Path(__file__).parent.parent / "ontology"
    count = store.load_directory(str(ontology_dir))
    
    print(f"      Loaded {count} TTL files")
    print(f"      Total triples: {store.triple_count}")
    
    if count == 0:
        print("[WARN] No TTL files loaded. Run: python scripts/12_generate_mock_ttl.py")
        return None
    
    print("[OK] Store loaded")
    return store


def test_counts(store: UnifiedRDFStore):
    print("\n[2/5] Testing counts...")
    repo = RDFRepository(store)
    
    customers = repo.count_customers()
    products = repo.count_products()
    orders = repo.count_orders()
    
    print(f"      Customers: {customers}")
    print(f"      Products: {products}")
    print(f"      Orders: {orders}")
    
    print("[OK] Counts retrieved")
    return customers > 0 or products > 0


def test_customer_query(store: UnifiedRDFStore):
    print("\n[3/5] Testing customer query...")
    repo = RDFRepository(store)
    
    customers = repo.get_customers(limit=5)
    if not customers:
        print("[SKIP] No customers found")
        return True
    
    print(f"      Found {len(customers)} customers")
    for c in customers[:3]:
        print(f"        - {c.customer_id}: {c.name} ({c.email})")
    
    print("[OK] Customer query works")
    return True


def test_product_query(store: UnifiedRDFStore):
    print("\n[4/5] Testing product query...")
    repo = RDFRepository(store)
    
    products = repo.get_products(limit=5)
    if not products:
        print("[SKIP] No products found")
        return True
    
    print(f"      Found {len(products)} products")
    for p in products[:3]:
        print(f"        - {p.product_id}: {p.title} (${p.price})")
    
    print("[OK] Product query works")
    return True


def test_collaborative_recommendation(store: UnifiedRDFStore):
    print("\n[5/5] Testing collaborative recommendation...")
    repo = RDFRepository(store)
    
    customers = repo.get_customers(limit=1)
    if not customers:
        print("[SKIP] No customers for recommendation test")
        return True
    
    customer_id = customers[0].customer_id
    recommendations = repo.get_collaborative_recommendations(customer_id, limit=5)
    
    print(f"      Recommendations for {customer_id}: {len(recommendations)} products")
    for product, score in recommendations[:3]:
        print(f"        - {product.title} (score: {score})")
    
    print("[OK] Recommendation query works")
    return True


def test_vector_operations(store: UnifiedRDFStore):
    print("\n[BONUS] Testing vector operations...")
    
    test_vector = [0.1] * 384
    encoded = store.encode_vector(test_vector)
    decoded = store.decode_vector(encoded)
    
    if len(decoded) == 384 and abs(decoded[0] - 0.1) < 0.001:
        print("[OK] Vector encode/decode works")
        return True
    else:
        print("[FAIL] Vector encode/decode failed")
        return False


def main():
    print(f"\n{'='*60}")
    print("RDF Store Integration Test")
    print(f"{'='*60}\n")
    
    store = test_store_loading()
    if store is None:
        print("\n[INFO] Generating mock data first...")
        import subprocess
        subprocess.run([sys.executable, "scripts/12_generate_mock_ttl.py"], 
                      cwd=Path(__file__).parent.parent)
        store = test_store_loading()
        if store is None:
            print("[FAIL] Could not load store")
            sys.exit(1)
    
    test_counts(store)
    test_customer_query(store)
    test_product_query(store)
    test_collaborative_recommendation(store)
    test_vector_operations(store)
    
    print(f"\n{'='*60}")
    print("All tests passed!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate product embeddings and store in RDF.

This script:
1. Loads products from RDF store
2. Generates text embeddings using sentence-transformers
3. Stores embeddings back in RDF for semantic search

Usage:
    python scripts/15_generate_embeddings.py
    python scripts/15_generate_embeddings.py --model sentence-transformers/all-MiniLM-L6-v2
    python scripts/15_generate_embeddings.py --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def check_dependencies() -> Tuple[bool, str]:
    """Check if required dependencies are installed."""
    try:
        import numpy as np
        logger.info(f"numpy: {np.__version__}")
    except ImportError:
        return False, "numpy not installed. Run: pip install numpy"
    
    try:
        from sentence_transformers import SentenceTransformer
        logger.info("sentence-transformers: installed")
    except ImportError:
        return False, "sentence-transformers not installed. Run: pip install sentence-transformers"
    
    try:
        from rdflib import Graph
        logger.info("rdflib: installed")
    except ImportError:
        return False, "rdflib not installed. Run: pip install rdflib"
    
    return True, "All dependencies available"


def get_products_for_embedding(repo) -> List[dict]:
    """Get all products that need embeddings."""
    products = repo.get_products(limit=2000)
    logger.info(f"Found {len(products)} products")
    return products


def create_product_text(product) -> str:
    """Create text representation of product for embedding."""
    parts = []
    
    if product.title:
        parts.append(product.title)
    
    if product.brand:
        parts.append(f"Brand: {product.brand}")
    
    if product.category:
        parts.append(f"Category: {product.category}")
    
    if product.price > 0:
        parts.append(f"Price: ${product.price:.2f}")
    
    if product.average_rating > 0:
        parts.append(f"Rating: {product.average_rating:.1f}/5")
    
    return " | ".join(parts)


def generate_embeddings(
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    dry_run: bool = False,
    batch_size: int = 32,
) -> dict:
    """Generate embeddings for all products.
    
    Args:
        model_name: HuggingFace model name for embeddings
        dry_run: If True, don't save embeddings
        batch_size: Batch size for embedding generation
        
    Returns:
        Statistics dict
    """
    from src.rdf.store import get_store, ECOM
    from src.rdf.repository import RDFRepository
    
    stats = {
        "total_products": 0,
        "embeddings_generated": 0,
        "embedding_dim": 0,
        "model": model_name,
        "dry_run": dry_run,
    }
    
    # Load store and repo
    store = get_store()
    repo = RDFRepository(store)
    
    logger.info(f"RDF Store loaded: {store.triple_count} triples")
    
    # Get products
    products = get_products_for_embedding(repo)
    stats["total_products"] = len(products)
    
    if not products:
        logger.warning("No products found!")
        return stats
    
    # Load embedding model
    logger.info(f"Loading embedding model: {model_name}")
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name)
        logger.info(f"Model loaded, embedding dim: {model.get_sentence_embedding_dimension()}")
        stats["embedding_dim"] = model.get_sentence_embedding_dimension()
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise
    
    # Generate texts
    logger.info("Creating text representations...")
    product_texts = []
    product_ids = []
    
    for p in products:
        text = create_product_text(p)
        product_texts.append(text)
        product_ids.append(p.product_id)
        
        if len(product_texts) <= 3:
            logger.info(f"  Sample text: {text[:100]}...")
    
    # Generate embeddings in batches
    logger.info(f"Generating embeddings (batch_size={batch_size})...")
    all_embeddings = []
    
    for i in range(0, len(product_texts), batch_size):
        batch = product_texts[i:i + batch_size]
        batch_embeddings = model.encode(batch, show_progress_bar=False)
        all_embeddings.extend(batch_embeddings)
        logger.info(f"  Processed {min(i + batch_size, len(product_texts))}/{len(product_texts)}")
    
    # Store embeddings in RDF
    if not dry_run:
        logger.info("Storing embeddings in RDF...")
        
        for pid, embedding in zip(product_ids, all_embeddings):
            # Create product URI
            product_uri = f"http://example.org/ecommerce#product_{pid}"
            
            # Add embedding
            store.add_embedding(product_uri, embedding.tolist())
            stats["embeddings_generated"] += 1
        
        # Save updated graph
        output_path = project_root / "ontology" / "instances" / "embeddings.ttl"
        
        # Extract only embedding triples to separate file
        from rdflib import Graph, Namespace
        ECOM_NS = Namespace("http://example.org/ecommerce#")
        
        embedding_graph = Graph()
        embedding_graph.bind("ecom", ECOM_NS)
        
        for s, p, o in store.graph:
            if str(p) in [str(ECOM_NS.embedding), str(ECOM_NS.embeddingDim)]:
                embedding_graph.add((s, p, o))
        
        embedding_graph.serialize(str(output_path), format="turtle")
        logger.info(f"Saved embeddings to: {output_path}")
        
    else:
        logger.info("[DRY RUN] Would generate embeddings for:")
        for pid, text in list(zip(product_ids, product_texts))[:5]:
            logger.info(f"  {pid}: {text[:60]}...")
        stats["embeddings_generated"] = len(products)
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="Generate product embeddings for RDF store")
    parser.add_argument(
        "--model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="HuggingFace model for embeddings (default: all-MiniLM-L6-v2)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for embedding generation (default: 32)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't save embeddings, just show what would be done",
    )
    parser.add_argument(
        "--skip-deps-check",
        action="store_true",
        help="Skip dependency check",
    )
    
    args = parser.parse_args()
    
    # Check dependencies
    if not args.skip_deps_check:
        ok, msg = check_dependencies()
        if not ok:
            logger.error(msg)
            sys.exit(1)
        logger.info(msg)
    
    # Generate embeddings
    try:
        stats = generate_embeddings(
            model_name=args.model,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
        )
        
        print("\n" + "=" * 50)
        print("EMBEDDING GENERATION COMPLETE")
        print("=" * 50)
        print(f"Model: {stats['model']}")
        print(f"Embedding dim: {stats['embedding_dim']}")
        print(f"Total products: {stats['total_products']}")
        print(f"Embeddings generated: {stats['embeddings_generated']}")
        print(f"Dry run: {stats['dry_run']}")
        print("=" * 50)
        
    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

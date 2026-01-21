# ONTOLOGY MODULE

RDF schema and instance data for Fuseki triple store.

**Updated:** 2026-01-19 | **Version:** 3.0 (Company entity added)

## STRUCTURE

```
ontology/
├── ecommerce.ttl        # OWL ontology schema (571 triples)
├── shacl/
│   └── ecommerce-shapes.ttl  # SHACL validation (393 triples)
└── instances/
    ├── customers.ttl    # 100 customers
    ├── products.ttl     # 1,492 products
    ├── orders.ttl       # 491 orders + 1,240 items
    ├── tickets.ttl      # 60 tickets
    ├── similarities.ttl # 4,416 product relations
    ├── embeddings.ttl   # 100 product vectors (384-dim)
    └── companies.ttl    # (Phase 1) Company instances
```

## NAMESPACES

| Prefix | URI |
|--------|-----|
| `ecom:` | `http://example.org/ecommerce#` |
| `schema:` | `http://schema.org/` |
| `rdf:` | Standard |
| `rdfs:` | Standard |
| `owl:` | Standard |
| `xsd:` | Standard |
| `sh:` | `http://www.w3.org/ns/shacl#` |

## OWL CLASSES

### Core Entities

| Class | Key Properties | Status |
|-------|---------------|--------|
| `ecom:Customer` | customerId, name, email, phone, membershipLevel | Existing |
| `ecom:Product` | productId, title, brand, price, averageRating, stockStatus | Existing |
| `ecom:Order` | orderId, status, orderDate, totalAmount, shippingAddress | Existing |
| `ecom:OrderItem` | quantity, unitPrice, hasProduct | Existing |
| `ecom:Ticket` | ticketId, issueType, status, priority, description | Existing |
| `ecom:Category` | Electronics, MobilePhone, Laptop, Audio, Accessories | Existing |
| **`ecom:Company`** | companyId, companyName, industry, companySize, foundedYear, headquarters, employeeCount, annualRevenue, website, stockTicker | **NEW (Phase 1)** |
| **`ecom:BusinessRelationship`** | relationshipType, relationshipStartDate, relationshipEndDate, relationshipStrength | **NEW (Phase 1)** |

### BusinessRelationship Subclasses

| Class | Description |
|-------|-------------|
| `ecom:SupplierRelationship` | 공급자-구매자 관계 |
| `ecom:PartnerRelationship` | 비즈니스 파트너 관계 |
| `ecom:CompetitorRelationship` | 경쟁사 관계 |
| `ecom:SubsidiaryRelationship` | 모회사-자회사 관계 |

## RELATIONSHIPS

### Existing Relationships

| Property | Domain → Range |
|----------|----------------|
| `ecom:purchased` | Customer → Product |
| `ecom:placedOrder` | Customer → Order |
| `ecom:containsItem` | Order → OrderItem |
| `ecom:hasProduct` | OrderItem → Product |
| `ecom:similarTo` | Product → Product (symmetric) |
| `ecom:hasTicket` | Customer → Ticket |
| `ecom:relatedToOrder` | Ticket → Order |
| `ecom:inCategory` | Product → Category |

### NEW: Company-Product Relationships

| Property | Domain → Range | Notes |
|----------|----------------|-------|
| `ecom:manufactures` / `ecom:manufacturedBy` | Company ↔ Product | Functional on Product side |
| `ecom:distributes` / `ecom:distributedBy` | Company ↔ Product | Many-to-many |

### NEW: Customer-Company Relationships

| Property | Domain → Range | Notes |
|----------|----------------|-------|
| `ecom:worksAt` / `ecom:hasEmployee` | Customer ↔ Company | Max 1 per Customer |
| `ecom:purchasedFrom` / `ecom:soldTo` | Customer ↔ Company | Derived from orders |
| `ecom:subscribedTo` / `ecom:hasSubscriber` | Customer ↔ Company | For B2B/SaaS |

### NEW: Company-Company Relationships

| Property | Domain → Range | Notes |
|----------|----------------|-------|
| `ecom:supplierOf` / `ecom:hasSupplier` | Company ↔ Company | Directional |
| `ecom:partnerWith` | Company ↔ Company | **Symmetric** |
| `ecom:competitorOf` | Company ↔ Company | **Symmetric** |
| `ecom:subsidiaryOf` / `ecom:hasSubsidiary` | Company ↔ Company | **Transitive** |

### Reified Relationship Properties

| Property | Domain | Description |
|----------|--------|-------------|
| `ecom:hasSourceCompany` | BusinessRelationship | 관계 시작 기업 |
| `ecom:hasTargetCompany` | BusinessRelationship | 관계 대상 기업 |

## SHACL SHAPES

### Existing Shapes

| Shape | Validates |
|-------|-----------|
| CustomerShape | customerId pattern, email format, membershipLevel enum |
| ProductShape | price >= 0, rating 0-5, stockStatus enum |
| OrderShape | orderId pattern, status enum |
| TicketShape | issueType enum, priority enum, status enum |

### NEW: Company Shapes (Phase 1)

| Shape | Validates |
|-------|-----------|
| **CompanyShape** | companyId pattern `COM_XXX`, companyName 1-200 chars, industry enum, companySize enum, foundedYear 1800-2026, employeeCount >= 1, annualRevenue >= 0, website URL pattern, stockTicker pattern |
| **CompanyProductConstraint** | manufactures/distributes → Product |
| **CompanyRelationshipConstraint** | supplierOf/partnerWith/competitorOf/subsidiaryOf → Company |
| **CustomerCompanyConstraint** | worksAt/purchasedFrom/subscribedTo → Company |
| **BusinessRelationshipShape** | hasSourceCompany, hasTargetCompany, relationshipType enum, relationshipStartDate required, relationshipStrength 0.0-1.0 |
| **ProductCompanyConstraint** | manufacturedBy/distributedBy → Company |

## LOAD TO FUSEKI

```bash
for f in ontology/ecommerce.ttl ontology/shacl/*.ttl ontology/instances/*.ttl; do
  curl -X POST 'http://ar_fuseki:3030/ecommerce/data' -u admin:admin123 \
    -H 'Content-Type: text/turtle' --data-binary @"$f"
done
```

## URI PATTERNS

| Entity | Pattern | Example |
|--------|---------|---------|
| Customer | `ecom:customer_XXX` | `ecom:customer_001` |
| Product | `ecom:product_XXXXX` | `ecom:product_B0001` |
| Order | `ecom:order_ORD_XXXXXXXX_XXXX` | `ecom:order_ORD_20251201_0001` |
| Ticket | `ecom:ticket_XXXX` | `ecom:ticket_0001` |
| **Company** | `ecom:company_XXX` | `ecom:company_001` |
| **BusinessRelationship** | `ecom:rel_XXX` | `ecom:rel_001` |

## CONVENTIONS

- **TTL format**: All files in Turtle syntax
- **URI patterns**: See table above
- **Generated files**: `instances/*.ttl` from `scripts/12_generate_mock_ttl.py`
- **Company instances**: Will be generated from `scripts/16_generate_company_data.py`

## ANTI-PATTERNS

- **Never edit instances manually** - regenerate from scripts
- **Never modify ecommerce.ttl without updating SHACL**
- **Never add Company without all required properties** (companyId, companyName, industry, companySize)
- **Never create circular subsidiary relationships** (A → B → A)

## VALIDATION EXAMPLE

```python
from rdflib import Graph
from pyshacl import validate

# Load ontology and SHACL
data_graph = Graph()
data_graph.parse('ontology/ecommerce.ttl')
data_graph.parse('ontology/instances/companies.ttl')

shacl_graph = Graph()
shacl_graph.parse('ontology/shacl/ecommerce-shapes.ttl')

# Validate
conforms, results_graph, results_text = validate(
    data_graph,
    shacl_graph=shacl_graph,
    inference='rdfs'
)

if not conforms:
    print(results_text)
```

## PHASE 1 ROADMAP

- [x] Company class and properties
- [x] BusinessRelationship class (reified)
- [x] Company-Product relationships
- [x] Customer-Company relationships
- [x] Company-Company relationships
- [x] SHACL shapes for Company
- [ ] Company instance data generation (scripts/16_generate_company_data.py)
- [ ] Company repository implementation
- [ ] API endpoints for Company CRUD

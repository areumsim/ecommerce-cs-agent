#!/usr/bin/env python3
"""
Company 데이터를 생성하고 RDF/TTL 형식으로 출력하는 스크립트.

Phase 1: Domain-Agnostic Ontology Engine

사용법:
    python scripts/16_generate_company_data.py
    python scripts/16_generate_company_data.py --companies 100  # 100개만 생성
    python scripts/16_generate_company_data.py --link-products   # Product 브랜드와 연결
"""

import argparse
import csv
import random
from pathlib import Path
from typing import Dict, List, Set, Tuple
from datetime import date, timedelta
from dataclasses import dataclass


@dataclass
class Company:
    company_id: str
    name: str
    industry: str
    size: str
    founded_year: int
    headquarters: str
    employee_count: int
    annual_revenue: float  # 억원
    website: str
    stock_ticker: str = ""
    description: str = ""


# 산업별 회사 템플릿
INDUSTRY_TEMPLATES = {
    "Electronics": {
        "prefixes": ["테크", "디지털", "스마트", "이노", "퓨처"],
        "suffixes": ["전자", "테크", "일렉트로닉스", "시스템즈", "솔루션즈"],
        "size_dist": {"startup": 0.1, "small": 0.2, "medium": 0.3, "large": 0.3, "enterprise": 0.1},
    },
    "Technology": {
        "prefixes": ["클라우드", "데이터", "AI", "넥스트", "인피니티"],
        "suffixes": ["소프트", "랩스", "테크놀로지", "시스템", "플랫폼"],
        "size_dist": {"startup": 0.3, "small": 0.3, "medium": 0.2, "large": 0.15, "enterprise": 0.05},
    },
    "Retail": {
        "prefixes": ["마켓", "쇼핑", "리테일", "커머스", "트레이드"],
        "suffixes": ["몰", "스토어", "마트", "플레이스", "허브"],
        "size_dist": {"startup": 0.1, "small": 0.3, "medium": 0.3, "large": 0.2, "enterprise": 0.1},
    },
    "Manufacturing": {
        "prefixes": ["프로", "인더스트리", "메이커", "팩토리", "프라임"],
        "suffixes": ["제조", "산업", "공업", "프로덕션", "매뉴팩처링"],
        "size_dist": {"startup": 0.05, "small": 0.15, "medium": 0.3, "large": 0.35, "enterprise": 0.15},
    },
    "Consumer Goods": {
        "prefixes": ["라이프", "홈", "데일리", "베스트", "프리미엄"],
        "suffixes": ["생활", "용품", "굿즈", "프로덕츠", "브랜드"],
        "size_dist": {"startup": 0.15, "small": 0.25, "medium": 0.3, "large": 0.2, "enterprise": 0.1},
    },
}

# 한국 도시
KOREAN_CITIES = [
    "서울", "부산", "인천", "대구", "대전", "광주", "울산", "수원",
    "성남", "고양", "용인", "창원", "청주", "전주", "천안", "안산",
]

# 유명 브랜드 → 회사 매핑 (실제 데이터와 연결용)
KNOWN_BRANDS = {
    "Samsung": ("삼성전자", "Electronics", "enterprise", 1969, "수원"),
    "Apple": ("애플코리아", "Electronics", "enterprise", 1976, "서울"),
    "Sony": ("소니코리아", "Electronics", "large", 1946, "서울"),
    "LG": ("LG전자", "Electronics", "enterprise", 1958, "서울"),
    "Bose": ("보스코리아", "Electronics", "large", 1964, "서울"),
    "JBL": ("JBL코리아", "Electronics", "large", 1946, "서울"),
    "Anker": ("앤커코리아", "Electronics", "medium", 2011, "서울"),
    "Logitech": ("로지텍코리아", "Electronics", "large", 1981, "서울"),
    "Microsoft": ("마이크로소프트코리아", "Technology", "enterprise", 1975, "서울"),
    "Google": ("구글코리아", "Technology", "enterprise", 1998, "서울"),
    "Amazon": ("아마존코리아", "Technology", "enterprise", 1994, "서울"),
}


def escape_ttl_string(s: str) -> str:
    if not s:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


def generate_company_name(industry: str, existing_names: Set[str]) -> str:
    """고유한 회사명 생성."""
    template = INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES["Technology"])
    
    for _ in range(100):  # 최대 100번 시도
        prefix = random.choice(template["prefixes"])
        suffix = random.choice(template["suffixes"])
        name = f"{prefix}{suffix}"
        
        if name not in existing_names:
            existing_names.add(name)
            return name
    
    # 모든 조합 사용됨 - 번호 추가
    return f"{prefix}{suffix}{random.randint(1, 999)}"


def select_company_size(industry: str) -> str:
    """산업별 분포에 따라 회사 규모 선택."""
    template = INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES["Technology"])
    sizes = list(template["size_dist"].keys())
    weights = list(template["size_dist"].values())
    return random.choices(sizes, weights=weights)[0]


def generate_employee_count(size: str) -> int:
    """규모에 따른 직원 수 생성."""
    ranges = {
        "startup": (1, 50),
        "small": (50, 200),
        "medium": (200, 1000),
        "large": (1000, 10000),
        "enterprise": (10000, 100000),
    }
    min_emp, max_emp = ranges.get(size, (50, 200))
    return random.randint(min_emp, max_emp)


def generate_annual_revenue(size: str, employee_count: int) -> float:
    """규모와 직원수에 따른 연매출(억원) 생성."""
    base_per_employee = {
        "startup": (0.5, 2),
        "small": (1, 3),
        "medium": (2, 5),
        "large": (3, 8),
        "enterprise": (5, 15),
    }
    min_rev, max_rev = base_per_employee.get(size, (1, 3))
    revenue_per_emp = random.uniform(min_rev, max_rev)
    return round(employee_count * revenue_per_emp, 2)


def generate_mock_companies(count: int, brands: Set[str] = None) -> Tuple[List[Company], Dict[str, str]]:
    """
    Mock Company 데이터 생성.
    
    Returns:
        Tuple[List[Company], Dict[str, str]]: 회사 목록과 브랜드→회사ID 매핑
    """
    companies = []
    brand_to_company: Dict[str, str] = {}
    existing_names: Set[str] = set()
    company_idx = 1
    
    # 1. 알려진 브랜드에서 회사 생성
    if brands:
        for brand in brands:
            if brand in KNOWN_BRANDS:
                name, industry, size, founded, hq = KNOWN_BRANDS[brand]
                company_id = f"COM_{company_idx:03d}"
                
                emp_count = generate_employee_count(size)
                revenue = generate_annual_revenue(size, emp_count)
                
                companies.append(Company(
                    company_id=company_id,
                    name=name,
                    industry=industry,
                    size=size,
                    founded_year=founded,
                    headquarters=hq,
                    employee_count=emp_count,
                    annual_revenue=revenue,
                    website=f"https://www.{brand.lower()}.co.kr",
                    stock_ticker=brand.upper()[:4] if size == "enterprise" else "",
                    description=f"{name}는 {industry} 분야의 선도 기업입니다.",
                ))
                
                brand_to_company[brand] = company_id
                existing_names.add(name)
                company_idx += 1
    
    # 2. 나머지 회사 랜덤 생성
    industries = list(INDUSTRY_TEMPLATES.keys())
    
    while len(companies) < count:
        company_id = f"COM_{company_idx:03d}"
        industry = random.choice(industries)
        name = generate_company_name(industry, existing_names)
        size = select_company_size(industry)
        
        founded_year = random.randint(1950, 2023)
        headquarters = random.choice(KOREAN_CITIES)
        emp_count = generate_employee_count(size)
        revenue = generate_annual_revenue(size, emp_count)
        
        # 큰 회사만 주식 티커 보유
        stock_ticker = ""
        if size in ("large", "enterprise") and random.random() > 0.5:
            stock_ticker = f"{name[:2].upper()}{random.randint(100, 999)}"
        
        companies.append(Company(
            company_id=company_id,
            name=name,
            industry=industry,
            size=size,
            founded_year=founded_year,
            headquarters=headquarters,
            employee_count=emp_count,
            annual_revenue=revenue,
            website=f"https://www.{name.lower().replace(' ', '')}.co.kr",
            stock_ticker=stock_ticker,
            description=f"{name}는 {headquarters}에 본사를 둔 {industry} 기업입니다.",
        ))
        company_idx += 1
    
    return companies, brand_to_company


def generate_company_relationships(
    companies: List[Company],
    supplier_ratio: float = 0.1,
    partner_ratio: float = 0.05,
    competitor_ratio: float = 0.08,
) -> List[Tuple[str, str, str, str, float]]:
    """
    회사 간 관계 생성.
    
    Returns:
        List[(source_id, target_id, rel_type, start_date, strength)]
    """
    relationships = []
    company_ids = [c.company_id for c in companies]
    company_by_industry: Dict[str, List[str]] = {}
    
    for c in companies:
        if c.industry not in company_by_industry:
            company_by_industry[c.industry] = []
        company_by_industry[c.industry].append(c.company_id)
    
    # Supplier relationships (cross-industry)
    num_suppliers = int(len(companies) * supplier_ratio)
    for _ in range(num_suppliers):
        source = random.choice(company_ids)
        target = random.choice(company_ids)
        if source != target:
            start_date = date(random.randint(2010, 2024), random.randint(1, 12), random.randint(1, 28))
            strength = round(random.uniform(0.3, 0.9), 2)
            relationships.append((source, target, "supplier", start_date.isoformat(), strength))
    
    # Partner relationships (cross-industry, symmetric)
    num_partners = int(len(companies) * partner_ratio)
    added_pairs = set()
    for _ in range(num_partners):
        source = random.choice(company_ids)
        target = random.choice(company_ids)
        if source != target:
            pair = tuple(sorted([source, target]))
            if pair not in added_pairs:
                added_pairs.add(pair)
                start_date = date(random.randint(2015, 2024), random.randint(1, 12), random.randint(1, 28))
                strength = round(random.uniform(0.5, 1.0), 2)
                relationships.append((source, target, "partner", start_date.isoformat(), strength))
    
    # Competitor relationships (same industry, symmetric)
    for industry, ids in company_by_industry.items():
        if len(ids) < 2:
            continue
        num_competitors = max(1, int(len(ids) * competitor_ratio))
        comp_pairs = set()
        for _ in range(num_competitors * 2):
            if len(ids) >= 2:
                source, target = random.sample(ids, 2)
                pair = tuple(sorted([source, target]))
                if pair not in comp_pairs:
                    comp_pairs.add(pair)
                    strength = round(random.uniform(0.4, 0.8), 2)
                    relationships.append((source, target, "competitor", "2020-01-01", strength))
    
    return relationships


def generate_companies_ttl(companies: List[Company]) -> str:
    """회사 데이터를 TTL로 변환."""
    lines = [
        '@prefix ecom: <http://example.org/ecommerce#> .',
        '@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .',
        '@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .',
        '',
        '# ============================================================================',
        '# Company Instances (Generated)',
        '# ============================================================================',
        '',
    ]
    
    for c in companies:
        safe_id = c.company_id.replace("-", "_")
        name = escape_ttl_string(c.name)
        desc = escape_ttl_string(c.description)
        
        lines.append(f'ecom:company_{safe_id} a ecom:Company ;')
        lines.append(f'    ecom:companyId "{c.company_id}" ;')
        lines.append(f'    ecom:companyName "{name}" ;')
        lines.append(f'    ecom:industry "{c.industry}" ;')
        lines.append(f'    ecom:companySize "{c.size}" ;')
        lines.append(f'    ecom:foundedYear {c.founded_year} ;')
        lines.append(f'    ecom:headquarters "{c.headquarters}" ;')
        lines.append(f'    ecom:employeeCount {c.employee_count} ;')
        lines.append(f'    ecom:annualRevenue {c.annual_revenue} ;')
        lines.append(f'    ecom:website <{c.website}> ;')
        if c.stock_ticker:
            lines.append(f'    ecom:stockTicker "{c.stock_ticker}" ;')
        if desc:
            lines.append(f'    ecom:description "{desc}" ;')
        
        lines[-1] = lines[-1].rstrip(' ;') + ' .'
        lines.append('')
    
    return '\n'.join(lines)


def generate_company_relationships_ttl(
    relationships: List[Tuple[str, str, str, str, float]]
) -> str:
    """회사 간 관계를 TTL로 변환."""
    lines = [
        '@prefix ecom: <http://example.org/ecommerce#> .',
        '@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .',
        '',
        '# ============================================================================',
        '# Company-Company Relationships (Generated)',
        '# ============================================================================',
        '',
    ]
    
    rel_type_to_property = {
        "supplier": "supplierOf",
        "partner": "partnerWith",
        "competitor": "competitorOf",
    }
    
    for idx, (source, target, rel_type, start_date, strength) in enumerate(relationships):
        safe_source = source.replace("-", "_")
        safe_target = target.replace("-", "_")
        prop = rel_type_to_property.get(rel_type, "partnerWith")
        
        # Direct relationship
        lines.append(f'ecom:company_{safe_source} ecom:{prop} ecom:company_{safe_target} .')
        
        # Reified relationship with metadata
        lines.append(f'ecom:rel_{idx:04d} a ecom:BusinessRelationship ;')
        lines.append(f'    ecom:hasSourceCompany ecom:company_{safe_source} ;')
        lines.append(f'    ecom:hasTargetCompany ecom:company_{safe_target} ;')
        lines.append(f'    ecom:relationshipType "{rel_type}" ;')
        lines.append(f'    ecom:relationshipStartDate "{start_date}"^^xsd:date ;')
        lines.append(f'    ecom:relationshipStrength {strength} .')
        lines.append('')
    
    return '\n'.join(lines)


def generate_product_company_links_ttl(
    brand_to_company: Dict[str, str],
    products_csv: Path,
) -> str:
    """Product의 brand 필드를 Company와 연결."""
    lines = [
        '@prefix ecom: <http://example.org/ecommerce#> .',
        '',
        '# ============================================================================',
        '# Product-Company Links (manufacturedBy)',
        '# ============================================================================',
        '',
    ]
    
    if not products_csv.exists():
        lines.append('# No products.csv found - skipping Product-Company links')
        return '\n'.join(lines)
    
    linked_count = 0
    with open(products_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            product_id = row["product_id"]
            brand = row.get("brand", "")
            
            if brand in brand_to_company:
                safe_product_id = product_id.replace("-", "_").replace(" ", "_")
                company_id = brand_to_company[brand]
                safe_company_id = company_id.replace("-", "_")
                
                lines.append(f'ecom:product_{safe_product_id} ecom:manufacturedBy ecom:company_{safe_company_id} .')
                linked_count += 1
    
    lines.insert(6, f'# Linked {linked_count} products to companies')
    return '\n'.join(lines)


def extract_brands_from_products(products_csv: Path) -> Set[str]:
    """products.csv에서 고유 브랜드 추출."""
    brands = set()
    if products_csv.exists():
        with open(products_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                brand = row.get("brand", "").strip()
                if brand:
                    brands.add(brand)
    return brands


def main():
    parser = argparse.ArgumentParser(description="Generate Company TTL data for Phase 1")
    parser.add_argument("--companies", type=int, default=500, help="Number of companies to generate")
    parser.add_argument("--link-products", action="store_true", help="Link products to companies via brand")
    parser.add_argument("--csv-dir", default="data/mock_csv", help="CSV directory for product data")
    parser.add_argument("--output-dir", default="ontology/instances", help="Output directory")
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    csv_dir = project_root / args.csv_dir
    output_dir = project_root / args.output_dir
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"Company Data Generator (Phase 1)")
    print(f"{'='*60}")
    print(f"Companies to generate: {args.companies}")
    print(f"Link products: {args.link_products}")
    print(f"Output Dir: {output_dir}")
    print(f"{'='*60}\n")
    
    # 1. 브랜드 추출 (link-products 옵션 시)
    brands = set()
    products_csv = csv_dir / "products_cache.csv"
    if args.link_products and products_csv.exists():
        print("[1/5] Extracting brands from products...")
        brands = extract_brands_from_products(products_csv)
        print(f"      Found {len(brands)} unique brands")
    else:
        print("[1/5] Skipping brand extraction")
    
    # 2. 회사 생성
    print("[2/5] Generating companies...")
    companies, brand_to_company = generate_mock_companies(args.companies, brands)
    print(f"      Generated {len(companies)} companies")
    print(f"      Brand-Company mappings: {len(brand_to_company)}")
    
    # 3. 회사 간 관계 생성
    print("[3/5] Generating company relationships...")
    relationships = generate_company_relationships(companies)
    print(f"      Generated {len(relationships)} relationships")
    
    # 4. TTL 파일 생성
    print("[4/5] Writing companies.ttl...")
    companies_ttl = generate_companies_ttl(companies)
    (output_dir / "companies.ttl").write_text(companies_ttl, encoding="utf-8")
    print(f"      Written: {output_dir / 'companies.ttl'}")
    
    print("[4b/5] Writing company_relationships.ttl...")
    relationships_ttl = generate_company_relationships_ttl(relationships)
    (output_dir / "company_relationships.ttl").write_text(relationships_ttl, encoding="utf-8")
    print(f"      Written: {output_dir / 'company_relationships.ttl'}")
    
    # 5. Product-Company 연결 (옵션)
    if args.link_products and brand_to_company:
        print("[5/5] Writing product_company_links.ttl...")
        links_ttl = generate_product_company_links_ttl(brand_to_company, products_csv)
        (output_dir / "product_company_links.ttl").write_text(links_ttl, encoding="utf-8")
        print(f"      Written: {output_dir / 'product_company_links.ttl'}")
    else:
        print("[5/5] Skipping product-company links")
    
    # CSV 출력 (데이터 확인용)
    csv_output = csv_dir / "companies.csv"
    print(f"\n[Extra] Writing companies.csv for reference...")
    with open(csv_output, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "company_id", "name", "industry", "size", "founded_year",
            "headquarters", "employee_count", "annual_revenue", "website", "stock_ticker"
        ])
        for c in companies:
            writer.writerow([
                c.company_id, c.name, c.industry, c.size, c.founded_year,
                c.headquarters, c.employee_count, c.annual_revenue, c.website, c.stock_ticker
            ])
    print(f"      Written: {csv_output}")
    
    print(f"\n{'='*60}")
    print(f"Done! Company data generated.")
    print(f"{'='*60}")
    print("\nGenerated files:")
    print(f"  - {output_dir / 'companies.ttl'}")
    print(f"  - {output_dir / 'company_relationships.ttl'}")
    if args.link_products:
        print(f"  - {output_dir / 'product_company_links.ttl'}")
    print(f"  - {csv_output}")
    print("\nNext steps:")
    print("  1. Load to Fuseki:")
    print("     curl -X POST 'http://ar_fuseki:3030/ecommerce/data' -u admin:admin123 \\")
    print("       -H 'Content-Type: text/turtle' --data-binary @ontology/instances/companies.ttl")
    print("  2. Verify: python scripts/14_test_rdf_store.py")


if __name__ == "__main__":
    main()

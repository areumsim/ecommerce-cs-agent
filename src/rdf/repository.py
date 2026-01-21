from typing import List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

from src.rdf.store import UnifiedRDFStore, get_store, ECOM

logger = logging.getLogger(__name__)


@dataclass
class Customer:
    customer_id: str
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    membership_level: str = "bronze"
    created_at: Optional[datetime] = None


@dataclass
class Product:
    product_id: str
    title: str
    brand: str
    category: str
    price: float
    average_rating: float = 0.0
    rating_number: int = 0
    stock_status: str = "in_stock"


@dataclass 
class Order:
    order_id: str
    user_id: str
    status: str
    order_date: datetime
    total_amount: float
    shipping_address: str
    delivery_date: Optional[datetime] = None


@dataclass
class OrderItem:
    item_id: str
    order_id: str
    product_id: str
    quantity: int
    unit_price: float
    title: Optional[str] = None
    brand: Optional[str] = None


@dataclass
class OrderDetail:
    order: Order
    items: List[OrderItem]


@dataclass
class OrderStatus:
    order_id: str
    status: str
    estimated_delivery: Optional[str] = None


@dataclass
class Ticket:
    ticket_id: str
    user_id: str
    order_id: Optional[str]
    issue_type: str
    description: str
    status: str
    priority: str
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class RDFRepository:
    
    def __init__(self, store: Optional[UnifiedRDFStore] = None):
        self.store = store or get_store()
    
    def get_customer(self, customer_id: str) -> Optional[Customer]:
        query = f"""
            SELECT ?name ?email ?phone ?address ?membershipLevel ?createdAt
            WHERE {{
                ?customer a ecom:Customer ;
                         ecom:customerId "{customer_id}" ;
                         ecom:name ?name ;
                         ecom:email ?email .
                OPTIONAL {{ ?customer ecom:phone ?phone }}
                OPTIONAL {{ ?customer ecom:address ?address }}
                OPTIONAL {{ ?customer ecom:membershipLevel ?membershipLevel }}
                OPTIONAL {{ ?customer ecom:createdAt ?createdAt }}
            }}
            LIMIT 1
        """
        results = self.store.query(query)
        
        if not results:
            return None
            
        r = results[0]
        return Customer(
            customer_id=customer_id,
            name=r["name"],
            email=r["email"],
            phone=r.get("phone"),
            address=r.get("address"),
            membership_level=r.get("membershipLevel") or "bronze",
            created_at=self._parse_datetime(r.get("createdAt")),
        )
    
    def get_customers(self, limit: int = 100) -> List[Customer]:
        query = f"""
            SELECT ?customerId ?name ?email ?phone ?address ?membershipLevel ?createdAt
            WHERE {{
                ?customer a ecom:Customer ;
                         ecom:customerId ?customerId ;
                         ecom:name ?name ;
                         ecom:email ?email .
                OPTIONAL {{ ?customer ecom:phone ?phone }}
                OPTIONAL {{ ?customer ecom:address ?address }}
                OPTIONAL {{ ?customer ecom:membershipLevel ?membershipLevel }}
                OPTIONAL {{ ?customer ecom:createdAt ?createdAt }}
            }}
            LIMIT {limit}
        """
        results = self.store.query(query)
        
        return [
            Customer(
                customer_id=r["customerId"],
                name=r["name"],
                email=r["email"],
                phone=r.get("phone"),
                address=r.get("address"),
                membership_level=r.get("membershipLevel") or "bronze",
                created_at=self._parse_datetime(r.get("createdAt")),
            )
            for r in results
        ]
    
    def get_product(self, product_id: str) -> Optional[Product]:
        query = f"""
            SELECT ?title ?brand ?category ?price ?avgRating ?ratingNum ?stockStatus
            WHERE {{
                ?product a ecom:Product ;
                        ecom:productId "{product_id}" ;
                        ecom:title ?title ;
                        ecom:brand ?brand ;
                        ecom:price ?price .
                OPTIONAL {{ ?product ecom:inCategory ?cat . ?cat rdfs:label ?category }}
                OPTIONAL {{ ?product ecom:averageRating ?avgRating }}
                OPTIONAL {{ ?product ecom:ratingNumber ?ratingNum }}
                OPTIONAL {{ ?product ecom:stockStatus ?stockStatus }}
            }}
            LIMIT 1
        """
        results = self.store.query(query)
        
        if not results:
            return None
            
        r = results[0]
        return Product(
            product_id=product_id,
            title=r["title"],
            brand=r["brand"],
            category=r.get("category") or "General",
            price=float(r["price"]),
            average_rating=float(r.get("avgRating") or 0),
            rating_number=int(r.get("ratingNum") or 0),
            stock_status=r.get("stockStatus") or "in_stock",
        )
    
    def get_products(self, category: Optional[str] = None, limit: int = 100) -> List[Product]:
        category_filter = f'FILTER(?categoryLabel = "{category}")' if category else ""
        
        query = f"""
            SELECT ?productId ?title ?brand ?categoryLabel ?price ?avgRating ?ratingNum ?stockStatus
            WHERE {{
                ?product a ecom:Product ;
                        ecom:productId ?productId ;
                        ecom:title ?title ;
                        ecom:brand ?brand ;
                        ecom:price ?price .
                OPTIONAL {{ ?product ecom:inCategory ?cat . ?cat rdfs:label ?categoryLabel }}
                OPTIONAL {{ ?product ecom:averageRating ?avgRating }}
                OPTIONAL {{ ?product ecom:ratingNumber ?ratingNum }}
                OPTIONAL {{ ?product ecom:stockStatus ?stockStatus }}
                {category_filter}
            }}
            LIMIT {limit}
        """
        results = self.store.query(query)
        
        return [
            Product(
                product_id=r["productId"],
                title=r["title"],
                brand=r["brand"],
                category=r.get("categoryLabel") or "General",
                price=float(r["price"]),
                average_rating=float(r.get("avgRating") or 0),
                rating_number=int(r.get("ratingNum") or 0),
                stock_status=r.get("stockStatus") or "in_stock",
            )
            for r in results
        ]
    
    def get_customer_orders(self, customer_id: str, limit: int = 10) -> List[Order]:
        query = f"""
            SELECT ?orderId ?status ?orderDate ?deliveryDate ?totalAmount ?shippingAddress
            WHERE {{
                ?customer a ecom:Customer ;
                         ecom:customerId "{customer_id}" ;
                         ecom:placedOrder ?order .
                ?order ecom:orderId ?orderId ;
                      ecom:status ?status ;
                      ecom:orderDate ?orderDate ;
                      ecom:totalAmount ?totalAmount ;
                      ecom:shippingAddress ?shippingAddress .
                OPTIONAL {{ ?order ecom:deliveryDate ?deliveryDate }}
            }}
            ORDER BY DESC(?orderDate)
            LIMIT {limit}
        """
        results = self.store.query(query)
        
        return [
            Order(
                order_id=r["orderId"],
                user_id=customer_id,
                status=r["status"],
                order_date=self._parse_datetime(r["orderDate"]) or datetime.now(),
                total_amount=float(r["totalAmount"]),
                shipping_address=r["shippingAddress"],
                delivery_date=self._parse_datetime(r.get("deliveryDate")),
            )
            for r in results
        ]
    
    def get_customer_purchased_products(self, customer_id: str) -> List[Product]:
        query = f"""
            SELECT DISTINCT ?productId ?title ?brand ?categoryLabel ?price ?avgRating ?ratingNum ?stockStatus
            WHERE {{
                ?customer a ecom:Customer ;
                         ecom:customerId "{customer_id}" ;
                         ecom:purchased ?product .
                ?product ecom:productId ?productId ;
                        ecom:title ?title ;
                        ecom:brand ?brand ;
                        ecom:price ?price .
                OPTIONAL {{ ?product ecom:inCategory ?cat . ?cat rdfs:label ?categoryLabel }}
                OPTIONAL {{ ?product ecom:averageRating ?avgRating }}
                OPTIONAL {{ ?product ecom:ratingNumber ?ratingNum }}
                OPTIONAL {{ ?product ecom:stockStatus ?stockStatus }}
            }}
        """
        results = self.store.query(query)
        
        return [
            Product(
                product_id=r["productId"],
                title=r["title"],
                brand=r["brand"],
                category=r.get("categoryLabel") or "General",
                price=float(r["price"]),
                average_rating=float(r.get("avgRating") or 0),
                rating_number=int(r.get("ratingNum") or 0),
                stock_status=r.get("stockStatus") or "in_stock",
            )
            for r in results
        ]
    
    def get_similar_products(self, product_id: str, limit: int = 10) -> List[Product]:
        query = f"""
            SELECT ?productId ?title ?brand ?categoryLabel ?price ?avgRating ?ratingNum ?stockStatus
            WHERE {{
                ?source a ecom:Product ;
                       ecom:productId "{product_id}" ;
                       ecom:similarTo ?product .
                ?product ecom:productId ?productId ;
                        ecom:title ?title ;
                        ecom:brand ?brand ;
                        ecom:price ?price .
                OPTIONAL {{ ?product ecom:inCategory ?cat . ?cat rdfs:label ?categoryLabel }}
                OPTIONAL {{ ?product ecom:averageRating ?avgRating }}
                OPTIONAL {{ ?product ecom:ratingNumber ?ratingNum }}
                OPTIONAL {{ ?product ecom:stockStatus ?stockStatus }}
            }}
            LIMIT {limit}
        """
        results = self.store.query(query)
        
        return [
            Product(
                product_id=r["productId"],
                title=r["title"],
                brand=r["brand"],
                category=r.get("categoryLabel") or "General",
                price=float(r["price"]),
                average_rating=float(r.get("avgRating") or 0),
                rating_number=int(r.get("ratingNum") or 0),
                stock_status=r.get("stockStatus") or "in_stock",
            )
            for r in results
        ]
    
    def get_collaborative_recommendations(self, customer_id: str, limit: int = 10) -> List[Tuple[Product, int]]:
        query = f"""
            SELECT ?productId ?title ?brand ?categoryLabel ?price ?avgRating ?ratingNum ?stockStatus (COUNT(?otherCustomer) as ?score)
            WHERE {{
                ?me a ecom:Customer ;
                   ecom:customerId "{customer_id}" ;
                   ecom:purchased ?commonProduct .
                
                ?otherCustomer a ecom:Customer ;
                              ecom:purchased ?commonProduct ;
                              ecom:purchased ?product .
                
                FILTER(?otherCustomer != ?me)
                FILTER NOT EXISTS {{ ?me ecom:purchased ?product }}
                
                ?product ecom:productId ?productId ;
                        ecom:title ?title ;
                        ecom:brand ?brand ;
                        ecom:price ?price .
                OPTIONAL {{ ?product ecom:inCategory ?cat . ?cat rdfs:label ?categoryLabel }}
                OPTIONAL {{ ?product ecom:averageRating ?avgRating }}
                OPTIONAL {{ ?product ecom:ratingNumber ?ratingNum }}
                OPTIONAL {{ ?product ecom:stockStatus ?stockStatus }}
            }}
            GROUP BY ?productId ?title ?brand ?categoryLabel ?price ?avgRating ?ratingNum ?stockStatus
            ORDER BY DESC(?score)
            LIMIT {limit}
        """
        results = self.store.query(query)
        
        return [
            (
                Product(
                    product_id=r["productId"],
                    title=r["title"],
                    brand=r["brand"],
                    category=r.get("categoryLabel") or "General",
                    price=float(r["price"]),
                    average_rating=float(r.get("avgRating") or 0),
                    rating_number=int(r.get("ratingNum") or 0),
                    stock_status=r.get("stockStatus") or "in_stock",
                ),
                int(r.get("score") or 0),
            )
            for r in results
        ]
    
    def search_products_by_embedding(
        self, 
        query_vector: List[float], 
        top_k: int = 10,
    ) -> List[Tuple[Product, float]]:
        type_uri = str(ECOM.Product) if ECOM else "http://example.org/ecommerce#Product"
        similar = self.store.vector_search(query_vector, type_filter=type_uri, top_k=top_k)
        
        results = []
        for uri, score in similar:
            product_id = uri.split("product_")[-1] if "product_" in uri else uri
            product = self.get_product(product_id)
            if product:
                results.append((product, score))
        
        return results
    
    def count_customers(self) -> int:
        type_uri = str(ECOM.Customer) if ECOM else "http://example.org/ecommerce#Customer"
        return self.store.count_by_type(type_uri)
    
    def count_products(self) -> int:
        type_uri = str(ECOM.Product) if ECOM else "http://example.org/ecommerce#Product"
        return self.store.count_by_type(type_uri)
    
    def count_orders(self) -> int:
        type_uri = str(ECOM.Order) if ECOM else "http://example.org/ecommerce#Order"
        return self.store.count_by_type(type_uri)
    
    def count_tickets(self) -> int:
        type_uri = str(ECOM.Ticket) if ECOM else "http://example.org/ecommerce#Ticket"
        return self.store.count_by_type(type_uri)
    
    def get_order(self, order_id: str) -> Optional[Order]:
        query = f"""
            SELECT ?userId ?status ?orderDate ?deliveryDate ?totalAmount ?shippingAddress
            WHERE {{
                ?order a ecom:Order ;
                       ecom:orderId "{order_id}" ;
                       ecom:status ?status ;
                       ecom:orderDate ?orderDate ;
                       ecom:totalAmount ?totalAmount ;
                       ecom:shippingAddress ?shippingAddress .
                OPTIONAL {{ ?order ecom:deliveryDate ?deliveryDate }}
                OPTIONAL {{
                    ?customer ecom:placedOrder ?order ;
                              ecom:customerId ?userId .
                }}
            }}
            LIMIT 1
        """
        results = self.store.query(query)
        if not results:
            return None
        
        r = results[0]
        return Order(
            order_id=order_id,
            user_id=r.get("userId") or "",
            status=r["status"],
            order_date=self._parse_datetime(r["orderDate"]) or datetime.now(),
            total_amount=float(r["totalAmount"]),
            shipping_address=r["shippingAddress"],
            delivery_date=self._parse_datetime(r.get("deliveryDate")),
        )
    
    def get_orders(self, status: Optional[str] = None, limit: int = 50) -> List[Order]:
        """Get all orders with optional status filter - O(1) query."""
        status_filter = f'FILTER(?status = "{status}")' if status else ""
        query = f"""
            SELECT ?orderId ?userId ?status ?orderDate ?deliveryDate ?totalAmount ?shippingAddress
            WHERE {{
                ?order a ecom:Order ;
                       ecom:orderId ?orderId ;
                       ecom:status ?status ;
                       ecom:orderDate ?orderDate ;
                       ecom:totalAmount ?totalAmount ;
                       ecom:shippingAddress ?shippingAddress .
                OPTIONAL {{ ?order ecom:deliveryDate ?deliveryDate }}
                OPTIONAL {{
                    ?customer ecom:placedOrder ?order ;
                              ecom:customerId ?userId .
                }}
                {status_filter}
            }}
            ORDER BY DESC(?orderDate)
            LIMIT {limit}
        """
        results = self.store.query(query)
        return [
            Order(
                order_id=r["orderId"],
                user_id=r.get("userId") or "",
                status=r["status"],
                order_date=self._parse_datetime(r["orderDate"]) or datetime.now(),
                total_amount=float(r["totalAmount"]),
                shipping_address=r["shippingAddress"],
                delivery_date=self._parse_datetime(r.get("deliveryDate")),
            )
            for r in results
        ]
    
    def get_user_orders(self, user_id: str, status: Optional[str] = None, limit: int = 10) -> List[Order]:
        status_filter = f'FILTER(?status = "{status}")' if status else ""
        query = f"""
            SELECT ?orderId ?status ?orderDate ?deliveryDate ?totalAmount ?shippingAddress
            WHERE {{
                ?customer a ecom:Customer ;
                          ecom:customerId "{user_id}" ;
                          ecom:placedOrder ?order .
                ?order ecom:orderId ?orderId ;
                       ecom:status ?status ;
                       ecom:orderDate ?orderDate ;
                       ecom:totalAmount ?totalAmount ;
                       ecom:shippingAddress ?shippingAddress .
                OPTIONAL {{ ?order ecom:deliveryDate ?deliveryDate }}
                {status_filter}
            }}
            ORDER BY DESC(?orderDate)
            LIMIT {limit}
        """
        results = self.store.query(query)
        return [
            Order(
                order_id=r["orderId"],
                user_id=user_id,
                status=r["status"],
                order_date=self._parse_datetime(r["orderDate"]) or datetime.now(),
                total_amount=float(r["totalAmount"]),
                shipping_address=r["shippingAddress"],
                delivery_date=self._parse_datetime(r.get("deliveryDate")),
            )
            for r in results
        ]
    
    def get_order_items(self, order_id: str) -> List[OrderItem]:
        safe_order_id = order_id.replace("-", "_").replace(" ", "_")
        query = f"""
            SELECT ?itemUri ?productId ?quantity ?unitPrice ?title ?brand
            WHERE {{
                ?order a ecom:Order ;
                       ecom:orderId "{order_id}" ;
                       ecom:containsItem ?itemUri .
                ?itemUri ecom:quantity ?quantity ;
                         ecom:unitPrice ?unitPrice ;
                         ecom:hasProduct ?product .
                ?product ecom:productId ?productId .
                OPTIONAL {{ ?product ecom:title ?title }}
                OPTIONAL {{ ?product ecom:brand ?brand }}
            }}
        """
        results = self.store.query(query)
        return [
            OrderItem(
                item_id=r.get("itemUri", "").split("#")[-1] if r.get("itemUri") else "",
                order_id=order_id,
                product_id=r["productId"],
                quantity=int(r["quantity"]),
                unit_price=float(r["unitPrice"]),
                title=r.get("title"),
                brand=r.get("brand"),
            )
            for r in results
        ]
    
    def get_order_detail(self, order_id: str) -> Optional[OrderDetail]:
        order = self.get_order(order_id)
        if not order:
            return None
        items = self.get_order_items(order_id)
        return OrderDetail(order=order, items=items)
    
    def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        order = self.get_order(order_id)
        if not order:
            return None
        est_delivery = None
        if order.delivery_date:
            est_delivery = order.delivery_date.isoformat()
        elif order.order_date:
            from datetime import timedelta
            est_delivery = (order.order_date + timedelta(days=3)).isoformat()
        return OrderStatus(
            order_id=order_id,
            status=order.status,
            estimated_delivery=est_delivery,
        )
    
    def update_order_status(self, order_id: str, new_status: str) -> bool:
        safe_order_id = order_id.replace("-", "_").replace(" ", "_")
        update_query = f"""
            DELETE {{ ?order ecom:status ?oldStatus }}
            INSERT {{ ?order ecom:status "{new_status}" }}
            WHERE {{
                ?order a ecom:Order ;
                       ecom:orderId "{order_id}" ;
                       ecom:status ?oldStatus .
            }}
        """
        return self.store.update(update_query)
    
    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        query = f"""
            SELECT ?userId ?orderId ?issueType ?description ?status ?priority ?createdAt ?resolvedAt
            WHERE {{
                ?ticket a ecom:Ticket ;
                        ecom:ticketId "{ticket_id}" ;
                        ecom:issueType ?issueType ;
                        ecom:status ?status ;
                        ecom:priority ?priority .
                OPTIONAL {{ ?ticket ecom:description ?description }}
                OPTIONAL {{ ?ticket ecom:createdAt ?createdAt }}
                OPTIONAL {{ ?ticket ecom:resolvedAt ?resolvedAt }}
                OPTIONAL {{ ?ticket ecom:relatedToOrder ?order . ?order ecom:orderId ?orderId }}
                OPTIONAL {{ ?customer ecom:hasTicket ?ticket ; ecom:customerId ?userId }}
            }}
            LIMIT 1
        """
        results = self.store.query(query)
        if not results:
            return None
        
        r = results[0]
        return Ticket(
            ticket_id=ticket_id,
            user_id=r.get("userId") or "",
            order_id=r.get("orderId"),
            issue_type=r["issueType"],
            description=r.get("description") or "",
            status=r["status"],
            priority=r["priority"],
            created_at=self._parse_datetime(r.get("createdAt")),
            resolved_at=self._parse_datetime(r.get("resolvedAt")),
        )
    
    def get_user_tickets(self, user_id: str, status: Optional[str] = None, limit: int = 20) -> List[Ticket]:
        status_filter = f'FILTER(?status = "{status}")' if status else ""
        query = f"""
            SELECT ?ticketId ?orderId ?issueType ?description ?status ?priority ?createdAt ?resolvedAt
            WHERE {{
                ?customer a ecom:Customer ;
                          ecom:customerId "{user_id}" ;
                          ecom:hasTicket ?ticket .
                ?ticket ecom:ticketId ?ticketId ;
                        ecom:issueType ?issueType ;
                        ecom:status ?status ;
                        ecom:priority ?priority .
                OPTIONAL {{ ?ticket ecom:description ?description }}
                OPTIONAL {{ ?ticket ecom:createdAt ?createdAt }}
                OPTIONAL {{ ?ticket ecom:resolvedAt ?resolvedAt }}
                OPTIONAL {{ ?ticket ecom:relatedToOrder ?order . ?order ecom:orderId ?orderId }}
                {status_filter}
            }}
            ORDER BY DESC(?createdAt)
            LIMIT {limit}
        """
        results = self.store.query(query)
        return [
            Ticket(
                ticket_id=r["ticketId"],
                user_id=user_id,
                order_id=r.get("orderId"),
                issue_type=r["issueType"],
                description=r.get("description") or "",
                status=r["status"],
                priority=r["priority"],
                created_at=self._parse_datetime(r.get("createdAt")),
                resolved_at=self._parse_datetime(r.get("resolvedAt")),
            )
            for r in results
        ]
    
    def create_ticket(
        self, 
        user_id: str, 
        issue_type: str, 
        description: str, 
        priority: str = "normal",
        order_id: Optional[str] = None,
    ) -> Ticket:
        import uuid
        ticket_id = f"TICKET_{uuid.uuid4().hex[:10].upper()}"
        now = datetime.now().isoformat() + "Z"
        
        safe_ticket_id = ticket_id.replace("-", "_")
        
        triples = f"""
            ecom:ticket_{safe_ticket_id} a ecom:Ticket ;
                ecom:ticketId "{ticket_id}" ;
                ecom:issueType "{issue_type}" ;
                ecom:description "{self._escape_sparql(description)}" ;
                ecom:status "open" ;
                ecom:priority "{priority}" ;
                ecom:createdAt "{now}"^^xsd:dateTime .
            ecom:customer_{user_id} ecom:hasTicket ecom:ticket_{safe_ticket_id} .
        """
        
        if order_id:
            safe_order_id = order_id.replace("-", "_").replace(" ", "_")
            triples += f"""
            ecom:ticket_{safe_ticket_id} ecom:relatedToOrder ecom:order_{safe_order_id} .
            """
        
        insert_query = f"""
            PREFIX ecom: <http://example.org/ecommerce#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            INSERT DATA {{
                {triples}
            }}
        """
        self.store.update(insert_query)
        
        return Ticket(
            ticket_id=ticket_id,
            user_id=user_id,
            order_id=order_id,
            issue_type=issue_type,
            description=description,
            status="open",
            priority=priority,
            created_at=datetime.now(),
            resolved_at=None,
        )
    
    def update_ticket_status(self, ticket_id: str, new_status: str) -> bool:
        now = datetime.now().isoformat() + "Z"
        resolved_insert = ""
        if new_status in ("resolved", "closed"):
            resolved_insert = f'?ticket ecom:resolvedAt "{now}"^^xsd:dateTime .'
        
        update_query = f"""
            PREFIX ecom: <http://example.org/ecommerce#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            DELETE {{ ?ticket ecom:status ?oldStatus }}
            INSERT {{ 
                ?ticket ecom:status "{new_status}" .
                {resolved_insert}
            }}
            WHERE {{
                ?ticket a ecom:Ticket ;
                        ecom:ticketId "{ticket_id}" ;
                        ecom:status ?oldStatus .
            }}
        """
        return self.store.update(update_query)
    
    @staticmethod
    def _escape_sparql(s: str) -> str:
        if not s:
            return ""
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
    
    @staticmethod
    def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
        if not dt_str:
            return None
        try:
            dt_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError):
            return None


_rdf_repo: Optional[RDFRepository] = None


def get_rdf_repository() -> RDFRepository:
    global _rdf_repo
    if _rdf_repo is None:
        _rdf_repo = RDFRepository()
    return _rdf_repo


def reset_rdf_repository() -> None:
    global _rdf_repo
    _rdf_repo = None

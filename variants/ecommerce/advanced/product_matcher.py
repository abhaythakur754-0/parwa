"""Product Matching Engine.

Provides fuzzy product matching capabilities:
- Fuzzy product name matching
- SKU lookup
- Variant detection
- Price range filtering
- Availability checking
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from difflib import SequenceMatcher
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class ProductMatch:
    """Product match result with similarity score."""
    product_id: str
    name: str
    sku: str
    price: Decimal
    similarity_score: float
    match_type: str  # 'exact', 'fuzzy', 'sku', 'variant'
    availability: bool
    variants: List[Dict[str, Any]] = field(default_factory=list)


class ProductMatcher:
    """Product matching with fuzzy search capabilities."""

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        """Initialize product matcher.

        Args:
            client_id: Client identifier for tenant isolation
            config: Optional configuration overrides
        """
        self.client_id = client_id
        self.config = config or {}
        self.min_similarity = self.config.get("min_similarity", 0.6)
        self._product_index: Dict[str, Dict[str, Any]] = {}

    def match_by_name(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10
    ) -> List[ProductMatch]:
        """Match products by name with fuzzy matching.

        Args:
            query: Product name search query
            category: Optional category filter
            limit: Maximum number of results

        Returns:
            List of product matches sorted by similarity
        """
        matches = []
        products = self._get_all_products(category)

        for product in products:
            similarity = self._calculate_similarity(query, product["name"])

            if similarity >= self.min_similarity:
                match_type = "exact" if similarity >= 0.95 else "fuzzy"
                matches.append(ProductMatch(
                    product_id=product["id"],
                    name=product["name"],
                    sku=product["sku"],
                    price=Decimal(str(product["price"])),
                    similarity_score=similarity,
                    match_type=match_type,
                    availability=product.get("availability", True),
                    variants=product.get("variants", [])
                ))

        # Sort by similarity descending
        matches.sort(key=lambda x: x.similarity_score, reverse=True)
        return matches[:limit]

    def match_by_sku(
        self,
        sku: str,
        exact_match: bool = True
    ) -> List[ProductMatch]:
        """Match products by SKU.

        Args:
            sku: SKU to search for
            exact_match: If True, require exact SKU match

        Returns:
            List of product matches
        """
        matches = []
        products = self._get_all_products()

        for product in products:
            product_sku = product["sku"]

            if exact_match:
                if sku.upper() == product_sku.upper():
                    matches.append(self._create_match(product, "sku", 1.0))
            else:
                # Partial SKU match
                if sku.upper() in product_sku.upper():
                    similarity = len(sku) / len(product_sku)
                    matches.append(self._create_match(product, "sku", similarity))

        return matches

    def detect_variants(
        self,
        product_id: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Detect product variants (size, color, etc.).

        Args:
            product_id: Base product ID

        Returns:
            Dictionary of variant types and their options
        """
        product = self._get_product(product_id)
        if not product:
            return {}

        variants = product.get("variants", [])
        variant_map: Dict[str, List[Dict[str, Any]]] = {}

        for variant in variants:
            for key, value in variant.items():
                if key not in ["id", "sku", "price"]:
                    if key not in variant_map:
                        variant_map[key] = []
                    variant_map[key].append({
                        "value": value,
                        "sku": variant.get("sku"),
                        "available": variant.get("available", True)
                    })

        return variant_map

    def filter_by_price_range(
        self,
        products: List[ProductMatch],
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None
    ) -> List[ProductMatch]:
        """Filter products by price range.

        Args:
            products: List of products to filter
            min_price: Minimum price (inclusive)
            max_price: Maximum price (inclusive)

        Returns:
            Filtered list of products
        """
        filtered = []

        for product in products:
            if min_price is not None and product.price < min_price:
                continue
            if max_price is not None and product.price > max_price:
                continue
            filtered.append(product)

        return filtered

    def filter_by_availability(
        self,
        products: List[ProductMatch],
        available_only: bool = True
    ) -> List[ProductMatch]:
        """Filter products by availability.

        Args:
            products: List of products to filter
            available_only: If True, only return available products

        Returns:
            Filtered list of products
        """
        if not available_only:
            return products
        return [p for p in products if p.availability]

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ProductMatch]:
        """Comprehensive product search.

        Args:
            query: Search query (name or SKU)
            filters: Optional filters (category, price_range, availability)

        Returns:
            List of matching products
        """
        filters = filters or {}

        # Try SKU match first
        sku_matches = self.match_by_sku(query, exact_match=False)

        # Also search by name
        name_matches = self.match_by_name(
            query,
            category=filters.get("category"),
            limit=20
        )

        # Combine and deduplicate
        all_matches = {m.product_id: m for m in sku_matches}
        for match in name_matches:
            if match.product_id not in all_matches:
                all_matches[match.product_id] = match

        results = list(all_matches.values())

        # Apply price filter
        price_range = filters.get("price_range")
        if price_range:
            min_p = price_range.get("min")
            max_p = price_range.get("max")
            results = self.filter_by_price_range(
                results,
                Decimal(str(min_p)) if min_p else None,
                Decimal(str(max_p)) if max_p else None
            )

        # Apply availability filter
        if filters.get("available_only", True):
            results = self.filter_by_availability(results)

        # Sort by similarity
        results.sort(key=lambda x: x.similarity_score, reverse=True)

        return results[:filters.get("limit", 10)]

    def _calculate_similarity(self, query: str, target: str) -> float:
        """Calculate string similarity using multiple methods."""
        # Normalize strings
        query_norm = self._normalize_string(query)
        target_norm = self._normalize_string(target)

        # Exact match
        if query_norm == target_norm:
            return 1.0

        # Sequence matcher similarity
        seq_similarity = SequenceMatcher(None, query_norm, target_norm).ratio()

        # Word overlap similarity
        query_words = set(query_norm.split())
        target_words = set(target_norm.split())
        if query_words and target_words:
            word_overlap = len(query_words & target_words) / max(len(query_words), len(target_words))
        else:
            word_overlap = 0.0

        # Combined score
        return max(seq_similarity, word_overlap)

    def _normalize_string(self, s: str) -> str:
        """Normalize string for comparison."""
        # Lowercase
        s = s.lower()
        # Remove special characters
        s = re.sub(r'[^a-z0-9\s]', '', s)
        # Normalize whitespace
        s = ' '.join(s.split())
        return s

    def _get_all_products(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all products (mock implementation)."""
        # Mock products
        base_products = [
            {
                "id": "prod_001",
                "name": "Premium Wireless Headphones",
                "sku": "SKU-HEAD-001",
                "price": 149.99,
                "category": "electronics",
                "availability": True,
                "variants": [
                    {"color": "black", "sku": "SKU-HEAD-001-BLK", "available": True},
                    {"color": "white", "sku": "SKU-HEAD-001-WHT", "available": True},
                ]
            },
            {
                "id": "prod_002",
                "name": "Smart Watch Pro",
                "sku": "SKU-WATCH-001",
                "price": 299.99,
                "category": "electronics",
                "availability": True,
                "variants": [
                    {"size": "40mm", "sku": "SKU-WATCH-001-40", "available": True},
                    {"size": "44mm", "sku": "SKU-WATCH-001-44", "available": True},
                ]
            },
            {
                "id": "prod_003",
                "name": "Cotton T-Shirt",
                "sku": "SKU-SHIRT-001",
                "price": 29.99,
                "category": "clothing",
                "availability": True,
                "variants": [
                    {"size": "S", "color": "blue", "sku": "SKU-SHIRT-001-S-BLU", "available": True},
                    {"size": "M", "color": "blue", "sku": "SKU-SHIRT-001-M-BLU", "available": True},
                    {"size": "L", "color": "blue", "sku": "SKU-SHIRT-001-L-BLU", "available": False},
                ]
            },
        ]

        if category:
            return [p for p in base_products if p["category"] == category]

        return base_products

    def _get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get single product by ID."""
        products = self._get_all_products()
        for product in products:
            if product["id"] == product_id:
                return product
        return None

    def _create_match(
        self,
        product: Dict[str, Any],
        match_type: str,
        similarity: float
    ) -> ProductMatch:
        """Create a ProductMatch from product dict."""
        return ProductMatch(
            product_id=product["id"],
            name=product["name"],
            sku=product["sku"],
            price=Decimal(str(product["price"])),
            similarity_score=similarity,
            match_type=match_type,
            availability=product.get("availability", True),
            variants=product.get("variants", [])
        )

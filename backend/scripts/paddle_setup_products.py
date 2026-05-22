"""
PARWA Paddle Setup Script — Create Products, Prices & Test Customer

Sets up the Paddle account with:
1. Parwa Products (Mini Parwa, Parwa, Parwa High)
2. Prices for each product (monthly)
3. A test customer (to verify write permissions end-to-end)

Run: python -m scripts.paddle_setup_products
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    load_dotenv(env_path)
except ImportError:
    pass

PADDLE_API_KEY = os.environ.get("PADDLE_API_KEY", "")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "sandbox")

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"


async def main():
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  PARWA PADDLE PRODUCT SETUP{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

    import httpx

    is_production = ENVIRONMENT == "production"
    base_url = "https://api.paddle.com/" if is_production else "https://sandbox-api.paddle.com/"
    headers = {
        "Authorization": f"Bearer {PADDLE_API_KEY}",
        "Content-Type": "application/json",
    }

    print(f"  Environment: {ENVIRONMENT}")
    print(f"  Base URL: {base_url}")
    print(f"  API Key: {PADDLE_API_KEY[:20]}...{PADDLE_API_KEY[-5:]}")

    created = {
        "products": [],
        "prices": [],
        "customer": None,
    }

    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        # ── Step 0: Check existing products ──
        print(f"\n  {YELLOW}→{RESET} Checking existing products...")
        resp = await client.get(f"{base_url}products", params={"per_page": 50})
        existing_products = resp.json().get("data", []) if resp.status_code == 200 else []
        print(f"  Existing products: {len(existing_products)}")

        # ── Step 1: Create Products ──
        parwa_products = [
            {
                "name": "Mini Parwa",
                "description": "Starter plan for small businesses — AI customer support basics",
                "tax_category": "standard",
                "type": "standard",
                "custom_data": {"parwa_plan": "mini_parwa"},
            },
            {
                "name": "Parwa",
                "description": "Professional plan for growing businesses — full AI support suite",
                "tax_category": "standard",
                "type": "standard",
                "custom_data": {"parwa_plan": "parwa"},
            },
            {
                "name": "Parwa High",
                "description": "Enterprise plan for large businesses — unlimited AI support with priority",
                "tax_category": "standard",
                "type": "standard",
                "custom_data": {"parwa_plan": "parwa_high"},
            },
        ]

        for product_def in parwa_products:
            # Check if product already exists
            existing = [p for p in existing_products if p.get("name") == product_def["name"]]
            if existing:
                product = existing[0]
                print(f"  {GREEN}✓{RESET} Product '{product_def['name']}' already exists: {product['id']}")
                created["products"].append(product)
                continue

            print(f"  {YELLOW}→{RESET} Creating product: {product_def['name']}...")
            resp = await client.post(f"{base_url}products", json=product_def)
            if resp.status_code in (200, 201):
                product = resp.json().get("data", {})
                print(f"  {GREEN}✓{RESET} Created product: {product_def['name']} → {product.get('id')}")
                created["products"].append(product)
            else:
                print(f"  {RED}✗{RESET} Failed to create product '{product_def['name']}': {resp.status_code}")
                print(f"    {resp.text[:300]}")

        # ── Step 2: Create Prices ──
        parwa_prices = [
            # Mini Parwa — $29/month
            {
                "product_id": None,  # filled dynamically
                "description": "Mini Parwa — Monthly",
                "type": "recurring",
                "recurring": {"interval": "month", "frequency": 1},
                "unit_price": {"amount": "2900", "currency_code": "USD"},
                "custom_data": {"parwa_plan": "mini_parwa", "billing_cycle": "monthly"},
            },
            # Parwa — $79/month
            {
                "product_id": None,
                "description": "Parwa Professional — Monthly",
                "type": "recurring",
                "recurring": {"interval": "month", "frequency": 1},
                "unit_price": {"amount": "7900", "currency_code": "USD"},
                "custom_data": {"parwa_plan": "parwa", "billing_cycle": "monthly"},
            },
            # Parwa High — $199/month
            {
                "product_id": None,
                "description": "Parwa High Enterprise — Monthly",
                "type": "recurring",
                "recurring": {"interval": "month", "frequency": 1},
                "unit_price": {"amount": "19900", "currency_code": "USD"},
                "custom_data": {"parwa_plan": "parwa_high", "billing_cycle": "monthly"},
            },
        ]

        # Map product names to created products
        product_name_map = {p.get("name"): p for p in created["products"]}

        price_product_map = [
            ("Mini Parwa", "mini_parwa"),
            ("Parwa", "parwa"),
            ("Parwa High", "parwa_high"),
        ]

        # Check existing prices
        resp = await client.get(f"{base_url}prices", params={"per_page": 50})
        existing_prices = resp.json().get("data", []) if resp.status_code == 200 else []
        print(f"\n  Existing prices: {len(existing_prices)}")

        for i, (product_name, plan_key) in enumerate(price_product_map):
            product = product_name_map.get(product_name)
            if not product:
                print(f"  {RED}✗{RESET} Skipping price for '{product_name}' — product not created")
                continue

            price_def = parwa_prices[i]
            price_def["product_id"] = product["id"]

            # Check if price already exists for this product
            existing = [p for p in existing_prices if p.get("product_id") == product["id"]]
            if existing:
                price = existing[0]
                amount = price.get("unit_price", {}).get("amount", "?")
                print(f"  {GREEN}✓{RESET} Price for '{product_name}' already exists: {price['id']} (${amount})")
                created["prices"].append(price)
                continue

            print(f"  {YELLOW}→{RESET} Creating price for {product_name} (${price_def['unit_price']['amount']}/mo)...")
            resp = await client.post(f"{base_url}prices", json=price_def)
            if resp.status_code in (200, 201):
                price = resp.json().get("data", {})
                print(f"  {GREEN}✓{RESET} Created price: {price.get('id')} (${price_def['unit_price']['amount']}/mo)")
                created["prices"].append(price)
            else:
                print(f"  {RED}✗{RESET} Failed to create price for '{product_name}': {resp.status_code}")
                print(f"    {resp.text[:300]}")

        # ── Step 3: Create a test customer ──
        test_customer = {
            "email": "test@parwa.ai",
            "name": "Parwa Test Customer",
            "custom_data": {"type": "test", "source": "paddle_setup_script"},
        }

        # Check if test customer already exists
        resp = await client.get(f"{base_url}customers", params={"email": "test@parwa.ai"})
        existing_custs = resp.json().get("data", []) if resp.status_code == 200 else []
        if existing_custs:
            customer = existing_custs[0]
            print(f"\n  {GREEN}✓{RESET} Test customer already exists: {customer['id']}")
            created["customer"] = customer
        else:
            print(f"\n  {YELLOW}→{RESET} Creating test customer: {test_customer['email']}...")
            resp = await client.post(f"{base_url}customers", json=test_customer)
            if resp.status_code in (200, 201):
                customer = resp.json().get("data", {})
                print(f"  {GREEN}✓{RESET} Created test customer: {customer.get('id')}")
                created["customer"] = customer
            else:
                print(f"  {RED}✗{RESET} Failed to create test customer: {resp.status_code}")
                print(f"    {resp.text[:300]}")

        # ── Step 4: Update .env with price IDs ──
        if created["prices"]:
            price_ids = {}
            for price in created["prices"]:
                custom = price.get("custom_data", {})
                plan_key = custom.get("parwa_plan", "unknown")
                price_ids[plan_key] = price["id"]

            print(f"\n  {BLUE}📊{RESET} Price IDs for .env:")
            print(f"    PADDLE_PRICE_IDS={json.dumps(price_ids)}")

            # Update .env with price IDs
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
            try:
                with open(env_path, "r") as f:
                    env_content = f.read()

                price_ids_str = json.dumps(price_ids)
                if "PADDLE_PRICE_IDS=" in env_content:
                    # Update existing
                    lines = env_content.split("\n")
                    for i, line in enumerate(lines):
                        if line.startswith("PADDLE_PRICE_IDS="):
                            lines[i] = f"PADDLE_PRICE_IDS={price_ids_str}"
                            break
                    env_content = "\n".join(lines)
                else:
                    env_content += f"\nPADDLE_PRICE_IDS={price_ids_str}\n"

                with open(env_path, "w") as f:
                    f.write(env_content)
                print(f"  {GREEN}✓{RESET} Updated .env with PADDLE_PRICE_IDS")
            except Exception as e:
                print(f"  {RED}✗{RESET} Could not update .env: {e}")

    # ── Summary ──
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  SETUP SUMMARY{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

    print(f"  Products: {len(created['products'])}")
    for p in created["products"]:
        print(f"    - {p.get('name')} ({p.get('id')})")

    print(f"  Prices: {len(created['prices'])}")
    for p in created["prices"]:
        amount = p.get("unit_price", {}).get("amount", "?")
        plan = p.get("custom_data", {}).get("parwa_plan", "?")
        print(f"    - {plan}: ${amount}/mo ({p.get('id')})")

    if created["customer"]:
        print(f"  Test Customer: {created['customer'].get('id')} ({created['customer'].get('email')})")

    # Save results
    results_path = "/home/z/my-project/parwa/backend/scripts/paddle_setup_results.json"
    with open(results_path, "w") as f:
        json.dump(created, f, indent=2, default=str)
    print(f"\n  Results saved to: {results_path}")

    print(f"\n  {GREEN}{BOLD}PADDLE SETUP COMPLETE!{RESET}")


if __name__ == "__main__":
    asyncio.run(main())

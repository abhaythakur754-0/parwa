"""
PARWA Paddle Price Creator — Fix price format for Paddle API v1

Creates recurring prices for the 3 Parwa products.
Paddle Billing API uses `billing_cycle` not `recurring`.
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


async def main():
    import httpx

    is_production = ENVIRONMENT == "production"
    base_url = "https://api.paddle.com/" if is_production else "https://sandbox-api.paddle.com/"
    headers = {
        "Authorization": f"Bearer {PADDLE_API_KEY}",
        "Content-Type": "application/json",
    }

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    print(f"\n{BOLD}Creating Parwa Prices (Fixed Format){RESET}\n")

    # Product IDs from previous run
    products = {
        "mini_parwa": "pro_01krxm347n849rkaraykhvqfhy",
        "parwa": "pro_01krxm34gy1bew3xqkgamt1ywa",
        "parwa_high": "pro_01krxm34tek4skgcaap69c0hmg",
    }

    # Prices with correct Paddle Billing API format
    prices_to_create = [
        {
            "product_id": products["mini_parwa"],
            "description": "Mini Parwa — Starter Plan Monthly",
            "type": "standard",
            "billing_cycle": {"interval": "month", "frequency": 1},
            "unit_price": {"amount": "2900", "currency_code": "USD"},
            "custom_data": {"parwa_plan": "mini_parwa", "billing_cycle": "monthly"},
        },
        {
            "product_id": products["parwa"],
            "description": "Parwa — Professional Plan Monthly",
            "type": "standard",
            "billing_cycle": {"interval": "month", "frequency": 1},
            "unit_price": {"amount": "7900", "currency_code": "USD"},
            "custom_data": {"parwa_plan": "parwa", "billing_cycle": "monthly"},
        },
        {
            "product_id": products["parwa_high"],
            "description": "Parwa High — Enterprise Plan Monthly",
            "type": "standard",
            "billing_cycle": {"interval": "month", "frequency": 1},
            "unit_price": {"amount": "19900", "currency_code": "USD"},
            "custom_data": {"parwa_plan": "parwa_high", "billing_cycle": "monthly"},
        },
    ]

    created_prices = {}

    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        # Check existing prices first
        resp = await client.get(f"{base_url}prices", params={"per_page": 50})
        existing = resp.json().get("data", []) if resp.status_code == 200 else []
        print(f"  Existing prices: {len(existing)}")

        for price_def in prices_to_create:
            plan = price_def["custom_data"]["parwa_plan"]
            amount = price_def["unit_price"]["amount"]

            # Check existing
            existing_match = [p for p in existing if p.get("product_id") == price_def["product_id"]]
            if existing_match:
                price = existing_match[0]
                created_prices[plan] = price["id"]
                print(f"  {GREEN}✓{RESET} Price for '{plan}' already exists: {price['id']}")
                continue

            print(f"  {YELLOW}→{RESET} Creating price for {plan} (${amount}/mo)...")

            # Try with billing_cycle format
            resp = await client.post(f"{base_url}prices", json=price_def)

            if resp.status_code in (200, 201):
                price = resp.json().get("data", {})
                created_prices[plan] = price["id"]
                print(f"  {GREEN}✓{RESET} Created price: {price['id']}")
            else:
                error_body = resp.text[:500]
                print(f"  {RED}✗{RESET} Failed: HTTP {resp.status_code}")
                print(f"    {error_body}")

                # Try alternative format
                alt_def = dict(price_def)
                # Remove billing_cycle and try without it
                if "billing_cycle" in alt_def:
                    alt_def["billing_cycle"] = {"interval": "month", "frequency": 1}
                print(f"  {YELLOW}→{RESET} Trying alternative format...")
                resp2 = await client.post(f"{base_url}prices", json=alt_def)
                if resp2.status_code in (200, 201):
                    price = resp2.json().get("data", {})
                    created_prices[plan] = price["id"]
                    print(f"  {GREEN}✓{RESET} Created with alt format: {price['id']}")
                else:
                    print(f"  {RED}✗{RESET} Alt format also failed: {resp2.status_code}")
                    print(f"    {resp2.text[:300]}")

    # Update .env with price IDs
    if created_prices:
        print(f"\n  {BOLD}Price IDs:{RESET}")
        for plan, price_id in created_prices.items():
            print(f"    {plan}: {price_id}")

        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        try:
            with open(env_path, "r") as f:
                env_content = f.read()

            price_ids_str = json.dumps(created_prices)
            if "PADDLE_PRICE_IDS=" in env_content:
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
            print(f"\n  {GREEN}✓{RESET} Updated .env with PADDLE_PRICE_IDS")
        except Exception as e:
            print(f"  {RED}✗{RESET} Could not update .env: {e}")

    # Save results
    results = {"prices": created_prices, "products": products}
    results_path = "/home/z/my-project/parwa/backend/scripts/paddle_prices_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n  Results saved to: {results_path}")


if __name__ == "__main__":
    asyncio.run(main())

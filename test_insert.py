import asyncio
from sqlalchemy import text
from backend.app.database import engine

async def test_insert():
    sql = """
    INSERT INTO tenants (id, name, plan, is_active)
    VALUES
      ('11111111-1111-1111-1111-111111111111', 'Acme Mini Corp', 'mini_parwa', true)
    ON CONFLICT (id) DO NOTHING;
    """
    async with engine.begin() as conn:
        print("Attempting insert...")
        await conn.execute(text(sql))
        print("Insert 1 successful.")
        
        print("Attempting duplicate insert...")
        await conn.execute(text(sql))
        print("Insert 2 successful (should have done nothing).")

if __name__ == "__main__":
    asyncio.run(test_insert())

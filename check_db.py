import asyncio
from sqlalchemy import text
from backend.app.database import engine

async def check():
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT * FROM tenants;"))
        rows = res.fetchall()
        print(f"Tenants count: {len(rows)}")
        for r in rows:
            print(r)

if __name__ == "__main__":
    asyncio.run(check())

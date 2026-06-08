import asyncio
import httpx

async def test_create_tenant():
    # Use localhost or production if we know it. I will use localhost if running
    # but I'll hit his production API to see what's actually happening!
    url = "https://rutaigeoproxi-private.onrender.com/api/v1/tenants"
    # or maybe https://rutaigeoproxi.onrender.com ?
    pass

asyncio.run(test_create_tenant())

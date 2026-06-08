import httpx
import asyncio

async def main():
    url = "https://rutaigeoproxi-back.onrender.com/tenants"
    login_url = "https://rutaigeoproxi-back.onrender.com/auth/login"
    
    async with httpx.AsyncClient() as client:
        # 1. Login as superadmin to get token
        print("Logueando para obtener token...")
        # NOTA: No tengo la contraseña real, pero intentaré con una si me la das
        # Por ahora solo quiero ver si /tenants responde sin slash y con slash
        r = await client.post(url, json={"nombre": "Test"})
        print(f"POST /tenants sin slash: {r.status_code}")
        
        r2 = await client.post(url + "/", json={"nombre": "Test"})
        print(f"POST /tenants/ con slash: {r2.status_code}")

if __name__ == "__main__":
    asyncio.run(main())

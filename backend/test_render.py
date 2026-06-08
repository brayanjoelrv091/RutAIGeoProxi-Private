import httpx
import asyncio

async def test_render():
    url = "https://rutaigeoproxi-back.onrender.com/tenants"
    login_url = "https://rutaigeoproxi-back.onrender.com/auth/login"
    
    async with httpx.AsyncClient() as client:
        print("Logging in...")
        try:
            # try json
            r = await client.post(login_url, json={"email": "admin@rutaigeoproxi.com", "password": "Admin2026!#"})
            print(f"Login status: {r.status_code}")
            if r.status_code != 200:
                print(r.text)
                return
            token = r.json()["access_token"]
            
            headers = {"Authorization": f"Bearer {token}"}
            payload = {
                "nombre": "Taller Render Test",
                "slug": "taller-render-test",
                "esta_activo": True,
                "plan": "basico",
                "email_admin": "brayanjoelrv091+rendertest@gmail.com"
            }
            print("Creating tenant...")
            resp = await client.post(url, json=payload, headers=headers, timeout=60.0)
            print("Status:", resp.status_code)
            print("Response:", resp.text)
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(test_render())

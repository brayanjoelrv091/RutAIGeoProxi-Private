import urllib.request
import json

urls = [
    "https://rutaigeoproxi-back.onrender.com",
    "https://rutai-backend.onrender.com"
]

credentials = [
    {"email": "admin@ruta.com", "password": "Password123"},
    {"email": "admin@rutaigeoproxi.com", "password": "Admin123*"},
    {"email": "taller@ruta.com", "password": "Password123"},
    {"email": "cliente@ruta.com", "password": "Password123"},
    {"email": "xdreicarlos@gmail.com", "password": "Password123"}
]

for url in urls:
    print(f"\n--- Probando backend: {url} ---")
    
    # Pruebas de salud basicas (GET /)
    try:
        req = urllib.request.Request(f"{url}/", method="GET")
        with urllib.request.urlopen(req, timeout=5) as r:
            print(f"  GET / - Status: {r.status} (Backend online)")
    except Exception as e:
        print(f"  GET / - Falló: {e}")
        
    for cred in credentials:
        login_url = f"{url}/auth/login"
        req_data = json.dumps(cred).encode("utf-8")
        req = urllib.request.Request(
            login_url,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                body = json.loads(r.read().decode("utf-8"))
                print(f"  Login {cred['email']} - ÉXITO! Status: {r.status}")
                if "access_token" in body:
                    print("    Token obtenido correctamente.")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"  Login {cred['email']} - HTTP {e.code}: {err_body.strip()}")
        except Exception as e:
            print(f"  Login {cred['email']} - Error: {e}")

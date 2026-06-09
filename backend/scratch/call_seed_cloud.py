import urllib.request
import json
import time

url = "https://rutaigeoproxi-back.onrender.com/api/v1/seed-cloud-full"

print(f"Llamando a {url} para poblar la base de datos en la nube...")
for attempt in range(1, 4):
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=120) as r:
            body = json.loads(r.read().decode("utf-8"))
            print(f"Respuesta del servidor: {body}")
            if body.get("status") == "exito":
                print("¡Base de datos en la nube poblada con éxito!")
                break
            else:
                print(f"Error devuelto: {body.get('detalle')}")
    except Exception as e:
        print(f"Intento {attempt} falló: {e}")
        if attempt < 3:
            print("Esperando 30 segundos antes de reintentar...")
            time.sleep(30)

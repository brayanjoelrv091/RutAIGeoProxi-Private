import urllib.request
import json
import base64

url = "https://rutaigeoproxi-back.onrender.com/auth/login"
cred = {"email": "admin@ruta.com", "password": "Password123"}
req_data = json.dumps(cred).encode("utf-8")
req = urllib.request.Request(
    url,
    data=req_data,
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(req, timeout=10) as r:
        body = json.loads(r.read().decode("utf-8"))
        token = body.get("access_token")
        if token:
            payload = token.split(".")[1]
            # padding
            payload += "=" * ((4 - len(payload) % 4) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
            print("JWT Payload:", decoded)
        else:
            print("No token in response:", body)
except Exception as e:
    print(f"Login failed: {e}")

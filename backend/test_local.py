import httpx
try:
    r = httpx.get("http://localhost:8000/api/v1/health")
    print("Backend locally running:", r.status_code)
except Exception as e:
    print("Backend not running locally", e)

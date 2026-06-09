import urllib.request
import json
import time

base_url = "https://rutaigeoproxi-back.onrender.com/api/v1"

print("1. Wiping database...")
try:
    req = urllib.request.Request(f"{base_url}/wipe-database-danger-zona", method="GET")
    with urllib.request.urlopen(req, timeout=120) as r:
        print(r.read().decode("utf-8"))
except Exception as e:
    print(f"Error wiping: {e}")

time.sleep(2)

print("\n2. Seeding database...")
try:
    req = urllib.request.Request(f"{base_url}/seed-cloud-full", method="GET")
    with urllib.request.urlopen(req, timeout=120) as r:
        print(r.read().decode("utf-8"))
except Exception as e:
    print(f"Error seeding: {e}")

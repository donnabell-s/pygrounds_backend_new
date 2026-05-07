"""
Shared auth + config for all perf-test scripts.
Obtains a JWT access token from the API once and caches it.
"""
import sys
import requests

BASE_URL = "http://localhost:8000"
TOKEN_URL = f"{BASE_URL}/api/token/"

# Admin credentials — change if needed
ADMIN_USERNAME = "kastellan"
ADMIN_PASSWORD = "user12345"  # update to actual password

_cached_token = None


def get_token() -> str:
    global _cached_token
    if _cached_token:
        return _cached_token

    resp = requests.post(TOKEN_URL, json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
    }, timeout=15)

    if resp.status_code != 200:
        print(f"[AUTH] Failed to get token: {resp.status_code} {resp.text}")
        sys.exit(1)

    _cached_token = resp.json()["access"]
    print(f"[AUTH] Token obtained for '{ADMIN_USERNAME}'")
    return _cached_token


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {get_token()}"}

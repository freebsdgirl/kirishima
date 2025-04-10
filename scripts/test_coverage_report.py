import yaml
import requests

services = {
    "api": "http://localhost:4200/__list_routes__",
    "brain": "http://localhost:4207/__list_routes__",
    "chromadb": "http://localhost:4206/__list_routes__",
    "contacts": "http://localhost:4202/__list_routes__",
    "imessage": "http://localhost:4204/__list_routes__",
    "proxy": "http://localhost:4205/__list_routes__",
    "scheduler": "http://localhost:4201/__list_routes__",
    "summarize": "http://localhost:4203/__list_routes__",
}

with open("../tests/test_manifest.yaml", "r") as f:
    test_manifest = yaml.safe_load(f)

for service, url in services.items():
    print(f"\n🔧 {service.upper()} @ {url}")
    try:
        r = requests.get(url)
        r.raise_for_status()
        routes = r.json()

        for route in routes:
            path = route["path"]
            covered = test_manifest.get(service, {}).get(path, False)
            status = "✅ TESTED" if covered else "❌ MISSING"
            print(f"  {status} {path}")

    except Exception as e:
        print(f"  ❌ ERROR: Could not reach service: {e}")


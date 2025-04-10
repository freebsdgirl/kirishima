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

manifest = {}

for service, url in services.items():
    try:
        r = requests.get(url)
        r.raise_for_status()
        routes = r.json()
        manifest[service] = {route["path"]: False for route in routes}
    except Exception as e:
        print(f"❌ {service}: {e}")

# Save to file
with open("../tests/test_manifest.yaml", "w") as f:
    yaml.dump(manifest, f, sort_keys=True)

print("\n✅ test_manifest.yaml generated.")


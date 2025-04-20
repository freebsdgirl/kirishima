import yaml
import requests
import os

services = {
    "api": "http://localhost:4200/__list_routes__",
    "brain": "http://localhost:4207/__list_routes__",
    "chromadb": "http://localhost:4206/__list_routes__",
    "contacts": "http://localhost:4202/__list_routes__",
    "imessage": "http://localhost:4204/__list_routes__",
    "intents": "http://localhost:4204/__list_routes__",
    "proxy": "http://localhost:4205/__list_routes__",
    "scheduler": "http://localhost:4201/__list_routes__",
    "summarize": "http://localhost:4203/__list_routes__",
}

manifest_path = os.path.join(os.path.dirname(__file__), "../tests/test_manifest.yaml")

# Try to load the existing manifest if it exists
if os.path.exists(manifest_path):
    with open(manifest_path, "r") as f:
        existing_manifest = yaml.safe_load(f) or {}
else:
    existing_manifest = {}

ignore_patterns = [
    "/ping",
    "/docs",
    "/docs/export",
    "/__list_routes__",
]

def should_ignore(path):
    return any(path == patt or path.startswith(patt + "/") for patt in ignore_patterns)

manifest = {}

for service, url in services.items():
    try:
        r = requests.get(url)
        r.raise_for_status()
        routes = r.json()
        manifest[service] = {}
        for route in routes:
            path = route["path"]
            if should_ignore(path):
                continue
            # Preserve True if it was already marked as tested
            prev = existing_manifest.get(service, {}).get(path, False)
            manifest[service][path] = prev
    except Exception as e:
        print(f"❌ {service}: {e}")

# Save to file
with open(manifest_path, "w") as f:
    yaml.dump(manifest, f, sort_keys=True)

print("\n✅ test_manifest.yaml generated (preserving existing test coverage, ignoring ping/docs routes).")


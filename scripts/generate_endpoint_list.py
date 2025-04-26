import os
import re
import json
import sys
import requests

# Endpoints we don't want to include
IGNORE_ENDPOINTS = {
    ("GET", "/ping"),
    ("GET", "/docs/export"),
    ("GET", "/__list_routes__"),
}

def load_ports(env_path):
    ports = {}
    with open(env_path, "r") as f:
        for line in f:
            match = re.match(r"(\w+)_PORT=(42\d{2})", line.strip())
            if match:
                service, port = match.groups()
                ports[service] = port
    return ports

def fetch_routes(service, port):
    url = f"http://localhost:{port}/__list_routes__"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️  Failed to fetch routes for {service} at port {port}: {e}")
        return []

def massage_data(service, routes):
    output = []
    for entry in routes:
        for method in entry.get("methods", []):
            # Check if (method, path) is in the ignore list
            if (method, entry["path"]) in IGNORE_ENDPOINTS:
                continue
            output.append(f"    \"{service}: {method} {entry['path']}\"")
    return output

def main():
    env_path = os.path.expanduser("~/kirishima/.env")

    if not os.path.exists(env_path):
        print(f"❌ Could not find {env_path}")
        sys.exit(1)

    ports = load_ports(env_path)
    all_outputs = []

    for service, port in ports.items():
        routes = fetch_routes(service, port)
        output = massage_data(service, routes)
        all_outputs.extend(output)

    # Final output
    for line in all_outputs:
        print(line)

if __name__ == "__main__":
    main()

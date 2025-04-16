import requests

from time import sleep
def get_service_address(service_name):
    # Query Consul API for a specific service
    response = requests.get(f'http://consul:8500/v1/catalog/service/{service_name}')
    if response.status_code == 200:
        services = response.json()
        # You might have multiple instances; here we just take the first one.
        if services:
            address = services[0]['Address']
            port = services[0]['ServicePort']
            return address, port
        else:
            raise Exception("Service not found")
    else:
        raise Exception(f"Consul API returned {response.status_code}")

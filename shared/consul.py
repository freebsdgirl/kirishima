import requests

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


api_address, api_port               = get_service_address('api')
brain_address, brain_port           = get_service_address('brain')
chromadb_address, chromadb_port     = get_service_address('chromadb')
contacts_address, contacts_port     = get_service_address('contacts')
imessage_address, imessage_port     = get_service_address('imessage')
proxy_address, proxy_port           = get_service_address('proxy')
scheduler_address, scheduler_port   = get_service_address('scheduler')
summarize_address, summarize_port   = get_service_address('summarize')
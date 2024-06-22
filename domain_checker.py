import os
import requests
import argparse
from dotenv import load_dotenv
from forex_python.converter import CurrencyRates

# Load environment variables
load_dotenv()

# Initialize CurrencyRates
c = CurrencyRates()

def usd_to_eur(usd_amount):
    try:
        return c.convert('USD', 'EUR', usd_amount)
    except Exception as e:
        print(f"Error converting currency: {e}")
        # Fallback to a fixed rate if API fails
        return usd_amount * 0.92  # You can update this fallback rate periodically

# GoDaddy API credentials
GODADDY_API_KEY = os.getenv('GODADDY_API_KEY')
GODADDY_API_SECRET = os.getenv('GODADDY_API_SECRET')
GODADDY_REQ_HEADERS = {
    'Authorization': f'sso-key {GODADDY_API_KEY}:{GODADDY_API_SECRET}',
    'Accept': 'application/json'
}

# Gandi API credentials
GANDI_API_KEY = os.getenv('GANDI_API_KEY')
GANDI_REQ_HEADERS = {
    'Authorization': f'Apikey {GANDI_API_KEY}',
    'Content-Type': 'application/json'
}
GANDI_QUERYSTRING= {
    "name":"example.com",
    "processes":["create","transfer"],
    "grid":"C"
}
# GoDaddy API functions
def get_godaddy_request_url(check_domain):
    return f"https://api.ote-godaddy.com/v1/domains/available?domain={check_domain}"

# Gandi API functions
def get_gandi_request_url(check_domain):
    return f"https://api.gandi.net/v5/domain/check"

# Check domain availability on GoDaddy
def check_godaddy_availability(check_domain):
    print(f"Checking availability of domain {check_domain} on GoDaddy")

    req_url = get_godaddy_request_url(check_domain)
    response = requests.get(req_url, headers=GODADDY_REQ_HEADERS)

    if response.status_code == 200:
        domains = response.json()
        print(domains)
        if domains['available']:
            price_usd = domains['price'] / 1000000  # GoDaddy returns prices in micros
            price_eur = usd_to_eur(price_usd)
            print(f"The domain {check_domain} is available on GoDaddy.")
            print(f"The domain price is ${price_usd:.2f} USD (€{price_eur:.2f} EUR)")
            return price_eur
        else:
            print(f"The domain {check_domain} is not available on GoDaddy.")
    else:
        print(f"Failed to retrieve domain info from GoDaddy. Status code: {response.status_code}, Response: {response.text}")
    return None

# Check domain availability on Gandi
def check_gandi_availability(check_domain):
    print(f"Checking availability of domain {check_domain} on Gandi")
    req_url = get_gandi_request_url(check_domain)
    GANDI_QUERYSTRING = {
        "name": check_domain,  # Remove the curly braces
        "processes": ["create", "transfer"],
        "grid": "C"
    }

    try:
        response = requests.request("GET", req_url, headers=GANDI_REQ_HEADERS, params=GANDI_QUERYSTRING)
        response.raise_for_status()

        if response.status_code == 200:
            domain_info = response.json()
            #print(f"Gandi API response: {domain_info}")

            if 'products' in domain_info and domain_info['products']:
                product = domain_info['products'][0]  # Assume the first product is the one we want
                if product['status'] == 'available':
                    for price_info in product.get('prices', []):
                        if price_info.get('duration_unit') == 'y' and price_info.get('min_duration') == 1:
                            price = price_info.get('price_after_taxes')
                            print(f"The domain {check_domain} is available on Gandi.")
                            print(f"The domain price is {price} EUR")
                            return price
                else:
                    print(f"The domain {check_domain} is not available on Gandi.")
            else:
                print("No product information found in the Gandi API response.")
        else:
            print(f"Unexpected status code from Gandi API: {response.status_code}")

    except requests.RequestException as e:
        print(f"Error during Gandi API request: {e}")

    return None

def find_lowest_price(domain):
    prices = {
        "GoDaddy.com": check_godaddy_availability(domain),
        "Gandi.net": check_gandi_availability(domain)
    }
    # Filter out None values (unavailable domains)
    valid_prices = {k: v for k, v in prices.items() if v is not None}
    if not valid_prices:
        return None, None
    return min(valid_prices.items(), key=lambda x: x[1])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Check domain availability and pricing")
    parser.add_argument("domain", type=str, help="Domain name to be checked")
    args = parser.parse_args()

    best_registrar, lowest_price = find_lowest_price(args.domain)
    if best_registrar and lowest_price:
        print(f"The lowest price for {args.domain} is €{lowest_price:.2f}/yr at {best_registrar}")
    else:
        print(f"Unable to find pricing information for {args.domain}")
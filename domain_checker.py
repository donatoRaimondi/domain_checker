import os
import requests
import argparse
import whois
import itertools
from dotenv import load_dotenv
from datetime import datetime
import socket
import PySimpleGUI as sg
import threading

# Load environment variables
load_dotenv()
EXCHANGE_RATE = os.getenv('EXCHANGE_RATE')
base_currency = 'USD'
target_currency = 'EUR'

def usd_to_eur(usd_amount):
    url = f'https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE}/latest/{base_currency}'

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        data = response.json()
        if response.status_code == 200:
            exchange_rate = data['conversion_rates'][target_currency]
            return usd_amount * exchange_rate
        else:
            print(f"Error fetching data: {data.get('error-type', 'Unknown error')}")
            # Fallback to a fixed rate if API fails
            return usd_amount * 0.92
    except requests.exceptions.RequestException as e:
        print(f"Error converting currency: {e}")
        # Fallback to a fixed rate if API fails
        return usd_amount * 0.92


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


# compare tld's with and gives a suggestion to the user based on the searched domain
def suggest_cheapest_tld(base_domain):
    # List of common TLDs to check
    tlds = ['.com', '.net', '.org', '.io', '.co', '.info', '.biz', '.me']

    # Split the base domain to get the name without TLD
    domain_parts = base_domain.split('.')
    domain_name = domain_parts[0]

    cheapest_domain = None
    cheapest_price = float('inf')
    cheapest_registrar = None

    print(f"Checking prices for variations of '{domain_name}':")

    for tld in tlds:
        full_domain = f"{domain_name}{tld}"
        registrar, price = find_lowest_price(full_domain)

        if price is not None:
            print(f"{full_domain}: €{price:.2f}/yr at {registrar}")
            if price < cheapest_price:
                cheapest_domain = full_domain
                cheapest_price = price
                cheapest_registrar = registrar
        else:
            print(f"{full_domain}: Not available or pricing information not found")

    if cheapest_domain:
        print(f"\nCheapest option: {cheapest_domain} at €{cheapest_price:.2f}/yr from {cheapest_registrar}")
    else:
        print("\nNo available domains found among the checked TLDs.")

    return cheapest_domain, cheapest_price, cheapest_registrar

#
def get_domain_info(domain):
    try:
        domain_info = whois.whois(domain)

        if domain_info:
            print(f"\nDomain Information for {domain}:")
            print(f"Registrar: {domain_info.registrar}")
            print(f"Creation Date: {domain_info.creation_date}")
            print(f"Expiration Date: {domain_info.expiration_date}")

            if domain_info.expiration_date:
                days_until_expiration = (domain_info.expiration_date - datetime.now()).days
                print(f"Days until expiration: {days_until_expiration}")
            else:
                print("Expiration information not available")

            return domain_info
        else:
            print(f"No WHOIS information available for {domain}")
            return None

    except Exception as e:
        print(f"Error retrieving WHOIS information for {domain}: {str(e)}")

        # Fallback to basic DNS lookup
        try:
            ip_address = socket.gethostbyname(domain)
            print(f"The domain {domain} exists (based on DNS lookup), but detailed WHOIS information is not available.")
            print(f"IP Address: {ip_address}")
        except socket.gaierror:
            print(f"The domain {domain} does not exist or is not registered.")

        return None

def long_operation_wrapper(func, *args, **kwargs):
    def wrapper():
        result = func(*args, **kwargs)
        window.write_event_value('-THREAD-', (func.__name__, result))
    threading.Thread(target=wrapper, daemon=True).start()

def create_main_window():
    layout = [
        [sg.Text("Enter a domain name:"), sg.Input(key="-DOMAIN-"), sg.Button("Check")],
        [sg.Multiline(size=(60, 15), key="-OUTPUT-", disabled=True)],
        [sg.Button("Suggest Cheapest TLD"), sg.Button("Get Domain Info"), sg.Button("Exit")]
    ]
    return sg.Window("Domain Checker", layout)

def main():
    global window
    window = create_main_window()

    while True:
        event, values = window.read()
        if event == sg.WINDOW_CLOSED or event == "Exit":
            break
        elif event == "Check":
            domain = values["-DOMAIN-"]
            window["-OUTPUT-"].update("")
            long_operation_wrapper(find_lowest_price, domain)
        elif event == "Suggest Cheapest TLD":
            domain = values["-DOMAIN-"]
            window["-OUTPUT-"].update("")
            long_operation_wrapper(suggest_cheapest_tld, domain)
        elif event == "Get Domain Info":
            domain = values["-DOMAIN-"]
            window["-OUTPUT-"].update("")
            long_operation_wrapper(get_domain_info, domain)
        elif event == "-THREAD-":
            func_name, result = values[event]
            if func_name == "find_lowest_price":
                best_registrar, lowest_price = result
                if best_registrar and lowest_price:
                    window["-OUTPUT-"].print(f"The lowest price for {values['-DOMAIN-']} is €{lowest_price:.2f}/yr at {best_registrar}")
                else:
                    window["-OUTPUT-"].print(f"Unable to find pricing information for {values['-DOMAIN-']}")
            elif func_name == "suggest_cheapest_tld":
                cheapest_domain, cheapest_price, cheapest_registrar = result
                if cheapest_domain:
                    window["-OUTPUT-"].print(f"Cheapest option: {cheapest_domain} at €{cheapest_price:.2f}/yr from {cheapest_registrar}")
                else:
                    window["-OUTPUT-"].print("No available domains found among the checked TLDs.")
            elif func_name == "get_domain_info":
                if result:
                    window["-OUTPUT-"].print(f"Domain Information for {values['-DOMAIN-']}:")
                    window["-OUTPUT-"].print(f"Registrar: {result.registrar}")
                    window["-OUTPUT-"].print(f"Creation Date: {result.creation_date}")
                    window["-OUTPUT-"].print(f"Expiration Date: {result.expiration_date}")
                else:
                    window["-OUTPUT-"].print(f"Unable to retrieve information for {values['-DOMAIN-']}")

    window.close()

if __name__ == '__main__':
    main()
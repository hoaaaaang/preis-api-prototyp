from google.oauth2 import service_account#
import requests
from google.auth.transport.requests import Request
import os
from dotenv import load_dotenv

load_dotenv

""" 
Holt die Preise von Google Cloud (GCP) über die Cloud Billing API.
Nutzt ein Service-Konto zur Anmeldung, geht alle Seiten der Ergebnisse durch 
und sammelt nur Einträge mit gültigen Preisen.
"""
def get_gcp_prices():
    key_path = os.getenv("GCP_SERVICE_ACCOUNT_JSON")

    credentials = service_account.Credentials.from_service_account_file(
        key_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    auth_req = Request()
    credentials.refresh(Request())
    token = credentials.token
    headers = {"Authorization": f"Bearer {token}"}

    url = "https://cloudbilling.googleapis.com/v1/services/6F81-5844-456A/skus"

    all_prices= []
    next_page = url

    while next_page: 
        # print(f"Hole GCP Preise von: {next_page}")
        response = requests.get(next_page, headers = headers)
        if response.status_code == 200:
            data = response.json()
            skus = data.get("skus", [])
            for item in skus: 
                pricing_info = item.get("pricingInfo", [])
                if not pricing_info: 
                    continue

                #if "europe-west3" not in item.get("serviceRegions", []):
                #    continue

                expr = pricing_info[0].get("pricingExpression", {})
                tiered = expr.get("tieredRates", [])
                if not tiered:
                    continue

                price_obj = tiered[0].get("unitPrice", {})
                units = int(price_obj.get("units", 0))
                nanos = int(price_obj.get("nanos", 0))
                price = units + nanos / 1e9

                if price == 0:
                    continue  # 0er-Preise überspringen

                region_list = item.get("serviceRegions", [])
                region = ",".join(region_list) if region_list else "unknown"

                all_prices.append({
                    "provider": "GCP",
                    "service": item.get("category", {}).get("resourceFamily", "unknown"),
                    "sku": item.get("description", "unknown"),
                    "resource_name": item.get("description"),
                    "region": region,
                    "price_per_unit": price,
                    "unit": expr.get("usageUnit", "unit"),
                    "currency": expr.get("currencyCode", "USD")
                })

            next_page = data.get("nextPageToken")
            next_token = data.get("nextPageToken")
            if next_token:
                next_page = f"{url}?pageToken={next_token}"
            else:
                next_page = None
        else:
            print(f"Fehler bei GCP Preis-API: {response.status_code}")
            break

    return all_prices
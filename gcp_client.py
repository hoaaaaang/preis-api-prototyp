from google.oauth2 import service_account
from google.auth.transport.requests import Request
import requests
import os
import re
from dotenv import load_dotenv

load_dotenv()


"""
Erstellt ein Authentifikations Header mit Token für die GCP API
"""
def _get_headers():
    key_path = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    credentials = service_account.Credentials.from_service_account_file(
        key_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(Request())
    token = credentials.token
    return {"Authorization": f"Bearer {token}"}


"""
Holt alle GCP-Billing-Services (mit id und Name), inkl. Pagination
"""
def _list_services(headers):
    url = "https://cloudbilling.googleapis.com/v1/services"
    out = []
    next_page = url
    while next_page:
        r = requests.get(next_page, headers=headers, timeout=60)
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("services", []))
        token = data.get("nextPageToken")
        next_page = f"{url}?pageToken={token}" if token else None
    return out


"""
Sucht zu gegebenen Display-Namen die passenden GCP-Service-IDs
"""
def _resolve_service_ids(headers, wanted_names):
    services = _list_services(headers)
    name_to_id = {}
    for alias, disp in wanted_names.items():
        sid = next((s["name"].split("/")[-1] for s in services
                    if s.get("displayName", "").strip().lower() == disp.lower()), None)
        name_to_id[alias] = sid
    return name_to_id


"""
Lädt alle SKUs eines GCP-Services
"""
def _fetch_skus_for_service(headers, service_id):
    base = f"https://cloudbilling.googleapis.com/v1/services/{service_id}/skus"
    all_skus = []
    next_page = base
    while next_page:
        r = requests.get(next_page, headers=headers, timeout=60)
        r.raise_for_status()
        data = r.json()
        all_skus.extend(data.get("skus", []))
        token = data.get("nextPageToken")
        next_page = f"{base}?pageToken={token}" if token else None
    return all_skus


"""
Liest den ersten Preis aus und gibt Wert, Einheit und Währung zurück
"""
def _unit_price_from_pricing_info(pi):
    if not pi:
        return None
    expr = pi[0].get("pricingExpression", {}) if isinstance(pi, list) else pi.get("pricingExpression", {})
    tiered = expr.get("tieredRates", []) or []
    if not tiered:
        return None
    up = tiered[0].get("unitPrice", {}) or {}
    units = int(up.get("units", 0))
    nanos = int(up.get("nanos", 0))
    price = units + nanos / 1e9
    if price <= 0:
        return None
    return price, expr.get("usageUnit", "unit"), expr.get("currencyCode", "USD")


"""
Versucht aus einer Beschreibung den Instanztyp zu erkennen, sonst "unknown"
"""
def _extract_instance_type(desc: str):
    if not isinstance(desc, str):
        return "unknown"
    m = re.search(r'\b([a-z0-9]{1,8}-[a-z]+(?:-[a-z0-9]+)?)\b', desc.lower())
    return (m.group(0) if m else "unknown")[:100]


"""
Wandelt ein GCP-SKU-Item ins Standard-Format um
"""
def _map_sku_item(item, service_label_override=None):
    pricing_info = item.get("pricingInfo", [])
    unit_price_pack = _unit_price_from_pricing_info(pricing_info)
    if not unit_price_pack:
        return None
    price, unit, currency = unit_price_pack

    desc = item.get("description", "")
    category = item.get("category", {}) or {}
    service_regions = item.get("serviceRegions", []) or []
    region = ",".join(service_regions) if service_regions else "unknown"

    service_label = service_label_override or category.get("serviceDisplayName") \
        or category.get("resourceFamily") or "unknown"

    instance_type = _extract_instance_type(desc)
    if instance_type == "unknown":
        rg = category.get("resourceGroup") or ""
        rf = category.get("resourceFamily") or ""
        if rg:
            instance_type = rg[:100]
        elif rf:
            instance_type = rf[:100]

    return {
        "provider": "GCP",
        "instance_type": instance_type,
        "service": service_label,
        "sku": item.get("skuId", "unknown"),
        "resource_name": desc or item.get("skuId", "unknown"),
        "region": region,
        "price_per_unit": float(price),
        "unit": unit,
        "currency": currency
    }


"""
Holt alle GCP-Preise und gibt sie als Liste zurück
"""
def get_gcp_prices():
    headers = _get_headers()
    url = "https://cloudbilling.googleapis.com/v1/services/6F81-5844-456A/skus"

    all_prices = []
    next_page = url

    while next_page:
        response = requests.get(next_page, headers=headers)
        if response.status_code == 200:
            data = response.json()
            skus = data.get("skus", [])
            for item in skus:
                price_pack = _unit_price_from_pricing_info(item.get("pricingInfo", []))
                if not price_pack:
                    continue
                price, unit, currency = price_pack

                desc = item.get("description", "").lower()
                instance_type = _extract_instance_type(desc)

                region_list = item.get("serviceRegions", [])
                region = ",".join(region_list) if region_list else "unknown"

                all_prices.append({
                    "provider": "GCP",
                    "instance_type": instance_type,
                    "service": item.get("category", {}).get("resourceFamily", "unknown"),
                    "sku": item.get("skuId", "unknown"),
                    "resource_name": item.get("description"),
                    "region": region,
                    "price_per_unit": price,
                    "unit": unit,
                    "currency": currency
                })

            next_token = data.get("nextPageToken")
            next_page = f"{url}?pageToken={next_token}" if next_token else None
        else:
            print(f"Fehler bei GCP Preis-API: {response.status_code}")
            break

    return all_prices


"""
Holt und mapped alle Compute Engine SKUs aus der GCP-API
"""
def get_gcp_prices_compute_engine():
    headers = _get_headers()
    ids = _resolve_service_ids(headers, {"ce": "Compute Engine"})
    sid = ids.get("ce")
    if not sid:
        return []
    skus = _fetch_skus_for_service(headers, sid)
    out = []
    for it in skus:
        mapped = _map_sku_item(it, service_label_override="Compute Engine")
        if mapped:
            out.append(mapped)
    return out


"""
Holt und mapped alle Cloud Storage SKUs aus der GCP-API
"""
def get_gcp_prices_cloud_storage():
    headers = _get_headers()
    ids = _resolve_service_ids(headers, {"cs": "Cloud Storage"})
    sid = ids.get("cs")
    if not sid:
        return []
    skus = _fetch_skus_for_service(headers, sid)
    out = []
    for it in skus:
        mapped = _map_sku_item(it, service_label_override="Cloud Storage")
        if mapped:
            out.append(mapped)
    return out


"""
Holt Compute Engine SKUs und filtert alle Persistent Disk relevanten Einträge
"""
def get_gcp_prices_persistent_disk():
    headers = _get_headers()
    ids = _resolve_service_ids(headers, {"ce": "Compute Engine"})
    sid = ids.get("ce")
    if not sid:
        return []
    skus = _fetch_skus_for_service(headers, sid)

    out = []
    for it in skus:
        cat = it.get("category", {}) or {}
        text = f"{it.get('description','')} {cat.get('resourceGroup','')}".lower()
        if ("persistent disk" in text) or ("pd-standard" in text) or ("pd-ssd" in text) \
           or ("balanced pd" in text) or ("hyperdisk" in text) \
           or (cat.get("resourceFamily") == "Storage" and "disk" in text):
            mapped = _map_sku_item(it, service_label_override="Persistent Disk")
            if mapped:
                out.append(mapped)
    return out


"""
Holt und mapped alle Cloud SQL SKUs aus der GCP-API
"""
def get_gcp_prices_cloud_sql():
    headers = _get_headers()
    ids = _resolve_service_ids(headers, {"sql": "Cloud SQL"})
    sid = ids.get("sql")
    if not sid:
        return []
    skus = _fetch_skus_for_service(headers, sid)
    out = []
    for it in skus:
        mapped = _map_sku_item(it, service_label_override="Cloud SQL")
        if mapped:
            out.append(mapped)
    return out


"""
Holt Preise für die 4 GCP-Dienste und gibt sie kombiniert zurück
"""
def get_gcp_prices_all_services():
    all_items = []
    try:
        all_items.extend(get_gcp_prices_compute_engine())
    except Exception as e:
        print("Compute Engine Fehler:", e)
    try:
        all_items.extend(get_gcp_prices_cloud_storage())
    except Exception as e:
        print("Cloud Storage Fehler:", e)
    try:
        all_items.extend(get_gcp_prices_persistent_disk())
    except Exception as e:
        print("Persistent Disk Fehler:", e)
    try:
        all_items.extend(get_gcp_prices_cloud_sql())
    except Exception as e:
        print("Cloud SQL Fehler:", e)
    return all_items


"""
Holt alle GCP-Preise, gibt Anzahl pro Dienst und Gesamtsumme aus
"""
if __name__ == "__main__":
    base = get_gcp_prices()
    print("GCP (bestehend) Compute-Engine-SKUs:", len(base))

    ce = get_gcp_prices_compute_engine()
    cs = get_gcp_prices_cloud_storage()
    pd = get_gcp_prices_persistent_disk()
    sql = get_gcp_prices_cloud_sql()

    total = len(ce) + len(cs) + len(pd) + len(sql)
    print("Compute Engine:", len(ce))
    print("Cloud Storage:", len(cs))
    print("Persistent Disk:", len(pd))
    print("Cloud SQL:", len(sql))
    print("Summe neue GCP-Preise:", total)


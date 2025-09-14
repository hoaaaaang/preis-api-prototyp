import time, random, requests

AZURE_PRICES_URL = "https://prices.azure.com/api/retail/prices"
_DEFAULT_TIMEOUT = 180
_MAX_RETRIES     = 4
_BACKOFF_SECONDS = 2.0
_MIN_INTERVAL_S  = 1.0    # min. Abstand zwischen Requests
_JITTER_S        = 0.3    # kleiner Zufallsjitter
_last_call_ts    = 0.0    # globales Throttle
_storage_cache   = None   # Cache für "Storage & Consumption"


"""
Stellt sicher, dass zwischen Aufrufen eine Mindestpause liegt
"""
def _respect_min_interval():
    global _last_call_ts
    now = time.monotonic()
    sleep_need = _MIN_INTERVAL_S - (now - _last_call_ts)
    if sleep_need > 0:
        time.sleep(sleep_need)
    _last_call_ts = time.monotonic()


"""
Die Funktion liest aus der HTTP-Antwort aus, wie viele Sekunden 
gewartet werden soll (Retry-After). Gibt sonst None zurück.
"""
def _retry_after_seconds(resp):
    # Azure/HTTP Header prüfen
    for k in ("Retry-After",
              "x-ms-ratelimit-microsoft.costmanagement-tenant-retry-after",
              "x-ms-ratelimit-microsoft.costmanagement-clienttype-retry-after"):
        v = resp.headers.get(k)
        if v:
            try:
                return float(v)
            except ValueError:
                pass
    return None


"""
Führt einen GET-Request aus, wiederholt bei Fehlern und wartet dazwischen.
"""
def _get(url, params=None, timeout=_DEFAULT_TIMEOUT):
    attempt = 0
    last_exc = None
    headers = {"Accept": "application/json", "User-Agent": "cloudprice-prototype/1.0"}
    while attempt < _MAX_RETRIES:
        try:
            _respect_min_interval()
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            if resp.status_code == 429 or resp.status_code >= 500:
                ra = _retry_after_seconds(resp)
                if ra is None:
                    ra = _BACKOFF_SECONDS * (2 ** attempt)
                ra += random.uniform(0, _JITTER_S)
                print(f"[Azure] WARN: {resp.status_code} – warte {ra:.1f}s (Versuch {attempt+1}/{_MAX_RETRIES}) …")
                time.sleep(ra)
                attempt += 1
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            last_exc = e
            ra = _BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, _JITTER_S)
            print(f"[Azure] WARN: Request fehlgeschlagen (Versuch {attempt+1}/{_MAX_RETRIES}): {e}. Backoff {ra:.1f}s …")
            time.sleep(ra)
            attempt += 1
    raise last_exc


"""
Holt alle Seiten via NextPageLink (kein $skip manuell).
"""
def _azure_fetch(filter_expr: str):
    results = []
    next_page = AZURE_PRICES_URL
    params = {"$filter": filter_expr}
    while next_page:
        resp = _get(next_page, params=params if next_page == AZURE_PRICES_URL else None)
        data = resp.json()
        items = data.get("Items", []) or []
        results.extend(items)
        next_page = data.get("NextPageLink")
    return results


"""
Normalisierung der Preisdaten
"""
def _map_items(items):
    mapped = []
    for item in items:
        if (item.get("retailPrice") or 0) > 0:
            arm = item.get("armSkuName")
            mapped.append({
                "provider": "Azure",
                "instance_type": arm or item.get("skuName", "unknown"),
                "service": item.get("serviceName"),
                "sku": arm or item.get("skuName") or item.get("skuId") or item.get("productId"),
                "resource_name": item.get("productName") or item.get("skuName"),
                "region": item.get("armRegionName"),
                "price_per_unit": item.get("retailPrice"),
                "unit": item.get("unitOfMeasure"),
                "currency": item.get("currencyCode"),
            })
    return mapped


"""
Die Funktion holt alle Preise für Microsoft Azure Virtual Machines aus der Azure Retail API, 
und gibt sie im vereinheitlichten Format zurück.
"""
def get_azure_vm_prices():
    items = _azure_fetch("serviceName eq 'Virtual Machines' and type eq 'Consumption'")
    return _map_items(items)


"""
Storage (einmal holen & cachen)
"""
def _get_storage_consumption_items():
    global _storage_cache
    if _storage_cache is None:
        _storage_cache = _azure_fetch("serviceName eq 'Storage' and type eq 'Consumption'")
    return _storage_cache


"""
Die Funktion holt alle Preise für Microsoft Azure Blob Prices aus der Azure Retail API, 
und gibt sie im vereinheitlichten Format zurück.
"""
def get_azure_blob_prices():
    items = _get_storage_consumption_items()
    filtered = []
    for it in items:
        pn = (it.get("productName") or "")
        sn = (it.get("skuName") or "")
        if ("blob" in pn.lower()) or ("blob" in sn.lower()):
            filtered.append(it)
    return _map_items(filtered)


"""
Die Funktion holt alle Preise für Microsoft Azure Disk Storage aus der Azure Retail API, 
und gibt sie im vereinheitlichten Format zurück.
"""
def get_azure_disk_prices():
    items = _get_storage_consumption_items()
    keys = ["disk", "managed disk", "premium ssd", "standard ssd", "standard hdd", "ultra disk"]
    filtered = []
    for it in items:
        text = f"{it.get('productName') or ''} {it.get('skuName') or ''}".lower()
        if any(k in text for k in keys):
            filtered.append(it)
    return _map_items(filtered)


"""
Die Funktion holt alle Preise für Microsoft Azure SQL Database aus der Azure Retail API, 
und gibt sie im vereinheitlichten Format zurück.
"""
def get_azure_sql_prices():
    items = _azure_fetch("serviceName eq 'SQL Database' and type eq 'Consumption'")
    return _map_items(items)

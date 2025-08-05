import requests


""" 
Ruft die aktuellen Preise für Azure Virtual Machines aus der Region 'germanywestcentral' über die Azure Retail Prices API ab.
Die Funktion verarbeitet mehrere Ergebnisseiten und gibt eine gefilterte Liste von Preisdetails zurück.
"""
def get_azure_vm_prices():
    url = "https://prices.azure.com/api/retail/prices"
    params = {
        "$filter": "serviceName eq 'Virtual Machines' and armRegionName eq 'germanywestcentral'"
    }

    results = []
    next_page = url

    while next_page: 
        response = requests.get(next_page, params=params if next_page == url else None)
        if response.status_code == 200:
            data = response.json()
            results.extend(data.get("Items", []))
            next_page = data.get("NextPageLink")
        else: 
            break

    mapped = []
    for item in results:
        #region = item.get("armRegionName", "").lower()
        #if "europe" not in region:
        #    continue
        if item.get("retailPrice", 0) > 0:
            mapped.append({
                "provider": "Azure", 
                "service": item.get("serviceName"),
                "sku": item.get("skuName"),
                "resource_name": item.get("productName") or item.get("skuName"),
                "region": item.get("armRegionName"),
                "price_per_unit": item.get("retailPrice"),
                "unit": item.get("unitOfMeasure"),
                "currency": item.get("currencyCode")
            })
    return mapped
    


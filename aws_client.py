
import os
from dotenv import load_dotenv
import boto3
import json

load_dotenv()

def get_aws_prices():
    client = boto3.client(
        'pricing',
        region_name='us-east-1',  # Muss diese Region sein
        aws_access_key_id=os.getenv("AKIARTWMKATPCJKGFMSG"),
        aws_secret_access_key=os.getenv("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")
    )

    prices = []
    next_token = None

    while True:
        params = {
            "ServiceCode": "AmazonEC2",
            "MaxResults": 100,
            "FormatVersion": "aws_v1",
            "MaxResults": 100,
            "Filters": [
                #{"Type": "TERM_MATCH", "Field": "location", "Value": "EU (Frankfurt)"},
                #{"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
                #{"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
                #{"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
                #{"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
                {"Type": "TERM_MATCH", "Field": "instanceType", "Value": "t3.micro"}
            ]
        }

        if next_token:
            params["NextToken"] = next_token

        response = client.get_products(**params)
        for offer_json in response["PriceList"]:
            offer = json.loads(offer_json)
            product = offer.get("product", {})
            terms = offer.get("terms", {}).get("OnDemand", {})

            for term in terms.values():
                price_dimensions = term.get("priceDimensions", {})
                for price_detail in price_dimensions.values():
                    price_per_unit = price_detail.get("pricePerUnit", {}).get("USD")
                    if price_per_unit:
                        prices.append({
                            "provider": "AWS",
                            "service": product.get("productFamily"),
                            "sku": product.get("sku"),
                            "resource_name": product.get("productFamily") or product.get("description"),
                            "region": product.get("attributes", {}).get("location"),
                            "price_per_unit": float(price_per_unit),
                            "unit": price_detail.get("unit"),
                            "currency": "USD"
                        })

        next_token = response.get("NextToken")
        if not next_token:
            break

    return prices

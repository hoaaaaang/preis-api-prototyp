import os
import time
import json
import boto3
from dotenv import load_dotenv
from db import insert_prices

load_dotenv()


"""
Die Funktion holt alle Preise für Amazon EC2 aus der AWS Price List API, 
bereitet sie auf und gibt sie als Liste zurück.
"""
def get_aws_prices_ec2():
    client = boto3.client(
        'pricing',
        region_name='us-east-1',
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    prices = []
    next_token = None

    while True:
        params = {
            "ServiceCode": "AmazonEC2",
            "FormatVersion": "aws_v1",
            "MaxResults": 100,
            "Filters": [
                {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
                {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
                {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"}
            ]
        }

        if next_token:
            params["NextToken"] = next_token

        response = client.get_products(**params)
        time.sleep(0.1)  
        for offer_json in response["PriceList"]:
            offer = json.loads(offer_json)
            product = offer.get("product", {})
            terms = offer.get("terms", {}).get("OnDemand", {})

            for term in terms.values():
                price_dimensions = term.get("priceDimensions", {})
                for price_detail in price_dimensions.values():
                    price_per_unit = price_detail.get("pricePerUnit", {}).get("USD")
                    if price_per_unit:
                        attr = product.get("attributes", {})
                        prices.append({
                            "provider": "AWS",
                            "instance_type": attr.get("instanceType", "unknown"),
                            "service": product.get("productFamily"),
                            "sku": product.get("attributes", {}).get("instanceType") or product.get("sku"),
                            "resource_name": f"{attr.get('instanceType', 'unknown')} | {attr.get('vcpu', '?')} vCPU | {attr.get('memory', '?')} RAM",
                            "region": attr.get("location", "unknown"),
                            "price_per_unit": float(price_per_unit),
                            "unit": price_detail.get("unit"),
                            "currency": "USD"
                        })

        next_token = response.get("NextToken")
        if not next_token:
            break

    return prices


"""
Die Funktion holt alle Preise für Amazon S3 aus der AWS Price List API, 
bereitet sie auf und gibt sie als Liste zurück.
"""
def get_aws_prices_s3():
    client = boto3.client(
        'pricing',
        region_name='us-east-1',
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    prices = []
    next_token = None

    while True:
        params = {
            "ServiceCode": "AmazonS3",
            "FormatVersion": "aws_v1",
            "MaxResults": 100,
            "Filters": []
        }
        if next_token:
            params["NextToken"] = next_token

        response = client.get_products(**params)
        time.sleep(0.1)

        for offer_json in response["PriceList"]:
            offer = json.loads(offer_json)
            product = offer.get("product", {})
            terms = offer.get("terms", {}).get("OnDemand", {})
            attr = product.get("attributes", {}) or {}

            for term in terms.values():
                for price_detail in term.get("priceDimensions", {}).values():
                    price_per_unit = price_detail.get("pricePerUnit", {}).get("USD")
                    if not price_per_unit:
                        continue
                    prices.append({
                        "provider": "AWS",
                        "instance_type": attr.get("storageClass") or attr.get("usagetype") or "unknown",
                        "service": product.get("productFamily") or "S3",
                        "sku": product.get("sku"),
                        "resource_name": f"{attr.get('storageClass', 'S3')} | {attr.get('usagetype', '')}".strip(),
                        "region": attr.get("location", "unknown"),
                        "price_per_unit": float(price_per_unit),
                        "unit": price_detail.get("unit"),
                        "currency": "USD"
                    })

        next_token = response.get("NextToken")
        if not next_token:
            break

    return prices


"""
Die Funktion holt alle Preise für Amazon EBS aus der AWS Price List API, 
bereitet sie auf und gibt sie als Liste zurück.
"""
def get_aws_prices_ebs():
    client = boto3.client(
        'pricing',
        region_name='us-east-1',
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    prices = []
    next_token = None

    while True:
        params = {
            "ServiceCode": "AmazonEC2",     
            "FormatVersion": "aws_v1",
            "MaxResults": 100,
            "Filters": [
                {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "Storage"}
            ]
        }
        if next_token:
            params["NextToken"] = next_token

        response = client.get_products(**params)
        time.sleep(0.1)

        for offer_json in response["PriceList"]:
            offer = json.loads(offer_json)
            product = offer.get("product", {})
            terms = offer.get("terms", {}).get("OnDemand", {})
            attr = product.get("attributes", {}) or {}

            for term in terms.values():
                for price_detail in term.get("priceDimensions", {}).values():
                    usd = price_detail.get("pricePerUnit", {}).get("USD")
                    if not usd:
                        continue
                    prices.append({
                        "provider": "AWS",
                        "instance_type": attr.get("volumeType") or attr.get("usagetype") or "unknown",
                        "service": product.get("productFamily") or "EBS",
                        "sku": product.get("sku"),
                        "resource_name": f"{attr.get('volumeType', 'EBS')} | {attr.get('usagetype', '')}".strip(),
                        "region": attr.get("location", "unknown"),
                        "price_per_unit": float(usd),
                        "unit": price_detail.get("unit"), 
                        "currency": "USD"
                    })

        next_token = response.get("NextToken")
        if not next_token:
            break

    return prices


"""
Die Funktion holt alle Preise für Amazon RDS aus der AWS Price List API, 
bereitet sie auf und gibt sie als Liste zurück.
"""
def get_aws_prices_rds():
    client = boto3.client(
        'pricing',
        region_name='us-east-1',
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    prices = []
    next_token = None

    while True:
        params = {
            "ServiceCode": "AmazonRDS",
            "FormatVersion": "aws_v1",
            "MaxResults": 100,
            "Filters": []
        }
        if next_token:
            params["NextToken"] = next_token

        response = client.get_products(**params)
        time.sleep(0.1)

        for offer_json in response["PriceList"]:
            offer = json.loads(offer_json)
            product = offer.get("product", {})
            terms = offer.get("terms", {}).get("OnDemand", {})
            attr = product.get("attributes", {}) or {}
            itype = attr.get("instanceType") or attr.get("databaseEdition") or attr.get("deploymentOption") or "unknown"
            db_engine = attr.get("databaseEngine")
            rname_bits = [itype]
            if db_engine:
                rname_bits.append(db_engine)
            rname = " | ".join([b for b in rname_bits if b])

            for term in terms.values():
                for price_detail in term.get("priceDimensions", {}).values():
                    price_per_unit = price_detail.get("pricePerUnit", {}).get("USD")
                    if not price_per_unit:
                        continue
                    prices.append({
                        "provider": "AWS",
                        "instance_type": itype,
                        "service": product.get("productFamily") or "RDS",
                        "sku": product.get("sku"),
                        "resource_name": rname or "RDS",
                        "region": attr.get("location", "unknown"),
                        "price_per_unit": float(price_per_unit),
                        "unit": price_detail.get("unit"),
                        "currency": "USD"
                    })

        next_token = response.get("NextToken")
        if not next_token:
            break

    return prices


"""
Wenn das Skript direkt gestartet wird, lädt es alle AWS-Preisdaten 
(EC2, S3, EBS, RDS) und speichert sie gesammelt in der Datenbank.
"""
if __name__ == "__main__":
    aws_prices = get_aws_prices_ec2()          # EC2 
    aws_prices += get_aws_prices_s3()          # S3
    aws_prices += get_aws_prices_ebs()         # EBS
    aws_prices += get_aws_prices_rds()         # RDS

    print("Gefundene AWS-Preise:", len(aws_prices))
    from db import insert_prices
    insert_prices(aws_prices, "AWS")













import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os
import time

load_dotenv()

host = os.getenv("DB_HOST")
user = os.getenv("DB_USER")



"""
Holt alle verschiedenen Regionen aus der Datenbank
"""
def get_all_regions():
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cursor = connection.cursor()
    cursor.execute("""
        SELECT DISTINCT region
        FROM cloud_prices
        WHERE region IS NOT NULL AND region <> ''
        ORDER BY region
    """)
    regions = [r[0] for r in cursor.fetchall()]
    cursor.close()
    connection.close()
    return regions


""" 
Stellt eine Verbindung zur MySQL-Datenbank her.
"""
def create_connection():
    try: 
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        if connection.is_connected():
            print("Verbindung zur MySQL-Datenbank hergestellt.")
            return connection
    except Error as e:
        print(f"Fehler bei der Herstellung der Verbindung: {e}")
        return None

    
""" 
Speichert Preisdaten in der Datenbank-Tabelle 'cloud_prices'.
"""
def insert_prices(prices,provider):
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cursor = connection.cursor()

    for entry in prices:

        UNIT_KEY_MAP = {
            "h": "hour", "hr": "hour", "hrs": "hour", "hour": "hour",
            "s": "seconds", "sec": "seconds", "secs": "seconds", "second": "seconds", "seconds": "seconds",
            "mo": "mo", "mon": "mo", "month": "mo", "months": "mo",
            "giby.mo": "giby.mo", "gb-month": "giby.mo",
            "giby":    "giby.mo",
            "giby.h":  "giby.h",
            "gby.h": "gby.h",
            "1 hour":  "hour",
            "mbps": "mbps",
            "gb-month": "giby.mo", "gb/mo": "giby.mo", "gb per month": "giby.mo",
            "gib.mo": "giby.mo", "gib-month": "giby.mo", "gibibyte month": "giby.mo",
            "request": "request", "requests": "request",
            "1k requests": "1kreq", "1000 requests": "1kreq",
            "1m requests": "1mreq", "million requests": "1mreq",
            "min": "minutes", "minute": "minutes", "minutes": "minutes"
        }

        UNIT_MAP = {
            "hour": "$/Stunde",
            "mo":   "$/Monat",
            "giby.mo": "$/GB/Monat",
            "gb-mo": "$/GB/Monat",
            "1/day": "$/Tag",
            "giby.h":   "$/GB/Stunde",
            "gby.h":   "$/GB/Stunde",
            "giby":      "$/GB/Monat",
            "gb":      "$/GB/Monat",
            "mbps": "$/MB/s",
            "seconds": "$/Sekunde",
            "request": "$/Request",
            "1kreq": "$/1k Requests",
            "1mreq": "$/1M Requests",
            "minutes": "$/Minute",
            "vcpu-hour": "$/vCPU/Stunde",
            "vcpu-months": "$/vCPU/Monat",
            "vcpu-hours": "$/vCPU/Stunde",
            "iops-mo": "$/IOPS/Monat"
        }

        # Sekunden-Rate in Stunden-Rate umrechnen 
        if entry["unit"].lower() == "seconds":
            entry["price_per_unit"] = float(entry["price_per_unit"]) * 3600
            entry["unit"] = "hour"

        # Normalisieren
        raw = entry["unit"].lower()
        key = UNIT_KEY_MAP.get(raw, raw)

        # Mappen
        entry["unit"] = UNIT_MAP.get(key, entry["unit"])

        # Preise ≤ 0 überspringen
        if float(entry["price_per_unit"]) <= 0.0:
            continue

        cursor.execute("""
            INSERT INTO cloud_prices
            (provider, instance_type, service, sku, resource_name, region, price_per_unit, unit, currency)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                instance_type = VALUES(instance_type),
                resource_name = VALUES(resource_name),
                price_per_unit = VALUES(price_per_unit),
                unit = VALUES(unit),
                currency = VALUES(currency)
        """, (
            provider,
            entry.get('instance_type'),
            entry['service'],
            entry['sku'],
            entry.get('resource_name'),
            entry['region'],
            entry['price_per_unit'],
            entry['unit'],
            entry['currency']
        ))

    connection.commit()
    cursor.close()
    connection.close()


"""
Löscht die alten Einträge aus der Datenbank
"""
def delete_provider_prices(provider):
    connection = create_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM cloud_prices WHERE provider = %s", (provider,))
    connection.commit()
    cursor.close()
    connection.close()


""" 
Liest Preiseinträge aus der Datenbank, sortiert nach Preis.
"""
def select_all_prices(limit=10):
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT provider, instance_type, sku, region, price_per_unit, currency
        FROM cloud_prices
        ORDER BY price_per_unit ASC
        LIMIT %s
    """, (limit,))

    rows = cursor.fetchall()
    cursor.close()
    connection.close()
    return rows


""" 
Holt alle Preise aus der Datenbank, die Regionen in Europa enthalten sind.
"""
_cached_prices = None
_last_cache_time = 0
_CACHE_TTL_SECONDS = 300  


def get_all_prices():
    global _cached_prices, _last_cache_time
    now = time.time()

    if _cached_prices is not None and now - _last_cache_time < _CACHE_TTL_SECONDS:
        return _cached_prices

    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM cloud_prices
        WHERE region LIKE '%Europe%' OR region LIKE '%EU%'
        ORDER BY provider
    """)
    result = cursor.fetchall() 
    conn.close()

    _cached_prices = result
    _last_cache_time = now
    return result


""" 
Entfernt doppelte Preiseinträge anhand von Provider, Service, SKU, Name, Region und Preis.
"""
def remove_duplicates(prices):
    seen = set()
    unique_prices = []
    for p in prices:
        key = (
            p["provider"].strip().lower(),
            p["service"].strip().lower(),
            p["sku"].strip().lower(),
            p["resource_name"].strip().lower(),
            p["region"].strip().lower(),
            round(float(p["price_per_unit"]), 6)  
        )
        if key not in seen:
            seen.add(key)
            unique_prices.append(p)
    return unique_prices


""" 
Filtert die Preise nach bestimmten Kriterien (Provider, Service usw.) und sortiert die Ergebnisse.
"""
def get_filtered_prices(filters, sort_by=None, order='asc'):
    allowed_sort_fields = ['provider', 'instance_type', 'service', 'sku', 'resource_name', 'region', 'price_per_unit']
    if sort_by not in allowed_sort_fields:
        sort_by = 'provider'
    if order not in ['asc', 'desc']:
        order = 'asc'

    defaults = {
        "provider": "", "q": "", "service": "", "sku": "",
        "resource_name": "", "resource": "", "instance_type": "", "region": ""
    }
    filters = {**defaults, **(filters or {})}

    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cursor = connection.cursor(dictionary=True)

    query = "SELECT * FROM cloud_prices WHERE 1=1"

    params = []

    if filters.get("q"):
        qv = f"%{filters['q']}%"
        query += " AND (provider LIKE %s OR sku LIKE %s OR resource_name LIKE %s)"
        params.extend([qv, qv, qv])

    if filters["provider"]:
        query += " AND provider LIKE %s"
        params.append(f"%{filters['provider']}%")

    if filters.get("instance_type"):
        query += " AND instance_type LIKE %s"
        params.append(f"%{filters['instance_type']}%")

    service  = (filters.get("service") or "").strip()
    provider = (filters.get("provider") or "").strip()

    if service:
        s = service.lower()

        if provider == "AWS":
            if s == "ec2":
                query += (" AND provider='AWS' AND ("
                        " service LIKE 'Compute%%'"
                        " OR resource_name LIKE '%%EC2%%'"
                        " OR instance_type REGEXP '^[a-z0-9]+(\\.[a-z0-9]+)?$'"
                        ")")
            elif s == "s3":
                query += (" AND provider='AWS' AND ("
                        " (service='Storage' OR service LIKE 'S3%%')"
                        " AND (resource_name LIKE '%%S3%%' OR instance_type LIKE '%%S3%%')"
                        ")")
            elif s == "ebs":
                query += (" AND provider='AWS' AND ("
                        " (service='Storage' OR service LIKE 'EBS%%')"
                        " AND (resource_name LIKE '%%EBS%%' OR instance_type LIKE '%%EBS%%' OR sku LIKE '%%EBS%%')"
                        ")")
            elif s == "rds":
                query += (" AND provider='AWS' AND ("
                        " service LIKE 'Database%%'"
                        " OR resource_name LIKE '%%RDS%%'"
                        " OR resource_name LIKE '%%RDS Proxy%%'"
                        " OR instance_type LIKE 'db.%%'"
                        ")")
            else:
                query += " AND service LIKE %s"
                params.append(f"%{service}%")

        elif provider == "Azure":
            if s == "virtual machines":
                query += " AND provider='Azure' AND service='Virtual Machines'"
            elif s == "sql database":
                query += " AND provider='Azure' AND service='SQL Database'"
            elif s in ("cloud storage", "blob storage"):
                query += (" AND provider='Azure' AND service='Storage' AND ("
                        " LOWER(resource_name) LIKE %s OR LOWER(sku) LIKE %s OR LOWER(instance_type) LIKE %s)")
                like = "%blob%"
                params.extend([like, like, like])
            elif s == "disk storage":
                disk_keys = ["disk", "managed disk", "premium ssd", "standard ssd", "standard hdd", "ultra disk"]
                or_parts = []
                for _ in disk_keys:
                    or_parts += ["LOWER(resource_name) LIKE %s", "LOWER(sku) LIKE %s", "LOWER(instance_type) LIKE %s"]
                query += " AND provider='Azure' AND service='Storage' AND (" + " OR ".join(or_parts) + ")"
                for k in disk_keys:
                    lk = f"%{k}%"
                    params.extend([lk, lk, lk])
            else:
                query += " AND service LIKE %s"
                params.append(f"%{service}%")

        elif provider == "GCP":
            if s == "compute engine":
                query += " AND provider='GCP' AND service LIKE 'Compute Engine%%'"
            elif s == "cloud storage":
                query += " AND provider='GCP' AND service LIKE 'Cloud Storage%%'"
            elif s == "persistent disk":
                query += " AND provider='GCP' AND service LIKE 'Persistent Disk%%'"
            elif s == "cloud sql":
                query += " AND provider='GCP' AND service LIKE 'Cloud SQL%%'"
            else:
                query += " AND service LIKE %s"
                params.append(f"%{service}%")

        else:
            
            query += " AND service LIKE %s"
            params.append(f"%{service}%")



    if filters["sku"]:
        query += " AND sku LIKE %s"
        params.append(f"%{filters['sku']}%")

    if filters["resource_name"]:
        query += " AND resource_name LIKE %s"
        params.append(f"%{filters['resource_name']}%")

    if filters["region"]:
        query += " AND region LIKE %s"
        params.append(f"%{filters['region']}%")


    if sort_by == 'provider':
        query += f" ORDER BY provider {order.upper()}, sku {order.upper()} LIMIT 3000"
    else:
        query += f" ORDER BY {sort_by} {order.upper()} LIMIT 3000"


    cursor.execute(query, params)
    result = cursor.fetchall()
    cursor.close()
    connection.close()
    return result


"""
Holt einen Preis-Datensatz anhand der ID aus der Datenbank
"""
def get_price_by_id(entry_id):
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT * FROM cloud_prices WHERE id = %s", (entry_id,))
    row = cursor.fetchone()

    cursor.close()
    connection.close()

    return row



if __name__ == "__main__":
    print(get_all_prices())



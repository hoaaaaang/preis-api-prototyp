import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os

load_dotenv()

host = os.getenv("DB_HOST")
user = os.getenv("DB_USER")

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
        return ModuleNotFoundError
    
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
        cursor.execute("""
            INSERT INTO cloud_prices
            (provider, service, sku, resource_name, region, price_per_unit, unit, currency)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            provider,
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
        SELECT provider, sku, region, price_per_unit, currency
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
def get_all_prices():
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
    return result

""" 
Entfernt doppelte Preiseinträge anhand von Provider, Service, SKU, Name, Region und Preis.
"""
def remove_duplicates(prices):
    seen = set()
    unique_prices = []
    for p in prices:
        key = (p["provider"], p["service"], p["sku"], p["resource_name"], p["region"], p["price_per_unit"])
        if key not in seen:
            seen.add(key)
            unique_prices.append(p)
    return unique_prices

""" 
Filtert die Preise nach bestimmten Kriterien (Provider, Service usw.) und sortiert die Ergebnisse.
"""
def get_filtered_prices(filters, sort_by=None, order='asc'):
    allowed_sort_fields = ['provider', 'service', 'sku', 'resource_name', 'region', 'price_per_unit']
    if sort_by not in allowed_sort_fields:
        sort_by = 'provider'
    if order not in ['asc', 'desc']:
        order = 'asc'

    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cursor = connection.cursor(dictionary=True)

    query = "SELECT * FROM cloud_prices WHERE 1=1"
    params = []

    if filters["provider"]:
        query += " AND provider LIKE %s"
        params.append(f"%{filters['provider']}%")

    if filters["service"]:
        query += " AND service LIKE %s"
        params.append(f"%{filters['service']}%")

    if filters["sku"]:
        query += " AND sku LIKE %s"
        params.append(f"%{filters['sku']}%")

    if filters["resource_name"]:
        query += " AND resource_name LIKE %s"
        params.append(f"%{filters['resource_name']}%")

    query += f" ORDER BY {sort_by} {order.upper()} LIMIT 100"

    cursor.execute(query, params)
    result = cursor.fetchall()
    cursor.close()
    connection.close()
    return result



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



from azure_client import get_azure_vm_prices
from aws_client import get_aws_prices
from gcp_client import get_gcp_prices
from db import insert_prices, select_all_prices
from update_timestamp import update_timestamp
from datetime import datetime
import time


# Startet das Logging für einen Provider: Gibt Startzeit aus und gibt Zeitstempel zurück.
def log_start(provider):
    now = datetime.now()
    print(f"[{now.strftime('%H:%M:%S')}] {provider} Preise abrufen...")
    return time.time(), now

# Beendet das Logging: Gibt Dauer und Anzahl der verarbeiteten Preise aus.
def log_end(start_time, provider, count):
    end_time = time.time()
    duration = end_time - start_time
    print(f"→ Dauer: {duration:.2f} Sekunden")
    print(f"Es wurden {count} {provider}-Preise gespeichert.\n")

# Hauptfunktion: Ruft nacheinander Azure-, AWS- und GCP-Preise ab, speichert sie und zeigt Infos an.
def main():
    # Azure
    start_az, _ = log_start("Azure")
    print("Azure Preise abrufen...")
    azure = get_azure_vm_prices()
    insert_prices(azure, provider="Azure")
    print(f"Es wurden {len(azure)} Azure-Preise gespeichert.\n")
    log_end(start_az, "Azure", len(azure))

    # AWS
    start_aws, _ = log_start("AWS")
    print("AWS Preise abrufen...")
    aws = get_aws_prices()
    insert_prices(aws, provider="AWS")
    print(f"Es wurden {len(aws)} AWS-Preise gespeichert.\n")
    log_end(start_aws, "AWS", len(aws))

    # GCP
    start_gcp, _ = log_start("GCP")
    print("GCP Preise abrufen...")
    gcp = get_gcp_prices()
    insert_prices(gcp, provider="GCP")
    print(f"Es wurden {len(gcp)} GCP-Preise gespeichert.\n")
    log_end(start_gcp, "GCP", len(gcp))

    update_timestamp()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Letzte Aktualisierung.")

if __name__ == "__main__":
    main()
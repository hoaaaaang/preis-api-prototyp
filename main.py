from db import insert_prices, select_all_prices, delete_provider_prices
from update_timestamp import update_timestamp
from datetime import datetime
import time
import threading
from pathlib import Path
import csv

# Azure: alle Dienste
from azure_client import (
    get_azure_vm_prices,
    get_azure_blob_prices,
    get_azure_disk_prices,
    get_azure_sql_prices,
)

# AWS: alle Dienste 
from aws_client import (
    get_aws_prices_ec2,          
    get_aws_prices_s3,
    get_aws_prices_ebs,
    get_aws_prices_rds,
)

# GCP: alle Dienste 
from gcp_client import ( 
    get_gcp_prices_compute_engine,
    get_gcp_prices_cloud_storage,
    get_gcp_prices_persistent_disk,
    get_gcp_prices_cloud_sql,
)


"""
Log-Datei für den Testlauf
"""
LOG_FILE = Path("logs/testlauf.csv")

def _append_row(start_dt: datetime, end_dt: datetime) -> None:
    """Schreibt eine Zeile: Iteration | Tag | Start | Ende | Dauer (Sek.)."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Header anlegen, falls Datei neu ist
    if not LOG_FILE.exists():
        with LOG_FILE.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(["Iteration", "Tag", "Start", "Ende", "Aktualisierungsdauer in Sekunden"])

    # Iteration = Anzahl Datenzeilen + 1
    with LOG_FILE.open("r", encoding="utf-8") as f:
        data_lines = max(0, sum(1 for _ in f) - 1)  # minus Header
    iteration = data_lines + 1

    duration = int((end_dt - start_dt).total_seconds())
    with LOG_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow([
            iteration,
            start_dt.strftime("%d.%m.%Y"),
            start_dt.strftime("%H:%M:%S"),
            end_dt.strftime("%H:%M:%S"),
            duration
        ])


"""
Startet das Logging für einen Provider: Gibt Startzeit aus und gibt Zeitstempel zurück.
"""
def log_start(provider):
    now = datetime.now()
    print(f"[{now.strftime('%H:%M:%S')}] {provider} Preise abrufen...")
    return time.time(), now


"""
Beendet das Logging: Gibt Dauer und Anzahl der verarbeiteten Preise aus.
"""
def log_end(start_time, provider, count):
    end_time = time.time()
    duration = end_time - start_time
    print(f"→ Dauer: {duration:.2f} Sekunden")
    print(f"Es wurden {count} {provider}-Preise gespeichert.\n")


"""
Hauptfunktion: Ruft Azure-, AWS- und GCP-Preise ab, speichert sie und zeigt Infos an.
"""
SERVICE_FUNCS = {
    "Azure": [
        ("Virtual Machines",            get_azure_vm_prices),
        ("Blob Storage",                get_azure_blob_prices),
        ("Disk Storage",                get_azure_disk_prices),
        ("SQL Database",                get_azure_sql_prices),
    ],
    "AWS": [
        ("EC2",                         get_aws_prices_ec2),
        ("S3",                          get_aws_prices_s3),
        ("EBS",                         get_aws_prices_ebs),
        ("RDS",                         get_aws_prices_rds),
    ],
    "GCP": [ 
        ("Compute Engine",              get_gcp_prices_compute_engine),
        ("Cloud Storage",               get_gcp_prices_cloud_storage),
        ("Persistent Disk",             get_gcp_prices_persistent_disk),
        ("Cloud SQL",                   get_gcp_prices_cloud_sql),
    ],
}


"""
Ruft alle Preisdaten für einen Anbieter ab und speichert sie in der Datenbank
"""
def process_provider(provider: str):
    start, _ = log_start(provider)

    all_rows = []
    for label, func in SERVICE_FUNCS[provider]:
        try:
            print(f"{provider}: {label} abrufen…")
            rows = func() or []
            print(f"{provider}: {label}: {len(rows)} Preise")
            all_rows.extend(rows)
        except Exception as e:
            print(f"{provider}: {label} FEHLER → {e}")

    if all_rows:
        insert_prices(all_rows, provider=provider)
    print(f"{provider}: Gesamt gespeichert: {len(all_rows)}")
    log_end(start, provider, len(all_rows))



"""
Führt den Update-Prozess aus und protokolliert Startzeit, Endzeit und Dauer
"""
def run_update():
    providers = ("Azure", "AWS", "GCP")
    threads = [threading.Thread(target=process_provider, args=(prov,)) for prov in providers]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    update_timestamp()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Letzte Aktualisierung.")


"""
Führt den Update-Prozess aus und protokolliert Startzeit, Endzeit und Dauer
"""
def run_with_logging():
    start = datetime.now()
    print(f"[{start.strftime('%H:%M:%S')}] Testlauf: Aktualisierung startet")
    run_update()
    end = datetime.now()
    _append_row(start, end)
    print(f"[{end.strftime('%H:%M:%S')}] Testlauf: Aktualisierung fertig – Dauer: {(end-start).total_seconds():.0f}s")



if __name__ == "__main__":
    run_with_logging()
    
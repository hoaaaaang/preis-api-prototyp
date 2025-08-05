import os
from datetime import datetime

""" 
Speichert den aktuellen Zeitpunkt in einer Datei namens 'last_updated.txt'.
Wird verwendet, um den Zeitpunkt der letzten Preisaktualisierung zu dokumentieren.
"""
def update_timestamp():
    base_path = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_path, "last_updated.txt")
    with open("last_updated.txt", "w") as f:
        f.write(datetime.now().strftime("%d.%m.%Y %H:%M:%S"))

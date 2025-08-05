from flask import Flask, render_template, request
from db import get_all_prices, get_filtered_prices, remove_duplicates
import threading
import time
import subprocess
from update_timestamp import update_timestamp
from flask import make_response
import csv
from io import StringIO
from fpdf import FPDF
import webbrowser
import threading


app = Flask(__name__)

""" 
Startseite der Anwendung. Zeigt gefilterte und sortierte Preisdaten an,
40 Ergebnisse pro Seite und Zeitpunkt der letzten Aktualisierung.
"""
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 40
    all_prices = get_all_prices()
    all_prices = remove_duplicates(all_prices)
    total = len(all_prices)
    start = (page - 1) * per_page
    end = start + per_page
    prices = all_prices[start:end]
    sort_by = request.args.get("sort_by", "provider")  # Standard: nach Anbieter
    order = request.args.get("order", "asc")           # Standard: aufsteigend
    filters = {
        "provider": request.args.get("provider", ""),
        "service": request.args.get("service", ""),
        "sku": request.args.get("sku", ""),
        "resource_name": request.args.get("resource", "")
    }
    prices = get_filtered_prices(filters, sort_by, order)  
    print("Gefundene Preise:", len(prices))
    last_updated = read_last_updated()
    return render_template('index.html', 
                           prices=prices, 
                           page=page, 
                           total_pages=(total + per_page - 1) // per_page,
                           last_updated=last_updated, 
                           request=request)

""" 
Öffnet automatisch den Standardbrowser beim Start.
"""
def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

""" 
Aktualisiert die Preisdaten stündlich.
"""
def refresh_data_periodically():
    while True:
        print("Datenaktualisierung wird gestartet...")
        subprocess.run(["python", "main.py"])
        update_timestamp()
        time.sleep(3600)  # 1 Stunde = 3600 Sekunden

""" 
Liest den letzten Aktualisierungszeitpunkt aus der Datei 'last_updated.txt'.
"""
def read_last_updated():
    try:
        with open("last_updated.txt", "r") as f:
            return f.read()
    except FileNotFoundError:
        return "unbekannt"
    
""" 
Erzeugt eine CSV-Datei mit den gefilterten Preisdaten und bietet sie zum Download an.
"""
@app.route('/download/csv')
def download_csv():
    sort_by = request.args.get("sort_by", "provider")
    order = request.args.get("order", "asc")
    filters = {
        "provider": request.args.get("provider", ""),
        "service": request.args.get("service", ""),
        "sku": request.args.get("sku", ""),
        "resource_name": request.args.get("resource", "")
    }
    prices = get_filtered_prices(filters, sort_by, order)

    si = StringIO()
    writer = csv.writer(si, delimiter=';')  # 👈 Semikolon für DE/Excel
    writer.writerow(["Anbieter", "Service", "SKU", "Resource Name", "Region", "Preis", "Einheit", "Währung"])

    for row in prices:
        writer.writerow([
            row["provider"],
            row["service"],
            row["sku"],
            row["resource_name"],
            row["region"],
            f'{row["price_per_unit"]:.6f}',  # 👈 Immer 6 Nachkommastellen
            row["unit"],
            row["currency"]
        ])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=Cloudpreise.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output



""" 
Erzeugt eine PDF-Datei mit den gefilterten Preisdaten und bietet sie zum Download an.
"""
@app.route('/download/pdf')
def download_pdf():
    sort_by = request.args.get("sort_by", "provider")
    order = request.args.get("order", "asc")
    filters = {
        "provider": request.args.get("provider", ""),
        "service": request.args.get("service", ""),
        "sku": request.args.get("sku", ""),
        "resource_name": request.args.get("resource", "")
    }
    prices = get_filtered_prices(filters, sort_by, order)

    pdf = FPDF(orientation='L', unit='mm', format='A4')  # Querformat
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=8)
    pdf.cell(0, 10, txt="Preisliste (gefiltert)", ln=True, align='C')
    pdf.ln(4)

    # Spaltenüberschriften & Breiten
    headers = ["Anbieter", "Service", "SKU", "Resource Name", "Region", "Preis", "Einheit", "Währung"]
    col_widths = [25, 30, 40, 40, 35, 20, 15, 15]

    # Kopfzeile
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 8, header, border=1)
    pdf.ln()

    # Inhalt
    for row in prices:
        values = [
            row["provider"],
            row["service"],
            row["sku"],
            row["resource_name"],
            row["region"],
            f'{row["price_per_unit"]:.6f}',
            row["unit"],
            row["currency"]
        ]
        for i, val in enumerate(values):
            text = str(val)
            if len(text) > 30:
                text = text[:27] + "…"  # abschneiden, damit nichts überlappt
            pdf.cell(col_widths[i], 8, text, border=1)
        pdf.ln()

    # PDF als HTTP-Response zurückgeben
    response = make_response(pdf.output(dest='S').encode('latin1'))
    response.headers["Content-Disposition"] = "attachment; filename=Cloudpreise.pdf"
    response.headers["Content-type"] = "application/pdf"
    return response


""" 
Öffnet ein neues Fenster, wo zwei Instanzen verglichen werden.
"""
@app.route('/compare')
def compare():
    ids = request.args.getlist('ids')
    if len(ids) != 2:
        return "Bitte genau zwei Einträge auswählen.", 400

    from db import get_price_by_id

    item1 = get_price_by_id(ids[0])
    item2 = get_price_by_id(ids[1])

    return render_template("compare.html", item1=item1, item2=item2)



""" 
Startet die Flask-App, öffnet den Browser und startet die Datenaktualisierung im Hintergrund.
"""
if __name__ == '__main__':
    threading.Timer(1.0, open_browser).start()
    app.run(debug=True)
    t = threading.Thread(target=refresh_data_periodically, daemon=True)
    t.start()
    app.run(debug=True)

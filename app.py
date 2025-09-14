from flask import Flask, render_template, request
from db import get_all_prices, get_filtered_prices, remove_duplicates, get_all_regions
import threading
import time
import subprocess
from update_timestamp import update_timestamp
from flask import make_response
import csv
from io import StringIO
from fpdf import FPDF
import webbrowser
import sys
from flask import abort
from db import get_price_by_id, get_filtered_prices
import re
import os

app = Flask(__name__)


""" 
Startseite der Anwendung. Zeigt gefilterte und sortierte Preisdaten an,
40100 Ergebnisse pro Seite und Zeitpunkt der letzten Aktualisierung.
"""
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 100
    regions = get_all_regions()
    sort_by = request.args.get("sort_by", "provider")  
    order = request.args.get("order", "asc")           
    filters = {
        "provider": request.args.get("provider", ""),        
        "q":        request.args.get("q", ""),               
        "service":  request.args.get("service", ""),
        "sku":      "",                                     
        "resource_name": "",                                  
        "instance_type": request.args.get("instance_type", ""),  
        "region":   request.args.get("region", "")
    }
    prices = get_filtered_prices(filters, sort_by, order)
    prices = remove_duplicates(prices)
    total  = len(prices)
    start  = (page - 1) * per_page
    end    = start + per_page
    prices = prices[start:end]
  
    print("Gefundene Preise:", len(prices))
    last_updated = read_last_updated()
    return render_template('index.html', 
                           prices=prices, 
                           page=page, 
                           total_pages=(total + per_page - 1) // per_page,
                           last_updated=last_updated, 
                           request=request,
                           regions=regions)


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
        subprocess.run([sys.executable, "main.py"])
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
Filterfunktion
"""
def build_filters(args):
    return {
        "provider":      args.get("provider", ""),
        "q":             args.get("q", ""),
        "service":       args.get("service", ""),
        "sku":           args.get("sku", ""),
        "resource_name": args.get("resource_name", ""),
        "resource":      args.get("resource", ""),         
        "instance_type": args.get("instance_type", ""),
        "region":        args.get("region", ""),
    }


"""
Die Funktion gibt den Basisdatensatz und eine Liste mit Basis + 4 besten 
Alternativen zurück, inkl. Preisunterschieden.
"""
def compute_alternatives(entry_id):
    base = get_price_by_id(entry_id)
    if not base:
        return None, []

    base_price = float(base.get("price_per_unit") or 0.0)
    region = (base.get("region") or "")
    region_prefix = (region.split("-")[0] + "-") if "-" in region else region

    filters = {
        "provider": base.get("provider", ""),
        "q": "",
        "service": base.get("service", ""),
        "sku": "",
        "resource_name": "",
        "resource": "",
        "instance_type": "",
        "region": "",
    }
    candidates = get_filtered_prices(filters, sort_by="price_per_unit", order="asc") or []

    cand_filtered = []
    for c in candidates:
        r = c.get("region") or ""
        if r == region or (region_prefix and r.startswith(region_prefix)):
            if c.get("id") != base.get("id"):
                cand_filtered.append(c)

    fam = _family_from_instance_type((base.get("resource_name") or "") + " " + (base.get("sku") or ""))
    scored = []
    for c in cand_filtered:
        c_price = float(c.get("price_per_unit") or 0.0)
        fam_c = _family_from_instance_type((c.get("resource_name") or "") + " " + (c.get("sku") or ""))
        fam_penalty = 0.0 if fam and fam_c == fam else 1.0
        price_dist = abs(c_price - base_price) / (base_price or 0.00001)
        score = fam_penalty + price_dist

        delta_abs = c_price - base_price
        delta_pct = (delta_abs / base_price * 100.0) if base_price else 0.0
        delta_dir = "down" if delta_abs < 0 else ("up" if delta_abs > 0 else "same")

        c2 = dict(c)
        c2.update(score=score, delta_abs=delta_abs, delta_pct=delta_pct, delta_dir=delta_dir)
        scored.append(c2)

    scored.sort(key=lambda x: (x["score"], float(x.get("price_per_unit") or 0.0)))

    items = scored[:4]
    base_row = dict(base)
    base_row.update(delta_abs=0.0, delta_pct=0.0, delta_dir="same", score=-1)
    items = [base_row] + items
    return base, items


"""
Versucht eine Instanz-Familie aus dem Namen zu extrahieren.
"""
def _family_from_instance_type(name: str) -> str:
    
    if not name:
        return ""
    # AWS: trenne bei Punkt
    if "." in name:
        return name.split(".")[0].strip()
    # Azure/GCP: nimm ersten Block
    return name.strip().split()[0]


""" 
Erzeugt eine CSV-Datei mit den gefilterten Preisdaten und bietet sie zum Download an.
"""
@app.route('/download/csv')
def download_csv():
    sort_by = request.args.get("sort_by", "provider")
    order = request.args.get("order", "asc")
    filters = build_filters(request.args)


    prices = get_filtered_prices(filters, sort_by, order)

    si = StringIO()
    writer = csv.writer(si, delimiter=';')  
    writer.writerow(["Anbieter", "Instance Type", "Service", "SKU", "Resource Name", "Region", "Preis", "Einheit", "Währung"])

    for row in prices:
        writer.writerow([
            row["provider"],
            row.get("instance_type", ""),
            row["service"],
            row["sku"],
            row["resource_name"],
            row["region"],
            f'{row["price_per_unit"]:.6f}',  
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
    filters = build_filters(request.args)
    prices = get_filtered_prices(filters, sort_by, order)

    pdf = FPDF(orientation='L', unit='mm', format='A4')  
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    font_path = os.path.join(app.root_path, "static", "fonts", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "", font_path, uni=True)
    pdf.set_font("DejaVu", "", 11)
    pdf.cell(0, 10, txt="Preisliste (gefiltert)", ln=True, align='C')
    pdf.ln(4)

    # Spaltenüberschriften 
    headers = ["Anbieter", "Instance Type", "Service", "SKU", "Resource Name", "Region", "Preis", "Einheit", "Währung"]
    col_widths = [25, 30, 30, 35, 80, 40, 25, 25, 20]  

    # Kopfzeile
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 8, header, border=1)
    pdf.ln()

    # Inhalt
    for row in prices:
        values = [
            row["provider"],
            row.get("instance_type", ""),
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
                text = text[:27] + "…"  
            pdf.cell(col_widths[i], 8, text, border=1)
        pdf.ln()

    # PDF als HTTP-Response zurückgeben  
    out = pdf.output(dest='S')  
    pdf_bytes = bytes(out) if isinstance(out, (bytearray, memoryview)) else out
    response = make_response(pdf_bytes)
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
Dieser Code zeigt für einen Eintrag alternative Cloud-Preise an und 
bietet die Möglichkeit, diese direkt als CSV oder PDF herunterzuladen.
"""
@app.route("/alternatives/<int:entry_id>")
def alternatives(entry_id):
    base, items = compute_alternatives(entry_id)
    if not base:
        abort(404)
    return render_template("alternatives.html", base=base, items=items)


def _latin(txt):
    if txt is None:
        return ""
    return str(txt).encode("latin-1", "replace").decode("latin-1")

@app.route("/alternatives/<int:entry_id>/export/<string:fmt>")
def export_alternatives(entry_id, fmt):
    base, items = compute_alternatives(entry_id)
    if not base:
        abort(404)

    columns = [
        ("provider", "Provider"),
        ("service", "Service"),
        ("region", "Region"),
        ("resource_name", "Resource / Instance"),
        ("sku", "SKU"),
        ("price_per_unit", "Preis/Std."),
        ("currency", "Währung"),
        ("delta_dir", "Δ Richtung"),
        ("delta_abs", "Δ absolut"),
        ("delta_pct", "Δ %"),
        ("score", "Score"),
    ]

    fmt = fmt.lower()
    if fmt == "csv":
        buf = StringIO()
        writer = csv.writer(buf, delimiter=";")
        writer.writerow([hdr for _, hdr in columns])
        for row in items:
            out = []
            for key, _ in columns:
                val = row.get(key, "")
                if isinstance(val, float):
                    val = f"{val:.6f}" if key != "delta_pct" else f"{val:.2f}%"
                out.append(val)
            writer.writerow(out)
        resp = make_response(buf.getvalue())
        resp.headers["Content-Type"] = "text/csv; charset=utf-8"
        resp.headers["Content-Disposition"] = f'attachment; filename="alternatives_{entry_id}.csv"'
        return resp

    if fmt == "pdf":
        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.add_page()
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, _latin(f"Alternativen – Eintrag #{entry_id}"), ln=1)
        pdf.set_font("Arial", "", 10)
        base_line = (
            f'Basis: {base.get("provider")} | {base.get("service")} | '
            f'{base.get("region")} | {base.get("resource_name")} | '
            f'SKU: {base.get("sku")} | Preis/Std.: {base.get("price_per_unit")} {base.get("currency")}'
        )
        pdf.multi_cell(0, 7, _latin(base_line))
        pdf.ln(2)

        # Kopfzeile
        pdf.set_font("Arial", "B", 10)
        col_widths = [35, 32, 28, 60, 28, 28, 20, 22, 25, 20, 18]
        for (_, hdr), w in zip(columns, col_widths):
            pdf.cell(w, 8, _latin(hdr), border=1)
        pdf.ln(8)

        # Zeilen
        pdf.set_font("Arial", "", 9)
        row_h = 7
        for row in items:
            cells = []
            for key, _ in columns:
                val = row.get(key, "")
                if isinstance(val, float):
                    val = f"{val:.6f}" if key != "delta_pct" else f"{val:.2f}%"
                cells.append(str(val))
            for text, w in zip(cells, col_widths):
                pdf.cell(w, row_h, _latin(text), border=1)
            pdf.ln(row_h)
            if pdf.get_y() > 190:  # einfacher Seitenumbruch
                pdf.add_page()
                pdf.set_font("Arial", "B", 10)
                for (_, hdr), w in zip(columns, col_widths):
                    pdf.cell(w, 8, _latin(hdr), border=1)
                pdf.ln(8)
                pdf.set_font("Arial", "", 9)

        out = pdf.output(dest="S")
        # fpdf2: bytearray/bytes | pyfpdf: str
        if isinstance(out, (bytes, bytearray)):
            pdf_bytes = bytes(out)
        else:
            pdf_bytes = out.encode("latin-1", "ignore")
        resp = make_response(pdf_bytes)
        resp.headers["Content-Type"] = "application/pdf"
        resp.headers["Content-Disposition"] = f'attachment; filename="alternatives_{entry_id}.pdf"'
        return resp

    abort(400)


""" 
Startet die Flask-App, öffnet den Browser und startet die Datenaktualisierung im Hintergrund.
"""
if __name__ == '__main__':
    threading.Timer(1.0, open_browser).start()
    app.run(debug=True)



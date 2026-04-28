from flask import Flask, render_template, request
import json
from flask import redirect
from datetime import datetime
import sqlite3

app = Flask(__name__)

# HOME PAGE (FORM)
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/invoice")
def invoice():
    number = get_next_number("invoice")
    fy = get_financial_year()
    invoice_no = f"A-{number}/{fy}"
    return render_template("index.html", invoice_no=invoice_no)

@app.route("/quotation")
def quotation():
    number = get_next_number("quotation")
    quotation_no = f"QTN-{number:04d}"
    return render_template("quotation.html", quotation_no=quotation_no)

def get_next_number(doc_type):
    fy = get_financial_year()

    with open("counter.json", "r") as file:
        data = json.load(file)

    if fy not in data[doc_type]:
        data[doc_type][fy] = 0

    data[doc_type][fy] += 1

    with open("counter.json", "w") as file:
        json.dump(data, file)

    return data[doc_type][fy]

from datetime import datetime

def get_financial_year():
    now = datetime.now()
    year = now.year
    month = now.month

    if month >= 4:  # April onwards
        start = year % 100
        end = (year + 1) % 100
    else:  # Jan–March
        start = (year - 1) % 100
        end = year % 100

    return f"{start:02d}-{end:02d}"
def number_to_words(n):
    ones = ["","one","two","three","four","five","six","seven","eight","nine",
            "ten","eleven","twelve","thirteen","fourteen","fifteen",
            "sixteen","seventeen","eighteen","nineteen"]

    tens = ["","","twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"]

    def convert(num):
        if num < 20:
            return ones[num]
        elif num < 100:
            return tens[num//10] + (" " + ones[num%10] if num%10 else "")
        elif num < 1000:
            return ones[num//100] + " hundred " + convert(num%100)
        elif num < 100000:
            return convert(num//1000) + " thousand " + convert(num%1000)
        else:
            return str(num)

    return convert(n)

# SAVE + PROCESS INVOICE
@app.route("/save", methods=["POST"])
def save():

    # BASIC DETAILS
    invoice_type = request.form.get("invoice_type")
    invoice_no = request.form.get("invoice_no")
    invoice_date_raw = request.form.get("invoice_date")
    state_main = request.form.get("state_main")
    stcd_main = request.form.get("stcd_main")
    DOS_raw = request.form.get("DOS")
    name1 = request.form.get("name1")
    address1 = request.form.get("address1")
    gstin1 = request.form.get("gstin1")
    state1 = request.form.get("state1")
    stcd1 = request.form.get("stcd1")
    invoice_date_db = invoice_date_raw   # already in YYYY-MM-DD
    invoice_date = datetime.strptime(invoice_date_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
    DOS = datetime.strptime(DOS_raw, "%Y-%m-%d").strftime("%d/%m/%Y") if DOS_raw else ""
    transportation = request.form.get("transportation")
    vehicle_no = request.form.get("vehicle_no")
    POS = request.form.get("POS")
    name2 = request.form.get("name2")
    address2 = request.form.get("address2")
    gstin2 = request.form.get("gstin2")
    state2 = request.form.get("state2")
    stcd2 = request.form.get("stcd2")
    aadhar = request.form.get("aadhar")


    # PRODUCT LIST
    products = []
    empty_rows = []

    total_amount = 0
    total_cgst = 0
    total_sgst = 0

    cgst_summary = {2.5: 0, 6: 0, 9: 0, 14: 0}
    sgst_summary = {2.5: 0, 6: 0, 9: 0, 14: 0}

    slno_counter = 1

    # CHANGE THIS NUMBER IF YOU HAVE MORE ROWS (like 23)
    for i in range(1, 23):

        product = request.form.get(f"product{i}") or ""
        hsn = request.form.get(f"hsn{i}") or ""
        qty = request.form.get(f"qty{i}")
        rate = request.form.get(f"rate{i}")
        crate = request.form.get(f"crate{i}")
        srate = request.form.get(f"srate{i}")

        # STORE ROW
        if product.strip() == "":
            products.append({
                "slno": "",
                "product": "",
                "hsn": "",
                "qty": "",
                "rate": "",
                "amount": "",
                "taxable": "",
                "crate": "",
                "cgst": "",
                "srate": "",
                "sgst": "",
                "total": "",
            })
            continue

            
        # CONVERT TO NUMBER SAFELY
        try:
            qty = float(qty) if qty else 0
            rate = float(rate) if rate else 0
            crate = float(crate) if crate else 0
            srate = float(srate) if srate else 0
        except:
            qty = 0
            rate = 0
            crate = 0
            srate = 0

        # CALCULATIONS
        amount = float(qty) * float(rate)
        taxable = float(amount)

        cgst = taxable * (float(crate)/100)
        sgst = taxable * (float(srate)/100)

        if crate in cgst_summary:
            cgst_summary[crate] += cgst

        if srate in sgst_summary:
            sgst_summary[srate] += sgst

        total = taxable + cgst + sgst

        # ADD TOTALS
        total_amount += amount
        total_cgst += cgst
        total_sgst += sgst

        products.append({
            "slno": slno_counter,
            "product": product,
            "hsn": hsn,
            "qty": qty,
            "rate": rate,
            "amount": round(amount, 2),
            "taxable": round(taxable, 2),
            "crate": crate,
            "cgst": round(cgst, 2),
            "srate": srate,
            "sgst": round(sgst, 2),
            "total": round(total, 2),
        })

        slno_counter += 1
    products.extend(empty_rows)

   
    # GRAND TOTAL
    total_taxable = total_amount
    total_gst = total_cgst + total_sgst
    grand_total = total_amount + total_cgst + total_sgst

    conn = sqlite3.connect("invoice.db")
    cursor = conn.cursor()

    # Save invoice
    cursor.execute("""
    INSERT INTO invoices (
        invoice_no, invoice_date, invoice_type,
        state_main, stcd_main,
        transportation, vehicle_no, DOS, POS,
        name1, address1, gstin1, state1, stcd1,
        name2, address2, gstin2, state2, stcd2,
        aadhar, total
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        invoice_no, invoice_date_db, invoice_type,
        state_main, stcd_main,
        transportation, vehicle_no, DOS, POS,
        name1, address1, gstin1, state1, stcd1,
        name2, address2, gstin2, state2, stcd2,
        aadhar, grand_total
    ))

    invoice_id = cursor.lastrowid  # 🔥 important

    # Save products
    for p in products:
            if p["product"]:  # skip empty rows
                cursor.execute("""
                INSERT INTO products (invoice_id, product, qty, rate, amount)
                VALUES (?, ?, ?, ?, ?)
                """, (
                    invoice_id,
                    p["product"],
                    p["qty"],
                    p["rate"],
                    p["amount"]
                ))

    conn.commit()
    conn.close()

    # SIMPLE AMOUNT IN WORDS
    words = number_to_words(int(grand_total))
    total_words = words + " rupees and GST included"

    # SEND TO RESULT PAGE
    return render_template(
        "result.html",
        invoice_type=invoice_type,
        invoice_no=invoice_no,
        invoice_date=invoice_date,
        state_main=state_main,
        stcd_main=stcd_main,
        DOS=DOS,
        name1=name1,
        address1=address1,
        gstin1=gstin1,
        state1=state1,
        stcd1=stcd1,
        products=products,
        total_amount=round(total_amount, 2),
        total_taxable=round(total_taxable, 2),
        total_cgst=round(total_cgst, 2),
        total_sgst=round(total_sgst, 2),
        grand_total=round(grand_total, 2),
        cgst_summary=cgst_summary,
        sgst_summary=sgst_summary,
        total_words=total_words,
        total_gst=round(total_gst, 2)
    )


@app.route("/save-quotation", methods=["POST"])
def save_quotation():

    invoice_type = request.form.get("invoice_type")
    state = request.form.get("state")
    quotation_no = request.form.get("quotation_no")
    quotation_date = request.form.get("quotation_date")
    name1 = request.form.get("name1")
    address1 = request.form.get("address1")
    gstin1 = request.form.get("gstin1")
    state1 = request.form.get("state1")
    stcd1 = request.form.get("stcd1")

    products = []

    total_amount = 0
    total_cgst = 0
    total_sgst = 0

    cgst_summary = {2.5: 0, 6: 0, 9: 0, 14: 0}
    sgst_summary = {2.5: 0, 6: 0, 9: 0, 14: 0}

    for i in range(1, 24):

        product = request.form.get(f"product{i}")
        hsn = request.form.get(f"hsn{i}")
        qty = request.form.get(f"qty{i}")
        rate = request.form.get(f"rate{i}")
        crate = request.form.get(f"crate{i}")
        srate = request.form.get(f"srate{i}")

        if not product or product.strip() == "":
            continue

        try:
            qty = float(qty)
            rate = float(rate)
            crate = float(crate) if crate else 0
            srate = float(srate) if srate else 0
        except:
            qty = rate = crate = srate = 0

        amount = qty * rate
        taxable = amount

        cgst = taxable * (crate/100)
        sgst = taxable * (srate/100)

        if crate in cgst_summary:
            cgst_summary[crate] += cgst

        if srate in sgst_summary:
            sgst_summary[srate] += sgst

        total = taxable + cgst + sgst

        total_amount += amount
        total_cgst += cgst
        total_sgst += sgst

        products.append({
            "slno": len(products) + 1,
            "product": product,
            "hsn": hsn,
            "qty": qty,
            "rate": rate,
            "amount": round(amount, 2),
            "taxable": round(taxable, 2),
            "crate": crate,
            "cgst": round(cgst, 2),
            "srate": srate,
            "sgst": round(sgst, 2),
            "total": round(total, 2)
        })

        total_taxable = total_amount
        return render_template(
            total_taxable=round(total_taxable, 2)
        )

    grand_total = total_amount + total_cgst + total_sgst
    total_gst = total_cgst + total_sgst
    words = number_to_words(int(grand_total))
    total_words = (words + " rupees and GST included").title()

    return render_template(
        "quotation_result.html",
        quotation_no=quotation_no,
        quotation_date=quotation_date,
        invoice_type=invoice_type,
        state=state,
        name1=name1,
        address1=address1,
        gstin1=gstin1,
        state1=state1,
        stcd1=stcd1,
        products=products,
        total_amount=round(total_amount, 2),
        total_cgst=round(total_cgst, 2),
        total_sgst=round(total_sgst, 2),
        total_gst=round(total_gst,2),
        grand_total=round(grand_total, 2),
        cgst_summary=cgst_summary,
        sgst_summary=sgst_summary,
        total_words=total_words
    )

def init_db():
    conn = sqlite3.connect("invoice.db")
    cursor = conn.cursor()

    # Invoice table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_no TEXT,
        invoice_date TEXT,
        invoice_type TEXT,
        state_main TEXT,
        stcd_main TEXT,
        transportation TEXT,
        vehicle_no TEXT,
        DOS TEXT,
        POS TEXT,
        name1 TEXT,
        address1 TEXT,
        gstin1 TEXT,
        state1 TEXT,
        stcd1 TEXT,
        name2 TEXT,
        address2 TEXT,
        gstin2 TEXT,
        state2 TEXT,
        stcd2 TEXT,
        aadhar TEXT,
        total REAL
    )
    """)

    # Products table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER,
        product TEXT,
        qty REAL,
        rate REAL,
        amount REAL
    )
    """)

    conn.commit()
    conn.close()

init_db()


@app.route("/dashboard")
def dashboard():
    conn = sqlite3.connect("invoice.db")
    cursor = conn.cursor()

    # 1. Total invoices
    cursor.execute("SELECT COUNT(*) FROM invoices")
    total_invoices = cursor.fetchone()[0]

    # 2. Total revenue
    cursor.execute("SELECT SUM(total) FROM invoices")
    total_revenue = cursor.fetchone()[0] or 0

    # 🔹 PER DAY (last 7 days)
    cursor.execute("""
        SELECT invoice_date, SUM(total)
        FROM invoices
        GROUP BY invoice_date
        ORDER BY invoice_date DESC
        LIMIT 7
    """)
    daily_data = cursor.fetchall()

     # 🔹 PER MONTH
    cursor.execute("""
        SELECT strftime('%Y-%m', invoice_date) as month, SUM(total)
        FROM invoices
        GROUP BY month
        ORDER BY month DESC
        LIMIT 6
    """)
    monthly_data = cursor.fetchall()

    # 🔹 PER YEAR
    cursor.execute("""
        SELECT strftime('%Y', invoice_date) as year, SUM(total)
        FROM invoices
        GROUP BY year
        ORDER BY year DESC
    """)
    yearly_data = cursor.fetchall()

    # 5. Top customers (Top 5)
    cursor.execute("""
        SELECT name1, SUM(total) as total_spent
        FROM invoices
        GROUP BY name1
        ORDER BY total_spent DESC
        LIMIT 5
    """)
    top_customers = cursor.fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        total_invoices=total_invoices,
        total_revenue=round(total_revenue, 2),
        daily_data=daily_data,
        monthly_data=monthly_data,
        yearly_data=yearly_data,
        top_customers=top_customers
    )


@app.route("/invoices")
def invoices():
    search = request.args.get("search")  # get search input

    conn = sqlite3.connect("invoice.db")
    cursor = conn.cursor()

    if search:
        cursor.execute("""
        SELECT * FROM invoices
        WHERE invoice_no LIKE ?
        OR name1 LIKE ?
        OR invoice_date LIKE ?
        ORDER BY id DESC
        """, (f"%{search}%", f"%{search}%", f"%{search}%"))
    else:
        cursor.execute("SELECT * FROM invoices ORDER BY id DESC")
    
    invoice_list = cursor.fetchall()
    conn.close()

    return render_template("invoices.html", invoices=invoice_list)

@app.route("/invoice/<int:id>")
def view_invoice(id):
    conn = sqlite3.connect("invoice.db")
    cursor = conn.cursor()

    # Get invoice
    cursor.execute("SELECT * FROM invoices WHERE id=?", (id,))
    invoice = cursor.fetchone()

    # Get products
    cursor.execute("SELECT * FROM products WHERE invoice_id=?", (id,))
    products_db = cursor.fetchall()

    conn.close()

    # 🔹 Convert DB products → your template format
    products = []

    total_amount = 0
    total_cgst = 0
    total_sgst = 0

    cgst_summary = {2.5: 0, 6: 0, 9: 0, 14: 0}
    sgst_summary = {2.5: 0, 6: 0, 9: 0, 14: 0}

    for i, p in enumerate(products_db, start=1):

        qty = p[3] or 0
        rate = p[4] or 0
        amount = p[5] or 0

        # Assume 9% + 9% GST (adjust if needed)
        crate = 9
        srate = 9

        taxable = amount
        cgst = taxable * (crate / 100)
        sgst = taxable * (srate / 100)
        total = taxable + cgst + sgst

        total_amount += amount
        total_cgst += cgst
        total_sgst += sgst

        cgst_summary[crate] += cgst
        sgst_summary[srate] += sgst

        products.append({
            "slno": i,
            "product": p[2],
            "hsn": "",
            "qty": qty,
            "rate": rate,
            "amount": amount,
            "taxable": amount,
            "crate": crate,
            "cgst": round(cgst, 2),
            "srate": srate,
            "sgst": round(sgst, 2),
            "total": round(total, 2),
        })

    total_taxable = total_amount
    total_gst = total_cgst + total_sgst
    grand_total = total_amount + total_gst

    # Amount in words
    words = number_to_words(int(grand_total))
    total_words = words + " rupees and GST included"

    return render_template(
        "result.html",
        invoice_type="",
        invoice_no=invoice[1],
        invoice_date=invoice[2],
        state_main="",
        stcd_main="",
        DOS="",
        name1=invoice[3],
        address1="",
        gstin1="",
        state1="",
        stcd1="",
        products=products,
        total_amount=round(total_amount, 2),
        total_taxable=round(total_taxable, 2),
        total_cgst=round(total_cgst, 2),
        total_sgst=round(total_sgst, 2),
        grand_total=round(grand_total, 2),
        cgst_summary=cgst_summary,
        sgst_summary=sgst_summary,
        total_words=total_words,
        total_gst=round(total_gst, 2)
    )

@app.route("/invoices")
def all_invoices():
    conn = sqlite3.connect("invoice.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM invoices ORDER BY id DESC")
    invoices = cursor.fetchall()

    conn.close()

    return render_template("invoices.html", invoices=invoices)

# RUN APP
if __name__ == "__main__":
    app.run(debug=True)
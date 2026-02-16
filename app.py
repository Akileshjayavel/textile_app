from flask import Flask, render_template, redirect, url_for, request, session,send_file
import sqlite3
import time
import json
from datetime import date, datetime
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics
from config import DB_PATH 

# ✅ BLUEPRINT IMPORTS (ONLY IMPORT, NO CREATION)
from modules.products import products_bp
from modules.admin_customers import admin_customers_bp
from modules.admin_reports import admin_reports_bp
from modules.reports import reports_bp


# BLUEPRINT
# from modules.products import products_bp

app = Flask(__name__)
app.secret_key = "textile_secret_key"
@app.route("/")
def index():
    return redirect(url_for("login"))


# DB_PATH = "database/billing.db" # MOVED TO CONFIG.PY

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session["role"] = user["role"]
            session["username"] = user["username"]

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("user_dashboard"))

        return render_template("auth/login.html", error="Invalid credentials")

    return render_template("auth/login.html")


# ---------------------------
# GLOBAL TEMPLATE VARIABLES
# ---------------------------

# ---------------------------
@app.route("/admin/dashboard")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM products WHERE is_active = 1")
    total_products = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM products
        WHERE stock <= low_stock_limit AND is_active = 1
    """)
    low_stock = cur.fetchone()[0]

    today = date.today().strftime("%Y-%m-%d")
    cur.execute("""
        SELECT COALESCE(SUM(total_amount), 0)
        FROM bills
        WHERE date(created_at) = ?
    """, (today,))
    today_sales = cur.fetchone()[0]

    conn.close()

    return render_template(
        "admin/dashboard.html",
        total_products=total_products,
        low_stock=low_stock,
        today_sales=today_sales
    )

# ---------------------------
# USER DASHBOARD
# ---------------------------
@app.route("/user/dashboard")
def user_dashboard():
    if session.get("role") != "user":
        return redirect(url_for("login"))

    conn = get_db_connection()
    bills = conn.execute("""
        SELECT * FROM bills
        ORDER BY created_at DESC
        LIMIT 50
    """).fetchall()
    conn.close()

    return render_template("user/dashboard.html", bills=bills)

# ---------------------------
# CUSTOMERS + PENDING
# ---------------------------
# ---------------------------
# CUSTOMERS (SEARCH + HISTORY + PENDING)
# ---------------------------
@app.route("/customers", methods=["GET", "POST"])
def customers():
    if session.get("role") not in ["admin", "user"]:
        return redirect(url_for("login"))

    conn = get_db_connection()

    customer = None
    bills = []
    pending_customers = []
    is_search = False
    error = None

    # ---------------------------
    # 🔍 SEARCH BY CUSTOMER MOBILE
    # ---------------------------
    if request.method == "POST":
        keyword = request.form.get("customer_mobile", "").strip()
        is_search = True

        customer = conn.execute("""
            SELECT *
            FROM customers
            WHERE REPLACE(mobile, ' ', '') = ?
        """, (keyword.replace(" ", ""),)).fetchone()

        if customer:
            bills = conn.execute("""
                SELECT *
                FROM bills
                WHERE customer_mobile = ?
                ORDER BY created_at DESC
            """, (customer["mobile"],)).fetchall()
        else:
            error = "Customer not found"

    # ---------------------------
    # 📋 DEFAULT VIEW: PENDING CUSTOMERS
    # ---------------------------
    if not is_search:
        pending_customers = conn.execute("""
    SELECT
    c.name,
    c.mobile,

    -- TOTAL BILLS
    COALESCE(SUM(b.total_amount), 0)

    -- MINUS BILLING-TIME PAYMENTS
    - COALESCE(SUM(b.cash_amount + b.paytm_amount), 0)

    -- MINUS LATER PAYMENTS
    - COALESCE((
        SELECT SUM(p.cash_amount + p.paytm_amount)
        FROM payments p
        WHERE p.customer_mobile = c.mobile
    ), 0)

    AS pending_amount

FROM customers c
LEFT JOIN bills b ON b.customer_mobile = c.mobile
GROUP BY c.mobile
HAVING pending_amount > 0
ORDER BY pending_amount DESC
                                         """).fetchall()

    conn.close()

    return render_template(
        "customers/customer_transactions.html",
        customer=customer,
        bills=bills,
        pending_customers=pending_customers,
        is_search=is_search,
        error=error
    )

    if request.method == "POST":keyword = request.form.get("customer_mobile", "").strip()
    is_search = True

    # 🔍 Find customer (NO pending condition)
    conn = get_db_connection()

    customer = conn.execute("""
        SELECT *
        FROM customers
        WHERE REPLACE(mobile, ' ', '') = ?
    """, (keyword.replace(" ", ""),)).fetchone()

    if customer:
        # 📜 Fetch ALL bills (full purchase history)
        bills = conn.execute("""
            SELECT *
            FROM bills
            WHERE customer_mobile = ?
            ORDER BY created_at DESC
        """, (customer["mobile"],)).fetchall()
    else:
        error = "Customer not found"



# ---------------------------
# CUSTOMER LEDGER
# ---------------------------
@app.route("/customers/ledger/<mobile>")
def customer_ledger(mobile):
    if session.get("role") not in ["admin", "user"]:
        return redirect(url_for("login"))

    conn = get_db_connection()

    customer = conn.execute(
        "SELECT * FROM customers WHERE mobile=?",
        (mobile,)
    ).fetchone()

    if not customer:
        conn.close()
        return redirect(url_for("customers"))

    # ---------------------------
    # BILLS (DEBIT)
    # ---------------------------
    bills = conn.execute("""
        SELECT
            created_at AS date,
            bill_no AS description,
            total_amount AS debit,
            0 AS credit,
            cash_amount,
            paytm_amount
        FROM bills
        WHERE customer_mobile=?
    """, (mobile,)).fetchall()

    entries = []

    for b in bills:
        # 🔴 FULL BILL AMOUNT (DEBIT)
        entries.append({
            "date": b["date"],
            "description": f"Bill {b['description']}",
            "debit": b["debit"],
            "credit": 0
        })

        # ✅ CASH / UPI RECEIVED AT BILLING (CREDIT)
        received = (b["cash_amount"] or 0) + (b["paytm_amount"] or 0)
        if received > 0:
            entries.append({
                "date": b["date"],
                "description": f"Payment (Billing) - {b['description']}",
                "debit": 0,
                "credit": received
            })

    # ---------------------------
    # PAYMENTS TABLE (CREDIT)
    # ---------------------------
    payments = conn.execute("""
        SELECT
            created_at AS date,
            'Payment Received' AS description,
            0 AS debit,
            (cash_amount + paytm_amount) AS credit
        FROM payments
        WHERE customer_mobile=?
    """, (mobile,)).fetchall() if table_exists(conn, "payments") else []

    entries.extend(payments)

    # ---------------------------
    # SORT + BALANCE
    # ---------------------------
    entries.sort(key=lambda x: x["date"])

    balance = 0
    ledger = []

    for e in entries:
        balance += e["debit"]
        balance -= e["credit"]

        ledger.append({
            "date": e["date"],
            "description": e["description"],
            "debit": e["debit"],
            "credit": e["credit"],
            "balance": round(balance, 2)
        })

    conn.close()

    return render_template(
        "customers/customer_ledger.html",
        customer=customer,
        ledger=ledger
    )

@app.route("/customers/receive-payment", methods=["POST"])
def receive_payment():
    if session.get("role") not in ["admin", "user"]:
        return redirect(url_for("login"))

    mobile = request.form["customer_mobile"]
    cash = float(request.form.get("cash_amount", 0))
    upi = float(request.form.get("paytm_amount", 0))
    received_amount = cash + upi

    if received_amount <= 0:
        return redirect(url_for("customers"))

    conn = get_db_connection()

    customer = conn.execute(
        "SELECT * FROM customers WHERE mobile=?",
        (mobile,)
    ).fetchone()

    if not customer:
        conn.close()
        return redirect(url_for("customers"))

    # ---------------------------
    # TOTAL BILLS
    # ---------------------------
    total_bills = conn.execute("""
        SELECT COALESCE(SUM(total_amount), 0)
        FROM bills
        WHERE customer_mobile = ?
    """, (mobile,)).fetchone()[0]

    # ---------------------------
    # TOTAL PAYMENTS ALREADY RECEIVED
    # ---------------------------
    total_paid = conn.execute("""
        SELECT COALESCE(SUM(cash_amount + paytm_amount), 0)
        FROM payments
        WHERE customer_mobile = ?
    """, (mobile,)).fetchone()[0]

    pending_amount = total_bills - total_paid

    # ---------------------------
    # ❌ VALIDATION: OVERPAYMENT
    # ---------------------------
    if received_amount > pending_amount:
        conn.close()
        return redirect(url_for("customer_ledger", mobile=mobile))

    # ---------------------------
    # SAVE PAYMENT
    # ---------------------------
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO payments
        (customer_mobile, cash_amount, paytm_amount, created_at)
        VALUES (?, ?, ?, datetime('now'))
    """, (mobile, cash, upi))

    payment_id = cursor.lastrowid

    conn.commit()
    conn.close()

    # ---------------------------
    # PRINT RECEIPT (IMPORTANT)
    # ---------------------------
    return redirect(url_for("print_payment", payment_id=payment_id))


@app.route("/payment/print/<int:payment_id>")
def print_payment(payment_id):
    if session.get("role") not in ["admin", "user"]:
        return redirect(url_for("login"))

    conn = get_db_connection()

    payment = conn.execute("""
        SELECT
            p.*,
            c.name AS customer_name,
            c.mobile AS customer_mobile
        FROM payments p
        JOIN customers c ON c.mobile = p.customer_mobile
        WHERE p.id = ?
    """, (payment_id,)).fetchone()

    if not payment:
        conn.close()
        return "Payment not found", 404

    # 🔢 TOTAL BILL AMOUNT
    total_bills = conn.execute("""
        SELECT COALESCE(SUM(total_amount), 0)
        FROM bills
        WHERE customer_mobile = ?
    """, (payment["customer_mobile"],)).fetchone()[0]

    # 🔢 TOTAL PAYMENTS (INCLUDING CURRENT)
    total_payments = conn.execute("""
        SELECT COALESCE(SUM(cash_amount + paytm_amount), 0)
        FROM payments
        WHERE customer_mobile = ?
    """, (payment["customer_mobile"],)).fetchone()[0]

    pending_amount = total_bills - total_payments

    conn.close()

    return render_template(
        "print/payment_receipt.html",
        payment=payment,
        pending_amount=pending_amount
    )
# ---------------------------
# BILL VIEW (FROM CUSTOMER HISTORY)
# ---------------------------
@app.route("/bill/view/<bill_no>")
def view_bill(bill_no):
    if session.get("role") not in ["admin", "user"]:
        return redirect(url_for("login"))

    conn = get_db_connection()

    bill = conn.execute(
        "SELECT * FROM bills WHERE bill_no = ?",
        (bill_no,)
    ).fetchone()

    if not bill:
        conn.close()
        return "Bill not found", 404

    items = conn.execute(
        "SELECT * FROM bill_items WHERE bill_id = ?",
        (bill["id"],)
    ).fetchall()

    customer = conn.execute(
        "SELECT * FROM customers WHERE mobile = ?",
        (bill["customer_mobile"],)
    ).fetchone()

    conn.close()

    return render_template(
        "customers/bill_view.html",
        bill=bill,
        items=items,
        customer=customer
    )


# ---------------------------
# USER BILLING (FIXED ADDRESS SAVE)
# ---------------------------
@app.route("/user/billing", methods=["GET", "POST"])
def user_billing():
    if session.get("role") != "user":
        return redirect(url_for("login"))

    conn = get_db_connection()

    if request.method == "POST":
        customer_name = request.form["customer_name"]
        customer_mobile = request.form["customer_mobile"].replace(" ", "")
        customer_address = request.form.get("customer_address", "")

        final_total = float(request.form["final_total"])
        items = json.loads(request.form["items_json"])

        cash_amount = float(request.form.get("cash_amount", 0))
        paytm_amount = float(request.form.get("paytm_amount", 0))

        existing_customer = conn.execute(
            "SELECT * FROM customers WHERE mobile=?",
            (customer_mobile,)
        ).fetchone()

        if not existing_customer:
            conn.execute("""
                INSERT INTO customers (name, mobile, address, created_at)
                VALUES (?, ?, ?, datetime('now'))
            """, (customer_name, customer_mobile, customer_address))

        bill_no = f"BILL-{int(time.time())}"
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO bills
            (bill_no, customer_mobile, total_amount, cash_amount, paytm_amount, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (
            bill_no,
            customer_mobile,
            final_total,
            cash_amount,
            paytm_amount
        ))

        bill_id = cursor.lastrowid

        for item in items:
            product = conn.execute(
                "SELECT * FROM products WHERE id=?",
                (item["id"],)
            ).fetchone()

            requested_qty = int(item["qty"])
            available_stock = int(product["stock"])

            if not product or requested_qty > available_stock:
                conn.close()
                error_msg = f"Stock issue (Available: {available_stock})"
                if request.form.get("is_ajax") == "1":
                    return {"success": False, "message": error_msg}
                return f"❌ {error_msg}"

            cursor.execute("""
                INSERT INTO bill_items
                (bill_id, product_name, quantity, price, subtotal)
                VALUES (?, ?, ?, ?, ?)
            """, (
                bill_id,
                product["name"],
                item["qty"],
                item["price"],
                item["qty"] * item["price"]
            ))

            cursor.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?",
                (requested_qty, item["id"])
            )

        conn.commit()
        conn.close()

        print_url = url_for("print_bill", bill_id=bill_id, auto=1)

        if request.form.get("is_ajax") == "1":
            return {"success": True, "bill_id": bill_id, "redirect_url": print_url}

        return redirect(print_url)

    products = conn.execute("""
    SELECT
        id,
        name,
        selling_price,
        stock
    FROM products
    WHERE is_active = 1 AND stock > 0
""").fetchall()

    customers = conn.execute("SELECT * FROM customers").fetchall()
    conn.close()

    return render_template(
        "user/billing.html",
        products=products,
        customers=customers
    )
# ---------------------------
# SALES REPORT (FINAL FIX)
# ---------------------------
# ---------------------------
# USER SALES REPORT PDF EXPORT
# ---------------------------

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from io import BytesIO
from datetime import datetime
import os


@app.route("/reports/export-pdf")
def export_pdf():

    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    # ---------------- DATABASE ----------------
    db = get_db_connection()

    rows = db.execute("""
        SELECT bill_no, created_at, cash_amount, paytm_amount,
               total_amount,
               (total_amount - (cash_amount + paytm_amount)) AS pending_amount
        FROM bills
        WHERE DATE(created_at) BETWEEN ? AND ?
        ORDER BY created_at DESC
    """, (from_date, to_date)).fetchall()

    total_bills = len(rows)
    cash_total = sum((r["cash_amount"] or 0) for r in rows)
    upi_total  = sum((r["paytm_amount"] or 0) for r in rows)
    total_sales = sum((r["total_amount"] or 0) for r in rows)
    pending_sales = sum((r["pending_amount"] or 0) for r in rows)

    payment_row = db.execute("""
        SELECT
            COALESCE(SUM(cash_amount),0) AS pending_cash,
            COALESCE(SUM(paytm_amount),0) AS pending_upi
        FROM payments
        WHERE DATE(created_at) BETWEEN ? AND ?
    """, (from_date, to_date)).fetchone()

    pending_cash = payment_row["pending_cash"] or 0
    pending_upi  = payment_row["pending_upi"] or 0
    pending_collected = pending_cash + pending_upi

    db.close()

    # ---------------- PDF ----------------
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []

    styles = getSampleStyleSheet()

    # Register Tamil Unicode font
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))

    # Styles
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontName="HYSMyeongJo-Medium",
        fontSize=11,
        leading=15
    )

    center_style = ParagraphStyle(
        'CenterStyle',
        parent=normal_style,
        alignment=1
    )

    title_style = ParagraphStyle(
        'TitleStyle',
        parent=normal_style,
        fontSize=18,
        alignment=1,
        spaceAfter=10
    )

    # -------- TITLE --------
    elements.append(Paragraph(
        "<b>SALES SUMMARY REPORT</b>",
        title_style
    ))

    # -------- REPORT PERIOD --------
    elements.append(Paragraph(
        f"<b>Report Period:</b> {from_date} to {to_date}",
        normal_style
    ))
    elements.append(Spacer(1, 4))

    # -------- GENERATED DATE --------
    elements.append(Paragraph(
        f"<b>Generated On:</b> {datetime.now().strftime('%d-%m-%Y')}",
        normal_style
    ))
    elements.append(Spacer(1, 15))

    # -------- SHOP HEADER --------
    shop_header = """
    <b>இரைமகள் ஜவுளி & ரெடிமேட்ஸ்</b><br/>
    #1 மும்பை பவன், ஆவட்டி கூட்ரோடு<br/>
    கல்லூர், கடலூர் மாவட்டம் - 606108<br/>
    Phone: +91 98406 48788, +91 95971 49615<br/>
    GSTIN: 33ABCDE1234Z5X
    """

    elements.append(Paragraph(shop_header, center_style))
    elements.append(Spacer(1, 8))

    # -------- Horizontal Line --------
    separator = Table([[""]], colWidths=[6.5 * inch])
    separator.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    elements.append(separator)
    elements.append(Spacer(1, 18))

    # -------- SUMMARY TABLE --------
    summary_data = [
        ["Total Bills", str(total_bills)],
        ["Total Sales", f"₹ {total_sales:.2f}"],
        ["Cash", f"₹ {cash_total:.2f}"],
        ["UPI", f"₹ {upi_total:.2f}"],
        ["Pending Sales", f"₹ {pending_sales:.2f}"],
        ["Pending Amount Received", f"₹ {pending_collected:.2f}"],
    ]

    summary_table = Table(summary_data, colWidths=[4.5*inch, 2*inch])

    summary_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 0.6, colors.black),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), "HYSMyeongJo-Medium"),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 40))

    elements.append(Paragraph(
        "Authorized Signature: __________________________",
        normal_style
    ))

    doc.build(elements)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="Sales_Report.pdf",
        mimetype="application/pdf"
    )


from datetime import date

from datetime import date
@app.route("/reports", methods=["GET", "POST"])
def reports():
    db = get_db_connection()

    selected_range = None
    rows = []

    # ===============================
    # DATE FILTER LOGIC
    # ===============================
    if request.method == "POST":
        date_range = request.form.get("date_range", "").strip()

        if " to " in date_range:
            from_date, to_date = date_range.split(" to ")
            selected_range = date_range

            rows = db.execute("""
                SELECT bill_no, created_at, cash_amount, paytm_amount,
                       (total_amount - (cash_amount + paytm_amount)) AS pending_amount
                FROM bills
                WHERE DATE(created_at) BETWEEN ? AND ?
                ORDER BY created_at DESC
            """, (from_date, to_date)).fetchall()

        elif date_range:
            selected_range = date_range

            rows = db.execute("""
                SELECT bill_no, created_at, cash_amount, paytm_amount,
                       (total_amount - (cash_amount + paytm_amount)) AS pending_amount
                FROM bills
                WHERE DATE(created_at) = ?
                ORDER BY created_at DESC
            """, (date_range,)).fetchall()

        else:
            rows = []

    else:
        selected_range = "Today"

        rows = db.execute("""
            SELECT bill_no, created_at, cash_amount, paytm_amount,
                   (total_amount - (cash_amount + paytm_amount)) AS pending_amount
            FROM bills
            WHERE DATE(created_at) = DATE('now')
            ORDER BY created_at DESC
        """).fetchall()

    # ===============================
    # KPI CALCULATIONS
    # ===============================
    total_bills = len(rows)

    bill_cash = sum((r["cash_amount"] or 0) for r in rows)
    bill_upi  = sum((r["paytm_amount"] or 0) for r in rows)

    # ===============================
    # DATE CONDITION
    # ===============================
    if selected_range == "Today":
        payment_where = "DATE(created_at) = DATE('now')"
        payment_params = ()

    elif " to " in (selected_range or ""):
        from_date, to_date = selected_range.split(" to ")
        payment_where = "DATE(created_at) BETWEEN ? AND ?"
        payment_params = (from_date, to_date)

    else:
        payment_where = "DATE(created_at) = ?"
        payment_params = (selected_range,)

    # ===============================
    # OLD PENDING COLLECTION (SAFE VERSION)
    # ===============================
    payment_row = db.execute(f"""
        SELECT
            COALESCE(SUM(p.cash_amount), 0) AS pending_cash,
            COALESCE(SUM(p.paytm_amount), 0) AS pending_upi
        FROM payments p
        WHERE {payment_where}
        AND EXISTS (
            SELECT 1
            FROM bills b
            WHERE b.customer_mobile = p.customer_mobile
            AND DATE(b.created_at) < DATE(p.created_at)
        )
    """, payment_params).fetchone()

    pending_cash = payment_row["pending_cash"] or 0
    pending_upi  = payment_row["pending_upi"] or 0

    # ===============================
    # FINAL VALUES
    # ===============================
    cash_total = bill_cash + pending_cash
    upi_total  = bill_upi  + pending_upi

    grand_total = cash_total + upi_total
    pending_total = sum((r["pending_amount"] or 0) for r in rows)

    old_pending_collected = pending_cash + pending_upi

    # ===============================
    # TOTAL SALES (VALUE OF GOODS SOLD)
    # ===============================
    sales_row = db.execute(f"""
        SELECT COALESCE(SUM(total_amount), 0) AS total_sales
        FROM bills
        WHERE {payment_where}
    """, payment_params).fetchone()

    total_sales = sales_row["total_sales"] or 0

    db.close()

    return render_template(
        "user/reports.html",
        rows=rows,
        selected_range=selected_range,
        total_bills=total_bills,
        total_sales=round(total_sales, 2),
        cash_total=round(cash_total, 2),
        upi_total=round(upi_total, 2),
        grand_total=round(grand_total, 2),
        pending_total=round(pending_total, 2),
        old_pending_collected=round(old_pending_collected, 2),
        now=datetime.now().strftime("%d-%b-%Y %I:%M %p")
    )


    # ===============================
    # ✅ EXISTING CALCULATIONS (UNCHANGED)
    # ===============================
    total_bills = len(rows)
    cash_total = sum((r["cash_amount"] or 0) for r in rows)
    upi_total = sum((r["paytm_amount"] or 0) for r in rows)
    grand_total = cash_total + upi_total
    pending_total = sum((r["pending_amount"] or 0) for r in rows)

    # ===============================
    # ✅ NEW: PROFESSIONAL RECONCILIATION
    # ===============================
    total_sales = grand_total + pending_total

    old_pending_collected = (cash_total + upi_total + pending_total) - total_sales

    reconciliation_error = False
    if old_pending_collected < 0:
        reconciliation_error = True
        old_pending_collected = 0

    db.close()

    return render_template(
        "user/reports.html",
        rows=rows,
        total_bills=total_bills,
        cash_total=cash_total,
        upi_total=upi_total,
        grand_total=grand_total,
        pending_total=pending_total,
        total_sales=total_sales,
        old_pending_collected=old_pending_collected,
        reconciliation_error=reconciliation_error,
        selected_range=selected_range
    )

@app.route("/bill/preview/<bill_no>")
def bill_preview(bill_no):
    db = get_db_connection()

    bill = db.execute("""
        SELECT * FROM bills WHERE bill_no = ?
    """, (bill_no,)).fetchone()

    items = db.execute("""
        SELECT * FROM bill_items WHERE bill_no = ?
    """, (bill_no,)).fetchall()

    db.close()

    if not bill:
        return "<p style='text-align:center;color:red'>Bill not found</p>"

    return render_template(
        "bill/receipt_preview.html",
        bill=bill,
        items=items
    )


def table_exists(conn, table_name):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cur.fetchone() is not None


@app.route("/bill/print/<int:bill_id>")
def print_bill(bill_id):
    auto = request.args.get("auto") == "1"
    db = get_db_connection()
    bill = db.execute(
        "SELECT * FROM bills WHERE id = ?", (bill_id,)
    ).fetchone()
    items = db.execute(
        "SELECT * FROM bill_items WHERE bill_id = ?", (bill_id,)
    ).fetchall()
    
    customer = None
    if bill and bill["customer_mobile"]:
        customer = db.execute(
            "SELECT * FROM customers WHERE mobile = ?", (bill["customer_mobile"],)
        ).fetchone()
        
    db.close()
    return render_template(
        "print/bill_print.html",
        bill=bill,
        items=items,
        customer=customer,
        auto=auto
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------
# REGISTER BLUEPRINTS
# ---------------------------
app.register_blueprint(products_bp)
app.register_blueprint(admin_customers_bp)
app.register_blueprint(admin_reports_bp)


if __name__ == "__main__":
    app.run(debug=True)

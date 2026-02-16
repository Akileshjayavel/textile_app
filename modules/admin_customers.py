from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file
)
import sqlite3
import pandas as pd
import io
from datetime import datetime
import sys
import os

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

# =============================
# BLUEPRINT
# =============================
admin_customers_bp = Blueprint(
    "admin_customers",
    __name__,
    url_prefix="/admin/customers"
)

# DB_PATHMOVED TO CONFIG

# =============================
# DB CONNECTION
# =============================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =============================
# LIST CUSTOMERS
# =============================
@admin_customers_bp.route("/")
def admin_customers():
    db = get_db()
    customers = db.execute("""
        SELECT id, name, mobile, address, created_at
        FROM customers
        ORDER BY created_at DESC
    """).fetchall()
    db.close()

    return render_template(
        "admin/customers.html",
        customers=customers
    )


# =============================
# CUSTOMER SUMMARY PAGE (FIXED)
# =============================
@admin_customers_bp.route("/<int:customer_id>")
def customer_summary_page(customer_id):
    db = get_db()

    # 1️⃣ CUSTOMER
    customer = db.execute(
        "SELECT * FROM customers WHERE id = ?",
        (customer_id,)
    ).fetchone()

    if not customer:
        db.close()
        return "Customer not found", 404

    customer_mobile = customer["mobile"]

    # 2️⃣ ALL BILLS
    bills = db.execute("""
        SELECT
            bill_no,
            bill_date_only,
            total_amount,
            cash_amount,
            paytm_amount,
            created_at
        FROM bills
        WHERE customer_mobile = ?
        ORDER BY created_at DESC
    """, (customer_mobile,)).fetchall()

    # 3️⃣ TOTAL BILL AMOUNT
    total_amount = sum(b["total_amount"] for b in bills)

    # 4️⃣ PAID AT BILL TIME
    paid_in_bills = sum(
        (b["cash_amount"] or 0) + (b["paytm_amount"] or 0)
        for b in bills
    )

    # 5️⃣ PAID VIA PAYMENTS TABLE
    payment_row = db.execute("""
        SELECT
            COALESCE(SUM(cash_amount + paytm_amount), 0) AS paid
        FROM payments
        WHERE customer_mobile = ?
    """, (customer_mobile,)).fetchone()

    paid_in_payments = payment_row["paid"] or 0

    # 6️⃣ FINAL PAID + PENDING
    paid_amount = paid_in_bills + paid_in_payments
    pending_amount = round(total_amount - paid_amount, 2)

    if pending_amount < 0:
        pending_amount = 0

    # 7️⃣ BILL STATUS (CURRENT PENDING ONLY)
    remaining_pending = pending_amount
    bill_list = []

    for b in bills:
        status = "Paid"

        if remaining_pending > 0:
            if remaining_pending >= b["total_amount"]:
                status = "Pending"
                remaining_pending -= b["total_amount"]
            else:
                status = "Pending"
                remaining_pending = 0

        bill_list.append({
            "bill_no": b["bill_no"],
            "date": b["bill_date_only"],
            "amount": b["total_amount"],
            "status": status
        })

    db.close()

    return render_template(
        "admin/customer_summary.html",
        customer=customer,
        bills=bill_list,
        total_amount=round(total_amount, 2),
        paid_amount=round(paid_amount, 2),
        pending_amount=round(pending_amount, 2)
    )


# =============================
# EDIT CUSTOMER
# =============================
@admin_customers_bp.route("/edit/<int:customer_id>", methods=["GET", "POST"])
def edit_customer(customer_id):
    db = get_db()

    if request.method == "POST":
        db.execute("""
            UPDATE customers
            SET name = ?, mobile = ?, address = ?
            WHERE id = ?
        """, (
            request.form["name"],
            request.form["mobile"],
            request.form.get("address"),
            customer_id
        ))
        db.commit()
        db.close()

        flash("Customer updated successfully", "success")
        return redirect(url_for("admin_customers.admin_customers"))

    customer = db.execute(
        "SELECT * FROM customers WHERE id = ?",
        (customer_id,)
    ).fetchone()
    db.close()

    if not customer:
        return "Customer not found", 404

    return render_template(
        "admin/edit_customer.html",
        customer=customer
    )


# =============================
# DELETE CUSTOMER
# =============================
@admin_customers_bp.route("/delete/<int:customer_id>", methods=["POST"])
def delete_customer(customer_id):
    db = get_db()
    db.execute(
        "DELETE FROM customers WHERE id = ?",
        (customer_id,)
    )
    db.commit()
    db.close()

    flash("Customer deleted", "warning")
    return redirect(url_for("admin_customers.admin_customers"))


# =============================
# DOWNLOAD ALL CUSTOMERS
# =============================
@admin_customers_bp.route("/download/all")
def download_all_customers():
    db = get_db()
    customers = db.execute("""
        SELECT name, mobile, address, created_at
        FROM customers
        ORDER BY created_at
    """).fetchall()
    db.close()

    df = pd.DataFrame(customers, columns=[
        "Name", "Mobile", "Address", "Created At"
    ])

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="all_customers.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# =============================
# DOWNLOAD NEW CUSTOMERS ONLY
# =============================
@admin_customers_bp.route("/download/new")
def download_new_customers():
    db = get_db()

    customers = db.execute("""
        SELECT id, name, mobile, address, created_at
        FROM customers
        WHERE id NOT IN (
            SELECT customer_id FROM exported_customers
        )
        ORDER BY created_at
    """).fetchall()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for c in customers:
        db.execute("""
            INSERT OR IGNORE INTO exported_customers (customer_id, exported_at)
            VALUES (?, ?)
        """, (c["id"], now))

    db.commit()
    db.close()

    df = pd.DataFrame(customers, columns=[
        "ID", "Name", "Mobile", "Address", "Created At"
    ])

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="new_customers.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


print("🔥 admin_customers blueprint loaded successfully")

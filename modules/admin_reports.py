from flask import Blueprint, render_template, session, request
import sqlite3
from datetime import datetime
from flask import Blueprint, render_template, session, request, redirect, url_for
# ... other imports like get_db

# ==========================================================
# ADMIN REPORTS BLUEPRINT 
# ==========================================================
admin_reports_bp = Blueprint(
    "admin_reports",
    __name__,
    url_prefix="/admin/reports"
)

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# =============================
# ADMIN REPORTS DASHBOARD
# =============================
@admin_reports_bp.route("/")
def admin_reports_dashboard():
    if session.get("role") != "admin":
        return "Unauthorized", 403

    start_date = request.args.get('start_date', datetime.now().strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    
    db = get_db()

    # KPI Data Logic
    report_data = db.execute("""
        SELECT 
            (SELECT COALESCE(SUM(total_amount), 0) FROM bills 
             WHERE DATE(created_at) BETWEEN ? AND ?) AS actual_revenue,
            (SELECT COALESCE(SUM(bi.quantity * bi.price), 0) 
             FROM bill_items bi JOIN bills b ON bi.bill_id = b.id 
             WHERE DATE(b.created_at) BETWEEN ? AND ?) AS gross_revenue,
            (SELECT COALESCE(SUM(bi.quantity * p.purchase_price), 0)
             FROM bill_items bi JOIN bills b ON bi.bill_id = b.id 
             JOIN products p ON p.name = bi.product_name
             WHERE DATE(b.created_at) BETWEEN ? AND ?) AS total_cost
    """, (start_date, end_date, start_date, end_date, start_date, end_date)).fetchone()

    total_sales = float(report_data["actual_revenue"] or 0)
    total_cost = float(report_data["total_cost"] or 0)
    gross_revenue = float(report_data["gross_revenue"] or 0)
    
    total_discount = gross_revenue - total_sales
    today_profit = total_sales - total_cost

    # Chart Logic
    is_multi_day = start_date != end_date
    sql_format = '%Y-%m-%d' if is_multi_day else '%H'

    chart_rows = db.execute(f"""
        SELECT strftime('{sql_format}', created_at) AS label, SUM(total_amount) AS amount
        FROM bills WHERE DATE(created_at) BETWEEN ? AND ?
        GROUP BY label ORDER BY label
    """, (start_date, end_date)).fetchall()

    chart_labels = [r['label'] + (":00" if not is_multi_day else "") for r in chart_rows]
    chart_values = [float(r["amount"] or 0) for r in chart_rows]

    # Table Data for Dashboard
    table_rows = db.execute("""
        SELECT id, bill_no, created_at as sale_date, total_amount, 
        (SELECT SUM(bi.quantity * bi.price) FROM bill_items bi WHERE bi.bill_id = bills.id) AS bill_gross,
        CASE WHEN (COALESCE(cash_amount, 0) + COALESCE(paytm_amount, 0)) < total_amount THEN 'Pending' ELSE 'Paid' END AS payment_status
        FROM bills WHERE DATE(created_at) BETWEEN ? AND ?
        ORDER BY created_at DESC
    """, (start_date, end_date)).fetchall()

    db.close()

    return render_template(
        "admin/reports.html",
        total_sales=round(total_sales, 2),
        total_cost=round(total_cost, 2),
        today_profit=round(today_profit, 2),
        total_discount=round(total_discount, 2),
        chart_labels=chart_labels,
        chart_values=chart_values,
        table_rows=table_rows,
        start_date=start_date,
        end_date=end_date
    )

# =============================
# NEW: STANDALONE PENDING PAGE
# =============================
from datetime import datetime

@admin_reports_bp.route("/pending")
def pending_payments():
    if session.get("role") != "admin":
        return "Unauthorized", 403

    db = get_db()
    
    # Using your specific logic: 
    # (Total Bills) - (Payments at Billing) - (Payments made Later)
    pending_rows = db.execute("""
        SELECT 
            c.name AS customer_name,
            c.mobile AS customer_mobile,
            COUNT(b.id) AS bill_count,
            (
                COALESCE(SUM(b.total_amount), 0) 
                - COALESCE(SUM(b.cash_amount + b.paytm_amount), 0)
                - COALESCE((
                    SELECT SUM(p.cash_amount + p.paytm_amount) 
                    FROM payments p 
                    WHERE p.customer_mobile = c.mobile
                ), 0)
            ) AS total_pending_amount
        FROM customers c
        LEFT JOIN bills b ON b.customer_mobile = c.mobile
        GROUP BY c.mobile, c.name
        HAVING total_pending_amount > 0
        ORDER BY total_pending_amount DESC
    """).fetchall()

    db.close()

    total_due = sum(row["total_pending_amount"] for row in pending_rows) if pending_rows else 0
    count_debtors = len(pending_rows)

    return render_template(
        "admin/pending.html", 
        table_rows=pending_rows, 
        total_due=round(total_due, 2),
        count_debtors=count_debtors
    )
@admin_reports_bp.route("/receive_payment", methods=["POST"])
def receive_payment():
    if session.get("role") not in ["admin", "user"]:
        return redirect(url_for("login"))

    mobile = request.form.get("mobile")
    
    # FIX: Get the value, if it's an empty string or None, use "0"
    raw_cash = request.form.get("cash_amount")
    raw_paytm = request.form.get("paytm_amount")
    
    try:
        cash = float(raw_cash) if raw_cash and raw_cash.strip() else 0.0
        paytm = float(raw_paytm) if raw_paytm and raw_paytm.strip() else 0.0
    except ValueError:
        # Fallback if someone types something that isn't a number
        cash = 0.0
        paytm = 0.0

    note = request.form.get("note", "Balance Settlement")

    if cash > 0 or paytm > 0:
        db = get_db()
        db.execute("""
            INSERT INTO payments (customer_mobile, cash_amount, paytm_amount, note, created_at)
            VALUES (?, ?, ?, ?, DATETIME('now', 'localtime'))
        """, (mobile, cash, paytm, note))
        db.commit()
        db.close()

    return redirect(url_for('admin_reports.pending_payments'))
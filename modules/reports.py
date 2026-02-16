from flask import Blueprint, render_template, session, redirect, url_for, send_file, request
import sqlite3
from datetime import date, datetime
from io import BytesIO
import os

# ReportLab Imports for PDF generation
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4

# =============================
# BLUEPRINT CONFIGURATION
# =============================
# Note: Using 'reports_bp' to avoid any conflict with 'admin_reports_bp'
reports_bp = Blueprint("reports", __name__, url_prefix="/admin/reports")

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------------------
# ADMIN DASHBOARD SUMMARY
# ---------------------------
@reports_bp.route("/dashboard")
def admin_dashboard_summary():
    # 🔐 ADMIN ACCESS ONLY
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db_connection()
    
    # 1. Total Products Count
    total_products = conn.execute("""
        SELECT COUNT(*) FROM products WHERE is_active = 1
    """).fetchone()[0]

    # 2. Low Stock Count
    low_stock = conn.execute("""
        SELECT COUNT(*) FROM products
        WHERE stock <= low_stock_limit AND is_active = 1
    """).fetchone()[0]

    # 3. Today's Total Sales
    today = date.today().strftime("%Y-%m-%d")
    today_sales = conn.execute("""
        SELECT COALESCE(SUM(total_amount), 0)
        FROM bills
        WHERE date(created_at) = ?
    """, (today,)).fetchone()[0]

    conn.close()

    return render_template(
        "admin/dashboard_summary.html",
        total_products=total_products,
        low_stock=low_stock,
        today_sales=round(float(today_sales), 2)
    )

# ---------------------------
# PROFESSIONAL SALES SUMMARY PDF
# ---------------------------
@reports_bp.route("/sales-summary-pdf")
def sales_summary_pdf():
    if session.get("role") != "admin":
        return "Unauthorized", 403

    conn = get_db_connection()

    # Data Aggregation for PDF
    total_bills = conn.execute("SELECT COUNT(*) FROM bills").fetchone()[0]
    total_sales = conn.execute("SELECT COALESCE(SUM(total_amount), 0) FROM bills").fetchone()[0]
    
    # Matching your schema for payments
    cash_total = conn.execute("SELECT COALESCE(SUM(cash_amount), 0) FROM bills").fetchone()[0]
    upi_total = conn.execute("SELECT COALESCE(SUM(paytm_amount), 0) FROM bills").fetchone()[0]
    
    # Calculate Pending (Total vs Collected)
    pending_sales = float(total_sales) - (float(cash_total) + float(upi_total))
    
    conn.close()

    # --- PDF GENERATION ---
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # Custom Styles
    title_style = ParagraphStyle(
        'TitleStyle', parent=styles['Heading1'],
        fontSize=22, spaceAfter=20, alignment=1 # Centered
    )
    normal_style = styles['Normal']

    # Header: Logo & Shop Info
    logo_path = "static/logo.png"
    if os.path.exists(logo_path):
        img = Image(logo_path, width=1.2*inch, height=1.2*inch)
        elements.append(img)
    
    elements.append(Paragraph("SALES SUMMARY REPORT", title_style))
    
    shop_info = """
    <b>Your Business Name</b><br/>
    123 Business Street, City, State<br/>
    Phone: +91 98765 43210 | Email: contact@shop.com
    """
    elements.append(Paragraph(shop_info, normal_style))
    elements.append(Spacer(1, 0.2*inch))
    elements.append(Paragraph(f"<b>Generated On:</b> {datetime.now().strftime('%d-%b-%Y %H:%M')}", normal_style))
    elements.append(Spacer(1, 0.3*inch))

    # Table Construction
    data = [
        ["Description", "Value"],
        ["Total Orders Processed", str(total_bills)],
        ["Gross Revenue", f"INR {total_sales:,.2f}"],
        ["Cash Collected", f"INR {cash_total:,.2f}"],
        ["UPI/PayTM Collected", f"INR {upi_total:,.2f}"],
        ["Outstanding (Pending)", f"INR {max(0, pending_sales):,.2f}"]
    ]

    report_table = Table(data, colWidths=[3.5*inch, 2*inch])
    report_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))

    elements.append(report_table)
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph("Authorized Signature: ______________________", normal_style))

    doc.build(elements)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Report_{date.today()}.pdf",
        mimetype='application/pdf'
    )
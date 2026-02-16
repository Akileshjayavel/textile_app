from flask import Blueprint, render_template, request, redirect, url_for, flash
import sqlite3
import sys
import os

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

products_bp = Blueprint("products", __name__, url_prefix="/admin/products")

from config import DB_PATH

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# -----------------------------
# PRODUCT LIST
# -----------------------------
@products_bp.route("/")
def products_list():
    db = get_db()
    products = db.execute("""
        SELECT *
        FROM products
        WHERE is_active = 1
        ORDER BY name
    """).fetchall()
    db.close()

    return render_template("admin/products.html", products=products)


# -----------------------------
# ADD PRODUCT
# -----------------------------
@products_bp.route("/add", methods=["GET", "POST"])
def add_product():
    if request.method == "POST":
        db = get_db()
        db.execute("""
            INSERT INTO products
            (name, category, purchase_price, selling_price, stock, low_stock_limit)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            request.form["name"],
            request.form.get("category"),
            request.form["purchase_price"],
            request.form["selling_price"],
            request.form["stock"],
            request.form.get("low_stock_limit", 5)
        ))
        db.commit()
        db.close()

        flash("Product added successfully", "success")
        return redirect(url_for("products.products_list"))

    # ✅ FIXED TEMPLATE NAME HERE
    return render_template("admin/add_products.html")


# -----------------------------
# EDIT PRODUCT
# -----------------------------
@products_bp.route("/edit/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    db = get_db()

    if request.method == "POST":
        db.execute("""
            UPDATE products
            SET
                name = ?,
                category = ?,
                purchase_price = ?,
                selling_price = ?,
                stock = ?,
                low_stock_limit = ?
            WHERE id = ?
        """, (
            request.form["name"],
            request.form.get("category"),
            request.form["purchase_price"],
            request.form["selling_price"],
            request.form["stock"],
            request.form.get("low_stock_limit", 5),
            product_id
        ))
        db.commit()
        db.close()

        flash("Product updated successfully", "success")
        return redirect(url_for("products.products_list"))

    product = db.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()
    db.close()

    if not product:
        return "Product not found", 404

    return render_template("admin/edit_product.html", product=product)


# -----------------------------
# DISABLE PRODUCT
# -----------------------------
@products_bp.route("/disable/<int:product_id>")
def disable_product(product_id):
    db = get_db()
    db.execute(
        "UPDATE products SET is_active = 0 WHERE id = ?",
        (product_id,)
    )
    db.commit()
    db.close()

    flash("Product disabled", "warning")
    return redirect(url_for("products.products_list"))

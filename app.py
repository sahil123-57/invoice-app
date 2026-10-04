import io
import json  # REDIS: to store the stats dictionary as text
from datetime import date
from decimal import Decimal

import redis  # REDIS: the client library
from flask import Flask, render_template, request, redirect, url_for, send_file, abort

from database import db, init_db, Customer, Item, Invoice, InvoiceLine

app = Flask(__name__)
init_db()

# REDIS: connection to the Redis server
cache = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True,       # get text back instead of bytes
    socket_connect_timeout=1,    # don't hang if Redis is not running
)


# open / close the database for every request
@app.before_request
def open_db():
    db.connect(reuse_if_open=True)


@app.teardown_request
def close_db(exc):
    if not db.is_closed():
        db.close()


# REDIS: after any POST (add / edit / delete), throw away the cached totals
@app.after_request
def clear_stats(response):
    if request.method == "POST":
        try:
            cache.delete("stats")
        except redis.RedisError:
            pass
    return response


def get_or_404(model, id):
    obj = model.get_or_none(model.id == id)
    if obj is None:
        abort(404)
    return obj


def next_number():
    n = (Invoice.select(Invoice.id).order_by(Invoice.id.desc()).scalar() or 0) + 1
    while Invoice.select().where(Invoice.number == f"INV-{n:04d}").exists():
        n += 1
    return f"INV-{n:04d}"


def save_lines(invoice):
    """Replace the invoice's lines with the rows submitted in the form."""
    InvoiceLine.delete().where(InvoiceLine.invoice == invoice).execute()
    rows = zip(
        request.form.getlist("description"),
        request.form.getlist("quantity"),
        request.form.getlist("price"),
    )
    for desc, qty, price in rows:
        if desc.strip():
            InvoiceLine.create(
                invoice=invoice,
                description=desc.strip(),
                quantity=int(qty or 1),
                price=Decimal(price or 0),
            )


# REDIS: dashboard totals, cached for 60 seconds
def get_stats():
    # 1. try Redis first
    try:
        cached = cache.get("stats")
        if cached:
            print("Dashboard loaded from REDIS")
            return json.loads(cached)
    except redis.RedisError:
        pass  # Redis is down, so use the database instead

    # 2. not in Redis, so calculate from the database
    print("Dashboard loaded from DATABASE")
    rows = list(Invoice.select())
    stats = {
        "count": len(rows),
        "paid_total": float(sum((i.total for i in rows if i.status == "Paid"), 0)),
        "unpaid_total": float(sum((i.total for i in rows if i.status != "Paid"), 0)),
    }

    # 3. save the result in Redis for next time (expires after 60 seconds)
    try:
        cache.set("stats", json.dumps(stats), ex=60)
    except redis.RedisError:
        pass
    return stats


# ---------- dashboard ----------
@app.route("/")
def index():
    recent = Invoice.select().order_by(Invoice.id.desc()).limit(5)
    return render_template("index.html", invoices=recent, **get_stats())


# ---------- customers ----------
@app.route("/customers")
def customers():
    rows = Customer.select().order_by(Customer.name)
    return render_template("customers.html", customers=rows)


@app.route("/customers/add", methods=["GET", "POST"])
def add_customer():
    if request.method == "POST":
        Customer.create(
            name=request.form["name"],
            email=request.form.get("email", ""),
            phone=request.form.get("phone", ""),
            address=request.form.get("address", ""),
        )
        return redirect(url_for("customers"))
    return render_template("customer_form.html", customer=None)


@app.route("/customers/<int:id>/edit", methods=["GET", "POST"])
def edit_customer(id):
    customer = get_or_404(Customer, id)
    if request.method == "POST":
        customer.name = request.form["name"]
        customer.email = request.form.get("email", "")
        customer.phone = request.form.get("phone", "")
        customer.address = request.form.get("address", "")
        customer.save()
        return redirect(url_for("customers"))
    return render_template("customer_form.html", customer=customer)


@app.route("/customers/<int:id>/delete", methods=["POST"])
def delete_customer(id):
    get_or_404(Customer, id).delete_instance()
    return redirect(url_for("customers"))


# ---------- items ----------
@app.route("/items")
def items():
    rows = Item.select().order_by(Item.name)
    return render_template("items.html", items=rows)


@app.route("/items/add", methods=["GET", "POST"])
def add_item():
    if request.method == "POST":
        Item.create(name=request.form["name"], price=Decimal(request.form.get("price") or 0))
        return redirect(url_for("items"))
    return render_template("item_form.html", item=None)


@app.route("/items/<int:id>/edit", methods=["GET", "POST"])
def edit_item(id):
    item = get_or_404(Item, id)
    if request.method == "POST":
        item.name = request.form["name"]
        item.price = Decimal(request.form.get("price") or 0)
        item.save()
        return redirect(url_for("items"))
    return render_template("item_form.html", item=item)


@app.route("/items/<int:id>/delete", methods=["POST"])
def delete_item(id):
    get_or_404(Item, id).delete_instance()
    return redirect(url_for("items"))


# ---------- invoices ----------
@app.route("/invoices")
def invoices():
    rows = Invoice.select().order_by(Invoice.id.desc())
    return render_template("invoices.html", invoices=rows)


@app.route("/invoices/add", methods=["GET", "POST"])
def add_invoice():
    if request.method == "POST":
        with db.atomic():
            invoice = Invoice.create(
                number=next_number(),
                customer=int(request.form["customer_id"]),
                date=date.fromisoformat(request.form["date"]),
                notes=request.form.get("notes", ""),
            )
            save_lines(invoice)
        return redirect(url_for("invoice_view", id=invoice.id))
    return render_template(
        "invoice_form.html",
        customers=Customer.select().order_by(Customer.name),
        items=Item.select().order_by(Item.name),
        today=date.today().isoformat(),
    )


@app.route("/invoices/<int:id>")
def invoice_view(id):
    return render_template("invoice_view.html", invoice=get_or_404(Invoice, id))


@app.route("/invoices/<int:id>/edit", methods=["GET", "POST"])
def edit_invoice(id):
    invoice = get_or_404(Invoice, id)
    if request.method == "POST":
        with db.atomic():
            invoice.customer = int(request.form["customer_id"])
            invoice.date = date.fromisoformat(request.form["date"])
            invoice.status = request.form.get("status", "Unpaid")
            invoice.notes = request.form.get("notes", "")
            invoice.save()
            save_lines(invoice)
        return redirect(url_for("invoice_view", id=invoice.id))
    return render_template(
        "invoice_edit.html",
        invoice=invoice,
        customers=Customer.select().order_by(Customer.name),
    )


@app.route("/invoices/<int:id>/delete", methods=["POST"])
def delete_invoice(id):
    get_or_404(Invoice, id).delete_instance()
    return redirect(url_for("invoices"))


@app.route("/invoices/<int:id>/pdf")
def invoice_pdf(id):
    from weasyprint import HTML  # imported here so the app still starts if WeasyPrint is missing

    invoice = get_or_404(Invoice, id)
    html = render_template("invoice_pdf.html", invoice=invoice)
    pdf = HTML(string=html).write_pdf()
    return send_file(
        io.BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{invoice.number}.pdf",
    )


if __name__ == "__main__":
    app.run(debug=True)
import datetime
import io
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from peewee import SqliteDatabase, Model, CharField, TextField, DecimalField, ForeignKeyField, DateField
from weasyprint import HTML

app = Flask(__name__)
db = SqliteDatabase('invoices.db')

class BaseModel(Model):
    class Meta:
        database = db

class Customer(BaseModel):
    name = CharField()            
    email = CharField(unique=True) 
    address = TextField()          

class Invoice(BaseModel):
    customer = ForeignKeyField(Customer, backref='invoices')       
    invoice_date = DateField(default=datetime.date.today)           
    due_date = DateField()                                          
    my_company_name = CharField(default="Your Company Name")        
    my_company_details = TextField(default="123 Business Street\nCity, State, Zip") 
    status = CharField(default="Balance Due")

class InvoiceItem(BaseModel):
    invoice = ForeignKeyField(Invoice, backref='items', on_delete='CASCADE') 
    description = CharField()                                                
    quantity = DecimalField(decimal_places=2, auto_round=True)               
    unit_price = DecimalField(decimal_places=2, auto_round=True)             

db.connect()
db.create_tables([Customer, Invoice, InvoiceItem])

# --- STANDALONE WEB PAGE SERVER ROUTES ---
@app.route('/')
@app.route('/customers')
@app.route('/customers/new')
@app.route('/invoices/new')
@app.route('/invoices/<int:invoice_id>')
def serve_spa_pages(**kwargs):
    # This acts as a single-page entry router. It sends our base index layout down,
    # and JavaScript Client-Side Rendering takes over the screen dynamically!
    return render_template('base.html')

# --- NEW: PURE JSON BACKEND API ENDPOINTS ---
@app.route('/api/invoices', methods=['GET'])
def api_get_invoices():
    invoices = Invoice.select()
    data = []
    for inv in invoices:
        data.append({
            "id": inv.id,
            "customer_name": inv.customer.name,
            "invoice_date": str(inv.invoice_date),
            "due_date": str(inv.due_date),
            "status": inv.status
        })
    return jsonify(data)

@app.route('/api/invoices/<int:invoice_id>', methods=['GET'])
def api_get_single_invoice(invoice_id):
    inv = Invoice.get_by_id(invoice_id)
    subtotal = sum(item.quantity * item.unit_price for item in inv.items)
    
    items_data = []
    for item in inv.items:
        items_data.append({
            "description": item.description,
            "quantity": float(item.quantity),
            "unit_price": float(item.unit_price),
            "total": float(item.quantity * item.unit_price)
        })
        
    return jsonify({
        "id": inv.id,
        "invoice_date": str(inv.invoice_date),
        "due_date": str(inv.due_date),
        "my_company_name": inv.my_company_name,
        "my_company_details": inv.my_company_details,
        "status": inv.status,
        "customer": {
            "name": inv.customer.name,
            "email": inv.customer.email,
            "address": inv.customer.address
        },
        "items": items_data,
        "subtotal": float(subtotal)
    })

@app.route('/api/invoices/<int:invoice_id>/toggle-status', methods=['POST'])
def api_toggle_status(invoice_id):
    inv = Invoice.get_by_id(invoice_id)
    inv.status = "Balance Due" if inv.status == "Paid" else "Paid"
    inv.save()
    return jsonify({"success": True, "new_status": inv.status})

@app.route('/invoices/<int:invoice_id>/download')
def invoice_pdf_download(invoice_id):
    inv = Invoice.get_by_id(invoice_id)
    subtotal = sum(item.quantity * item.unit_price for item in inv.items)
    rendered_html = render_template('invoice_pdf.html', invoice=inv, subtotal=subtotal)
    pdf_binary = HTML(string=rendered_html).write_pdf()
    pdf_stream = io.BytesIO(pdf_binary)
    pdf_stream.seek(0)
    return send_file(pdf_stream, mimetype='application/pdf', as_attachment=True, download_name=f"Invoice_{inv.id}.pdf")

if __name__ == '__main__':
    app.run(debug=True)

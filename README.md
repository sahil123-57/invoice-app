# Invoice App — Flask + SQLite + WeasyPrint

A CRUD invoicing app: manage Customers, Items, and Invoices, and download
any invoice as a real PDF.

## 1. How to run it

```bash
# 1. Go into the project folder
cd invoice_app

# 2. (Recommended) create a virtual environment
python3 -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. WeasyPrint needs some system libraries (it renders HTML/CSS itself,
#    it doesn't use a browser). On Ubuntu/Debian:
sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
                      libharfbuzz-subset0 libgdk-pixbuf2.0-0
#    On macOS:  brew install pango
#    On Windows: see https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows

# 5. Run the app
python app.py
```

Then open **http://127.0.0.1:5000** in your browser. A file called
`invoice_app.db` (SQLite database) is created automatically on first run.

## 2. Project structure

```
invoice_app/
├── app.py              # All Flask routes (URLs) + PDF generation logic
├── database.py          # SQLite table creation + connection helper
├── requirements.txt
├── templates/            # HTML pages, rendered with Jinja2
│   ├── base.html          # shared layout (navbar)
│   ├── index.html         # dashboard
│   ├── customers.html / customer_form.html
│   ├── items.html / item_form.html
│   ├── invoices.html / invoice_form.html / invoice_view.html
│   └── invoice_pdf.html   # standalone template used ONLY for the PDF
└── static/style.css      # all on-screen styling
```

## 3. How to explain this app in a viva/assignment review

**Q: What does CRUD mean here?**
Create/Read/Update/Delete on three entities: Customer, Item, Invoice.
Each has its own set of Flask routes following the same pattern:
`GET /thing` (list), `GET+POST /thing/add`, `GET+POST /thing/edit/<id>`,
`POST /thing/delete/<id>`.

**Q: Why SQLite and not a bigger database?**
SQLite stores the entire database as a single file, no server setup
needed — ideal for learning and small apps. The SQL you write
(`SELECT`, `INSERT`, `UPDATE`, `DELETE`) is exactly what you'd use on
PostgreSQL/MySQL too — SQLite is a real relational database, just
lightweight.

**Q: Why is there an `invoice_items` table instead of items linking
directly to invoices?**
Because an invoice needs to remember the quantity and price *at the
time it was billed*. If a customer's invoice shows "3 x Hosting @ ₹500"
and you later raise your hosting price to ₹700, old invoices must NOT
change. So `invoice_items` copies the name/price into its own row.

**Q: How does the PDF actually get generated?**
1. We fetch the invoice + its line items from SQLite.
2. We render `invoice_pdf.html` (a plain HTML template with inline
   CSS, including a `@page` rule for page size/margins) into an HTML
   *string* using Jinja2 — `render_template()`.
3. WeasyPrint's `HTML(string=...).write_pdf()` takes that HTML string
   and lays it out like a browser would, then outputs raw PDF bytes.
4. Flask sends those bytes back with `Content-Type: application/pdf`
   and a `Content-Disposition: attachment` header, which makes the
   browser download it as a file instead of just displaying it.

**Q: Why a separate `invoice_pdf.html` instead of reusing the on-screen
invoice page?**
The screen version has a navbar, "Download" button, edit links — none
of that belongs on a printed document. Keeping them separate means each
one can be styled for its actual purpose.

**Q: Why parameterized queries (`?` placeholders) instead of building
SQL strings with Python f-strings?**
To prevent **SQL injection** — if a customer's name contained something
like `'); DROP TABLE customers;--`, an f-string would let that text run
as real SQL. Placeholders make sure user input is always treated as
plain data, never as code.

**Q: How do dynamic invoice line items work (add/remove item rows)?**
Handled with a small bit of JavaScript in `invoice_form.html`. Every
row's inputs share the same `name="item_name[]"` etc. On submit, Flask
reads them all back as parallel Python lists via
`request.form.getlist()`, and `zip()` pairs them up row by row to
insert into `invoice_items`.

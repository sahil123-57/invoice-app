from datetime import date
from peewee import *

db = SqliteDatabase("invoices.db", pragmas={"foreign_keys": 1})


class BaseModel(Model):
    class Meta:
        database = db


class Customer(BaseModel):
    name = CharField()
    email = CharField(default="")
    phone = CharField(default="")
    address = TextField(default="")


class Item(BaseModel):
    name = CharField()
    price = DecimalField(decimal_places=2, default=0)


class Invoice(BaseModel):
    number = CharField(unique=True)
    customer = ForeignKeyField(Customer, backref="invoices", on_delete="CASCADE")
    date = DateField(default=date.today)
    status = CharField(default="Unpaid")  # Unpaid / Paid
    notes = TextField(default="")

    @property
    def total(self):
        return sum((line.amount for line in self.lines), 0)


class InvoiceLine(BaseModel):
    invoice = ForeignKeyField(Invoice, backref="lines", on_delete="CASCADE")
    description = CharField()
    quantity = IntegerField(default=1)
    price = DecimalField(decimal_places=2, default=0)

    @property
    def amount(self):
        return self.quantity * self.price


def init_db():
    db.connect(reuse_if_open=True)
    db.create_tables([Customer, Item, Invoice, InvoiceLine])
    db.close()
from flask_login import UserMixin
from app import db
from datetime import datetime

class UserRole:
    MILK_SELLER = 'milk_seller'
    BIKE_MILK_SELLER = 'bike_milk_seller'
    DAIRY_HOLDER = 'dairy_holder'
    MILK_BUYER = 'milk_buyer'
    
    @classmethod
    def get_all_roles(cls):
        return [cls.MILK_SELLER, cls.BIKE_MILK_SELLER, cls.DAIRY_HOLDER, cls.MILK_BUYER]

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(15))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships based on role
    milk_transactions = db.relationship('MilkTransaction', backref='user', lazy=True)
    delivery_transactions = db.relationship('DeliveryTransaction', backref='user', lazy=True)
    dairy_stocks = db.relationship('DairyStock', backref='user', lazy=True)
    purchase_transactions = db.relationship('PurchaseTransaction', backref='user', lazy=True)
    
    def is_milk_seller(self):
        return self.role == UserRole.MILK_SELLER
    
    def is_bike_milk_seller(self):
        return self.role == UserRole.BIKE_MILK_SELLER
    
    def is_dairy_holder(self):
        return self.role == UserRole.DAIRY_HOLDER
        
    def is_milk_buyer(self):
        return self.role == UserRole.MILK_BUYER 
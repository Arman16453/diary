from app import db
from datetime import datetime

# Define MilkQuality as a mixin class
class MilkQualityMixin:
    fat_percentage = db.Column(db.Float, nullable=False)
    snf_percentage = db.Column(db.Float, nullable=False)  # Solids-Not-Fat
    comments = db.Column(db.Text)

class MilkTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    buyer_type = db.Column(db.String(20), default='dairy_holder')  # 'dairy_holder' or 'bike_milk_seller'
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    quantity = db.Column(db.Float, nullable=False)  # in liters
    price_per_liter = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Milk quality metrics
    fat_percentage = db.Column(db.Float, nullable=False)
    snf_percentage = db.Column(db.Float, nullable=False)
    
    # Payment status
    is_paid = db.Column(db.Boolean, default=False)
    payment_date = db.Column(db.DateTime)
    
    def calculate_total(self):
        self.total_amount = self.quantity * self.price_per_liter
        return self.total_amount

class DeliveryTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bike_seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_address = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # in liters
    price_per_liter = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Payment status
    is_paid = db.Column(db.Boolean, default=False)
    payment_date = db.Column(db.DateTime)
    
    def calculate_total(self):
        self.total_amount = self.quantity * self.price_per_liter
        return self.total_amount

class PurchaseTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    supplier_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # in liters
    price_per_liter = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Milk quality metrics
    fat_percentage = db.Column(db.Float, nullable=False)
    snf_percentage = db.Column(db.Float, nullable=False)
    
    # Additional fields for milk buyers
    milk_type = db.Column(db.String(50))  # e.g., "Cow", "Buffalo", etc.
    source_location = db.Column(db.String(100))
    quality_grade = db.Column(db.String(20))  # e.g., "A", "B", "Premium"
    
    # Payment status
    is_paid = db.Column(db.Boolean, default=False)
    payment_date = db.Column(db.DateTime)
    
    def calculate_total(self):
        self.total_amount = self.quantity * self.price_per_liter
        return self.total_amount

class DairyStock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dairy_holder_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_stock = db.Column(db.Float, nullable=False)  # in liters
    date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Milk quality metrics (aggregate)
    avg_fat_percentage = db.Column(db.Float)
    avg_snf_percentage = db.Column(db.Float)
    
    # Stock movements
    stock_in = db.Column(db.Float, default=0.0)
    stock_out = db.Column(db.Float, default=0.0)
    
    def update_stock(self, amount, is_addition=True):
        if is_addition:
            self.stock_in += amount
            self.total_stock += amount
        else:
            self.stock_out += amount
            self.total_stock -= amount
        return self.total_stock

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 'Feed', 'Medicine', 'Equipment', 'Packaging', 'Other'
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)  # 'kg', 'g', 'l', 'ml', 'units', 'pcs'
    added_on = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime, nullable=True)
    restock_level = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    
    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        return self.expiry_date < datetime.utcnow()
    
    @property
    def is_low(self):
        return self.quantity <= self.restock_level
    
    @property
    def days_to_expiry(self):
        if not self.expiry_date:
            return None
        delta = self.expiry_date - datetime.utcnow()
        return max(0, delta.days)

class InventoryTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dairy_holder_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    supplier_name = db.Column(db.String(100), nullable=False)
    milk_type = db.Column(db.String(50), nullable=False)  # 'cow', 'buffalo', 'mixed'
    quantity = db.Column(db.Float, nullable=False)
    price_per_liter = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    fat_percentage = db.Column(db.Float, nullable=False)
    snf_percentage = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.Date, default=datetime.utcnow().date)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    is_paid = db.Column(db.Boolean, default=False)
    payment_date = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    # Relationship with dairy holder
    dairy_holder = db.relationship(
        'User',
        foreign_keys=[dairy_holder_id],
        backref=db.backref('inventory_transactions', lazy=True)
    )
    
    # Relationship with supplier
    supplier = db.relationship(
        'User',
        foreign_keys=[supplier_id],
        backref=db.backref('supplied_inventory', lazy=True)
    )
    
    def calculate_total(self):
        self.total_amount = self.quantity * self.price_per_liter
        return self.total_amount 
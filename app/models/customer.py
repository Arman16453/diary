from app import db
from datetime import datetime
from sqlalchemy.ext.declarative import declared_attr

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100))
    bike_seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    daily_quantity = db.Column(db.Float, default=0.0)  # Default daily milk requirement
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Use string name to avoid circular imports
    deliveries = db.relationship('DeliveryTransaction', 
                                foreign_keys='DeliveryTransaction.customer_id',
                                backref=db.backref('customer', lazy='joined'), 
                                lazy='dynamic')
    
    def __repr__(self):
        return f'<Customer {self.name} ({self.id})>' 
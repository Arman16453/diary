from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_login import current_user, login_required, logout_user
from app.models.user import UserRole
from app.models.user import User
from app.models.transaction import Transaction
from app.models.purchase_transaction import PurchaseTransaction
from app.models.delivery import Delivery
from app.models.customer import Customer
from app.models.inventory import Inventory
import sqlite3
from datetime import datetime, timedelta
from sqlalchemy import func
from app import db

main = Blueprint('main', __name__)

@main.route('/')
def index():
    # If user is logged in, redirect based on role
    if current_user.is_authenticated:
        # Check what roles are available and redirect to appropriate dashboard
        if current_user.is_milk_seller():
            return redirect(url_for('milk_seller.dashboard'))
        elif current_user.is_bike_milk_seller():
            return redirect(url_for('bike_milk_seller.dashboard'))
        elif current_user.is_dairy_holder():
            return redirect(url_for('dairy_holder.dashboard'))
        elif current_user.is_milk_buyer():
            return redirect(url_for('milk_buyer.dashboard'))
        else:
            # Unknown role - log them out
            flash('Unknown user role. Please contact administrator.', 'danger')
            logout_user()
            return redirect(url_for('auth.login'))
    
    # If not logged in, redirect to login page
    return redirect(url_for('auth.login'))

@main.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@main.route('/settings')
@login_required
def settings():
    return render_template('settings.html', user=current_user)

@main.route('/role-selection')
@login_required
def role_selection():
    stats = {}
    
    # Stats for Milk Seller
    if current_user.is_milk_seller():
        recent_transactions = Transaction.query.filter_by(seller_id=current_user.id).order_by(Transaction.date.desc()).limit(5).all()
        total_quantity = db.session.query(func.sum(Transaction.quantity)).filter_by(seller_id=current_user.id).scalar() or 0
        total_earnings = db.session.query(func.sum(Transaction.amount)).filter_by(seller_id=current_user.id).scalar() or 0
        pending_payment = db.session.query(func.sum(Transaction.amount)).filter_by(seller_id=current_user.id, is_paid=False).scalar() or 0
        
        stats['milk_seller'] = {
            'recent_transactions': recent_transactions,
            'total_quantity': round(total_quantity, 2),
            'total_earnings': round(total_earnings, 2),
            'pending_payment': round(pending_payment, 2)
        }
    
    # Stats for Bike Milk Seller
    if current_user.is_bike_milk_seller():
        customers_count = Customer.query.filter_by(bike_seller_id=current_user.id).count()
        active_customers = Customer.query.filter_by(bike_seller_id=current_user.id, is_active=True).count()
        
        # Handle both old and new delivery transactions
        # For transactions with customer_id (new format)
        total_deliveries_new = Delivery.query.filter_by(
            bike_seller_id=current_user.id
        ).filter(
            Delivery.customer_id.isnot(None)
        ).count()
        
        # For transactions without customer_id (old format)
        total_deliveries_old = Delivery.query.filter_by(
            bike_seller_id=current_user.id
        ).filter(
            Delivery.customer_id.is_(None)
        ).count()
        
        total_deliveries = total_deliveries_new + total_deliveries_old
        
        recent_deliveries = Delivery.query.filter_by(bike_seller_id=current_user.id) \
                               .order_by(Delivery.date.desc()) \
                               .limit(5).all()
        
        total_quantity = db.session.query(func.sum(Delivery.quantity)).filter_by(bike_seller_id=current_user.id).scalar() or 0
        total_earnings = db.session.query(func.sum(Delivery.total_amount)).filter_by(bike_seller_id=current_user.id).scalar() or 0
        
        # Get last 7 days' data
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        
        daily_data = []
        for i in range(7):
            day = week_ago + timedelta(days=i+1)
            day_deliveries = Delivery.query.filter(
                Delivery.bike_seller_id == current_user.id,
                func.date(Delivery.date) == day
            ).all()
            
            day_quantity = sum(d.quantity for d in day_deliveries)
            day_amount = sum(d.total_amount for d in day_deliveries)
            
            daily_data.append({
                'date': day.strftime('%d %b'),
                'quantity': round(day_quantity, 2),
                'amount': round(day_amount, 2),
                'deliveries': len(day_deliveries)
            })
        
        stats['bike_milk_seller'] = {
            'customers_count': customers_count,
            'active_customers': active_customers,
            'total_deliveries': total_deliveries,
            'recent_deliveries': recent_deliveries,
            'total_quantity': round(total_quantity, 2),
            'total_earnings': round(total_earnings, 2),
            'daily_data': daily_data
        }
    
    # Stats for Dairy Holder
    if current_user.is_dairy_holder():
        total_inventory = db.session.query(func.sum(Inventory.quantity)).filter_by(dairy_holder_id=current_user.id).scalar() or 0
        total_spent = db.session.query(func.sum(Inventory.amount)).filter_by(dairy_holder_id=current_user.id).scalar() or 0
        pending_payment = db.session.query(func.sum(Inventory.amount)).filter_by(dairy_holder_id=current_user.id, is_paid=False).scalar() or 0
        suppliers_count = db.session.query(func.count(func.distinct(Inventory.supplier_id))).filter_by(dairy_holder_id=current_user.id).scalar() or 0
        recent_inventory = Inventory.query.filter_by(dairy_holder_id=current_user.id).order_by(Inventory.date.desc()).limit(5).all()
        
        stats['dairy_holder'] = {
            'total_inventory': round(total_inventory, 2),
            'total_spent': round(total_spent, 2),
            'pending_payment': round(pending_payment, 2),
            'suppliers_count': suppliers_count,
            'recent_inventory': recent_inventory
        }
    
    # Stats for Milk Buyer
    if current_user.is_milk_buyer():
        total_purchased = db.session.query(func.sum(PurchaseTransaction.quantity)).filter_by(buyer_id=current_user.id).scalar() or 0
        total_spent = db.session.query(func.sum(PurchaseTransaction.amount)).filter_by(buyer_id=current_user.id).scalar() or 0
        pending_payment = db.session.query(func.sum(PurchaseTransaction.amount)).filter_by(buyer_id=current_user.id, is_paid=False).scalar() or 0
        suppliers_count = db.session.query(func.count(func.distinct(PurchaseTransaction.supplier_name))).filter_by(buyer_id=current_user.id).scalar() or 0
        recent_purchases = PurchaseTransaction.query.filter_by(buyer_id=current_user.id).order_by(PurchaseTransaction.date.desc()).limit(5).all()
        
        stats['milk_buyer'] = {
            'total_purchased': round(total_purchased, 2),
            'total_spent': round(total_spent, 2),
            'pending_payment': round(pending_payment, 2),
            'suppliers_count': suppliers_count,
            'recent_purchases': recent_purchases
        }
    
    return render_template('role_selection.html', stats=stats)

@main.route('/switch-role')
@login_required
def switch_role():
    # This is an alias for role_selection to handle template references
    return redirect(url_for('main.role_selection')) 
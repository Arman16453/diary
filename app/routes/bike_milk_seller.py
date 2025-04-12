from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models.transactions import DeliveryTransaction
from app.models.user import UserRole
from datetime import datetime, timedelta
from sqlalchemy import and_, or_

bike_milk_seller = Blueprint('bike_milk_seller', __name__)

def role_required(view_function):
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_bike_milk_seller():
            flash('Access denied: You must be a bike milk seller to view this page')
            return redirect(url_for('main.index'))
        return view_function(*args, **kwargs)
    decorated_function.__name__ = view_function.__name__
    return decorated_function

@bike_milk_seller.route('/dashboard')
@role_required
def dashboard():
    # Get recent deliveries
    deliveries = DeliveryTransaction.query.filter_by(bike_seller_id=current_user.id) \
                                     .order_by(DeliveryTransaction.date.desc()) \
                                     .limit(10).all()
    
    # Calculate statistics
    total_delivered = DeliveryTransaction.query.filter_by(bike_seller_id=current_user.id) \
                                       .with_entities(db.func.sum(DeliveryTransaction.quantity)).scalar() or 0
    
    total_earnings = DeliveryTransaction.query.filter_by(bike_seller_id=current_user.id) \
                                     .with_entities(db.func.sum(DeliveryTransaction.total_amount)).scalar() or 0
    
    pending_payment = DeliveryTransaction.query.filter_by(bike_seller_id=current_user.id, is_paid=False) \
                                     .with_entities(db.func.sum(DeliveryTransaction.total_amount)).scalar() or 0
    
    return render_template('bike_milk_seller/dashboard.html', 
                          deliveries=deliveries,
                          total_delivered=total_delivered,
                          total_earnings=total_earnings,
                          pending_payment=pending_payment)

@bike_milk_seller.route('/deliveries')
@role_required
def deliveries():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get filter parameters
    customer_name = request.args.get('customer_name', '')
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    payment_status = request.args.get('payment_status', '')
    
    # Build query with filters
    query = DeliveryTransaction.query.filter_by(bike_seller_id=current_user.id)
    
    if customer_name:
        query = query.filter(DeliveryTransaction.customer_name.ilike(f'%{customer_name}%'))
    
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        query = query.filter(DeliveryTransaction.date >= start_date)
    
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        # Add one day to include the end date fully
        end_date = end_date + timedelta(days=1)
        query = query.filter(DeliveryTransaction.date < end_date)
    
    if payment_status:
        if payment_status == 'paid':
            query = query.filter(DeliveryTransaction.is_paid == True)
        elif payment_status == 'pending':
            query = query.filter(DeliveryTransaction.is_paid == False)
    
    # Order and paginate results
    deliveries = query.order_by(DeliveryTransaction.date.desc()) \
                      .paginate(page=page, per_page=per_page)
    
    return render_template('bike_milk_seller/deliveries.html', deliveries=deliveries)

@bike_milk_seller.route('/add_delivery', methods=['GET', 'POST'])
@role_required
def add_delivery():
    if request.method == 'POST':
        customer_name = request.form.get('customer_name')
        customer_address = request.form.get('customer_address')
        quantity = float(request.form.get('quantity'))
        price_per_liter = float(request.form.get('price_per_liter'))
        
        # Create new delivery
        delivery = DeliveryTransaction(
            bike_seller_id=current_user.id,
            customer_name=customer_name,
            customer_address=customer_address,
            quantity=quantity,
            price_per_liter=price_per_liter,
            total_amount=quantity * price_per_liter,
            date=datetime.utcnow(),
            is_paid=False
        )
        
        db.session.add(delivery)
        db.session.commit()
        
        flash('Delivery added successfully!')
        return redirect(url_for('bike_milk_seller.deliveries'))
    
    # Check if customer data was provided in URL (from customer list)
    prefill_customer_name = request.args.get('customer_name', '')
    prefill_customer_address = request.args.get('customer_address', '')
    
    return render_template('bike_milk_seller/add_delivery.html',
                          customer_name=prefill_customer_name,
                          customer_address=prefill_customer_address)

@bike_milk_seller.route('/update_payment/<int:delivery_id>', methods=['POST'])
@role_required
def update_payment(delivery_id):
    delivery = DeliveryTransaction.query.get_or_404(delivery_id)
    
    # Ensure the delivery belongs to the current bike seller
    if delivery.bike_seller_id != current_user.id:
        flash('Access denied: This delivery does not belong to you')
        return redirect(url_for('bike_milk_seller.deliveries'))
    
    delivery.is_paid = True
    delivery.payment_date = datetime.utcnow()
    db.session.commit()
    
    flash('Payment status updated successfully!')
    return redirect(url_for('bike_milk_seller.deliveries'))

@bike_milk_seller.route('/customer_list')
@role_required
def customer_list():
    # Get unique customers from delivery transactions
    customers = db.session.query(
        DeliveryTransaction.customer_name,
        DeliveryTransaction.customer_address,
        db.func.sum(DeliveryTransaction.quantity).label('total_quantity'),
        db.func.count(DeliveryTransaction.id).label('delivery_count')
    ) \
    .filter_by(bike_seller_id=current_user.id) \
    .group_by(DeliveryTransaction.customer_name, DeliveryTransaction.customer_address) \
    .order_by(db.func.sum(DeliveryTransaction.quantity).desc()) \
    .all()
    
    return render_template('bike_milk_seller/customer_list.html', customers=customers) 
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models.transactions import PurchaseTransaction
from app.models.user import UserRole
from datetime import datetime, timedelta
from sqlalchemy import and_, or_

milk_buyer = Blueprint('milk_buyer', __name__)

def role_required(view_function):
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_milk_buyer():
            flash('Access denied: You must be a milk buyer to view this page')
            return redirect(url_for('main.index'))
        return view_function(*args, **kwargs)
    decorated_function.__name__ = view_function.__name__
    return decorated_function

@milk_buyer.route('/dashboard')
@role_required
def dashboard():
    # Get recent purchases
    purchases = PurchaseTransaction.query.filter_by(buyer_id=current_user.id) \
                                    .order_by(PurchaseTransaction.date.desc()) \
                                    .limit(10).all()
    
    # Calculate statistics
    total_purchased = PurchaseTransaction.query.filter_by(buyer_id=current_user.id) \
                                      .with_entities(db.func.sum(PurchaseTransaction.quantity)).scalar() or 0
    
    total_spent = PurchaseTransaction.query.filter_by(buyer_id=current_user.id) \
                                  .with_entities(db.func.sum(PurchaseTransaction.total_amount)).scalar() or 0
    
    pending_payment = PurchaseTransaction.query.filter_by(buyer_id=current_user.id, is_paid=False) \
                                     .with_entities(db.func.sum(PurchaseTransaction.total_amount)).scalar() or 0
    
    return render_template('milk_buyer/dashboard.html', 
                          purchases=purchases,
                          total_purchased=total_purchased,
                          total_spent=total_spent,
                          pending_payment=pending_payment)

@milk_buyer.route('/purchases')
@role_required
def purchases():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get filter parameters
    supplier_name = request.args.get('supplier_name', '')
    milk_type = request.args.get('milk_type', '')
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    payment_status = request.args.get('payment_status', '')
    
    # Build query with filters
    query = PurchaseTransaction.query.filter_by(buyer_id=current_user.id)
    
    if supplier_name:
        query = query.filter(PurchaseTransaction.supplier_name.ilike(f'%{supplier_name}%'))
    
    if milk_type:
        query = query.filter(PurchaseTransaction.milk_type == milk_type)
    
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        query = query.filter(PurchaseTransaction.date >= start_date)
    
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        # Add one day to include the end date fully
        end_date = end_date + timedelta(days=1)
        query = query.filter(PurchaseTransaction.date < end_date)
    
    if payment_status:
        if payment_status == 'paid':
            query = query.filter(PurchaseTransaction.is_paid == True)
        elif payment_status == 'pending':
            query = query.filter(PurchaseTransaction.is_paid == False)
    
    # Order and paginate results
    purchases = query.order_by(PurchaseTransaction.date.desc()) \
                     .paginate(page=page, per_page=per_page)
    
    return render_template('milk_buyer/purchases.html', purchases=purchases)

@milk_buyer.route('/add_purchase', methods=['GET', 'POST'])
@role_required
def add_purchase():
    if request.method == 'POST':
        supplier_name = request.form.get('supplier_name')
        quantity = float(request.form.get('quantity'))
        price_per_liter = float(request.form.get('price_per_liter'))
        fat_percentage = float(request.form.get('fat_percentage'))
        snf_percentage = float(request.form.get('snf_percentage'))
        milk_type = request.form.get('milk_type')
        source_location = request.form.get('source_location')
        quality_grade = request.form.get('quality_grade')
        
        # Create new purchase
        purchase = PurchaseTransaction(
            buyer_id=current_user.id,
            supplier_name=supplier_name,
            quantity=quantity,
            price_per_liter=price_per_liter,
            total_amount=quantity * price_per_liter,
            fat_percentage=fat_percentage,
            snf_percentage=snf_percentage,
            milk_type=milk_type,
            source_location=source_location,
            quality_grade=quality_grade,
            date=datetime.utcnow(),
            is_paid=False
        )
        
        db.session.add(purchase)
        db.session.commit()
        
        flash('Purchase added successfully!')
        return redirect(url_for('milk_buyer.purchases'))
    
    return render_template('milk_buyer/add_purchase.html')

@milk_buyer.route('/update_payment/<int:purchase_id>', methods=['POST'])
@role_required
def update_payment(purchase_id):
    purchase = PurchaseTransaction.query.get_or_404(purchase_id)
    
    # Ensure the purchase belongs to the current milk buyer
    if purchase.buyer_id != current_user.id:
        flash('Access denied: This purchase does not belong to you')
        return redirect(url_for('milk_buyer.purchases'))
    
    purchase.is_paid = True
    purchase.payment_date = datetime.utcnow()
    db.session.commit()
    
    flash('Payment status updated successfully!')
    return redirect(url_for('milk_buyer.purchases'))

@milk_buyer.route('/suppliers')
@role_required
def suppliers():
    # Get unique suppliers from purchase transactions
    suppliers = db.session.query(
        PurchaseTransaction.supplier_name,
        db.func.sum(PurchaseTransaction.quantity).label('total_quantity'),
        db.func.avg(PurchaseTransaction.fat_percentage).label('avg_fat'),
        db.func.avg(PurchaseTransaction.snf_percentage).label('avg_snf'),
        db.func.count(PurchaseTransaction.id).label('purchase_count')
    ) \
    .filter_by(buyer_id=current_user.id) \
    .group_by(PurchaseTransaction.supplier_name) \
    .order_by(db.func.sum(PurchaseTransaction.quantity).desc()) \
    .all()
    
    return render_template('milk_buyer/suppliers.html', suppliers=suppliers)

@milk_buyer.route('/reports')
@role_required
def reports():
    # Get date range from request
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date and end_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
        end_date = end_date + timedelta(days=1)  # Include the end date
        
        purchases = PurchaseTransaction.query.filter_by(buyer_id=current_user.id) \
                                        .filter(PurchaseTransaction.date >= start_date) \
                                        .filter(PurchaseTransaction.date < end_date) \
                                        .order_by(PurchaseTransaction.date.desc()) \
                                        .all()
    else:
        purchases = PurchaseTransaction.query.filter_by(buyer_id=current_user.id) \
                                        .order_by(PurchaseTransaction.date.desc()) \
                                        .all()
    
    # Generate report data
    milk_types = {}
    suppliers = {}
    daily_volumes = {}
    
    for purchase in purchases:
        # Summarize by milk type
        if purchase.milk_type in milk_types:
            milk_types[purchase.milk_type] += purchase.quantity
        else:
            milk_types[purchase.milk_type] = purchase.quantity
        
        # Summarize by supplier
        if purchase.supplier_name in suppliers:
            suppliers[purchase.supplier_name] += purchase.quantity
        else:
            suppliers[purchase.supplier_name] = purchase.quantity
        
        # Daily volumes
        date_str = purchase.date.strftime('%Y-%m-%d')
        if date_str in daily_volumes:
            daily_volumes[date_str] += purchase.quantity
        else:
            daily_volumes[date_str] = purchase.quantity
    
    return render_template('milk_buyer/reports.html', 
                          purchases=purchases,
                          milk_types=milk_types,
                          suppliers=suppliers,
                          daily_volumes=daily_volumes) 
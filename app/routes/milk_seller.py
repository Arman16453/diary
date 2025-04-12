from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models.transactions import MilkTransaction
from app.models.user import UserRole
from datetime import datetime

milk_seller = Blueprint('milk_seller', __name__)

def role_required(view_function):
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_milk_seller():
            flash('Access denied: You must be a milk seller to view this page')
            return redirect(url_for('main.index'))
        return view_function(*args, **kwargs)
    decorated_function.__name__ = view_function.__name__
    return decorated_function

@milk_seller.route('/dashboard')
@role_required
def dashboard():
    # Get recent transactions
    transactions = MilkTransaction.query.filter_by(seller_id=current_user.id) \
                                      .order_by(MilkTransaction.date.desc()) \
                                      .limit(10).all()
    
    # Calculate statistics
    total_milk = MilkTransaction.query.filter_by(seller_id=current_user.id) \
                                   .with_entities(db.func.sum(MilkTransaction.quantity)).scalar() or 0
    
    total_earnings = MilkTransaction.query.filter_by(seller_id=current_user.id) \
                                      .with_entities(db.func.sum(MilkTransaction.total_amount)).scalar() or 0
    
    pending_payment = MilkTransaction.query.filter_by(seller_id=current_user.id, is_paid=False) \
                                     .with_entities(db.func.sum(MilkTransaction.total_amount)).scalar() or 0
    
    return render_template('milk_seller/dashboard.html', 
                          transactions=transactions,
                          total_milk=total_milk,
                          total_earnings=total_earnings,
                          pending_payment=pending_payment)

@milk_seller.route('/transactions')
@role_required
def transactions():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    transactions = MilkTransaction.query.filter_by(seller_id=current_user.id) \
                                     .order_by(MilkTransaction.date.desc()) \
                                     .paginate(page=page, per_page=per_page)
    
    return render_template('milk_seller/transactions.html', transactions=transactions)

@milk_seller.route('/add_transaction', methods=['GET', 'POST'])
@role_required
def add_transaction():
    if request.method == 'POST':
        quantity = float(request.form.get('quantity'))
        price_per_liter = float(request.form.get('price_per_liter'))
        fat_percentage = float(request.form.get('fat_percentage'))
        snf_percentage = float(request.form.get('snf_percentage'))
        
        # Create new transaction
        transaction = MilkTransaction(
            seller_id=current_user.id,
            quantity=quantity,
            price_per_liter=price_per_liter,
            fat_percentage=fat_percentage,
            snf_percentage=snf_percentage,
            total_amount=quantity * price_per_liter,
            date=datetime.utcnow(),
            is_paid=False
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        flash('Transaction added successfully!')
        return redirect(url_for('milk_seller.transactions'))
    
    return render_template('milk_seller/add_transaction.html')

@milk_seller.route('/reports')
@role_required
def reports():
    # Get date range from request
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date and end_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
        
        transactions = MilkTransaction.query.filter_by(seller_id=current_user.id) \
                                        .filter(MilkTransaction.date >= start_date) \
                                        .filter(MilkTransaction.date <= end_date) \
                                        .order_by(MilkTransaction.date.desc()) \
                                        .all()
    else:
        transactions = MilkTransaction.query.filter_by(seller_id=current_user.id) \
                                        .order_by(MilkTransaction.date.desc()) \
                                        .all()
    
    return render_template('milk_seller/reports.html', transactions=transactions) 
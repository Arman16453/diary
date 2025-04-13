from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user, logout_user
from app import db
from app.models.transactions import MilkTransaction
from app.models.user import UserRole, User
from datetime import datetime, timedelta
from functools import wraps

milk_seller = Blueprint('milk_seller', __name__)

def role_required(view_function):
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
            
        if not current_user.is_milk_seller():
            flash('You must be a milk seller to access this page.', 'warning')
            return redirect(url_for('main.role_selection'))
            
        return view_function(*args, **kwargs)
    
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
    
    # Get monthly data for chart
    last_month = datetime.utcnow() - timedelta(days=30)
    monthly_data = MilkTransaction.query.filter_by(seller_id=current_user.id) \
                                    .filter(MilkTransaction.date >= last_month) \
                                    .order_by(MilkTransaction.date.asc()) \
                                    .all()
                                    
    # Format data for chart
    dates = []
    quantities = []
    for transaction in monthly_data:
        date_str = transaction.date.strftime('%d-%m-%Y')
        if date_str in dates:
            index = dates.index(date_str)
            quantities[index] += transaction.quantity
        else:
            dates.append(date_str)
            quantities.append(transaction.quantity)
    
    return render_template('milk_seller/dashboard.html', 
                          transactions=transactions,
                          total_milk=total_milk,
                          total_earnings=total_earnings,
                          pending_payment=pending_payment,
                          chart_dates=dates,
                          chart_quantities=quantities)

@milk_seller.route('/transactions')
@role_required
def transactions():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get filter parameters
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    payment_status = request.args.get('payment_status', '')
    
    # Build query with filters
    query = MilkTransaction.query.filter_by(seller_id=current_user.id)
    
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        query = query.filter(MilkTransaction.date >= start_date)
    
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        # Add one day to include the end date fully
        end_date = end_date + timedelta(days=1)
        query = query.filter(MilkTransaction.date < end_date)
    
    if payment_status:
        if payment_status == 'paid':
            query = query.filter(MilkTransaction.is_paid == True)
        elif payment_status == 'pending':
            query = query.filter(MilkTransaction.is_paid == False)
    
    # Order and paginate results
    transactions = query.order_by(MilkTransaction.date.desc()) \
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

@milk_seller.route('/sell_milk')
@role_required
def sell_milk():
    # Get available dairy holders
    dairy_holders = User.query.filter_by(role=UserRole.DAIRY_HOLDER).all()
    
    # Get available bike milk sellers
    bike_milk_sellers = User.query.filter_by(role=UserRole.BIKE_MILK_SELLER).all()
    
    return render_template('milk_seller/sell_milk.html', 
                          dairy_holders=dairy_holders,
                          bike_milk_sellers=bike_milk_sellers)

@milk_seller.route('/sell_to_dairy', methods=['GET', 'POST'])
@role_required
def sell_to_dairy():
    dairy_holder_id = request.args.get('dairy_holder_id')
    
    if request.method == 'POST':
        dairy_holder_id = request.form.get('dairy_holder_id')
        quantity = float(request.form.get('quantity'))
        price_per_liter = float(request.form.get('price_per_liter'))
        fat_percentage = float(request.form.get('fat_percentage'))
        snf_percentage = float(request.form.get('snf_percentage'))
        
        # Create new transaction
        transaction = MilkTransaction(
            seller_id=current_user.id,
            buyer_type='dairy_holder',
            buyer_id=dairy_holder_id,
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
        
        flash('Milk sold to dairy holder successfully!')
        return redirect(url_for('milk_seller.transactions'))
    
    dairy_holders = User.query.filter_by(role=UserRole.DAIRY_HOLDER).all()
    selected_dairy = User.query.get(dairy_holder_id) if dairy_holder_id else None
    
    return render_template('milk_seller/sell_to_dairy.html', 
                          dairy_holders=dairy_holders,
                          selected_dairy=selected_dairy)

@milk_seller.route('/sell_to_bike_seller', methods=['GET', 'POST'])
@role_required
def sell_to_bike_seller():
    bike_seller_id = request.args.get('bike_seller_id')
    
    if request.method == 'POST':
        bike_seller_id = request.form.get('bike_seller_id')
        quantity = float(request.form.get('quantity'))
        price_per_liter = float(request.form.get('price_per_liter'))
        fat_percentage = float(request.form.get('fat_percentage'))
        snf_percentage = float(request.form.get('snf_percentage'))
        
        # Create new transaction
        transaction = MilkTransaction(
            seller_id=current_user.id,
            buyer_type='bike_milk_seller',
            buyer_id=bike_seller_id,
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
        
        flash('Milk sold to bike milk seller successfully!')
        return redirect(url_for('milk_seller.transactions'))
    
    bike_sellers = User.query.filter_by(role=UserRole.BIKE_MILK_SELLER).all()
    selected_bike_seller = User.query.get(bike_seller_id) if bike_seller_id else None
    
    return render_template('milk_seller/sell_to_bike_seller.html', 
                          bike_sellers=bike_sellers,
                          selected_bike_seller=selected_bike_seller)

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
    
    # Prepare report data
    total_quantity = sum(t.quantity for t in transactions)
    total_amount = sum(t.total_amount for t in transactions)
    avg_fat = sum(t.fat_percentage for t in transactions) / len(transactions) if transactions else 0
    avg_snf = sum(t.snf_percentage for t in transactions) / len(transactions) if transactions else 0
    
    # Monthly data
    monthly_data = {}
    for trans in transactions:
        month_key = trans.date.strftime('%B %Y')
        if month_key in monthly_data:
            monthly_data[month_key]['quantity'] += trans.quantity
            monthly_data[month_key]['amount'] += trans.total_amount
        else:
            monthly_data[month_key] = {
                'quantity': trans.quantity,
                'amount': trans.total_amount
            }
    
    return render_template('milk_seller/reports.html', 
                          transactions=transactions,
                          total_quantity=total_quantity,
                          total_amount=total_amount,
                          avg_fat=avg_fat,
                          avg_snf=avg_snf,
                          monthly_data=monthly_data)

@milk_seller.route('/customers')
@role_required
def customers():
    # In a real app, this would get data from a customers table
    # For now, we'll simulate with dairy holder info
    dairy_holders = User.query.filter_by(role=UserRole.DAIRY_HOLDER).all()
    
    # Get transaction counts for each customer
    customer_data = []
    for customer in dairy_holders:
        # Count transactions where this customer might be involved
        # This is a simplification - in a real app you'd have a proper relationship
        transaction_count = MilkTransaction.query.filter_by(
            seller_id=current_user.id, is_paid=True
        ).count()
        
        customer_data.append({
            'customer': customer,
            'transaction_count': transaction_count,
            'last_transaction': datetime.utcnow() - timedelta(days=len(customer_data) + 1)
        })
    
    return render_template('milk_seller/customers.html', customers=customer_data, now=datetime.utcnow())

@milk_seller.route('/quality')
@role_required
def quality():
    # Get transaction quality data
    transactions = MilkTransaction.query.filter_by(seller_id=current_user.id) \
                                    .order_by(MilkTransaction.date.desc()) \
                                    .limit(30).all()
    
    # Calculate averages for quality metrics
    avg_fat = sum(t.fat_percentage for t in transactions) / len(transactions) if transactions else 0
    avg_snf = sum(t.snf_percentage for t in transactions) / len(transactions) if transactions else 0
    
    # Get quality trend data
    dates = [t.date.strftime('%d-%m-%Y') for t in transactions]
    fat_values = [t.fat_percentage for t in transactions]
    snf_values = [t.snf_percentage for t in transactions]
    
    return render_template('milk_seller/quality.html', 
                          transactions=transactions,
                          avg_fat=avg_fat,
                          avg_snf=avg_snf,
                          dates=dates,
                          fat_values=fat_values,
                          snf_values=snf_values)

@milk_seller.route('/analytics')
@role_required
def analytics():
    # Get all transaction data for analytics
    transactions = MilkTransaction.query.filter_by(seller_id=current_user.id).all()
    
    # Prepare analytics data
    monthly_income = {}
    quality_trend = {}
    payment_status = {'paid': 0, 'pending': 0}
    
    for transaction in transactions:
        # Monthly income
        month_key = transaction.date.strftime('%B %Y')
        if month_key in monthly_income:
            monthly_income[month_key]['quantity'] += transaction.quantity
            monthly_income[month_key]['amount'] += transaction.total_amount
        else:
            monthly_income[month_key] = {
                'quantity': transaction.quantity,
                'amount': transaction.total_amount
            }
        
        # Quality trend
        date_key = transaction.date.strftime('%Y-%m-%d')
        if date_key in quality_trend:
            quality_trend[date_key]['fat'] += transaction.fat_percentage
            quality_trend[date_key]['snf'] += transaction.snf_percentage
            quality_trend[date_key]['count'] += 1
        else:
            quality_trend[date_key] = {
                'fat': transaction.fat_percentage,
                'snf': transaction.snf_percentage,
                'count': 1
            }
        
        # Payment status
        if transaction.is_paid:
            payment_status['paid'] += transaction.total_amount
        else:
            payment_status['pending'] += transaction.total_amount
    
    # Calculate average quality for each date
    for date, data in quality_trend.items():
        data['avg_fat'] = data['fat'] / data['count']
        data['avg_snf'] = data['snf'] / data['count']
    
    # Calculate additional statistics needed by the template
    total_revenue = payment_status['paid'] + payment_status['pending']
    total_volume = sum(transaction.quantity for transaction in transactions)
    avg_price = total_revenue / total_volume if total_volume > 0 else 0
    pending_amount = payment_status['pending']
    paid_amount = payment_status['paid']
    paid_percentage = (paid_amount / total_revenue * 100) if total_revenue > 0 else 0
    
    # Calculate insights
    # Find best earning day
    daily_earnings = {}
    for transaction in transactions:
        date_str = transaction.date.strftime('%d %b %Y')
        if date_str in daily_earnings:
            daily_earnings[date_str] += transaction.total_amount
        else:
            daily_earnings[date_str] = transaction.total_amount
    
    best_day = max(daily_earnings.items(), key=lambda x: x[1])[0] if daily_earnings else 'N/A'
    best_day_amount = max(daily_earnings.values()) if daily_earnings else 0
    
    # Find highest price achieved
    highest_price = max([t.price_per_liter for t in transactions]) if transactions else 0
    highest_price_transaction = next((t for t in transactions if t.price_per_liter == highest_price), None)
    highest_price_date = highest_price_transaction.date.strftime('%d %b %Y') if highest_price_transaction else 'N/A'
    
    # Find most productive month
    monthly_volumes = {}
    for transaction in transactions:
        month_str = transaction.date.strftime('%b %Y')
        if month_str in monthly_volumes:
            monthly_volumes[month_str] += transaction.quantity
        else:
            monthly_volumes[month_str] = transaction.quantity
    
    best_month = max(monthly_volumes.items(), key=lambda x: x[1])[0] if monthly_volumes else 'N/A'
    best_month_volume = max(monthly_volumes.values()) if monthly_volumes else 0
    
    # Prepare monthly summary
    monthly_summary = []
    for month, data in sorted(monthly_income.items()):
        month_data = {
            'month_name': month,
            'volume': data['quantity'],
            'revenue': data['amount'],
            'avg_price': data['amount'] / data['quantity'] if data['quantity'] > 0 else 0,
        }
        
        # Calculate average quality metrics for this month
        month_fat_values = []
        month_snf_values = []
        month_start = None
        month_end = None
        
        # Parse the month string to get date range
        try:
            month_date = datetime.strptime(month, '%B %Y')
            month_start = month_date.replace(day=1)
            # Get last day of month
            next_month = month_date.replace(day=28) + timedelta(days=4)
            month_end = next_month - timedelta(days=next_month.day)
        except ValueError:
            # If parsing fails, skip quality metrics for this month
            month_data['avg_fat'] = 0
            month_data['avg_snf'] = 0
            monthly_summary.append(month_data)
            continue
        
        # Get all quality data points in this month
        for date_str, quality_data in quality_trend.items():
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d')
                if month_start <= date <= month_end:
                    month_fat_values.append(quality_data['avg_fat'])
                    month_snf_values.append(quality_data['avg_snf'])
            except ValueError:
                continue
        
        # Calculate averages for this month
        month_data['avg_fat'] = sum(month_fat_values) / len(month_fat_values) if month_fat_values else 0
        month_data['avg_snf'] = sum(month_snf_values) / len(month_snf_values) if month_snf_values else 0
        
        monthly_summary.append(month_data)
    
    # Prepare chart data
    monthly_labels = [month['month_name'] for month in monthly_summary]
    monthly_revenue = [month['revenue'] for month in monthly_summary]
    monthly_volume = [month['volume'] for month in monthly_summary]
    
    return render_template('milk_seller/analytics.html',
                          transactions=transactions,
                          monthly_income=monthly_income,
                          quality_trend=quality_trend,
                          payment_status=payment_status,
                          total_revenue=total_revenue,
                          total_volume=total_volume,
                          avg_price=avg_price,
                          pending_amount=pending_amount,
                          paid_amount=paid_amount,
                          paid_percentage=paid_percentage,
                          best_day=best_day,
                          best_day_amount=best_day_amount,
                          highest_price=highest_price,
                          highest_price_date=highest_price_date,
                          best_month=best_month,
                          best_month_volume=best_month_volume,
                          monthly_summary=monthly_summary,
                          monthly_labels=monthly_labels,
                          monthly_revenue=monthly_revenue,
                          monthly_volume=monthly_volume)

@milk_seller.route('/mark_paid/<int:transaction_id>', methods=['POST'])
@role_required
def mark_paid(transaction_id):
    transaction = MilkTransaction.query.get_or_404(transaction_id)
    
    # Ensure the transaction belongs to the current milk seller
    if transaction.seller_id != current_user.id:
        flash('Access denied: This transaction does not belong to you', 'danger')
        return redirect(url_for('milk_seller.transactions'))
    
    transaction.is_paid = True
    transaction.payment_date = datetime.utcnow()
    db.session.commit()
    
    flash('Transaction marked as paid successfully!', 'success')
    return redirect(url_for('milk_seller.transactions')) 
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user, logout_user
from app import db
from app.models.transactions import DeliveryTransaction, MilkTransaction
from app.models.user import UserRole, User
from app.models.customer import Customer
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func
from functools import wraps

bike_milk_seller = Blueprint('bike_milk_seller', __name__)

def role_required(view_function):
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
            
        if not current_user.is_bike_milk_seller():
            flash('You must be a bike milk seller to access this page.', 'warning')
            return redirect(url_for('main.role_selection'))
            
        return view_function(*args, **kwargs)
    
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
    
    # Get milk purchases (milk received from milk sellers)
    milk_purchases = MilkTransaction.query.filter_by(buyer_id=current_user.id, buyer_type='bike_milk_seller') \
                                    .order_by(MilkTransaction.date.desc()) \
                                    .limit(5).all()
    
    # Calculate total milk received
    total_milk_received = MilkTransaction.query.filter_by(buyer_id=current_user.id, buyer_type='bike_milk_seller') \
                                       .with_entities(db.func.sum(MilkTransaction.quantity)).scalar() or 0
    
    return render_template('bike_milk_seller/dashboard.html', 
                          deliveries=deliveries,
                          total_delivered=total_delivered,
                          total_earnings=total_earnings,
                          pending_payment=pending_payment,
                          milk_purchases=milk_purchases,
                          total_milk_received=total_milk_received)

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
    # Get customer_id from URL if provided
    customer_id = request.args.get('customer_id', None, type=int)
    customer = None
    
    if customer_id:
        customer = Customer.query.filter_by(id=customer_id, bike_seller_id=current_user.id).first()
    
    if request.method == 'POST':
        customer_id = request.form.get('customer_id', type=int)
        quantity = float(request.form.get('quantity'))
        price_per_liter = float(request.form.get('price_per_liter'))
        
        # Validate customer belongs to current bike seller
        customer = Customer.query.filter_by(id=customer_id, bike_seller_id=current_user.id).first()
        
        if not customer:
            flash('Invalid customer selection', 'danger')
            return redirect(url_for('bike_milk_seller.add_delivery'))
        
        # Create new delivery
        delivery = DeliveryTransaction(
            bike_seller_id=current_user.id,
            customer_id=customer.id,
            customer_name=customer.name,
            customer_address=customer.address,
            quantity=quantity,
            price_per_liter=price_per_liter,
            total_amount=quantity * price_per_liter,
            date=datetime.utcnow(),
            created_at=datetime.utcnow(),
            is_paid=False
        )
        
        db.session.add(delivery)
        db.session.commit()
        
        flash('Delivery added successfully!', 'success')
        return redirect(url_for('bike_milk_seller.deliveries'))
    
    # Get all customers for dropdown
    customers = Customer.query.filter_by(bike_seller_id=current_user.id, is_active=True).order_by(Customer.name).all()
    
    return render_template('bike_milk_seller/add_delivery.html',
                          customer=customer,
                          customers=customers)

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
    # Get all customers for the current bike seller
    query = Customer.query.filter_by(bike_seller_id=current_user.id)
    
    # Search functionality
    search_term = request.args.get('search', '')
    if search_term:
        query = query.filter(
            or_(
                Customer.name.ilike(f'%{search_term}%'),
                Customer.address.ilike(f'%{search_term}%'),
                Customer.phone.ilike(f'%{search_term}%')
            )
        )
    
    # Retrieve all matching customers
    all_customers = query.order_by(Customer.name).all()
    
    # Enrich customer data with delivery information
    for customer in all_customers:
        # Count deliveries for this customer using customer_id
        delivery_data = db.session.query(
            func.count(DeliveryTransaction.id).label('delivery_count'),
            func.sum(DeliveryTransaction.quantity).label('total_quantity'),
            func.sum(DeliveryTransaction.total_amount).label('total_amount')
        ).filter_by(
            bike_seller_id=current_user.id,
            customer_id=customer.id
        ).first()
        
        customer.delivery_count = delivery_data.delivery_count if delivery_data and delivery_data.delivery_count else 0
        customer.total_quantity = delivery_data.total_quantity if delivery_data and delivery_data.total_quantity else 0
        customer.total_amount = delivery_data.total_amount if delivery_data and delivery_data.total_amount else 0
    
    # Create a simple pagination object
    class Pagination:
        def __init__(self, items, page=1, per_page=10):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = len(items)
            self.pages = (self.total + self.per_page - 1) // self.per_page  # Ceiling division
            
            # Calculate start and end indices
            start = (page - 1) * per_page
            end = min(start + per_page, self.total)
            
            # Slice the items for the current page
            self.current_items = items[start:end]
            
            # Pagination navigation
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None
        
        def iter_pages(self):
            for i in range(1, self.pages + 1):
                yield i
    
    # Get page from request
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Create pagination object
    pagination = Pagination(all_customers, page=page, per_page=per_page)
    customers = pagination.current_items
    
    return render_template('bike_milk_seller/customer_list.html', customers=customers, pagination=pagination)

@bike_milk_seller.route('/milk_purchases')
@role_required
def milk_purchases():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get filter parameters
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    payment_status = request.args.get('payment_status', '')
    
    # Build query with filters
    query = MilkTransaction.query.filter_by(buyer_id=current_user.id, buyer_type='bike_milk_seller')
    
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
    purchases = query.order_by(MilkTransaction.date.desc()) \
                    .paginate(page=page, per_page=per_page)
    
    # Get milk sellers for the dropdown
    milk_sellers = User.query.filter_by(role=UserRole.MILK_SELLER).all()
    
    return render_template('bike_milk_seller/milk_purchases.html', 
                          purchases=purchases,
                          milk_sellers=milk_sellers)

@bike_milk_seller.route('/reports')
@role_required
def reports():
    # Get date range from request
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date and end_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
        
        deliveries = DeliveryTransaction.query.filter_by(bike_seller_id=current_user.id) \
                                         .filter(DeliveryTransaction.date >= start_date) \
                                         .filter(DeliveryTransaction.date <= end_date) \
                                         .order_by(DeliveryTransaction.date.desc()) \
                                         .all()
        
        milk_purchases = MilkTransaction.query.filter_by(buyer_id=current_user.id, buyer_type='bike_milk_seller') \
                                        .filter(MilkTransaction.date >= start_date) \
                                        .filter(MilkTransaction.date <= end_date) \
                                        .order_by(MilkTransaction.date.desc()) \
                                        .all()
    else:
        deliveries = DeliveryTransaction.query.filter_by(bike_seller_id=current_user.id) \
                                         .order_by(DeliveryTransaction.date.desc()) \
                                         .all()
        
        milk_purchases = MilkTransaction.query.filter_by(buyer_id=current_user.id, buyer_type='bike_milk_seller') \
                                        .order_by(MilkTransaction.date.desc()) \
                                        .all()
    
    # Prepare report data for deliveries
    total_delivered = sum(d.quantity for d in deliveries)
    total_sales = sum(d.total_amount for d in deliveries)
    
    # Prepare report data for purchases
    total_purchased = sum(p.quantity for p in milk_purchases)
    total_purchase_cost = sum(p.total_amount for p in milk_purchases)
    
    # Calculate profit/margin
    total_profit = total_sales - total_purchase_cost
    profit_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
    
    # Average quality of purchased milk
    avg_fat = sum(p.fat_percentage for p in milk_purchases) / len(milk_purchases) if milk_purchases else 0
    avg_snf = sum(p.snf_percentage for p in milk_purchases) / len(milk_purchases) if milk_purchases else 0
    
    # Monthly data
    monthly_data = {}
    for delivery in deliveries:
        month_key = delivery.date.strftime('%B %Y')
        if month_key in monthly_data:
            monthly_data[month_key]['delivered_quantity'] += delivery.quantity
            monthly_data[month_key]['sales_amount'] += delivery.total_amount
        else:
            monthly_data[month_key] = {
                'delivered_quantity': delivery.quantity,
                'sales_amount': delivery.total_amount,
                'purchase_quantity': 0,
                'purchase_amount': 0
            }
    
    for purchase in milk_purchases:
        month_key = purchase.date.strftime('%B %Y')
        if month_key in monthly_data:
            monthly_data[month_key]['purchase_quantity'] += purchase.quantity
            monthly_data[month_key]['purchase_amount'] += purchase.total_amount
        else:
            monthly_data[month_key] = {
                'delivered_quantity': 0,
                'sales_amount': 0,
                'purchase_quantity': purchase.quantity,
                'purchase_amount': purchase.total_amount
            }
    
    # Calculate profit for each month
    for month in monthly_data:
        monthly_data[month]['profit'] = monthly_data[month]['sales_amount'] - monthly_data[month]['purchase_amount']
    
    return render_template('bike_milk_seller/reports.html', 
                          deliveries=deliveries,
                          milk_purchases=milk_purchases,
                          total_delivered=total_delivered,
                          total_sales=total_sales,
                          total_purchased=total_purchased,
                          total_purchase_cost=total_purchase_cost,
                          total_profit=total_profit,
                          profit_margin=profit_margin,
                          avg_fat=avg_fat,
                          avg_snf=avg_snf,
                          monthly_data=monthly_data)

@bike_milk_seller.route('/quality')
@role_required
def quality():
    # Get milk purchase quality data
    purchases = MilkTransaction.query.filter_by(buyer_id=current_user.id, buyer_type='bike_milk_seller') \
                                  .order_by(MilkTransaction.date.desc()) \
                                  .limit(30).all()
    
    # Calculate averages for quality metrics
    avg_fat = sum(p.fat_percentage for p in purchases) / len(purchases) if purchases else 0
    avg_snf = sum(p.snf_percentage for p in purchases) / len(purchases) if purchases else 0
    
    # Get quality trend data
    dates = [p.date.strftime('%d-%m-%Y') for p in purchases]
    fat_values = [p.fat_percentage for p in purchases]
    snf_values = [p.snf_percentage for p in purchases]
    
    # Get quality data by milk seller
    seller_quality = {}
    
    for purchase in purchases:
        seller = User.query.get(purchase.seller_id)
        if seller:
            seller_name = seller.name
            if seller_name in seller_quality:
                seller_quality[seller_name]['fat_sum'] += purchase.fat_percentage
                seller_quality[seller_name]['snf_sum'] += purchase.snf_percentage
                seller_quality[seller_name]['count'] += 1
            else:
                seller_quality[seller_name] = {
                    'fat_sum': purchase.fat_percentage,
                    'snf_sum': purchase.snf_percentage,
                    'count': 1
                }
    
    # Calculate averages for each seller
    for seller in seller_quality:
        if seller_quality[seller]['count'] > 0:
            seller_quality[seller]['avg_fat'] = seller_quality[seller]['fat_sum'] / seller_quality[seller]['count']
            seller_quality[seller]['avg_snf'] = seller_quality[seller]['snf_sum'] / seller_quality[seller]['count']
    
    return render_template('bike_milk_seller/quality.html', 
                          purchases=purchases,
                          avg_fat=avg_fat,
                          avg_snf=avg_snf,
                          dates=dates,
                          fat_values=fat_values,
                          snf_values=snf_values,
                          seller_quality=seller_quality)

@bike_milk_seller.route('/analytics')
@role_required
def analytics():
    # Get all delivery and purchase data for analytics
    deliveries = DeliveryTransaction.query.filter_by(bike_seller_id=current_user.id).all()
    purchases = MilkTransaction.query.filter_by(buyer_id=current_user.id, buyer_type='bike_milk_seller').all()
    
    # Prepare analytics data
    monthly_sales = {}
    monthly_purchases = {}
    quality_trend = {}
    payment_status = {'paid': 0, 'pending': 0}
    customer_data = {}
    stock_balance = 0  # Current milk stock (purchased - delivered)
    
    # Process deliveries for analytics
    for delivery in deliveries:
        # Monthly sales
        month_key = delivery.date.strftime('%B %Y')
        if month_key in monthly_sales:
            monthly_sales[month_key]['quantity'] += delivery.quantity
            monthly_sales[month_key]['amount'] += delivery.total_amount
        else:
            monthly_sales[month_key] = {
                'quantity': delivery.quantity,
                'amount': delivery.total_amount
            }
        
        # Customer data
        if delivery.customer_name in customer_data:
            customer_data[delivery.customer_name]['quantity'] += delivery.quantity
            customer_data[delivery.customer_name]['amount'] += delivery.total_amount
            customer_data[delivery.customer_name]['count'] += 1
        else:
            customer_data[delivery.customer_name] = {
                'quantity': delivery.quantity,
                'amount': delivery.total_amount,
                'count': 1,
                'address': delivery.customer_address
            }
        
        # Payment status
        if delivery.is_paid:
            payment_status['paid'] += delivery.total_amount
        else:
            payment_status['pending'] += delivery.total_amount
        
        # Update stock balance
        stock_balance -= delivery.quantity
    
    # Process purchases for analytics
    for purchase in purchases:
        # Monthly purchases
        month_key = purchase.date.strftime('%B %Y')
        if month_key in monthly_purchases:
            monthly_purchases[month_key]['quantity'] += purchase.quantity
            monthly_purchases[month_key]['amount'] += purchase.total_amount
        else:
            monthly_purchases[month_key] = {
                'quantity': purchase.quantity,
                'amount': purchase.total_amount
            }
        
        # Quality trend
        date_key = purchase.date.strftime('%Y-%m-%d')
        if date_key in quality_trend:
            quality_trend[date_key]['fat'] += purchase.fat_percentage
            quality_trend[date_key]['snf'] += purchase.snf_percentage
            quality_trend[date_key]['count'] += 1
        else:
            quality_trend[date_key] = {
                'fat': purchase.fat_percentage,
                'snf': purchase.snf_percentage,
                'count': 1
            }
        
        # Update stock balance
        stock_balance += purchase.quantity
    
    # Calculate average quality for each date
    for date, data in quality_trend.items():
        data['avg_fat'] = data['fat'] / data['count']
        data['avg_snf'] = data['snf'] / data['count']
    
    # Calculate additional statistics
    total_revenue = sum(delivery.total_amount for delivery in deliveries)
    total_cost = sum(purchase.total_amount for purchase in purchases)
    total_profit = total_revenue - total_cost
    
    total_delivered = sum(delivery.quantity for delivery in deliveries)
    total_purchased = sum(purchase.quantity for purchase in purchases)
    
    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    # Find top customers
    sorted_customers = sorted(customer_data.items(), key=lambda x: x[1]['quantity'], reverse=True)
    top_customers = dict(sorted_customers[:10])  # Top 10 customers
    
    # Prepare monthly summary
    monthly_summary = []
    all_months = set(list(monthly_sales.keys()) + list(monthly_purchases.keys()))
    
    for month in sorted(all_months):
        sales_data = monthly_sales.get(month, {'quantity': 0, 'amount': 0})
        purchase_data = monthly_purchases.get(month, {'quantity': 0, 'amount': 0})
        
        month_data = {
            'month_name': month,
            'sales_volume': sales_data['quantity'],
            'sales_amount': sales_data['amount'],
            'purchase_volume': purchase_data['quantity'],
            'purchase_amount': purchase_data['amount'],
            'profit': sales_data['amount'] - purchase_data['amount']
        }
        
        # Calculate averages
        if month in monthly_purchases:
            month_fat_values = []
            month_snf_values = []
            
            # Parse the month string to get date range
            try:
                month_date = datetime.strptime(month, '%B %Y')
                month_start = month_date.replace(day=1)
                # Get last day of month
                next_month = month_date.replace(day=28) + timedelta(days=4)
                month_end = next_month - timedelta(days=next_month.day)
                
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
            except ValueError:
                month_data['avg_fat'] = 0
                month_data['avg_snf'] = 0
        else:
            month_data['avg_fat'] = 0
            month_data['avg_snf'] = 0
        
        monthly_summary.append(month_data)
    
    # Prepare chart data
    months = [data['month_name'] for data in monthly_summary]
    sales_quantities = [data['sales_volume'] for data in monthly_summary]
    sales_amounts = [data['sales_amount'] for data in monthly_summary]
    purchase_quantities = [data['purchase_volume'] for data in monthly_summary]
    purchase_amounts = [data['purchase_amount'] for data in monthly_summary]
    profit_values = [data['profit'] for data in monthly_summary]
    
    # Calculate best metrics
    best_sales_day = max(deliveries, key=lambda x: x.total_amount).date.strftime('%d %b %Y') if deliveries else 'N/A'
    best_sales_amount = max([d.total_amount for d in deliveries]) if deliveries else 0
    
    most_profitable_month = max(monthly_summary, key=lambda x: x['profit'])['month_name'] if monthly_summary else 'N/A'
    most_profitable_amount = max([m['profit'] for m in monthly_summary]) if monthly_summary else 0
    
    top_customer = sorted_customers[0][0] if sorted_customers else 'N/A'
    top_customer_volume = sorted_customers[0][1]['quantity'] if sorted_customers else 0
    
    return render_template('bike_milk_seller/analytics.html',
                          deliveries=deliveries,
                          purchases=purchases,
                          monthly_sales=monthly_sales,
                          monthly_purchases=monthly_purchases,
                          quality_trend=quality_trend,
                          payment_status=payment_status,
                          total_revenue=total_revenue,
                          total_cost=total_cost,
                          total_profit=total_profit,
                          total_delivered=total_delivered,
                          total_purchased=total_purchased,
                          profit_margin=profit_margin,
                          stock_balance=stock_balance,
                          top_customers=top_customers,
                          monthly_summary=monthly_summary,
                          months=months,
                          sales_quantities=sales_quantities,
                          sales_amounts=sales_amounts,
                          purchase_quantities=purchase_quantities,
                          purchase_amounts=purchase_amounts,
                          profit_values=profit_values,
                          best_sales_day=best_sales_day,
                          best_sales_amount=best_sales_amount,
                          most_profitable_month=most_profitable_month,
                          most_profitable_amount=most_profitable_amount,
                          top_customer=top_customer,
                          top_customer_volume=top_customer_volume)

@bike_milk_seller.route('/add_customer', methods=['POST'])
@role_required
def add_customer():
    name = request.form.get('name')
    address = request.form.get('address')
    phone = request.form.get('phone', '')
    daily_quantity = request.form.get('daily_quantity', 0, type=float)
    is_active = 'is_active' in request.form
    
    customer = Customer(
        name=name,
        address=address,
        phone=phone,
        daily_quantity=daily_quantity,
        is_active=is_active,
        bike_seller_id=current_user.id
    )
    
    db.session.add(customer)
    db.session.commit()
    
    flash('Customer added successfully!', 'success')
    return redirect(url_for('bike_milk_seller.customer_list'))

@bike_milk_seller.route('/edit_customer/<int:customer_id>', methods=['POST'])
@role_required
def edit_customer(customer_id):
    customer = Customer.query.filter_by(id=customer_id, bike_seller_id=current_user.id).first_or_404()
    
    customer.name = request.form.get('name')
    customer.address = request.form.get('address')
    customer.phone = request.form.get('phone', '')
    customer.daily_quantity = request.form.get('daily_quantity', 0, type=float)
    customer.is_active = 'is_active' in request.form
    
    db.session.commit()
    
    flash('Customer updated successfully!', 'success')
    return redirect(url_for('bike_milk_seller.customer_list'))

@bike_milk_seller.route('/delete_customer/<int:customer_id>', methods=['POST'])
@role_required
def delete_customer(customer_id):
    customer = Customer.query.filter_by(id=customer_id, bike_seller_id=current_user.id).first_or_404()
    
    # Find all deliveries for this customer and delete them
    deliveries = DeliveryTransaction.query.filter_by(customer_id=customer.id, bike_seller_id=current_user.id).all()
    for delivery in deliveries:
        db.session.delete(delivery)
    
    db.session.delete(customer)
    db.session.commit()
    
    flash('Customer and associated deliveries deleted successfully!', 'success')
    return redirect(url_for('bike_milk_seller.customer_list')) 
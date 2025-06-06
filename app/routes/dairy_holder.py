from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify
from flask_login import login_required, current_user, logout_user
from app import db
from app.models.transactions import DairyStock, MilkTransaction, Inventory, PurchaseTransaction, InventoryTransaction, MilkSaleTransaction
from app.models.user import UserRole, User
from datetime import datetime, date, timedelta
import csv
import io
from sqlalchemy import func, extract, desc
from app.utils.constants import USER_ROLES
from functools import wraps
from fpdf import FPDF

dairy_holder = Blueprint('dairy_holder', __name__, url_prefix='/dairy_holder')

def role_required(view_function):
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        if not current_user.is_dairy_holder():
            flash('You must be a dairy holder to access this page.', 'warning')
            return redirect(url_for('main.role_selection'))
        
        return view_function(*args, **kwargs)
    
    return decorated_function

@dairy_holder.route('/dashboard')
@login_required
@role_required
def dashboard():
    # Get today's date
    today = date.today()
    start_of_month = today.replace(day=1)
    
    # Get recent inventory transactions
    recent_transactions = InventoryTransaction.query.filter_by(dairy_holder_id=current_user.id).order_by(
        InventoryTransaction.transaction_date.desc()
    ).limit(5).all()
    
    # Calculate total inventory
    total_inventory = db.session.query(func.sum(InventoryTransaction.quantity)).filter(
        InventoryTransaction.dairy_holder_id == current_user.id
    ).scalar() or 0
    
    # Calculate pending payments
    pending_payments = db.session.query(func.sum(InventoryTransaction.total_amount)).filter(
        InventoryTransaction.dairy_holder_id == current_user.id,
        InventoryTransaction.is_paid == False
    ).scalar() or 0
    
    # Count pending transactions
    pending_count = db.session.query(func.count(InventoryTransaction.id)).filter(
        InventoryTransaction.dairy_holder_id == current_user.id,
        InventoryTransaction.is_paid == False
    ).scalar() or 0
    
    # Get supplier count
    supplier_count = db.session.query(func.count(func.distinct(InventoryTransaction.supplier_id))).filter(
        InventoryTransaction.dairy_holder_id == current_user.id
    ).scalar() or 0
    
    # Calculate average quality (fat and SNF)
    quality_data = db.session.query(
        func.avg(InventoryTransaction.fat_percentage), 
        func.avg(InventoryTransaction.snf_percentage)
    ).filter(
        InventoryTransaction.dairy_holder_id == current_user.id
    ).first()
    
    avg_fat = quality_data[0] or 0
    avg_snf = quality_data[1] or 0
    avg_quality = (avg_fat + avg_snf) / 2  # Simple quality index
    
    # Today's collection
    todays_collection = db.session.query(func.sum(InventoryTransaction.quantity)).filter(
        InventoryTransaction.dairy_holder_id == current_user.id,
        InventoryTransaction.transaction_date == today
    ).scalar() or 0
    
    # Get monthly inventory data for chart
    monthly_data = db.session.query(
        extract('day', InventoryTransaction.transaction_date).label('day'),
        func.sum(InventoryTransaction.quantity).label('quantity')
    ).filter(
        InventoryTransaction.dairy_holder_id == current_user.id,
        InventoryTransaction.transaction_date >= start_of_month
    ).group_by('day').all()
    
    days = [data[0] for data in monthly_data]
    quantities = [float(data[1]) for data in monthly_data]
    
    # Get milk types count
    milk_types_count = db.session.query(
        func.count(func.distinct(InventoryTransaction.milk_type))
    ).filter(
        InventoryTransaction.dairy_holder_id == current_user.id
    ).scalar() or 0
    
    # Get monthly data for quality trends chart
    monthly_quality = db.session.query(
        extract('day', InventoryTransaction.transaction_date).label('day'),
        func.avg(InventoryTransaction.fat_percentage).label('fat'),
        func.avg(InventoryTransaction.snf_percentage).label('snf')
    ).filter(
        InventoryTransaction.dairy_holder_id == current_user.id,
        InventoryTransaction.transaction_date >= start_of_month
    ).group_by('day').all()
    
    quality_days = [data.day for data in monthly_quality]
    fat_values = [float(data.fat) for data in monthly_quality]
    snf_values = [float(data.snf) for data in monthly_quality]
    
    return render_template('dairy_holder/dashboard.html',
                           recent_transactions=recent_transactions,
                           recent_inventory=recent_transactions,  # Alias for template compatibility
                           total_inventory=total_inventory,
                           pending_payments=pending_payments,
                           pending_count=pending_count,
                           supplier_count=supplier_count,
                           quality_index=round(avg_quality, 2),
                           avg_quality=round(avg_quality, 2),  # Alias for template compatibility
                           avg_fat=round(avg_fat, 2),
                           avg_snf=round(avg_snf, 2),
                           todays_collection=todays_collection,
                           days=days,
                           quantities=quantities,
                           months=days,  # Alias for template compatibility  
                           monthly_quantities=quantities,  # Alias for template compatibility
                           milk_types_count=milk_types_count,
                           quality_days=quality_days,
                           fat_values=fat_values,
                           snf_values=snf_values)

@dairy_holder.route('/stock')
@role_required
def stock():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    stocks = DairyStock.query.filter_by(dairy_holder_id=current_user.id) \
                          .order_by(DairyStock.date.desc()) \
                          .paginate(page=page, per_page=per_page)
    
    return render_template('dairy_holder/stock.html', stocks=stocks)

@dairy_holder.route('/update_stock', methods=['GET', 'POST'])
@role_required
def update_stock():
    if request.method == 'POST':
        quantity = float(request.form.get('quantity'))
        is_addition = request.form.get('transaction_type') == 'addition'
        fat_percentage = float(request.form.get('fat_percentage')) if request.form.get('fat_percentage') else None
        snf_percentage = float(request.form.get('snf_percentage')) if request.form.get('snf_percentage') else None
        
        # Get current stock or create new
        current_stock = DairyStock.query.filter_by(dairy_holder_id=current_user.id) \
                                    .order_by(DairyStock.date.desc()) \
                                    .first()
        
        if not current_stock:
            # Initialize stock if none exists
            current_stock = DairyStock(
                dairy_holder_id=current_user.id,
                total_stock=0,
                avg_fat_percentage=fat_percentage,
                avg_snf_percentage=snf_percentage,
                date=datetime.utcnow()
            )
            db.session.add(current_stock)
        
        # Update stock with new values
        current_stock.update_stock(quantity, is_addition)
        
        # Update quality metrics if provided
        if fat_percentage and snf_percentage:
            if is_addition:
                # Weighted average for additions
                total_before = current_stock.total_stock - quantity
                if total_before > 0:
                    current_fat = current_stock.avg_fat_percentage or 0
                    current_snf = current_stock.avg_snf_percentage or 0
                    
                    new_fat = ((current_fat * total_before) + (fat_percentage * quantity)) / current_stock.total_stock
                    new_snf = ((current_snf * total_before) + (snf_percentage * quantity)) / current_stock.total_stock
                    
                    current_stock.avg_fat_percentage = new_fat
                    current_stock.avg_snf_percentage = new_snf
                else:
                    # First addition
                    current_stock.avg_fat_percentage = fat_percentage
                    current_stock.avg_snf_percentage = snf_percentage
        
        # Create a new stock record for today
        new_stock = DairyStock(
            dairy_holder_id=current_user.id,
            total_stock=current_stock.total_stock,
            avg_fat_percentage=current_stock.avg_fat_percentage,
            avg_snf_percentage=current_stock.avg_snf_percentage,
            stock_in=quantity if is_addition else 0,
            stock_out=quantity if not is_addition else 0,
            date=datetime.utcnow()
        )
        
        db.session.add(new_stock)
        db.session.commit()
        
        flash('Stock updated successfully!')
        return redirect(url_for('dairy_holder.stock'))
    
    return render_template('dairy_holder/update_stock.html')

@dairy_holder.route('/suppliers')
@role_required
def suppliers():
    # Get all suppliers who have provided milk
    supplier_data = db.session.query(
        InventoryTransaction.supplier_id,
        func.sum(InventoryTransaction.quantity).label('total_quantity'),
        func.avg(InventoryTransaction.fat_percentage).label('avg_fat'),
        func.avg(InventoryTransaction.snf_percentage).label('avg_snf'),
        func.count(InventoryTransaction.id).label('transaction_count')
    ).filter(
        InventoryTransaction.dairy_holder_id == current_user.id
    ).group_by(
        InventoryTransaction.supplier_id
    ).all()
    
    suppliers_list = []
    for data in supplier_data:
        supplier = User.query.get(data.supplier_id)
        if supplier:
            suppliers_list.append({
                'id': supplier.id,
                'name': supplier.name,
                'email': supplier.email,
                'phone': supplier.phone,
                'total_quantity': float(data.total_quantity),
                'avg_fat': float(data.avg_fat),
                'avg_snf': float(data.avg_snf),
                'transaction_count': data.transaction_count
            })
    
    return render_template('dairy_holder/suppliers.html', suppliers=suppliers_list)

@dairy_holder.route('/reports')
@role_required
def reports():
    # Get date range from request
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date and end_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
        
        stocks = DairyStock.query.filter_by(dairy_holder_id=current_user.id) \
                             .filter(DairyStock.date >= start_date) \
                             .filter(DairyStock.date <= end_date) \
                             .order_by(DairyStock.date.asc()) \
                             .all()
    else:
        stocks = DairyStock.query.filter_by(dairy_holder_id=current_user.id) \
                             .order_by(DairyStock.date.asc()) \
                             .all()
    
    # Generate chart data
    dates = [stock.date.strftime('%Y-%m-%d') for stock in stocks]
    stock_levels = [stock.total_stock for stock in stocks]
    stock_in_values = [stock.stock_in for stock in stocks]
    stock_out_values = [stock.stock_out for stock in stocks]
    
    return render_template('dairy_holder/reports.html', 
                          stocks=stocks,
                          dates=dates,
                          stock_levels=stock_levels,
                          stock_in_values=stock_in_values,
                          stock_out_values=stock_out_values)

@dairy_holder.route('/export_report')
@role_required
def export_report():
    # Get all stock data
    stocks = DairyStock.query.filter_by(dairy_holder_id=current_user.id) \
                         .order_by(DairyStock.date.asc()) \
                         .all()
    
    # Create CSV file
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Date', 'Total Stock', 'Stock In', 'Stock Out', 'Avg Fat %', 'Avg SNF %'])
    
    # Write stock data
    for stock in stocks:
        writer.writerow([
            stock.date.strftime('%Y-%m-%d'),
            stock.total_stock,
            stock.stock_in,
            stock.stock_out,
            stock.avg_fat_percentage,
            stock.avg_snf_percentage
        ])
    
    # Create response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=dairy_stock_report.csv"}
    )

@dairy_holder.route('/inventory')
@role_required
def inventory():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Get filter parameters
    supplier_id = request.args.get('supplier')
    milk_type = request.args.get('milk_type')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Build query
    query = InventoryTransaction.query.filter_by(dairy_holder_id=current_user.id)
    
    # Apply filters
    if supplier_id:
        query = query.filter(InventoryTransaction.supplier_id == supplier_id)
    
    if milk_type:
        query = query.filter(InventoryTransaction.milk_type == milk_type)
    
    if date_from:
        date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        query = query.filter(InventoryTransaction.transaction_date >= date_from)
    
    if date_to:
        date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        query = query.filter(InventoryTransaction.transaction_date <= date_to)
    
    # Order by date (newest first)
    query = query.order_by(InventoryTransaction.transaction_date.desc())
    
    # Paginate
    inventory_pagination = query.paginate(page=page, per_page=per_page)
    
    # Get suppliers for filter dropdown
    suppliers = User.query.filter_by(role=USER_ROLES.MILK_SELLER).all()
    
    # Statistics for cards
    total_inventory = db.session.query(func.sum(InventoryTransaction.quantity)).filter(
        InventoryTransaction.dairy_holder_id == current_user.id
    ).scalar() or 0
    
    today = date.today()
    todays_collection = db.session.query(func.sum(InventoryTransaction.quantity)).filter(
        InventoryTransaction.dairy_holder_id == current_user.id,
        InventoryTransaction.transaction_date == today
    ).scalar() or 0
    
    milk_types_count = db.session.query(
        func.count(func.distinct(InventoryTransaction.milk_type))
    ).filter(
        InventoryTransaction.dairy_holder_id == current_user.id
    ).scalar() or 0
    
    return render_template('dairy_holder/inventory.html',
                           inventory_items=inventory_pagination.items,
                           page=page,
                           total_pages=inventory_pagination.pages,
                           has_next=inventory_pagination.has_next,
                           has_prev=inventory_pagination.has_prev,
                           suppliers=suppliers,
                           total_inventory=total_inventory,
                           todays_collection=todays_collection,
                           milk_types_count=milk_types_count)

@dairy_holder.route('/add_inventory', methods=['POST'])
@role_required
def add_inventory():
    supplier_id = request.form.get('supplier_id')
    milk_type = request.form.get('milk_type')
    quantity = float(request.form.get('quantity'))
    price_per_liter = float(request.form.get('price_per_liter'))
    fat_percentage = float(request.form.get('fat_percentage'))
    snf_percentage = float(request.form.get('snf_percentage'))
    notes = request.form.get('notes')
    is_paid = 'is_paid' in request.form
    
    # Calculate total amount
    total_amount = quantity * price_per_liter
    
    # Create new inventory transaction
    inventory = InventoryTransaction(
        dairy_holder_id=current_user.id,
        supplier_id=supplier_id,
        milk_type=milk_type,
        quantity=quantity,
        price_per_liter=price_per_liter,
        fat_percentage=fat_percentage,
        snf_percentage=snf_percentage,
        total_amount=total_amount,
        is_paid=is_paid,
        notes=notes,
        transaction_date=date.today()
    )
    
    db.session.add(inventory)
    
    try:
        db.session.commit()
        flash('Inventory added successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding inventory: {str(e)}', 'danger')
    
    return redirect(url_for('dairy_holder.inventory'))

@dairy_holder.route('/edit_inventory', methods=['POST'])
@role_required
def edit_inventory():
    inventory_id = request.form.get('inventory_id')
    
    # Find the inventory transaction
    inventory = InventoryTransaction.query.filter_by(
        id=inventory_id, 
        dairy_holder_id=current_user.id
    ).first()
    
    if not inventory:
        flash('Inventory record not found.', 'danger')
        return redirect(url_for('dairy_holder.inventory'))
    
    # Update inventory details
    inventory.supplier_id = request.form.get('supplier_id')
    inventory.milk_type = request.form.get('milk_type')
    inventory.quantity = float(request.form.get('quantity'))
    inventory.price_per_liter = float(request.form.get('price_per_liter'))
    inventory.fat_percentage = float(request.form.get('fat_percentage'))
    inventory.snf_percentage = float(request.form.get('snf_percentage'))
    inventory.notes = request.form.get('notes')
    inventory.is_paid = 'is_paid' in request.form
    
    # Recalculate total amount
    inventory.total_amount = inventory.quantity * inventory.price_per_liter
    
    try:
        db.session.commit()
        flash('Inventory updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating inventory: {str(e)}', 'danger')
    
    return redirect(url_for('dairy_holder.inventory'))

@dairy_holder.route('/mark_paid/<int:inventory_id>')
@role_required
def mark_paid(inventory_id):
    inventory = InventoryTransaction.query.filter_by(
        id=inventory_id, 
        dairy_holder_id=current_user.id,
        is_paid=False
    ).first()
    
    if inventory:
        inventory.is_paid = True
        try:
            db.session.commit()
            flash('Payment marked as complete!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating payment status: {str(e)}', 'danger')
    else:
        flash('Inventory record not found or already paid.', 'warning')
    
    return redirect(url_for('dairy_holder.inventory'))

@dairy_holder.route('/export_inventory')
@role_required
def export_inventory():
    # This would be implemented to export data in various formats
    # For now, we'll just redirect back with a message
    format_type = request.args.get('format', 'csv')
    flash(f'Exporting inventory as {format_type} is not implemented yet.', 'info')
    return redirect(url_for('dairy_holder.inventory'))

@dairy_holder.route('/api/dairy_holder/inventory/<int:inventory_id>')
@role_required
def get_inventory_details(inventory_id):
    inventory = InventoryTransaction.query.filter_by(
        id=inventory_id, 
        dairy_holder_id=current_user.id
    ).first()
    
    if not inventory:
        return jsonify({'error': 'Inventory not found'}), 404
    
    supplier = User.query.get(inventory.supplier_id)
    
    return jsonify({
        'id': inventory.id,
        'supplier_id': inventory.supplier_id,
        'supplier_name': supplier.name if supplier else 'Unknown',
        'milk_type': inventory.milk_type,
        'quantity': inventory.quantity,
        'fat_percentage': inventory.fat_percentage,
        'snf_percentage': inventory.snf_percentage,
        'price_per_liter': inventory.price_per_liter,
        'total_amount': inventory.total_amount,
        'is_paid': inventory.is_paid,
        'date': inventory.transaction_date.strftime('%Y-%m-%d'),
        'notes': inventory.notes
    })

@dairy_holder.route('/analytics', methods=['GET'])
@login_required
@role_required
def analytics():
    time_period = request.args.get('period', 'last_6_months')
    today = datetime.now().date()
    
    # Set date range based on selected period
    if time_period == 'last_30_days':
        start_date = today - timedelta(days=30)
    elif time_period == 'last_90_days':
        start_date = today - timedelta(days=90)
    elif time_period == 'last_6_months':
        start_date = today - timedelta(days=180)
    elif time_period == 'last_year':
        start_date = today - timedelta(days=365)
    elif time_period == 'all_time':
        start_date = datetime(2000, 1, 1).date()  # Just a very old date
    else:
        start_date = today - timedelta(days=180)  # Default to last 6 months
    
    # Get inventory entries for the current user within the date range
    inventory_entries = db.session.query(InventoryTransaction).filter(
        InventoryTransaction.dairy_holder_id == current_user.id,
        InventoryTransaction.transaction_date >= start_date
    ).order_by(InventoryTransaction.transaction_date).all()
    
    # Aggregate data by month
    monthly_data = {}
    
    for entry in inventory_entries:
        month_key = entry.transaction_date.strftime('%Y-%m')
        month_name = entry.transaction_date.strftime('%b %Y')
        
        if month_key not in monthly_data:
            monthly_data[month_key] = {
                'month_name': month_name,
                'quantity': 0,
                'amount': 0,
                'fat_values': [],
                'snf_values': [],
                'entries_count': 0
            }
        
        monthly_data[month_key]['quantity'] += entry.quantity
        monthly_data[month_key]['amount'] += entry.total_amount
        monthly_data[month_key]['fat_values'].append(entry.fat_percentage)
        monthly_data[month_key]['snf_values'].append(entry.snf_percentage)
        monthly_data[month_key]['entries_count'] += 1
    
    # Calculate averages for each month
    for month_data in monthly_data.values():
        if month_data['entries_count'] > 0:
            month_data['avg_fat'] = sum(month_data['fat_values']) / month_data['entries_count']
            month_data['avg_snf'] = sum(month_data['snf_values']) / month_data['entries_count']
        else:
            month_data['avg_fat'] = 0
            month_data['avg_snf'] = 0
    
    # Sort months chronologically
    sorted_months = sorted(monthly_data.items())
    
    # Prepare data for charts
    months = [month_data['month_name'] for _, month_data in sorted_months]
    monthly_quantities = [month_data['quantity'] for _, month_data in sorted_months]
    monthly_amounts = [month_data['amount'] for _, month_data in sorted_months]
    monthly_fat = [month_data['avg_fat'] for _, month_data in sorted_months]
    monthly_snf = [month_data['avg_snf'] for _, month_data in sorted_months]
    
    # Calculate overall summary
    total_volume = sum(monthly_quantities)
    total_spent = sum(monthly_amounts)
    
    avg_fat = sum([entry.fat_percentage for entry in inventory_entries]) / len(inventory_entries) if inventory_entries else 0
    avg_snf = sum([entry.snf_percentage for entry in inventory_entries]) / len(inventory_entries) if inventory_entries else 0
    
    # Find the most active supplier
    supplier_data = {}
    for entry in inventory_entries:
        if entry.supplier_id not in supplier_data:
            supplier_data[entry.supplier_id] = {
                'quantity': 0,
                'amount': 0,
                'fat_values': [],
                'snf_values': []
            }
        
        supplier_data[entry.supplier_id]['quantity'] += entry.quantity
        supplier_data[entry.supplier_id]['amount'] += entry.total_amount
        supplier_data[entry.supplier_id]['fat_values'].append(entry.fat_percentage)
        supplier_data[entry.supplier_id]['snf_values'].append(entry.snf_percentage)
    
    # Calculate averages for each supplier
    for supplier in supplier_data.values():
        if len(supplier['fat_values']) > 0:
            supplier['avg_fat'] = sum(supplier['fat_values']) / len(supplier['fat_values'])
            supplier['avg_snf'] = sum(supplier['snf_values']) / len(supplier['snf_values'])
        else:
            supplier['avg_fat'] = 0
            supplier['avg_snf'] = 0
    
    # Find the supplier with highest volume and best quality
    if supplier_data:
        most_active_supplier = max(supplier_data.items(), key=lambda x: x[1]['quantity'])
        best_quality_supplier = max(supplier_data.items(), key=lambda x: x[1]['avg_fat'] + x[1]['avg_snf'])
    else:
        most_active_supplier = ("None", {'quantity': 0})
        best_quality_supplier = ("None", {'avg_fat': 0, 'avg_snf': 0})
    
    # Find the most active month
    most_active_month = max(monthly_data.items(), key=lambda x: x[1]['quantity']) if monthly_data else (None, {'month_name': 'None', 'quantity': 0})
    
    return render_template(
        'dairy_holder/analytics.html',
        time_period=time_period,
        months=months,
        monthly_quantities=monthly_quantities,
        monthly_amounts=monthly_amounts,
        monthly_fat=monthly_fat,
        monthly_snf=monthly_snf,
        monthly_data=sorted_months,
        total_volume=total_volume,
        total_spent=total_spent,
        avg_fat=avg_fat,
        avg_snf=avg_snf,
        most_active_supplier=most_active_supplier,
        best_quality_supplier=best_quality_supplier,
        most_active_month=most_active_month[1]['month_name'] if most_active_month[0] else 'None'
    )

@dairy_holder.route('/quality')
@login_required
@role_required
def quality():
    # Get all inventory transactions for quality analysis
    inventory_transactions = InventoryTransaction.query.filter_by(
        dairy_holder_id=current_user.id
    ).order_by(InventoryTransaction.transaction_date.desc()).all()
    
    # Calculate overall averages
    total_fat = sum(t.fat_percentage for t in inventory_transactions) if inventory_transactions else 0
    total_snf = sum(t.snf_percentage for t in inventory_transactions) if inventory_transactions else 0
    count = len(inventory_transactions)
    
    avg_fat = total_fat / count if count > 0 else 0
    avg_snf = total_snf / count if count > 0 else 0
    
    # Group by month for trend analysis
    monthly_data = {}
    for transaction in inventory_transactions:
        month_key = transaction.transaction_date.strftime('%Y-%m')
        month_name = transaction.transaction_date.strftime('%b %Y')
        
        if month_key not in monthly_data:
            monthly_data[month_key] = {
                'month': month_name,
                'fat_values': [],
                'snf_values': [],
                'transactions_count': 0
            }
        
        monthly_data[month_key]['fat_values'].append(transaction.fat_percentage)
        monthly_data[month_key]['snf_values'].append(transaction.snf_percentage)
        monthly_data[month_key]['transactions_count'] += 1
    
    # Calculate monthly averages
    for month_data in monthly_data.values():
        month_count = month_data['transactions_count']
        month_data['avg_fat'] = sum(month_data['fat_values']) / month_count if month_count > 0 else 0
        month_data['avg_snf'] = sum(month_data['snf_values']) / month_count if month_count > 0 else 0
    
    # Sort by month (chronologically)
    sorted_months = sorted(monthly_data.items())
    
    # Prepare data for quality trend chart
    months = [data['month'] for month_key, data in sorted_months]
    fat_trend = [data['avg_fat'] for month_key, data in sorted_months]
    snf_trend = [data['avg_snf'] for month_key, data in sorted_months]
    
    # Group by supplier for comparison
    supplier_data = {}
    for transaction in inventory_transactions:
        supplier_id = transaction.supplier_id
        if supplier_id not in supplier_data:
            supplier = User.query.get(supplier_id)
            supplier_name = supplier.name if supplier else f"Unknown ({supplier_id})"
            supplier_data[supplier_id] = {
                'name': supplier_name,
                'fat_values': [],
                'snf_values': [],
                'transactions_count': 0
            }
        
        supplier_data[supplier_id]['fat_values'].append(transaction.fat_percentage)
        supplier_data[supplier_id]['snf_values'].append(transaction.snf_percentage)
        supplier_data[supplier_id]['transactions_count'] += 1
    
    # Calculate supplier averages
    for supplier in supplier_data.values():
        count = supplier['transactions_count']
        supplier['avg_fat'] = sum(supplier['fat_values']) / count if count > 0 else 0
        supplier['avg_snf'] = sum(supplier['snf_values']) / count if count > 0 else 0
        supplier['quality_score'] = (supplier['avg_fat'] + supplier['avg_snf']) / 2
    
    # Sort suppliers by quality score (descending)
    sorted_suppliers = sorted(
        supplier_data.values(), 
        key=lambda x: x['quality_score'], 
        reverse=True
    )
    
    return render_template(
        'dairy_holder/quality.html',
        inventory_transactions=inventory_transactions,
        avg_fat=avg_fat,
        avg_snf=avg_snf,
        months=months,
        fat_trend=fat_trend,
        snf_trend=snf_trend,
        suppliers=sorted_suppliers
    )

@dairy_holder.route('/api/supplier/<int:supplier_id>')
@role_required
def get_supplier_details(supplier_id):
    supplier = User.query.get(supplier_id)
    
    if not supplier:
        return jsonify({'error': 'Supplier not found'}), 404
    
    # Get supplier's transactions
    transactions = InventoryTransaction.query.filter_by(
        dairy_holder_id=current_user.id,
        supplier_id=supplier_id
    ).order_by(InventoryTransaction.transaction_date.desc()).all()
    
    # Get recent transactions
    recent_transactions = []
    for tx in transactions[:5]:  # Get up to 5 recent transactions
        recent_transactions.append({
            'date': tx.transaction_date.strftime('%Y-%m-%d'),
            'quantity': float(tx.quantity),
            'fat': float(tx.fat_percentage),
            'snf': float(tx.snf_percentage),
            'amount': float(tx.total_amount)
        })
    
    # Get monthly quality data
    monthly_data = db.session.query(
        extract('month', InventoryTransaction.transaction_date).label('month'),
        func.avg(InventoryTransaction.fat_percentage).label('avg_fat'),
        func.avg(InventoryTransaction.snf_percentage).label('avg_snf')
    ).filter(
        InventoryTransaction.dairy_holder_id == current_user.id,
        InventoryTransaction.supplier_id == supplier_id,
        InventoryTransaction.transaction_date >= datetime.now() - timedelta(days=365)
    ).group_by('month').all()
    
    # Format the monthly data
    months = []
    monthly_fat = []
    monthly_snf = []
    
    for data in monthly_data:
        month_name = datetime.strptime(str(int(data.month)), '%m').strftime('%b')
        months.append(month_name)
        monthly_fat.append(float(data.avg_fat))
        monthly_snf.append(float(data.avg_snf))
    
    # Calculate transaction totals
    total_quantity = sum(tx.quantity for tx in transactions)
    transaction_count = len(transactions)
    
    # Calculate quality averages
    avg_fat = sum(tx.fat_percentage for tx in transactions) / transaction_count if transaction_count > 0 else 0
    avg_snf = sum(tx.snf_percentage for tx in transactions) / transaction_count if transaction_count > 0 else 0
    
    return jsonify({
        'id': supplier.id,
        'name': supplier.name,
        'email': supplier.email or 'Not provided',
        'phone': supplier.phone or 'Not provided',
        'total_quantity': float(total_quantity),
        'avg_fat': float(avg_fat),
        'avg_snf': float(avg_snf),
        'transaction_count': transaction_count,
        'recent_transactions': recent_transactions,
        'months': months,
        'monthly_fat': monthly_fat,
        'monthly_snf': monthly_snf,
        'transactions_url': url_for('dairy_holder.inventory', supplier=supplier_id)
    })

@dairy_holder.route('/print_receipt/<int:inventory_id>')
@role_required
def print_receipt(inventory_id):
    # Get the inventory transaction details
    inventory = InventoryTransaction.query.get_or_404(inventory_id)
    
    # Verify that this inventory belongs to the current user
    if inventory.dairy_holder_id != current_user.id:
        flash('You do not have permission to access this receipt.', 'danger')
        return redirect(url_for('dairy_holder.inventory'))
    
    # Get supplier information
    supplier = None
    if inventory.supplier_id:
        supplier = User.query.filter_by(id=inventory.supplier_id).first()
    
    # Create the PDF receipt
    pdf = FPDF(format='A6')  # A6 is a good size for a receipt
    pdf.add_page()
    
    # Set up fonts
    pdf.set_font('Arial', 'B', 12)
    
    # Header
    pdf.cell(0, 10, 'SMART DAIRY - INVENTORY RECEIPT', 0, 1, 'C')
    pdf.set_font('Arial', '', 8)
    pdf.cell(0, 5, f'Receipt Date: {datetime.now().strftime("%d-%m-%Y %H:%M")}', 0, 1, 'C')
    pdf.cell(0, 5, f'Transaction Date: {inventory.transaction_date.strftime("%d-%m-%Y")}', 0, 1, 'C')
    pdf.cell(0, 5, f'Transaction ID: {inventory.id}', 0, 1, 'C')
    pdf.line(10, 30, 140, 30)
    
    # Dairy Holder and Supplier Info
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 10, 'TRANSACTION DETAILS', 0, 1, 'L')
    
    pdf.set_font('Arial', '', 8)
    pdf.cell(40, 5, 'Dairy Holder:', 0, 0, 'L')
    pdf.cell(0, 5, current_user.username, 0, 1, 'L')
    
    if supplier:
        pdf.cell(40, 5, 'Supplier:', 0, 0, 'L')
        pdf.cell(0, 5, supplier.username, 0, 1, 'L')
        pdf.cell(40, 5, 'Supplier Type:', 0, 0, 'L')
        role_name = "Milk Seller" if supplier.role == UserRole.MILK_SELLER else "Bike Milk Seller"
        pdf.cell(0, 5, role_name, 0, 1, 'L')
    
    pdf.line(10, 55, 140, 55)
    
    # Inventory Details
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 10, 'MILK DETAILS', 0, 1, 'L')
    
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 5, 'Milk Type:', 0, 0, 'L')
    pdf.cell(0, 5, inventory.milk_type.capitalize(), 0, 1, 'L')
    
    pdf.cell(60, 5, 'Quantity:', 0, 0, 'L')
    pdf.cell(0, 5, f'{inventory.quantity:.2f} L', 0, 1, 'L')
    
    pdf.cell(60, 5, 'Price per Liter:', 0, 0, 'L')
    pdf.cell(0, 5, f'Rs. {inventory.price_per_liter:.2f}', 0, 1, 'L')
    
    pdf.cell(60, 5, 'Fat Percentage:', 0, 0, 'L')
    pdf.cell(0, 5, f'{inventory.fat_percentage:.1f}%', 0, 1, 'L')
    
    pdf.cell(60, 5, 'SNF Percentage:', 0, 0, 'L')
    pdf.cell(0, 5, f'{inventory.snf_percentage:.1f}%', 0, 1, 'L')
    
    pdf.line(10, 90, 140, 90)
    
    # Payment Details
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 10, 'PAYMENT DETAILS', 0, 1, 'L')
    
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 5, 'Total Amount:', 0, 0, 'L')
    pdf.cell(0, 5, f'Rs. {inventory.total_amount:.2f}', 0, 1, 'L')
    
    pdf.cell(60, 5, 'Payment Status:', 0, 0, 'L')
    pdf.cell(0, 5, 'PAID' if inventory.is_paid else 'PENDING', 0, 1, 'L')
    
    if inventory.is_paid and inventory.payment_date:
        pdf.cell(60, 5, 'Payment Date:', 0, 0, 'L')
        pdf.cell(0, 5, inventory.payment_date.strftime('%d-%m-%Y'), 0, 1, 'L')
    
    # Notes
    if inventory.notes:
        pdf.cell(60, 5, 'Notes:', 0, 0, 'L')
        pdf.cell(0, 5, inventory.notes[:30] + '...' if len(inventory.notes) > 30 else inventory.notes, 0, 1, 'L')
    
    # Footer
    pdf.line(10, 115, 140, 115)
    pdf.set_font('Arial', 'I', 6)
    pdf.cell(0, 10, 'This is a computer generated receipt and does not require signature.', 0, 1, 'C')
    pdf.cell(0, 5, 'Smart Dairy & Milk Tracking System', 0, 1, 'C')
    
    # Generate PDF content
    pdf_output = io.BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    
    # Return the PDF as a response
    return Response(
        pdf_output,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename=inventory_receipt_{inventory.id}.pdf"}
    )

@dairy_holder.route('/milk_transactions')
@role_required
def milk_transactions():
    try:
        # Get current inventory status
        total_purchases = InventoryTransaction.query.filter_by(
            dairy_holder_id=current_user.id
        ).with_entities(db.func.sum(InventoryTransaction.quantity)).scalar() or 0
        
        # Check for milk_sale_transaction table
        total_sales = 0
        try:
            total_sales = MilkSaleTransaction.query.filter_by(
                dairy_holder_id=current_user.id
            ).with_entities(db.func.sum(MilkSaleTransaction.quantity)).scalar() or 0
        except Exception as e:
            print(f"Error fetching milk sales: {str(e)}")
            # Continue with total_sales = 0
        
        # Calculate current inventory
        total_inventory = total_purchases - total_sales
        
        # Get milk type breakdown
        milk_types = ['cow', 'buffalo', 'mixed']
        milk_type_data = []
        
        for milk_type in milk_types:
            # Calculate purchases of this type
            type_purchases = InventoryTransaction.query.filter_by(
                dairy_holder_id=current_user.id, 
                milk_type=milk_type
            ).with_entities(db.func.sum(InventoryTransaction.quantity)).scalar() or 0
            
            # Calculate sales of this type
            type_sales = 0
            try:
                type_sales = MilkSaleTransaction.query.filter_by(
                    dairy_holder_id=current_user.id,
                    milk_type=milk_type
                ).with_entities(db.func.sum(MilkSaleTransaction.quantity)).scalar() or 0
            except Exception as e:
                print(f"Error fetching milk sales for type {milk_type}: {str(e)}")
                # Continue with type_sales = 0
            
            # Calculate net inventory of this type
            type_inventory = type_purchases - type_sales
            
            # Calculate percentage of total
            type_percentage = 0
            if total_inventory > 0:
                type_percentage = (type_inventory / total_inventory) * 100
            
            milk_type_data.append({
                'type': milk_type.capitalize(),
                'quantity': type_inventory,
                'percentage': type_percentage
            })
        
        # Get today's transactions
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        todays_purchases = InventoryTransaction.query.filter_by(
            dairy_holder_id=current_user.id
        ).filter(InventoryTransaction.transaction_date >= today_start
        ).with_entities(db.func.sum(InventoryTransaction.quantity)).scalar() or 0
        
        todays_sales = 0
        try:
            todays_sales = MilkSaleTransaction.query.filter_by(
                dairy_holder_id=current_user.id
            ).filter(MilkSaleTransaction.date >= today_start
            ).with_entities(db.func.sum(MilkSaleTransaction.quantity)).scalar() or 0
        except Exception as e:
            print(f"Error fetching today's milk sales: {str(e)}")
            # Continue with todays_sales = 0
        
        # Get suppliers for dropdown list
        suppliers = User.query.filter(
            User.role.in_([UserRole.MILK_SELLER, UserRole.BIKE_MILK_SELLER])
        ).all()
        
        # Get buyers for dropdown list (can be milk buyers or end customers)
        buyers = User.query.filter_by(role=UserRole.MILK_BUYER).all()
        
        # Get recent milk transactions (both buy and sell)
        recent_buy_transactions = InventoryTransaction.query.filter_by(
            dairy_holder_id=current_user.id
        ).order_by(InventoryTransaction.transaction_date.desc()).limit(5).all()
        
        # Get recent milk sale transactions
        recent_sell_transactions = []
        try:
            recent_sell_transactions = MilkSaleTransaction.query.filter_by(
                dairy_holder_id=current_user.id
            ).order_by(MilkSaleTransaction.date.desc()).limit(5).all()
        except Exception as e:
            print(f"Error fetching recent milk sales: {str(e)}")
            # Continue with recent_sell_transactions = []
        
        return render_template('dairy_holder/milk_transactions.html',
                              total_inventory=total_inventory,
                              milk_type_data=milk_type_data,
                              todays_purchases=todays_purchases,
                              todays_sales=todays_sales,
                              suppliers=suppliers,
                              buyers=buyers,
                              recent_buy_transactions=recent_buy_transactions,
                              recent_sell_transactions=recent_sell_transactions)
    except Exception as e:
        flash(f"An error occurred while loading Milk Transactions: {str(e)}", "danger")
        print(f"Error in milk_transactions: {str(e)}")
        return redirect(url_for('dairy_holder.dashboard'))

@dairy_holder.route('/add_milk_purchase', methods=['POST'])
@role_required
def add_milk_purchase():
    supplier_id = request.form.get('supplier_id')
    milk_type = request.form.get('milk_type')
    quantity = float(request.form.get('quantity'))
    price_per_liter = float(request.form.get('price_per_liter'))
    fat_percentage = float(request.form.get('fat_percentage'))
    snf_percentage = float(request.form.get('snf_percentage'))
    notes = request.form.get('notes', '')
    is_paid = 'is_paid' in request.form
    
    # Create new inventory transaction (milk purchase)
    supplier = User.query.get(supplier_id)
    if not supplier:
        flash('Invalid supplier selection', 'danger')
        return redirect(url_for('dairy_holder.milk_transactions'))
    
    transaction = InventoryTransaction(
        dairy_holder_id=current_user.id,
        supplier_id=supplier_id,
        supplier_name=supplier.name,
        milk_type=milk_type,
        quantity=quantity,
        price_per_liter=price_per_liter,
        fat_percentage=fat_percentage,
        snf_percentage=snf_percentage,
        total_amount=quantity * price_per_liter,
        transaction_date=datetime.utcnow(),
        is_paid=is_paid,
        payment_date=datetime.utcnow() if is_paid else None,
        notes=notes
    )
    
    db.session.add(transaction)
    db.session.commit()
    
    flash('Milk purchase added successfully!', 'success')
    return redirect(url_for('dairy_holder.milk_transactions'))

@dairy_holder.route('/add_milk_sale', methods=['POST'])
@role_required
def add_milk_sale():
    try:
        buyer_id = request.form.get('buyer_id', '')
        buyer_name = request.form.get('customer_name', '')
        milk_type = request.form.get('milk_type')
        quantity = float(request.form.get('quantity'))
        price_per_liter = float(request.form.get('price_per_liter'))
        fat_percentage = float(request.form.get('fat_percentage', 0) or 0)
        snf_percentage = float(request.form.get('snf_percentage', 0) or 0)
        notes = request.form.get('notes', '')
        is_paid = 'is_paid' in request.form
        
        # Check if we have enough inventory
        total_purchases = InventoryTransaction.query.filter_by(
            dairy_holder_id=current_user.id
        ).with_entities(db.func.sum(InventoryTransaction.quantity)).scalar() or 0
        
        # Also check for existing sales to get the true current inventory
        total_sales = 0
        try:
            total_sales = MilkSaleTransaction.query.filter_by(
                dairy_holder_id=current_user.id
            ).with_entities(db.func.sum(MilkSaleTransaction.quantity)).scalar() or 0
        except Exception as e:
            print(f"Error checking total milk sales: {str(e)}")
            # Continue with total_sales = 0
        
        # Calculate actual inventory
        actual_inventory = total_purchases - total_sales
        
        if quantity > actual_inventory:
            flash('Not enough inventory to complete this sale. Current inventory: {:.2f} L'.format(actual_inventory), 'danger')
            return redirect(url_for('dairy_holder.milk_transactions'))
        
        # If buyer_id is provided and valid, use the buyer's name from the database
        buyer_display_name = buyer_name
        if buyer_id:
            buyer = User.query.get(buyer_id)
            if buyer:
                buyer_display_name = buyer.name
        
        # Create a MilkSaleTransaction record
        sale_transaction = MilkSaleTransaction(
            dairy_holder_id=current_user.id,
            buyer_id=buyer_id if buyer_id else None,
            buyer_name=buyer_display_name if buyer_display_name else 'Direct Customer',
            milk_type=milk_type,
            quantity=quantity,
            price_per_liter=price_per_liter,
            total_amount=quantity * price_per_liter,
            fat_percentage=fat_percentage,
            snf_percentage=snf_percentage,
            date=datetime.utcnow(),
            is_paid=is_paid,
            payment_date=datetime.utcnow() if is_paid else None,
            notes=notes
        )
        
        try:
            db.session.add(sale_transaction)
            db.session.commit()
            flash('Milk sale recorded successfully! Inventory has been updated.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording milk sale: {str(e)}', 'danger')
            print(f"Database error in add_milk_sale: {str(e)}")
            
        return redirect(url_for('dairy_holder.milk_transactions'))
    except Exception as e:
        flash(f'An error occurred while processing your request: {str(e)}', 'danger')
        print(f"General error in add_milk_sale: {str(e)}")
        return redirect(url_for('dairy_holder.milk_transactions'))

@dairy_holder.route('/milk_manager')
@role_required
def milk_manager():
    try:
        # Get current inventory status
        total_purchases = InventoryTransaction.query.filter_by(
            dairy_holder_id=current_user.id
        ).with_entities(db.func.sum(InventoryTransaction.quantity)).scalar() or 0
        
        # Check if milk_sale_transaction table exists
        total_sales = 0
        try:
            total_sales = MilkSaleTransaction.query.filter_by(
                dairy_holder_id=current_user.id
            ).with_entities(db.func.sum(MilkSaleTransaction.quantity)).scalar() or 0
        except Exception as e:
            print(f"Error fetching milk sales: {str(e)}")
            # If there's an error, we continue with total_sales = 0
        
        # Calculate current inventory
        total_inventory = total_purchases - total_sales
        
        # Get milk type breakdown
        milk_types = ['cow', 'buffalo', 'mixed']
        milk_type_data = []
        
        for milk_type in milk_types:
            # Calculate purchases of this type
            type_purchases = InventoryTransaction.query.filter_by(
                dairy_holder_id=current_user.id, 
                milk_type=milk_type
            ).with_entities(db.func.sum(InventoryTransaction.quantity)).scalar() or 0
            
            # Calculate sales of this type
            type_sales = MilkSaleTransaction.query.filter_by(
                dairy_holder_id=current_user.id,
                milk_type=milk_type
            ).with_entities(db.func.sum(MilkSaleTransaction.quantity)).scalar() or 0
            
            # Calculate net inventory of this type
            type_inventory = type_purchases - type_sales
            
            # Calculate percentage of total
            type_percentage = 0
            if total_inventory > 0:
                type_percentage = (type_inventory / total_inventory) * 100
            
            milk_type_data.append({
                'type': milk_type.capitalize(),
                'quantity': type_inventory,
                'percentage': type_percentage
            })
        
        # Get today's transactions
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        todays_purchases = InventoryTransaction.query.filter_by(
            dairy_holder_id=current_user.id
        ).filter(InventoryTransaction.transaction_date >= today_start
        ).with_entities(db.func.sum(InventoryTransaction.quantity)).scalar() or 0
        
        todays_sales = MilkSaleTransaction.query.filter_by(
            dairy_holder_id=current_user.id
        ).filter(MilkSaleTransaction.date >= today_start
        ).with_entities(db.func.sum(MilkSaleTransaction.quantity)).scalar() or 0
        
        # Get suppliers for dropdown list
        suppliers = User.query.filter(
            User.role.in_([UserRole.MILK_SELLER, UserRole.BIKE_MILK_SELLER])
        ).all()
        
        # Get buyers for dropdown list (can be milk buyers or end customers)
        buyers = User.query.filter_by(role=UserRole.MILK_BUYER).all()
        
        # Calculate average prices for today's transactions
        today_purchase_transactions = InventoryTransaction.query.filter_by(
            dairy_holder_id=current_user.id
        ).filter(InventoryTransaction.transaction_date >= today_start).all()
        
        avg_purchase_price = 0
        if today_purchase_transactions:
            total_amount = sum(t.total_amount for t in today_purchase_transactions)
            total_quantity = sum(t.quantity for t in today_purchase_transactions)
            if total_quantity > 0:
                avg_purchase_price = total_amount / total_quantity
        
        # Similarly handle potential errors for sale transactions
        today_sale_transactions = []
        avg_selling_price = 0
        try:
            today_sale_transactions = MilkSaleTransaction.query.filter_by(
                dairy_holder_id=current_user.id
            ).filter(MilkSaleTransaction.date >= today_start).all()
            
            if today_sale_transactions:
                total_amount = sum(t.total_amount for t in today_sale_transactions)
                total_quantity = sum(t.quantity for t in today_sale_transactions)
                if total_quantity > 0:
                    avg_selling_price = total_amount / total_quantity
        except Exception as e:
            print(f"Error calculating avg selling price: {str(e)}")
            # Continue with empty today_sale_transactions and avg_selling_price = 0
        
        # Combine recent purchase and sale transactions for the timeline
        recent_purchases = InventoryTransaction.query.filter_by(
            dairy_holder_id=current_user.id
        ).order_by(InventoryTransaction.transaction_date.desc()).limit(10).all()
        
        recent_sales = []
        try:
            recent_sales = MilkSaleTransaction.query.filter_by(
                dairy_holder_id=current_user.id
            ).order_by(MilkSaleTransaction.date.desc()).limit(10).all()
        except Exception as e:
            print(f"Error fetching recent sales: {str(e)}")
            # Continue with empty recent_sales
        
        recent_transactions = []
        
        for purchase in recent_purchases:
            recent_transactions.append({
                'type': 'purchase',
                'name': purchase.supplier_name,
                'date': purchase.transaction_date,
                'quantity': purchase.quantity,
                'milk_type': purchase.milk_type,
                'price_per_liter': purchase.price_per_liter,
                'total_amount': purchase.total_amount,
                'fat': purchase.fat_percentage,
                'snf': purchase.snf_percentage,
                'is_paid': purchase.is_paid
            })
        
        for sale in recent_sales:
            recent_transactions.append({
                'type': 'sale',
                'name': sale.buyer_name,
                'date': sale.date,
                'quantity': sale.quantity,
                'milk_type': sale.milk_type,
                'price_per_liter': sale.price_per_liter,
                'total_amount': sale.total_amount,
                'fat': sale.fat_percentage or 0,
                'snf': sale.snf_percentage or 0,
                'is_paid': sale.is_paid
            })
        
        # Sort combined transactions by date (newest first)
        recent_transactions.sort(key=lambda x: x['date'], reverse=True)
        
        return render_template('dairy_holder/milk_manager.html',
                              total_inventory=total_inventory,
                              milk_type_data=milk_type_data,
                              todays_purchases=todays_purchases,
                              todays_sales=todays_sales,
                              suppliers=suppliers,
                              buyers=buyers,
                              avg_purchase_price=avg_purchase_price,
                              avg_selling_price=avg_selling_price,
                              recent_transactions=recent_transactions[:15])  # Limit to 15 most recent
    except Exception as e:
        flash(f"An error occurred while loading the Milk Manager: {str(e)}", "danger")
        print(f"Error in milk_manager: {str(e)}")
        return redirect(url_for('dairy_holder.dashboard')) 
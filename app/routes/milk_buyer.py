from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user, logout_user
from app import db
from app.models.user import UserRole
from app.models.transactions import PurchaseTransaction, Inventory
from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from functools import wraps

milk_buyer = Blueprint('milk_buyer', __name__)

def role_required(view_function):
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
            
        if not current_user.is_milk_buyer():
            flash('You must be a milk buyer to access this page.', 'warning')
            return redirect(url_for('main.role_selection'))
            
        return view_function(*args, **kwargs)
    
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
    
    pending_payments = PurchaseTransaction.query.filter_by(buyer_id=current_user.id, is_paid=False) \
                                          .with_entities(db.func.sum(PurchaseTransaction.total_amount)).scalar() or 0
    
    # Count unique suppliers
    supplier_count = db.session.query(PurchaseTransaction.supplier_name) \
                             .filter(PurchaseTransaction.buyer_id == current_user.id) \
                             .distinct().count()
    
    return render_template('milk_buyer/dashboard.html',
                          purchases=purchases,
                          total_purchased=total_purchased,
                          total_spent=total_spent,
                          pending_payments=pending_payments,
                          supplier_count=supplier_count)

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
    
    # Get all milk types for filter dropdown
    milk_types = db.session.query(PurchaseTransaction.milk_type) \
                         .filter(PurchaseTransaction.buyer_id == current_user.id) \
                         .distinct().all()
    milk_types = [m[0] for m in milk_types if m[0]]
    
    # Get all supplier names for filter dropdown
    suppliers = db.session.query(PurchaseTransaction.supplier_name) \
                        .filter(PurchaseTransaction.buyer_id == current_user.id) \
                        .distinct().all()
    suppliers = [s[0] for s in suppliers]
    
    return render_template('milk_buyer/purchases.html',
                          purchases=purchases,
                          suppliers=suppliers,
                          milk_types=milk_types)

@milk_buyer.route('/add_purchase', methods=['GET', 'POST'])
@role_required
def add_purchase():
    if request.method == 'POST':
        supplier_name = request.form.get('supplier_name')
        milk_type = request.form.get('milk_type')
        quantity = float(request.form.get('quantity'))
        price_per_liter = float(request.form.get('price_per_liter'))
        fat_percentage = float(request.form.get('fat_percentage'))
        snf_percentage = float(request.form.get('snf_percentage'))
        quality_grade = request.form.get('quality_grade')
        source_location = request.form.get('source_location')
        
        # Create new purchase transaction
        purchase = PurchaseTransaction(
            buyer_id=current_user.id,
            supplier_name=supplier_name,
            milk_type=milk_type,
            quantity=quantity,
            price_per_liter=price_per_liter,
            fat_percentage=fat_percentage,
            snf_percentage=snf_percentage,
            total_amount=quantity * price_per_liter,
            quality_grade=quality_grade,
            source_location=source_location,
            date=datetime.utcnow(),
            is_paid=False
        )
        
        db.session.add(purchase)
        db.session.commit()
        
        flash('Purchase transaction added successfully!', 'success')
        return redirect(url_for('milk_buyer.purchases'))
    
    # Get all existing supplier names for the autocomplete
    suppliers = db.session.query(PurchaseTransaction.supplier_name) \
                       .filter(PurchaseTransaction.buyer_id == current_user.id) \
                       .distinct().all()
    suppliers = [s[0] for s in suppliers]
    
    return render_template('milk_buyer/add_purchase.html', suppliers=suppliers)

@milk_buyer.route('/update_payment/<int:purchase_id>', methods=['POST'])
@role_required
def update_payment(purchase_id):
    purchase = PurchaseTransaction.query.get_or_404(purchase_id)
    
    # Verify ownership
    if purchase.buyer_id != current_user.id:
        flash('You do not have permission to update this transaction.', 'danger')
        return redirect(url_for('milk_buyer.purchases'))
    
    purchase.is_paid = True
    purchase.payment_date = datetime.utcnow()
    db.session.commit()
    
    flash('Payment status updated successfully!', 'success')
    return redirect(url_for('milk_buyer.purchases'))

@milk_buyer.route('/suppliers')
@role_required
def suppliers():
    # Get all suppliers and aggregate data
    supplier_data = {}
    
    purchases = PurchaseTransaction.query.filter_by(buyer_id=current_user.id).all()
    
    for purchase in purchases:
        if purchase.supplier_name not in supplier_data:
            supplier_data[purchase.supplier_name] = {
                'name': purchase.supplier_name,
                'total_quantity': 0,
                'total_amount': 0,
                'fat_sum': 0,
                'snf_sum': 0,
                'purchase_count': 0
            }
        
        supplier_data[purchase.supplier_name]['total_quantity'] += purchase.quantity
        supplier_data[purchase.supplier_name]['total_amount'] += purchase.total_amount
        supplier_data[purchase.supplier_name]['fat_sum'] += purchase.fat_percentage
        supplier_data[purchase.supplier_name]['snf_sum'] += purchase.snf_percentage
        supplier_data[purchase.supplier_name]['purchase_count'] += 1
    
    # Calculate averages
    for supplier in supplier_data.values():
        if supplier['purchase_count'] > 0:
            supplier['avg_fat'] = supplier['fat_sum'] / supplier['purchase_count']
            supplier['avg_snf'] = supplier['snf_sum'] / supplier['purchase_count']
            supplier['avg_price'] = supplier['total_amount'] / supplier['total_quantity']
    
    # Convert to list for template
    suppliers = list(supplier_data.values())
    
    # Sort by total quantity (descending)
    suppliers.sort(key=lambda x: x['total_quantity'], reverse=True)
    
    return render_template('milk_buyer/suppliers.html', suppliers=suppliers)

@milk_buyer.route('/reports')
@role_required
def reports():
    # Get date range from request (default to last 30 days)
    end_date = datetime.now()
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)  # Include the end date
    else:
        # Default to last 30 days
        start_date = end_date - timedelta(days=30)
    
    # Query purchases within the date range
    purchases = PurchaseTransaction.query.filter_by(buyer_id=current_user.id) \
                                    .filter(PurchaseTransaction.date >= start_date) \
                                    .filter(PurchaseTransaction.date <= end_date) \
                                    .order_by(PurchaseTransaction.date).all()
    
    # Prepare summary data
    summary = {
        'total_quantity': sum(p.quantity for p in purchases),
        'total_amount': sum(p.total_amount for p in purchases),
        'avg_fat': sum(p.fat_percentage for p in purchases) / len(purchases) if purchases else 0,
        'avg_snf': sum(p.snf_percentage for p in purchases) / len(purchases) if purchases else 0,
        'purchase_count': len(purchases),
        'paid_amount': sum(p.total_amount for p in purchases if p.is_paid),
        'pending_amount': sum(p.total_amount for p in purchases if not p.is_paid)
    }
    
    # Prepare data by milk type
    milk_types = {}
    for purchase in purchases:
        milk_type = purchase.milk_type or 'Unspecified'
        if milk_type not in milk_types:
            milk_types[milk_type] = {
                'quantity': 0,
                'amount': 0,
                'count': 0
            }
        milk_types[milk_type]['quantity'] += purchase.quantity
        milk_types[milk_type]['amount'] += purchase.total_amount
        milk_types[milk_type]['count'] += 1
    
    # Prepare data by supplier
    suppliers = {}
    for purchase in purchases:
        if purchase.supplier_name not in suppliers:
            suppliers[purchase.supplier_name] = {
                'quantity': 0,
                'amount': 0,
                'count': 0
            }
        suppliers[purchase.supplier_name]['quantity'] += purchase.quantity
        suppliers[purchase.supplier_name]['amount'] += purchase.total_amount
        suppliers[purchase.supplier_name]['count'] += 1
    
    # Prepare daily volume data for chart
    daily_volumes = {}
    for purchase in purchases:
        date_str = purchase.date.strftime('%Y-%m-%d')
        if date_str not in daily_volumes:
            daily_volumes[date_str] = {
                'date': date_str,
                'quantity': 0,
                'amount': 0
            }
        daily_volumes[date_str]['quantity'] += purchase.quantity
        daily_volumes[date_str]['amount'] += purchase.total_amount
    
    # Sort daily volumes for chart
    daily_chart_data = sorted(daily_volumes.values(), key=lambda x: x['date'])
    
    return render_template('milk_buyer/reports.html',
                          start_date=start_date.strftime('%Y-%m-%d'),
                          end_date=(end_date - timedelta(days=1)).strftime('%Y-%m-%d'),
                          summary=summary,
                          milk_types=milk_types,
                          suppliers=suppliers,
                          daily_chart_data=daily_chart_data)

@milk_buyer.route('/analytics')
@role_required
def analytics():
    # Get current date and default end date (today)
    end_date = datetime.now().replace(hour=23, minute=59, second=59)
    start_date = end_date - timedelta(days=180)  # Last 6 months
    
    # Get period from request if provided
    period = request.args.get('period', 'last_6_months')
    if period == 'last_30_days':
        start_date = end_date - timedelta(days=30)
    elif period == 'last_90_days':
        start_date = end_date - timedelta(days=90)
    elif period == 'last_year':
        start_date = end_date - timedelta(days=365)
    elif period == 'all_time':
        start_date = datetime(2000, 1, 1)  # Effectively all time
    
    # Get purchase data for the selected period
    purchases = PurchaseTransaction.query.filter_by(buyer_id=current_user.id) \
                                  .filter(PurchaseTransaction.date >= start_date) \
                                  .filter(PurchaseTransaction.date <= end_date) \
                                  .order_by(PurchaseTransaction.date) \
                                  .all()
    
    # Monthly analytics data
    monthly_data = {}
    monthly_quality = {}
    
    # Supplier analytics
    supplier_data = {}
    
    # Quality trends
    fat_data = []
    snf_data = []
    
    # Process purchases for analytics
    for purchase in purchases:
        # Extract month and year
        month_key = purchase.date.strftime('%Y-%m')
        month_name = purchase.date.strftime('%b %Y')
        
        # Initialize month data if not exists
        if month_key not in monthly_data:
            monthly_data[month_key] = {
                'month': month_name,
                'quantity': 0,
                'amount': 0,
                'count': 0
            }
            monthly_quality[month_key] = {
                'month': month_name,
                'fat_sum': 0,
                'snf_sum': 0,
                'count': 0
            }
        
        # Update monthly data
        monthly_data[month_key]['quantity'] += purchase.quantity
        monthly_data[month_key]['amount'] += purchase.total_amount
        monthly_data[month_key]['count'] += 1
        
        # Update monthly quality data
        monthly_quality[month_key]['fat_sum'] += purchase.fat_percentage
        monthly_quality[month_key]['snf_sum'] += purchase.snf_percentage
        monthly_quality[month_key]['count'] += 1
        
        # Update supplier data
        if purchase.supplier_name not in supplier_data:
            supplier_data[purchase.supplier_name] = {
                'quantity': 0,
                'amount': 0,
                'count': 0,
                'fat_sum': 0,
                'snf_sum': 0
            }
        
        supplier_data[purchase.supplier_name]['quantity'] += purchase.quantity
        supplier_data[purchase.supplier_name]['amount'] += purchase.total_amount
        supplier_data[purchase.supplier_name]['count'] += 1
        supplier_data[purchase.supplier_name]['fat_sum'] += purchase.fat_percentage
        supplier_data[purchase.supplier_name]['snf_sum'] += purchase.snf_percentage
        
        # Add quality data for trends
        fat_data.append({
            'date': purchase.date.strftime('%Y-%m-%d'),
            'value': purchase.fat_percentage
        })
        
        snf_data.append({
            'date': purchase.date.strftime('%Y-%m-%d'),
            'value': purchase.snf_percentage
        })
    
    # Calculate averages for monthly quality
    for month in monthly_quality:
        if monthly_quality[month]['count'] > 0:
            monthly_quality[month]['avg_fat'] = monthly_quality[month]['fat_sum'] / monthly_quality[month]['count']
            monthly_quality[month]['avg_snf'] = monthly_quality[month]['snf_sum'] / monthly_quality[month]['count']
    
    # Calculate averages for supplier data
    for supplier in supplier_data:
        if supplier_data[supplier]['count'] > 0:
            supplier_data[supplier]['avg_fat'] = supplier_data[supplier]['fat_sum'] / supplier_data[supplier]['count']
            supplier_data[supplier]['avg_snf'] = supplier_data[supplier]['snf_sum'] / supplier_data[supplier]['count']
            supplier_data[supplier]['avg_price'] = supplier_data[supplier]['amount'] / supplier_data[supplier]['quantity']
    
    # Sort supplier data by quantity (descending)
    sorted_suppliers = sorted(supplier_data.items(), key=lambda x: x[1]['quantity'], reverse=True)
    top_suppliers = dict(sorted_suppliers[:10])  # Top 10 suppliers
    
    # Prepare data for charts
    months = [data['month'] for month_key, data in sorted(monthly_data.items())]
    quantities = [data['quantity'] for month_key, data in sorted(monthly_data.items())]
    amounts = [data['amount'] for month_key, data in sorted(monthly_data.items())]
    
    # Quality chart data
    quality_months = [data['month'] for month_key, data in sorted(monthly_quality.items())]
    fat_values = [data.get('avg_fat', 0) for month_key, data in sorted(monthly_quality.items())]
    snf_values = [data.get('avg_snf', 0) for month_key, data in sorted(monthly_quality.items())]
    
    return render_template('milk_buyer/analytics.html',
                          period=period,
                          months=months,
                          quantities=quantities,
                          amounts=amounts,
                          quality_months=quality_months,
                          fat_values=fat_values,
                          snf_values=snf_values,
                          top_suppliers=top_suppliers,
                          fat_data=fat_data,
                          snf_data=snf_data)

@milk_buyer.route('/inventory')
@role_required
def inventory():
    """Display inventory management page for milk buyers."""
    # Get all inventory items for the current user
    inventory_items = Inventory.query.filter_by(user_id=current_user.id).order_by(Inventory.name).all()
    
    # Prepare inventory summary
    inventory_summary = {
        'total_items': len(inventory_items),
        'low_stock_items': sum(1 for item in inventory_items if item.is_low),
        'expired_items': sum(1 for item in inventory_items if item.is_expired),
        'healthy_items': sum(1 for item in inventory_items if not item.is_low and not item.is_expired)
    }
    
    # Find items expiring soon (within 30 days)
    expiring_soon = [item for item in inventory_items 
                     if item.expiry_date and not item.is_expired 
                     and item.days_to_expiry <= 30]
    expiring_soon.sort(key=lambda x: x.days_to_expiry)
    
    # Find items that need restocking
    need_restock = [item for item in inventory_items if item.is_low]
    need_restock.sort(key=lambda x: x.quantity / x.restock_level)
    
    # Prepare data for stock distribution chart
    types = ['Feed', 'Medicine', 'Equipment', 'Packaging', 'Other']
    type_counts = {}
    for item_type in types:
        type_counts[item_type] = sum(1 for item in inventory_items if item.type == item_type)
    
    type_distribution = [type_counts.get(item_type, 0) for item_type in types]
    
    return render_template('milk_buyer/inventory.html',
                          inventory_items=inventory_items,
                          inventory_summary=inventory_summary,
                          expiring_soon=expiring_soon,
                          need_restock=need_restock,
                          type_distribution=type_distribution)

@milk_buyer.route('/add_inventory', methods=['POST'])
@role_required
def add_inventory():
    """Add a new inventory item."""
    name = request.form.get('name')
    item_type = request.form.get('type')
    quantity = float(request.form.get('quantity'))
    unit = request.form.get('unit')
    restock_level = float(request.form.get('restock_level'))
    notes = request.form.get('notes')
    
    # Handle expiry date (may be empty)
    expiry_date_str = request.form.get('expiry_date')
    expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d') if expiry_date_str else None
    
    # Create new inventory item
    inventory_item = Inventory(
        user_id=current_user.id,
        name=name,
        type=item_type,
        quantity=quantity,
        unit=unit,
        expiry_date=expiry_date,
        restock_level=restock_level,
        notes=notes
    )
    
    db.session.add(inventory_item)
    db.session.commit()
    
    flash('Inventory item added successfully!', 'success')
    return redirect(url_for('milk_buyer.inventory'))

@milk_buyer.route('/edit_inventory', methods=['POST'])
@role_required
def edit_inventory():
    """Edit an existing inventory item."""
    item_id = request.form.get('item_id')
    name = request.form.get('name')
    item_type = request.form.get('type')
    quantity = float(request.form.get('quantity'))
    unit = request.form.get('unit')
    restock_level = float(request.form.get('restock_level'))
    notes = request.form.get('notes')
    
    # Handle expiry date (may be empty)
    expiry_date_str = request.form.get('expiry_date')
    expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d') if expiry_date_str else None
    
    # Get the inventory item and check ownership
    inventory_item = Inventory.query.get_or_404(item_id)
    if inventory_item.user_id != current_user.id:
        flash('You do not have permission to edit this item.', 'danger')
        return redirect(url_for('milk_buyer.inventory'))
    
    # Update item
    inventory_item.name = name
    inventory_item.type = item_type
    inventory_item.quantity = quantity
    inventory_item.unit = unit
    inventory_item.expiry_date = expiry_date
    inventory_item.restock_level = restock_level
    inventory_item.notes = notes
    
    db.session.commit()
    
    flash('Inventory item updated successfully!', 'success')
    return redirect(url_for('milk_buyer.inventory'))

@milk_buyer.route('/delete_inventory', methods=['POST'])
@role_required
def delete_inventory():
    """Delete an inventory item."""
    item_id = request.form.get('item_id')
    
    # Get the inventory item and check ownership
    inventory_item = Inventory.query.get_or_404(item_id)
    if inventory_item.user_id != current_user.id:
        flash('You do not have permission to delete this item.', 'danger')
        return redirect(url_for('milk_buyer.inventory'))
    
    db.session.delete(inventory_item)
    db.session.commit()
    
    flash('Inventory item deleted successfully!', 'success')
    return redirect(url_for('milk_buyer.inventory'))

@milk_buyer.route('/get_inventory_item')
@role_required
def get_inventory_item():
    """Get inventory item data for AJAX requests."""
    item_id = request.args.get('item_id')
    
    # Get the inventory item and check ownership
    inventory_item = Inventory.query.get_or_404(item_id)
    if inventory_item.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    # Format expiry date for input field (YYYY-MM-DD)
    expiry_date = inventory_item.expiry_date.strftime('%Y-%m-%d') if inventory_item.expiry_date else ''
    
    # Return item data as JSON
    return jsonify({
        'id': inventory_item.id,
        'name': inventory_item.name,
        'type': inventory_item.type,
        'quantity': inventory_item.quantity,
        'unit': inventory_item.unit,
        'expiry_date': expiry_date,
        'restock_level': inventory_item.restock_level,
        'notes': inventory_item.notes or ''
    }) 
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from app import db
from app.models.transactions import DairyStock, MilkTransaction
from app.models.user import UserRole, User
from datetime import datetime, timedelta
import csv
import io

dairy_holder = Blueprint('dairy_holder', __name__)

def role_required(view_function):
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_dairy_holder():
            flash('Access denied: You must be a dairy holder to view this page')
            return redirect(url_for('main.index'))
        return view_function(*args, **kwargs)
    decorated_function.__name__ = view_function.__name__
    return decorated_function

@dairy_holder.route('/dashboard')
@role_required
def dashboard():
    # Get stock data
    stocks = DairyStock.query.filter_by(dairy_holder_id=current_user.id) \
                           .order_by(DairyStock.date.desc()) \
                           .limit(10).all()
    
    # Get daily stock data for the past 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    daily_stocks = DairyStock.query.filter_by(dairy_holder_id=current_user.id) \
                                 .filter(DairyStock.date >= thirty_days_ago) \
                                 .order_by(DairyStock.date.asc()) \
                                 .all()
    
    # Calculate statistics
    current_stock = DairyStock.query.filter_by(dairy_holder_id=current_user.id) \
                               .order_by(DairyStock.date.desc()) \
                               .first()
    
    if current_stock:
        current_stock_level = current_stock.total_stock
        avg_fat = current_stock.avg_fat_percentage
        avg_snf = current_stock.avg_snf_percentage
    else:
        current_stock_level = 0
        avg_fat = 0
        avg_snf = 0
    
    # Generate stock chart data (would be rendered in template with Chart.js)
    stock_dates = [stock.date.strftime('%Y-%m-%d') for stock in daily_stocks]
    stock_levels = [stock.total_stock for stock in daily_stocks]
    
    return render_template('dairy_holder/dashboard.html', 
                          stocks=stocks,
                          current_stock=current_stock_level,
                          avg_fat=avg_fat,
                          avg_snf=avg_snf,
                          stock_dates=stock_dates,
                          stock_levels=stock_levels)

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
    # Get all milk sellers
    suppliers = User.query.filter_by(role=UserRole.MILK_SELLER).all()
    
    # Get transaction data for each supplier
    supplier_data = []
    for supplier in suppliers:
        transactions = MilkTransaction.query.filter_by(seller_id=supplier.id).all()
        total_volume = sum(t.quantity for t in transactions) if transactions else 0
        avg_quality = sum(t.fat_percentage for t in transactions) / len(transactions) if transactions else 0
        
        supplier_data.append({
            'supplier': supplier,
            'transaction_count': len(transactions),
            'total_volume': total_volume,
            'avg_quality': avg_quality
        })
    
    return render_template('dairy_holder/suppliers.html', supplier_data=supplier_data)

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
from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.user import User, UserRole

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to appropriate dashboard
    if current_user.is_authenticated:
        if current_user.is_milk_seller():
            return redirect(url_for('milk_seller.dashboard'))
        elif current_user.is_bike_milk_seller():
            return redirect(url_for('bike_milk_seller.dashboard'))
        elif current_user.is_dairy_holder():
            return redirect(url_for('dairy_holder.dashboard'))
        elif current_user.is_milk_buyer():
            return redirect(url_for('milk_buyer.dashboard'))
            
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password, password):
            flash('Please check your login details and try again.')
            return redirect(url_for('auth.login'))
        
        login_user(user)
        
        # Redirect based on user role
        if user.is_milk_seller():
            return redirect(url_for('milk_seller.dashboard'))
        elif user.is_bike_milk_seller():
            return redirect(url_for('bike_milk_seller.dashboard'))
        elif user.is_dairy_holder():
            return redirect(url_for('dairy_holder.dashboard'))
        elif user.is_milk_buyer():
            return redirect(url_for('milk_buyer.dashboard'))
        
        return redirect(url_for('main.index'))
    
    return render_template('auth/login.html')

@auth.route('/register', methods=['GET', 'POST'])
def register():
    # If user is already logged in, redirect to appropriate dashboard
    if current_user.is_authenticated:
        if current_user.is_milk_seller():
            return redirect(url_for('milk_seller.dashboard'))
        elif current_user.is_bike_milk_seller():
            return redirect(url_for('bike_milk_seller.dashboard'))
        elif current_user.is_dairy_holder():
            return redirect(url_for('dairy_holder.dashboard'))
        elif current_user.is_milk_buyer():
            return redirect(url_for('milk_buyer.dashboard'))
            
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')
        role = request.form.get('role')
        phone = request.form.get('phone')
        address = request.form.get('address')
        
        # Check if user already exists
        user = User.query.filter_by(email=email).first()
        
        if user:
            flash('Email address already exists')
            return redirect(url_for('auth.register'))
        
        # Validate role
        if role not in UserRole.get_all_roles():
            flash('Invalid role selected')
            return redirect(url_for('auth.register'))
        
        # Create new user
        new_user = User(
            email=email,
            name=name,
            password=generate_password_hash(password, method='scrypt'),
            role=role,
            phone=phone,
            address=address
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', roles=UserRole.get_all_roles())

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index')) 
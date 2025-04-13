from flask import redirect, url_for, flash
from flask_login import current_user
from functools import wraps

def role_required(role=None):
    def decorator(view_function):
        @wraps(view_function)
        def decorated_function(*args, **kwargs):
            # If user is not authenticated, the login_required decorator should handle it
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            # If no specific role required or user has the role
            if role is None:
                return view_function(*args, **kwargs)
            
            # For string roles like UserRole.DAIRY_HOLDER
            role_name = role
            if hasattr(role, 'lower'):  # If it's a string
                role_name = role.lower()
            
            # Check the role
            role_check_method = f'is_{role_name}'
            if hasattr(current_user, role_check_method) and getattr(current_user, role_check_method)():
                return view_function(*args, **kwargs)
            
            # User doesn't have the required role
            flash(f'You need to be a {role_name} to access this page.', 'warning')
            return redirect(url_for('main.role_selection'))
        
        return decorated_function
    
    # Handle both @role_required and @role_required(UserRole.XXX) syntax
    if callable(role):
        view_func = role
        role = None
        return decorator(view_func)
    
    return decorator 
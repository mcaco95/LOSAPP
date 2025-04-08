from functools import wraps
from flask import abort, flash, redirect, url_for, request, jsonify, current_app
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def operations_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_app.logger.info("=== Operations Required Decorator ===")
        current_app.logger.info(f"User authenticated: {current_user.is_authenticated}")
        current_app.logger.info(f"Has operations_profile attr: {hasattr(current_user, 'operations_profile')}")
        if hasattr(current_user, 'operations_profile'):
            current_app.logger.info(f"Operations profile exists: {bool(current_user.operations_profile)}")
            if current_user.operations_profile:
                current_app.logger.info(f"Operations profile ID: {current_user.operations_profile.id}")
        
        if not current_user.is_authenticated or not hasattr(current_user, 'operations_profile') or not current_user.operations_profile:
            # Check if it's an API request (based on Accept header or URL)
            if request.is_json or request.path.startswith('/operations/call'):
                current_app.logger.error("API request denied - operations access required")
                return jsonify({'success': False, 'message': 'Operations access required'}), 403
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('main.dashboard'))
        
        current_app.logger.info("Operations access granted")
        return f(*args, **kwargs)
    return decorated_function

def referral_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if hasattr(current_user, 'operations_profile') and current_user.operations_profile:
            flash('Operations users do not have access to referral features.', 'error')
            return redirect(url_for('main.operations_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

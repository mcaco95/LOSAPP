from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
from flask_mail import Message
from ..models.user import User
from .. import db, mail
from ..forms import LoginForm, RegisterForm, ForgotPasswordForm, ResetPasswordForm

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        print("User already authenticated, redirecting to dashboard")
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user = User.query.filter_by(email=email).first()
        
        print(f"Login attempt for email: {email}")
        print(f"User found: {user is not None}")
        if user:
            print(f"Is admin: {user.is_admin}")
        
        if user is None or not user.check_password(password):
            flash('Invalid email or password')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=form.remember.data)
        print(f"Login successful for {email}, is_admin: {user.is_admin}")
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('main.dashboard')
        return redirect(next_page)
    
    return render_template('auth/login.html', form=form)

@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = user.generate_reset_token()
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            msg = Message('Password Reset Request',
                        recipients=[user.email])
            msg.body = f'''To reset your password, visit the following link:
{reset_url}

If you did not make this request, simply ignore this email and no changes will be made.
'''
            mail.send(msg)
            flash('Check your email for instructions to reset your password.')
            return redirect(url_for('auth.login'))
        flash('Email address not found.')
        return redirect(url_for('auth.forgot_password'))
    
    return render_template('auth/forgot_password.html', form=form)

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    user = User.query.filter_by(reset_token=token).first()
    if user is None or not user.verify_reset_token(token):
        flash('Invalid or expired reset token.')
        return redirect(url_for('auth.forgot_password'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.clear_reset_token()
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', form=form, token=token)
        

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered')
            return redirect(url_for('auth.register'))
        
        user = User(email=form.email.data, name=form.name.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import qrcode
from io import BytesIO
import base64
from ..decorators import admin_required
from ..models.user import User, db
from ..forms import AdminUserForm, AdminUserEditForm, ChangePasswordForm, ProfilePictureForm

users = Blueprint('users', __name__)

@users.route('/users')
@login_required
@admin_required
def index():
    users_list = User.query.all()
    return render_template('users/index.html', users=users_list)

@users.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    form = AdminUserForm()
    if form.validate_on_submit():
        user = User(
            name=form.name.data,
            email=form.email.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
            flash('User created successfully!', 'success')
            return redirect(url_for('users.index'))
        except Exception as e:
            db.session.rollback()
            flash('Error creating user. Email might be already taken.', 'error')
    return render_template('users/create.html', form=form)

@users.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    user = User.query.get_or_404(id)
    form = AdminUserEditForm(obj=user)
    
    if form.validate_on_submit():
        user.name = form.name.data
        user.email = form.email.data
        if form.password.data:
            user.set_password(form.password.data)
        try:
            db.session.commit()
            flash('User updated successfully!', 'success')
            return redirect(url_for('users.index'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating user. Email might be already taken.', 'error')
    
    return render_template('users/edit.html', form=form, user=user)

@users.route('/users/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    user = User.query.get_or_404(id)
    if user.email == 'simon@logisticsonesource.com':
        flash('Cannot delete admin user!', 'error')
        return redirect(url_for('users.index'))
    
    try:
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting user.', 'error')
    
    return redirect(url_for('users.index'))

@users.route('/profile', methods=['GET'])
@login_required
def profile():
    password_form = ChangePasswordForm()
    picture_form = ProfilePictureForm()
    
    # Generate QR code for referral link
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"https://logisticsonesource.com/ref/{current_user.unique_link}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert QR code to base64 for embedding in HTML
    buffered = BytesIO()
    qr_img.save(buffered, format="PNG")
    qr_code_url = f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}"
    
    return render_template('dashboard/user/profile.html',
                         password_form=password_form,
                         picture_form=picture_form,
                         qr_code_url=qr_code_url)

@users.route('/profile/change-password', methods=['POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.check_password(form.current_password.data):
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Password updated successfully!', 'success')
        else:
            flash('Current password is incorrect.', 'error')
    return redirect(url_for('users.profile'))

@users.route('/profile/update-picture', methods=['POST'])
@login_required
def update_profile_picture():
    form = ProfilePictureForm()
    if form.validate_on_submit():
        file = form.picture.data
        filename = secure_filename(file.filename)
        
        # Create user-specific directory if it doesn't exist
        user_upload_dir = os.path.join(current_app.static_folder, 'uploads', str(current_user.id))
        os.makedirs(user_upload_dir, exist_ok=True)
        
        # Save file
        file_path = os.path.join(user_upload_dir, filename)
        file.save(file_path)
        
        # Update user's profile picture path (relative to static folder)
        current_user.profile_picture = f'uploads/{current_user.id}/{filename}'
        db.session.commit()
        
        flash('Profile picture updated successfully!', 'success')
    else:
        flash('Invalid file type. Please upload an image file.', 'error')
    return redirect(url_for('users.profile'))

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import RadialGradiantColorMask
from PIL import Image, ImageDraw
from io import BytesIO
import base64
from ..decorators import admin_required
from ..models.user import User, db
from ..forms import AdminUserForm, AdminUserEditForm, ChangePasswordForm, ProfilePictureForm
from ..models.operations_user import OperationsUser

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
        user.is_admin = form.is_admin.data
        
        if form.password.data:
            user.set_password(form.password.data)
            
        # Handle operations user settings
        if form.is_operations.data:
            # Create or update operations profile
            if not user.operations_profile:
                ops_user = OperationsUser(
                    user_id=user.id,
                    phone_number=form.phone_number.data,
                    extension=form.extension.data,
                    role=form.operations_role.data
                )
                db.session.add(ops_user)
            else:
                user.operations_profile.phone_number = form.phone_number.data
                user.operations_profile.extension = form.extension.data
                user.operations_profile.role = form.operations_role.data
        else:
            # Remove operations profile if exists
            if user.operations_profile:
                db.session.delete(user.operations_profile)
        
        try:
            db.session.commit()
            flash('User updated successfully!', 'success')
            return redirect(url_for('users.index'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating user. The email might be already taken or extension is in use.', 'error')
    
    # Pre-populate operations fields if user has operations profile
    if user.operations_profile:
        form.is_operations.data = True
        form.phone_number.data = user.operations_profile.phone_number
        form.extension.data = user.operations_profile.extension
        form.operations_role.data = user.operations_profile.role
    
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
    
    # Generate QR code for referral link with the correct URL format
    qr = qrcode.QRCode(
        version=None,  # Let it determine the best version
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction for logo
        box_size=10,
        border=4
    )
    
    # Use the /r/unique_link format for the referral URL
    qr.add_data(f"{request.host_url}r/{current_user.unique_link}")
    qr.make(fit=True)
    
    # Create basic QR code in black
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGBA')
    
    # Load and prepare the logo
    logo_path = os.path.join(current_app.static_folder, 'img/LOS_watermark_red.png')
    logo = Image.open(logo_path).convert('RGBA')
    
    # Calculate logo size (about 25% of QR code)
    qr_width, qr_height = qr_img.size
    logo_size = int(qr_width * 0.25)
    logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
    
    # Calculate position to center the logo
    box = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)
    
    # Create a mask for smooth edges
    mask = Image.new('L', logo.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (logo_size, logo_size)], radius=int(logo_size*0.1), fill=255)
    
    # Paste the logo onto the QR code
    qr_img.paste(logo, box, mask)
    
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

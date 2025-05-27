from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
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
from ..decorators import admin_required, operations_required
from ..models.user import User, db
from ..forms import AdminUserForm, AdminUserEditForm, ChangePasswordForm, ProfilePictureForm
from ..models.operations_user import OperationsUser
from ..models.sales_user import SalesUser

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
    # Instantiate form differently for GET and POST
    if request.method == 'POST':
        form = AdminUserEditForm() # Instantiate empty form for POST
    else: # GET request
        form = AdminUserEditForm(obj=user) # Populate form from object for GET
    
    if form.validate_on_submit(): # Process submitted data
        # Manually update user object from validated form data
        user.name = form.name.data
        user.email = form.email.data
        user.is_admin = form.is_admin.data
        
        if form.password.data:
            user.set_password(form.password.data)
            
        # Handle operations user settings
        if form.is_operations.data:
            ops_phone_value = form.phone_number.data.strip() if form.phone_number.data else None
            ops_phone_value = None if ops_phone_value == '' else ops_phone_value
            ops_ext_value = form.extension.data.strip() if form.extension.data else None
            ops_ext_value = None if ops_ext_value == '' else ops_ext_value
            ops_role_value = form.operations_role.data or 'operator'
            
            if not user.operations_profile:
                # Make sure to check for unique constraint violations here too eventually
                ops_user = OperationsUser(
                    user_id=user.id,
                    phone_number=ops_phone_value,
                    extension=ops_ext_value,
                    role=ops_role_value
                )
                db.session.add(ops_user)
            else:
                user.operations_profile.phone_number = ops_phone_value
                user.operations_profile.extension = ops_ext_value
                user.operations_profile.role = ops_role_value
        elif user.operations_profile: # If checkbox unchecked and profile exists
            current_app.logger.info(f"Attempting to DELETE operations profile for user {id}")
            db.session.delete(user.operations_profile)

        # Handle sales user settings
        if form.is_sales.data:
            sales_phone_value = form.sales_phone_number.data.strip() if form.sales_phone_number.data else None
            sales_phone_value = None if sales_phone_value == '' else sales_phone_value
            sales_extension_value = form.sales_extension.data.strip() if form.sales_extension.data else None
            sales_extension_value = None if sales_extension_value == '' else sales_extension_value
            # Explicitly use the validated form data for role
            sales_role_value = form.sales_role.data
            # Ensure 'Not Sales' selection translates to a default if needed, or handle appropriately
            if not sales_role_value: # If user selected '-- Not Sales --' which has value ''
                 sales_role_value = 'sales_rep' # Or raise error, or handle based on requirements
                 current_app.logger.warning(f"Sales role selected as empty for user {id}, defaulting to 'sales_rep'. Review requirements if this isn't desired.")

            if not user.sales_profile:
                current_app.logger.info(f"Attempting to CREATE sales profile for user {id} with role {sales_role_value}")
                sales_user = SalesUser(
                    user_id=user.id,
                    phone_number=sales_phone_value,
                    extension=sales_extension_value,
                    role=sales_role_value # Use processed value
                )
                db.session.add(sales_user)
            else:
                current_app.logger.info(f"Attempting to UPDATE sales profile for user {id}")
                current_app.logger.info(f"  - Original Role: {user.sales_profile.role}")
                current_app.logger.info(f"  - Form Role Value: {form.sales_role.data}") 
                current_app.logger.info(f"  - Setting Role To: {sales_role_value}")
                user.sales_profile.phone_number = sales_phone_value
                user.sales_profile.extension = sales_extension_value
                user.sales_profile.role = sales_role_value # Directly assign validated form value
                current_app.logger.info(f"  - Role After Assignment: {user.sales_profile.role}")
        elif user.sales_profile: # If checkbox unchecked and profile exists
            current_app.logger.info(f"Attempting to DELETE sales profile for user {id}")
            db.session.delete(user.sales_profile)
            # Optionally ensure the relationship is cleared on the user object
            # user.sales_profile = None # Might help if delete alone isn't sufficient
        
        try:
            db.session.commit()
            flash('User updated successfully!', 'success')
            return redirect(url_for('users.index'))
        except Exception as e:
            db.session.rollback()
            # Make error message more generic as conflicts could be email, ops ext, or sales ext
            current_app.logger.error(f"Error updating user {id}: {str(e)}") 
            flash('Error updating user. The email or extension might be already taken/in use.', 'error') 
    
    # Pre-populate operations fields - This is now done ONLY on GET request by form(obj=user)
    # Pre-populate sales fields - This is now done ONLY on GET request by form(obj=user)

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

@users.route('/users/operations', methods=['GET'])
@login_required
@operations_required
def get_operations_users():
    """Get all users with operations access"""
    try:
        users = User.query.join(OperationsUser).all()
        
        return jsonify({
            'status': 'success',
            'users': [{
                'id': user.id,
                'name': user.name,
                'email': user.email
            } for user in users]
        })
        
    except Exception as e:
        current_app.logger.error(f"Error fetching operations users: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch operations users'
        }), 500

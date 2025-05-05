from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SubmitField, HiddenField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')

class RegisterForm(FlaskForm):
    name = StringField('Your Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Send Reset Link')

class AdminUserForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        EqualTo('password', message='Passwords must match')
    ])

class AdminUserEditForm(FlaskForm):
    id = HiddenField('ID')
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[Optional()])
    is_admin = BooleanField('Admin Access')
    
    # Operations User Fields
    is_operations = BooleanField('Operations Access')
    phone_number = StringField('Phone Number', validators=[Optional()])
    extension = StringField('Extension', validators=[Optional()])
    operations_role = SelectField('Operations Role', 
        choices=[
            ('', 'Not Operations'),
            ('operator', 'Operator'),
            ('supervisor', 'Supervisor'),
            ('manager', 'Manager')
        ], 
        validators=[Optional()]
    )

    # Sales User Fields
    is_sales = BooleanField('Sales Access')
    sales_phone_number = StringField('Sales Phone Number', validators=[Optional()])
    sales_extension = StringField('Sales Extension', validators=[Optional()])
    sales_role = SelectField('Sales Role',
        choices=[
            ('', 'Not Sales'),
            ('sales_rep', 'Sales Rep'),
            ('sales_manager', 'Sales Manager')
        ],
        validators=[Optional()]
    )

    def __init__(self, *args, **kwargs):
        super(AdminUserEditForm, self).__init__(*args, **kwargs)
        user_obj = kwargs.get('obj', None)
        if hasattr(user_obj, 'operations_profile'):
            ops_profile = user_obj.operations_profile
            if ops_profile:
                self.is_operations.data = True
                self.phone_number.data = ops_profile.phone_number
                self.extension.data = ops_profile.extension
                self.operations_role.data = ops_profile.role
        # Populate sales fields if user has sales profile
        if hasattr(user_obj, 'sales_profile'):
            sales_profile = user_obj.sales_profile
            if sales_profile:
                self.is_sales.data = True
                self.sales_phone_number.data = sales_profile.phone_number
                self.sales_extension.data = sales_profile.extension
                self.sales_role.data = sales_profile.role

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Reset Password')

class RedirectUrlForm(FlaskForm):
    url = StringField('Redirect URL', validators=[
        DataRequired(),
        Length(max=500, message='URL must be less than 500 characters')
    ])
    submit = SubmitField('Update Redirect URL')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match')
    ])

class ProfilePictureForm(FlaskForm):
    picture = FileField('Profile Picture', validators=[
        DataRequired(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')
    ])

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

    def __init__(self, *args, **kwargs):
        super(AdminUserEditForm, self).__init__(*args, **kwargs)
        # If user is operations, populate operations fields
        if hasattr(kwargs.get('obj', None), 'operations_profile'):
            ops_profile = kwargs['obj'].operations_profile
            if ops_profile:
                self.is_operations.data = True
                self.phone_number.data = ops_profile.phone_number
                self.extension.data = ops_profile.extension
                self.operations_role.data = ops_profile.role

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

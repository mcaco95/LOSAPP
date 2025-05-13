from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, BooleanField, SubmitField, HiddenField, SelectField, TextAreaField, DateField, FloatField, IntegerField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, NumberRange, URL
from wtforms_sqlalchemy.fields import QuerySelectField
from flask_login import current_user

# Import models for choices and QuerySelectField
from .models.crm_account import CrmAccount, CRM_ACCOUNT_STATUSES # Assuming CrmAccount is in models
from .models.contact import Contact, CONTACT_STATUSES, CONTACT_SOURCES # Import status and source lists, ADDED Contact
from .models.note import Note
from .models.task import Task, TASK_STATUSES, TASK_PRIORITIES # Added Task model and constants
from .models.deal import Deal, DEAL_STAGES # Added Deal model and stages
from .models.custom_field import CustomFieldType, CustomFieldAppliesTo
from .models.call_log import CALL_OUTCOMES # Added for CallLogDetailForm

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

# +++ CRM FORMS START HERE +++

def get_user_crm_accounts():
    """Query factory for CrmAccount QuerySelectField, filters by current sales_rep."""
    if hasattr(current_user, 'sales_profile') and current_user.sales_profile:
        return CrmAccount.query.filter_by(sales_rep_id=current_user.sales_profile.id).order_by(CrmAccount.name).all()
    return []

class ContactForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=100)])
    last_name = StringField('Last Name', validators=[Optional(), Length(max=100)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    phone_number = StringField('Phone Number', validators=[DataRequired(), Length(max=30)])
    job_title = StringField('Job Title', validators=[Optional(), Length(max=100)])
    
    crm_account = QuerySelectField(
        'Company/Account',
        query_factory=get_user_crm_accounts,
        get_label='name',
        allow_blank=True,
        blank_text='-- Select Company (Optional)',
        validators=[Optional()]
    )
    
    status = SelectField(
        'Status', 
        choices=[(status, status) for status in CONTACT_STATUSES], 
        validators=[DataRequired()]
    )
    source = SelectField(
        'Source', 
        choices=[('', '-- Select Source (Optional) --')] + [(source, source) for source in CONTACT_SOURCES],
        validators=[Optional()]
    )
    
    submit = SubmitField('Save Contact')

# You might want to add a CrmAccountForm later as well
# class CrmAccountForm(FlaskForm):
#     name = StringField('Company Name', validators=[DataRequired(), Length(max=255)])
#     website = StringField('Website', validators=[Optional(), Length(max=255)])
#     industry = StringField('Industry', validators=[Optional(), Length(max=100)])
#     phone_number = StringField('Company Phone', validators=[Optional(), Length(max=30)])
#     address = TextAreaField('Address', validators=[Optional()])
#     status = SelectField('Status', choices=[(s, s) for s in CRM_ACCOUNT_STATUSES], validators=[Optional()])
#     custom_data = TextAreaField('Additional Information (JSON format)', validators=[Optional()])
#     submit = SubmitField('Save Company')

class NoteForm(FlaskForm):
    content = TextAreaField('Note Content', validators=[DataRequired()])
    submit = SubmitField('Add Note')

# --- CrmAccount Form --- 
class CrmAccountForm(FlaskForm):
    name = StringField('Company Name', validators=[DataRequired()])
    website = StringField('Website', validators=[Optional(), URL()])
    phone_number = StringField('Main Phone Number', validators=[Optional()])
    industry = StringField('Industry', validators=[Optional()])
    
    # REMOVING these fields for now
    # address_street = StringField('Street Address', validators=[Optional()])
    # address_city = StringField('City', validators=[Optional()])
    # address_state = StringField('State/Province', validators=[Optional()])
    # address_zip = StringField('ZIP/Postal Code', validators=[Optional()])
    # address_country = StringField('Country', validators=[Optional()])
    
    # Keep the general address field for now
    address = TextAreaField('Address (General)', validators=[Optional()]) 
    
    # Status field
    # Use choices defined in the model or config
    status_choices = [('-', '-- Select Status --')] + [(s, s) for s in CRM_ACCOUNT_STATUSES]
    status = SelectField('Status', choices=status_choices, validators=[Optional()])
    
    submit = SubmitField('Save Account')

# --- CSV Import Form --- #
class ImportCsvForm(FlaskForm):
    import_type = SelectField('Import Type', choices=[('contacts', 'Contacts'), ('accounts', 'Accounts')], validators=[DataRequired()])
    csv_file = FileField('CSV File', validators=[FileRequired(), FileAllowed(['csv'], 'CSV files only!')])
    submit = SubmitField('Upload and Preview Mapping')

# New TaskForm
class TaskForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=1, max=255)])
    description = TextAreaField('Description')
    due_date = DateField('Due Date', format='%Y-%m-%d', validators=[Optional()])
    status = SelectField('Status', choices=TASK_STATUSES, validators=[DataRequired()])
    priority = SelectField('Priority', choices=TASK_PRIORITIES, validators=[DataRequired()])
    
    # QuerySelectFields for linking to Contact and CrmAccount
    # These need a query_factory, typically set in the route
    contact_id = QuerySelectField('Link to Contact (Optional)', 
                                query_factory=lambda: Contact.query.order_by(Contact.first_name).all(),
                                get_label=lambda contact: f"{contact.full_name} (ID: {contact.id})",
                                allow_blank=True,
                                blank_text='-- Select Contact --',
                                validators=[Optional()])
                                
    crm_account_id = QuerySelectField('Link to Account (Optional)',
                                 query_factory=lambda: CrmAccount.query.order_by(CrmAccount.name).all(),
                                 get_label=lambda account: f"{account.name} (ID: {account.id})",
                                 allow_blank=True,
                                 blank_text='-- Select Account --',
                                 validators=[Optional()])
                                 
    deal_id = QuerySelectField('Associated Deal', 
                                 query_factory=lambda: Deal.query.order_by(Deal.name),
                                 get_label='name',
                                 allow_blank=True,
                                 blank_text='-- Select Deal --',
                                 validators=[Optional()])
                                 
    submit = SubmitField('Save Task')

# New DealForm
class DealForm(FlaskForm):
    name = StringField('Deal Name', validators=[DataRequired(), Length(max=255)])
    description = TextAreaField('Description', validators=[Optional()])
    amount = FloatField('Amount', validators=[DataRequired(message="Please enter a valid amount.")], default=0.0)
    stage = SelectField('Stage', choices=DEAL_STAGES, validators=[DataRequired()])
    expected_close_date = DateField('Expected Close Date', format='%Y-%m-%d', validators=[Optional()])
    probability = IntegerField('Probability (%)', validators=[Optional(), NumberRange(min=0, max=100)])

    crm_account_id = QuerySelectField(
        'Account',
        query_factory=lambda: CrmAccount.query.filter_by(sales_rep_id=current_user.sales_profile.id).order_by(CrmAccount.name).all() if hasattr(current_user, 'sales_profile') and current_user.sales_profile else [],
        get_label='name',
        allow_blank=False, # An account is typically required for a deal
        validators=[DataRequired(message="Please select an account.")]
    )

    contact_id = QuerySelectField(
        'Primary Contact (Optional)',
        query_factory=lambda: Contact.query.filter_by(sales_rep_id=current_user.sales_profile.id).order_by(Contact.first_name).all() if hasattr(current_user, 'sales_profile') and current_user.sales_profile else [],
        get_label='full_name',
        allow_blank=True,
        blank_text='-- Select Contact --',
        validators=[Optional()]
    )
    
    submit = SubmitField('Save Deal')

# Form for linking a contact to a company directly
class LinkContactToCompanyForm(FlaskForm):
    crm_account = QuerySelectField(
        'Company/Account',
        query_factory=get_user_crm_accounts, # Reuse the existing query factory
        get_label='name',
        allow_blank=True, # Allow unlinking by selecting blank
        blank_text='-- Unlink/Select No Company --',
        validators=[Optional()]
    )
    submit = SubmitField('Update Company Link')

# --- Custom Field Definition Form --- #
class CustomFieldDefinitionForm(FlaskForm):
    name = StringField('Field Name', 
                       validators=[DataRequired(), Length(max=100)],
                       description='The label that will be shown for this field (e.g., \'Lead Score\', \'Contract Renewal Date\').')
    
    field_type = SelectField('Field Type', 
                             choices=[(ft.value, ft.name.replace('_', ' ').title()) for ft in CustomFieldType],
                             validators=[DataRequired()],
                             description='The type of data this field will hold.')
    
    applies_to = SelectField('Applies To', 
                             choices=[(at.value, at.name.replace('_', ' ').title()) for at in CustomFieldAppliesTo],
                             validators=[DataRequired()],
                             description='Which type of record this field is for (Contact or Account).')

    # Options field, specifically for dropdowns
    options = TextAreaField('Dropdown Options (one per line)', 
                            validators=[Optional()], 
                            render_kw={'rows': 4},
                            description='Required only if Field Type is \'Dropdown\'. Enter each choice on a new line.')

    submit = SubmitField('Save Custom Field')

    def validate_options(self, field):
        # Custom validator: 'options' is required if 'field_type' is DROPDOWN
        if self.field_type.data == CustomFieldType.DROPDOWN.value:
            if not field.data or not field.data.strip():
                raise ValidationError('Dropdown Options are required when the Field Type is Dropdown.')
            # Optional: Validate that options are unique or meet other criteria
            lines = [line.strip() for line in field.data.strip().split('\n') if line.strip()]
            if not lines:
                 raise ValidationError('Dropdown Options cannot be empty or just whitespace when the Field Type is Dropdown.')
            if len(lines) != len(set(lines)):
                raise ValidationError('Dropdown options must be unique.')

# +++ Call Log Detail Form +++
class CallLogDetailForm(FlaskForm):
    outcome = SelectField('Call Outcome',
                          choices=[('', '-- Select Outcome --')] + CALL_OUTCOMES,
                          validators=[Optional()])
    notes = TextAreaField('Notes', validators=[Optional()])
    contact_id = QuerySelectField('Linked Contact',
                                query_factory=lambda: Contact.query.filter_by(sales_rep_id=current_user.sales_profile.id).order_by(Contact.first_name).all() if hasattr(current_user, 'sales_profile') and current_user.sales_profile else Contact.query.order_by(Contact.first_name).all(), # Fallback for non-sales users or general view
                                get_label=lambda contact: f"{contact.full_name} (ID: {contact.id})",
                                allow_blank=True,
                                blank_text='-- Unlink/Select Contact --',
                                validators=[Optional()])
    submit = SubmitField('Update Call Log')

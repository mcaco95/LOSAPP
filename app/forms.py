from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, BooleanField, SubmitField, HiddenField, SelectField, TextAreaField, DateField, FloatField, IntegerField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, NumberRange, URL
from wtforms_sqlalchemy.fields import QuerySelectField
from flask_login import current_user
import sys # Temporary for debugging
from sqlalchemy import or_, false # Added false
from wtforms.utils import unset_value # Add this import

# Import models for choices and QuerySelectField
from .models.crm_account import CrmAccount, CRM_ACCOUNT_STATUSES # Assuming CrmAccount is in models
from .models.contact import Contact, CONTACT_STATUSES, CONTACT_SOURCES # Import status and source lists, ADDED Contact
from .models.note import Note
from .models.task import Task, TASK_STATUSES, TASK_PRIORITIES # Added Task model and constants
from .models.deal import Deal, DEAL_STAGES # Added Deal model and stages
from .models.custom_field import CustomFieldType, CustomFieldAppliesTo
from .models.call_log import CALL_OUTCOMES # Added for CallLogDetailForm
from .models.user import User # Ensure User model is imported for SalesUser relationship
from .models.sales_user import SalesUser # Import SalesUser for the new field

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

# MODIFIED: Renamed and returns a query object, sales managers see all accounts
def get_user_crm_accounts_query():
    """Query factory for CrmAccount QuerySelectField. 
    Sales reps see their accounts. Sales managers see all accounts.
    Returns a query object."""
    if hasattr(current_user, 'sales_profile') and current_user.sales_profile:
        if current_user.sales_profile.role == 'sales_manager':
            return CrmAccount.query # Sales managers see all accounts
        else: # sales_rep
            return CrmAccount.query.filter(CrmAccount.sales_rep_id == current_user.sales_profile.id)
    return CrmAccount.query.filter(false()) # No sales profile, or no specific logic, yields no results

class ContactForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=100)])
    last_name = StringField('Last Name', validators=[Optional(), Length(max=100)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    phone_number = StringField('Phone Number', validators=[DataRequired(), Length(max=30)])
    job_title = StringField('Job Title', validators=[Optional(), Length(max=100)])
    
    crm_account = QuerySelectField(
        'Company/Account',
        get_label='name',
        allow_blank=True,
        blank_text='-- Select Company (Optional) --',
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

    def __init__(self, formdata=None, obj=None, **kwargs):
        super(ContactForm, self).__init__(formdata=formdata, obj=obj, **kwargs)

        current_crm_account_query_base = get_user_crm_accounts_query()

        if hasattr(current_user, 'sales_profile') and current_user.sales_profile and current_user.sales_profile.role == 'sales_manager':
            # Managers see all accounts in the dropdown.
            self.crm_account.query = current_crm_account_query_base.order_by(CrmAccount.name)
        else:
            # Non-managers: Dropdown should show their accounts + the contact's currently assigned account (if any).
            users_accounts_filter_expression = current_crm_account_query_base.whereclause

            if obj and obj.crm_account_id:
                condition_current_obj_account = (CrmAccount.id == obj.crm_account_id)

                if users_accounts_filter_expression is not None:
                    # Combine user's default accounts filter with the current object's account
                    # This works even if users_accounts_filter_expression is false() from get_user_crm_accounts_query
                    final_filter = or_(users_accounts_filter_expression, condition_current_obj_account)
                else:
                    # Fallback if base query had no filter (shouldn't happen for non-manager via get_user_crm_accounts_query)
                    final_filter = condition_current_obj_account
                
                self.crm_account.query = CrmAccount.query.filter(final_filter).order_by(CrmAccount.name)
            else:
                # No specific contact object or it's not linked to an account.
                # Use the base query for the user (which is already filtered for non-managers by sales_rep_id or to false()).
                self.crm_account.query = current_crm_account_query_base.order_by(CrmAccount.name)

        self.crm_account.query_factory = None # Crucial: disable factory if .query is set

        # For the logic below, use the 'formdata' and 'obj' parameters
        # that were passed into this __init__ method, NOT self.formdata or self.obj.

        field_name_srid = 'sales_rep_id'
        field_name_srid_hidden = 'sales_rep_id_hidden'
        processed_dynamic_srid_field = False

        if hasattr(current_user, 'sales_profile') and current_user.sales_profile and current_user.sales_profile.role == 'sales_manager':
            unbound_field = QuerySelectField(
                'Assigned Sales Rep',
                query_factory=lambda: SalesUser.query.join(User).order_by(User.name).all(),
                get_label=lambda x: x.user.name if x.user else 'Unknown User',
                allow_blank=True,
                blank_text='-- Unassigned --',
                validators=[Optional()]
            )
            bound_field = unbound_field.bind(form=self, name=field_name_srid, prefix=self._prefix, _meta=self.meta)
            setattr(self, field_name_srid, bound_field)
            self._fields[field_name_srid] = bound_field
            
            data_for_field = getattr(obj, 'sales_rep', unset_value) 
            bound_field.process(formdata.getlist(field_name_srid) if formdata else None, data=data_for_field)
            processed_dynamic_srid_field = True
            
            if not hasattr(bound_field, '_formdata'):
                bound_field._formdata = None 

        elif hasattr(current_user, 'sales_profile') and current_user.sales_profile: # This is a sales_rep
            default_value_for_hidden = obj.sales_rep_id if obj and obj.sales_rep_id else current_user.sales_profile.id
            unbound_hidden_field = HiddenField(default=default_value_for_hidden) 
            
            bound_hidden_field = unbound_hidden_field.bind(form=self, name=field_name_srid_hidden, prefix=self._prefix, _meta=self.meta)
            setattr(self, field_name_srid_hidden, bound_hidden_field)
            self._fields[field_name_srid_hidden] = bound_hidden_field
            
            bound_hidden_field.process(formdata.getlist(field_name_srid_hidden) if formdata else None, data=default_value_for_hidden)
            processed_dynamic_srid_field = True

            if not hasattr(bound_hidden_field, '_formdata'):
                bound_hidden_field._formdata = None 
        
        # If no dynamic sales_rep_id field was processed (e.g. user has no sales_profile), ensure no lingering field
        if not processed_dynamic_srid_field:
            if field_name_srid in self._fields: del self._fields[field_name_srid]
            if hasattr(self, field_name_srid): delattr(self, field_name_srid)
            if field_name_srid_hidden in self._fields: del self._fields[field_name_srid_hidden]
            if hasattr(self, field_name_srid_hidden): delattr(self, field_name_srid_hidden)

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

    def __init__(self, formdata=None, obj=None, **kwargs):
        super(CrmAccountForm, self).__init__(formdata=formdata, obj=obj, **kwargs)
        
        field_name_srid = 'sales_rep_id'
        field_name_srid_hidden = 'sales_rep_id_hidden'
        processed_dynamic_srid_field = False # Flag to track if we handled SRID field

        if hasattr(current_user, 'sales_profile') and current_user.sales_profile and current_user.sales_profile.role == 'sales_manager':
            # Manager: Add QuerySelectField for sales_rep_id
            if field_name_srid_hidden in self._fields: # Clean up hidden field if it exists from a different context
                del self._fields[field_name_srid_hidden]
            if hasattr(self, field_name_srid_hidden):
                delattr(self, field_name_srid_hidden)

            unbound_field = QuerySelectField(
                'Assigned Sales Rep',
                query_factory=lambda: SalesUser.query.join(User).order_by(User.name).all(),
                get_label=lambda sr: sr.user.name if sr.user else 'Unknown Rep',
                allow_blank=True,
                blank_text='-- Unassigned --',
                validators=[Optional()] # Added Optional validator
            )
            # Bind the field to the form instance
            bound_field = unbound_field.bind(form=self, name=field_name_srid, prefix=self._prefix, _meta=self.meta)
            setattr(self, field_name_srid, bound_field) # Make it an attribute of the form
            self._fields[field_name_srid] = bound_field   # Add to form's _fields dictionary

            # Explicitly process the field using the original formdata and obj's relevant data
            # The `bind` method above should call `process`, but we ensure it here with correct data.
            # `data` should be the actual SalesUser object if `obj` has `sales_rep`.
            data_for_field = getattr(obj, 'sales_rep', unset_value) # Use 'sales_rep' if obj is CrmAccount
            
            # Process with the formdata specific to this field, or None if not in formdata
            # And data from the object if available.
            field_formdata = formdata.getlist(field_name_srid) if formdata else None
            bound_field.process(field_formdata, data=data_for_field)
            
            # Safeguard: Ensure _formdata attribute exists, as QuerySelectField expects it.
            # It should be None if no form data was provided for this field.
            if not hasattr(bound_field, '_formdata'):
                bound_field._formdata = None # Explicitly set if missing after process

            processed_dynamic_srid_field = True
        
        elif hasattr(current_user, 'sales_profile'): # Non-manager sales user
            # Non-Manager: Add HiddenField for sales_rep_id_hidden
            if field_name_srid in self._fields: # Clean up QuerySelectField if it exists
                del self._fields[field_name_srid]
            if hasattr(self, field_name_srid):
                delattr(self, field_name_srid)

            default_value_for_hidden = current_user.sales_profile.id # Default to current user's ID
            if obj and obj.sales_rep_id is not None: # If editing, use existing ID
                default_value_for_hidden = obj.sales_rep_id
            
            unbound_hidden_field = HiddenField(default=str(default_value_for_hidden))
            bound_hidden_field = unbound_hidden_field.bind(form=self, name=field_name_srid_hidden, prefix=self._prefix, _meta=self.meta)
            setattr(self, field_name_srid_hidden, bound_hidden_field)
            self._fields[field_name_srid_hidden] = bound_hidden_field
            
            field_formdata = formdata.getlist(field_name_srid_hidden) if formdata else None
            bound_hidden_field.process(field_formdata, data=str(default_value_for_hidden))

            if not hasattr(bound_hidden_field, '_formdata'):
                bound_hidden_field._formdata = None
            
            processed_dynamic_srid_field = True

        # If no sales_profile, or some other case where neither field was added, ensure no lingering fields.
        if not processed_dynamic_srid_field:
            if field_name_srid in self._fields: del self._fields[field_name_srid]
            if hasattr(self, field_name_srid): delattr(self, field_name_srid)
            if field_name_srid_hidden in self._fields: del self._fields[field_name_srid_hidden]
            if hasattr(self, field_name_srid_hidden): delattr(self, field_name_srid_hidden)

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
        query_factory=get_user_crm_accounts_query, # Reuse the existing query factory
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

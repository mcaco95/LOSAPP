from flask import Blueprint, render_template, redirect, request, url_for, jsonify, flash, current_app, Response, session, g
from flask_login import login_required, current_user
from ..decorators import sales_required # Import the sales decorator
from flask_wtf.csrf import generate_csrf, validate_csrf # Added validate_csrf
from wtforms.validators import ValidationError # Added ValidationError
# --- ADDED WTForms imports for dynamic fields ---
from wtforms import StringField, IntegerField, DateField as WTDatefield, SelectField, BooleanField
from wtforms.validators import Optional, NumberRange # Added Optional, NumberRange
# --- END ADDED ---
from sqlalchemy import desc, or_, func, case, cast, Date # Added desc, or_, func, case, cast, Date
# Import necessary components
from .. import db, csrf
from ..services.call_manager import CallManager
from ..models.call_log import CallLog, CALL_OUTCOMES # Import CALL_OUTCOMES
from ..models.sales_user import SalesUser # Import SalesUser
from ..models.crm_account import CrmAccount, CRM_ACCOUNT_STATUSES # Added CrmAccount model & statuses
from ..models.contact import Contact, CONTACT_STATUSES, CONTACT_SOURCES  # Added Contact model & statuses/sources
from ..models.note import Note # Added Note model
from ..models.task import Task, TASK_STATUSES, TASK_PRIORITIES # Import Task model and constants
from ..models.deal import Deal, DEAL_STAGES # Import Deal model and constants
from ..forms import ContactForm, NoteForm, CrmAccountForm, ImportCsvForm, TaskForm, DealForm, LinkContactToCompanyForm, CustomFieldDefinitionForm, get_user_crm_accounts_query # Added LinkContactToCompanyForm and CustomFieldDefinitionForm, and get_user_crm_accounts_query
from ..forms import CallLogDetailForm # Added CallLogDetailForm
from ..models.custom_field import CustomFieldDefinition, CustomFieldValue, CustomFieldType, CustomFieldAppliesTo # Import custom field models and enums
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from datetime import datetime, date, timedelta # Import date object and timedelta
import json # For handling custom_data JSON
import csv
import io # For reading file stream
from werkzeug.utils import secure_filename # For secure file handling
import os # For os.path and os.makedirs
import uuid # For unique filenames
from urllib.parse import urlencode
import re
from ..models.user import User # Ensure User model is imported

# --- ADDED NEW HELPER FUNCTION for dynamic form class creation ---
def create_dynamic_form_class(BaseFormClass, entity_type):
    """
    Dynamically creates a new form class inheriting from BaseFormClass,
    adding custom fields based on CustomFieldDefinitions.

    Args:
        BaseFormClass: The base WTForm class (e.g., ContactForm).
        entity_type (CustomFieldAppliesTo): The type of entity (CONTACT or ACCOUNT).

    Returns:
        tuple: (NewDynamicFormClass, list_of_dynamic_fields)
               list_of_dynamic_fields contains (field_name, definition_object) tuples.
    """
    definitions = CustomFieldDefinition.query.filter_by(applies_to=entity_type).order_by(CustomFieldDefinition.name).all()
    dynamic_fields_list = []

    # Create a unique class name (optional, but good practice)
    dynamic_class_name = f"{BaseFormClass.__name__}Dynamic_{entity_type.name}"
    # Create the new class dynamically, inheriting from the base
    NewDynamicFormClass = type(dynamic_class_name, (BaseFormClass,), {})

    for definition in definitions:
        field_name = f"custom_{definition.id}"
        field_label = definition.name
        field_validators = [Optional()] # Start with Optional
        field_kwargs = {'label': field_label, 'validators': field_validators}
        field_class = None

        if definition.field_type == CustomFieldType.TEXT:
            field_class = StringField
        elif definition.field_type == CustomFieldType.NUMBER:
            field_class = IntegerField
        elif definition.field_type == CustomFieldType.DATE:
            field_class = WTDatefield
            field_kwargs['format'] = '%Y-%m-%d'
        elif definition.field_type == CustomFieldType.DROPDOWN:
            field_class = SelectField
            choices = [('', '-- Select --')]
            if definition.options and 'options' in definition.options:
                choices.extend([(opt, opt) for opt in definition.options['options']])
            field_kwargs['choices'] = choices
        elif definition.field_type == CustomFieldType.BOOLEAN:
            field_class = BooleanField
            field_kwargs['validators'] = [] # Boolean doesn't need Optional

        if field_class:
            # Add the field definition as a class attribute to the dynamic class
            setattr(NewDynamicFormClass, field_name, field_class(**field_kwargs))
            dynamic_fields_list.append((field_name, definition))
        else:
            current_app.logger.error(f"Unsupported custom field type: {definition.field_type} for Definition ID: {definition.id}")

    return NewDynamicFormClass, dynamic_fields_list
# --- END NEW HELPER --- 

# --- ADDED HELPER to save custom field values --- #
def save_custom_field_values(form, entity_type, entity_obj, dynamic_fields):
    """
    Processes and saves the custom field values submitted through a dynamic form.

    Args:
        form: The validated WTForm instance (dynamic subclass).
        entity_type (CustomFieldAppliesTo): The type of entity (CONTACT or ACCOUNT).
        entity_obj: The actual Contact or CrmAccount object instance.
        dynamic_fields (list): The list of (field_name, definition) tuples.
    """
    if not entity_obj or not entity_obj.id:
        current_app.logger.error("save_custom_field_values called with invalid entity object")
        return # Cannot save without a valid, saved entity
    
    entity_id = entity_obj.id
    contact_id_or_none = entity_id if entity_type == CustomFieldAppliesTo.CONTACT else None
    account_id_or_none = entity_id if entity_type == CustomFieldAppliesTo.ACCOUNT else None # CORRECTED: Was CRMACCOUNT

    for field_name, definition in dynamic_fields:
        if hasattr(form, field_name):
            submitted_value = getattr(form, field_name).data
            value_to_store = None

            # Convert submitted data to storable string format
            if submitted_value is not None:
                if definition.field_type == CustomFieldType.BOOLEAN:
                    value_to_store = str(submitted_value) # Store as 'True' or 'False'
                elif definition.field_type == CustomFieldType.DATE and isinstance(submitted_value, date):
                    value_to_store = submitted_value.isoformat() # Store as YYYY-MM-DD string
                elif submitted_value: # Text, Number, Dropdown
                    value_to_store = str(submitted_value).strip()
            
            # Find existing value object
            existing_value_obj = CustomFieldValue.query.filter_by(
                definition_id=definition.id,
                contact_id=contact_id_or_none,
                account_id=account_id_or_none
            ).first()

            if value_to_store is not None and value_to_store != "":
                if existing_value_obj:
                    # Update if changed
                    if existing_value_obj.value != value_to_store:
                        existing_value_obj.value = value_to_store
                        db.session.add(existing_value_obj) # Mark for update
                else:
                    # Create new value
                    new_custom_value = CustomFieldValue(
                        definition_id=definition.id,
                        contact_id=contact_id_or_none,
                        account_id=account_id_or_none,
                        value=value_to_store
                    )
                    db.session.add(new_custom_value)
            elif existing_value_obj:
                # Delete existing db record if submitted value is None or empty string
                db.session.delete(existing_value_obj)
        else:
             current_app.logger.warning(f"Form did not have expected custom field attribute: {field_name}")
# --- END HELPER --- #

# Define the blueprint
crm_bp = Blueprint(
    'crm', 
    __name__, 
    template_folder='../templates/crm', # Point to the crm templates directory
    url_prefix='/crm' # Set base URL prefix for all routes in this blueprint
)

def get_current_sales_rep_id():
    """Helper function to get the current user's sales rep ID."""
    if not current_user.is_authenticated or not hasattr(current_user, 'sales_profile') or not current_user.sales_profile:
        return None
    return current_user.sales_profile.id

# Define target fields for CSV import mapping
CONTACT_IMPORT_FIELDS = {
    'first_name': 'First Name',
    'last_name': 'Last Name',
    'email': 'Email',
    'phone_number': 'Phone Number',
    'job_title': 'Job Title',
    'crm_account_name': 'Account Name (for linking)', # Special field for linking by name
    'status': 'Status',
    'source': 'Source',
    'custom_data': 'Custom Data (JSON or Text)'
}

ACCOUNT_IMPORT_FIELDS = {
    'name': 'Account Name',
    'email': 'Email',
    'phone_number': 'Phone Number',
    'website': 'Website',
    'industry': 'Industry',
    'address_street': 'Street Address',
    'address_city': 'City',
    'address_state': 'State/Province',
    'address_zip': 'ZIP/Postal Code',
    'address_country': 'Country',
    'custom_data': 'Custom Data (JSON or Text)'
}

UPLOAD_FOLDER = 'instance/csv_uploads' # Define upload folder relative to app root
ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Dashboard --- #
@crm_bp.route('/dashboard')
@login_required
@sales_required
def dashboard():
    """CRM Dashboard - Landing page for sales users"""
    if not current_user.sales_profile:
        flash('Sales profile not found for this user.', 'error')
        return redirect(url_for('main.dashboard'))

    sales_profile = current_user.sales_profile 
    sales_rep_id = sales_profile.id
    is_manager = sales_profile.role == 'sales_manager'
    today = date.today()

    # --- Time Period Filter --- #
    selected_period = request.args.get('period', 'all') # Default to 'all'
    start_date = None
    if selected_period == 'today':
        start_date = datetime.combine(today, datetime.min.time()) # Start of today
    elif selected_period == 'week':
        start_date = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time()) # Start of this week (Monday)
    elif selected_period == 'month':
        start_date = datetime.combine(today.replace(day=1), datetime.min.time()) # Start of this month
    # 'all' means start_date remains None

    # Base queries - Filter by sales_rep_id unless manager
    contact_query = Contact.query
    account_query = CrmAccount.query
    deal_query = Deal.query
    task_query = Task.query
    call_log_query = CallLog.query
    note_query = Note.query # Assuming notes have sales_rep_id

    # Apply base role filtering
    if not is_manager:
        contact_query = contact_query.filter(Contact.sales_rep_id == sales_rep_id)
        account_query = account_query.filter(CrmAccount.sales_rep_id == sales_rep_id)
        deal_query = deal_query.filter(Deal.sales_rep_id == sales_rep_id)
        task_query = task_query.filter(Task.sales_rep_id == sales_rep_id)
        call_log_query = call_log_query.filter(CallLog.sales_rep_id == sales_rep_id)
        note_query = note_query.filter(Note.sales_rep_id == sales_rep_id)

    # Apply time period filtering where applicable (created_at/timestamp fields)
    deal_query_filtered = deal_query
    task_query_filtered = task_query # Note: Tasks are usually filtered by due_date, not created_at for dashboard stats
    call_log_query_filtered = call_log_query
    note_query_filtered = note_query

    if start_date:
        deal_query_filtered = deal_query_filtered.filter(Deal.created_at >= start_date)
        # task_query_filtered = task_query_filtered.filter(Task.created_at >= start_date)
        call_log_query_filtered = call_log_query_filtered.filter(CallLog.created_at >= start_date)
        note_query_filtered = note_query_filtered.filter(Note.timestamp >= start_date)

    # --- Calculate Metrics (using potentially time-filtered queries) --- 

    # Basic Counts (usually not time-filtered, use base queries)
    contact_count = contact_query.count()
    account_count = account_query.count()
    deal_count = deal_query.count() # Total deals (all time)
    task_count = task_query.count() # Total tasks (all time)

    # Overdue Tasks (not time-period dependent, uses base task_query)
    overdue_tasks_query = task_query.filter(
        Task.status != 'Completed',
        Task.due_date != None,
        cast(Task.due_date, Date) < today # Explicitly cast due_date to Date for comparison
    )
    overdue_task_count = overdue_tasks_query.count()
    recent_overdue_tasks = overdue_tasks_query.order_by(Task.due_date.asc()).limit(5).all()

    # Call Metrics (using filtered call_log_query_filtered)
    call_subq = call_log_query_filtered.subquery() # Create subquery
    total_calls = call_log_query_filtered.count() # Count can use the original query directly
    total_call_duration_secs = db.session.query(func.sum(func.coalesce(call_subq.c.duration, 0)))\
                                      .scalar() or 0 # Query directly from subquery columns
    total_call_duration_mins = round(total_call_duration_secs / 60)

    # Deal Metrics (using filtered deal_query_filtered)
    open_deal_stages = [s[0] for s in DEAL_STAGES if s[0] not in ('Closed Won', 'Closed Lost')]
    open_deals_query_filtered = deal_query_filtered.filter(Deal.stage.in_(open_deal_stages))
    open_deals_subq = open_deals_query_filtered.subquery() # Create subquery for open deals
    
    open_deals_count = open_deals_query_filtered.count() # Count can use the original query directly
    total_pipeline_value = db.session.query(func.sum(func.coalesce(open_deals_subq.c.amount, 0)))\
                                   .scalar() or 0 # Query directly from subquery columns

    # Deals by Stage (using filtered deal_query_filtered for the chart)
    deals_filtered_subq = deal_query_filtered.subquery() # Create subquery for all filtered deals
    deals_by_stage_query = db.session.query(deals_filtered_subq.c.stage, func.count(deals_filtered_subq.c.id))\
                                  .group_by(deals_filtered_subq.c.stage) # Query and group by subquery columns
    deals_by_stage_data = {stage: count for stage, count in deals_by_stage_query.all()}

    # --- Recent Items (Fetch using potentially time-filtered queries) ---
    # Note: Activity feed might feel weird if filtered by time, maybe always show latest?
    # For now, use filtered queries, but consider reverting if it feels wrong.
    recent_deals = deal_query_filtered.order_by(Deal.created_at.desc()).limit(5).all()
    recent_tasks = task_query_filtered.order_by(Task.created_at.desc()).limit(5).all()
    recent_call_logs = call_log_query_filtered.order_by(CallLog.created_at.desc()).limit(5).all()
    recent_notes = note_query_filtered.order_by(Note.timestamp.desc()).limit(5).all()

    # Combine and sort recent activities (as before)
    combined_activities = []
    for deal in recent_deals:
        combined_activities.append({
            'type': 'deal',
            'obj': deal,
            'text': f"Deal: {deal.name}",
            'url': url_for('crm.view_deal', deal_id=deal.id),
            'timestamp': deal.created_at
        })
    for task in recent_tasks:
        combined_activities.append({
            'type': 'task',
            'obj': task,
            'text': f"Task: {task.title}",
            'url': url_for('crm.edit_task', task_id=task.id), 
            'timestamp': task.created_at
        })
    for log in recent_call_logs:
        log_text = f"Call {log.direction}"
        if log.direction == 'outbound':
            log_text += f" to {log.to_number}"
        else:
            log_text += f" from {log.from_number}"
        if log.contact:
             log_text += f" ({log.contact.full_name})"
        combined_activities.append({
            'type': 'call_log',
            'obj': log,
            'text': log_text,
            'url': url_for('crm.calls'), 
            'timestamp': log.created_at,
            'notes': log.notes,      # <-- ADDED
            'outcome': log.outcome   # <-- ADDED
        })
    for note in recent_notes:
        note_text = "Note added"
        note_url = '#' 
        if note.contact:
            note_text += f" for {note.contact.full_name}"
            note_url = url_for('crm.view_contact', contact_id=note.contact_id)
        combined_activities.append({
            'type': 'note',
            'obj': note,
            'text': note_text,
            'url': note_url,
            'timestamp': note.timestamp
        })

    recent_activities = sorted(
        combined_activities,
        key=lambda x: x['timestamp'] if x['timestamp'] else datetime.min, 
        reverse=True
    )[:10] 

    return render_template('crm/dashboard.html', 
                           sales_profile=sales_profile,
                           selected_period=selected_period, # Pass selected period for button highlighting
                           # Counts (All Time)
                           contact_count=contact_count,
                           account_count=account_count,
                           deal_count=deal_count, 
                           task_count=task_count,
                           # Overdue Tasks (Not time-based)
                           overdue_task_count=overdue_task_count,
                           recent_overdue_tasks=recent_overdue_tasks,
                           # Call Metrics (Time-based)
                           total_calls=total_calls,
                           total_call_duration_mins=total_call_duration_mins,
                           # Deal Metrics (Time-based)
                           open_deals_count=open_deals_count,
                           total_pipeline_value=total_pipeline_value,
                           deals_by_stage_data=deals_by_stage_data, # (Time-based)
                           # Recent Activity Feed (Currently time-based, review if needed)
                           recent_activities=recent_activities,
                           # Pass constants if needed by template
                           TASK_STATUSES=TASK_STATUSES,
                           TASK_PRIORITIES=TASK_PRIORITIES,
                           DEAL_STAGES=DEAL_STAGES,
                           today=today
                           )

# --- AJAX Data Endpoint for Dashboard --- #
@crm_bp.route('/dashboard-data')
@login_required
@sales_required
def dashboard_data():
    """Return dashboard data as JSON for AJAX requests."""
    # Basic validation
    if not current_user.sales_profile:
        return jsonify({'error': 'Sales profile not found'}), 403

    target = request.args.get('target')
    if target not in ['deals', 'calls']:
        return jsonify({'error': 'Invalid target specified'}), 400
    
    selected_period = request.args.get('period', 'all')
    if selected_period not in ['today', 'week', 'month', 'all']:
        return jsonify({'error': 'Invalid period specified'}), 400

    # --- Setup --- 
    sales_rep_id = current_user.sales_profile.id
    is_manager = current_user.sales_profile.role == 'sales_manager'
    today = date.today()
    start_date = None
    if selected_period == 'today':
        start_date = datetime.combine(today, datetime.min.time())
    elif selected_period == 'week':
        start_date = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time())
    elif selected_period == 'month':
        start_date = datetime.combine(today.replace(day=1), datetime.min.time())
    
    response_data = {}

    # --- Calculate Data --- #
    try:
        if target == 'deals':
            # Deals calculation logic...
            deal_query = Deal.query
            if not is_manager:
                deal_query = deal_query.filter(Deal.sales_rep_id == sales_rep_id)
            
            deal_query_filtered = deal_query
            if start_date:
                deal_query_filtered = deal_query_filtered.filter(Deal.created_at >= start_date)

            open_deal_stages = [s[0] for s in DEAL_STAGES if s[0] not in ('Closed Won', 'Closed Lost')]
            open_deals_query_filtered = deal_query_filtered.filter(Deal.stage.in_(open_deal_stages))
                         
            response_data['total_pipeline_value'] = db.session.query(func.sum(func.coalesce(Deal.amount, 0)))\
                                           .select_from(open_deals_query_filtered.subquery())\
                                           .scalar() or 0

            deals_by_stage_query = db.session.query(Deal.stage, func.count(Deal.id))\
                                          .select_from(deal_query_filtered.subquery())\
                                          .group_by(Deal.stage)
            response_data['deals_by_stage_data'] = {stage or 'Unknown': count for stage, count in deals_by_stage_query.all()}

        elif target == 'calls':
            # Calls calculation logic...
            call_log_query = CallLog.query
            if not is_manager:
                call_log_query = call_log_query.filter(CallLog.sales_rep_id == sales_rep_id)

            call_log_query_filtered = call_log_query
            if start_date:
                call_log_query_filtered = call_log_query_filtered.filter(CallLog.created_at >= start_date)
            
            response_data['total_calls'] = call_log_query_filtered.count()
            total_call_duration_secs = db.session.query(func.sum(func.coalesce(CallLog.duration, 0)))\
                                              .select_from(call_log_query_filtered.subquery())\
                                              .scalar() or 0
            response_data['total_call_duration_mins'] = round(total_call_duration_secs / 60)
            
    except Exception as e:
        # Log the exception
        current_app.logger.error(f"Error calculating dashboard data for target '{target}', period '{selected_period}': {e}")
        # Return an error response
        return jsonify({'error': 'An internal error occurred while calculating data.'}), 500

    # If try block succeeded without exception, return the data
    return jsonify(response_data)

# --- Contact Routes --- #
@crm_bp.route('/contacts')
@login_required
@sales_required
def contacts():
    """List contacts based on user role, now with pagination and filtering."""
    if not current_user.sales_profile:
        flash('Sales profile not found for this user.', 'error')
        return redirect(url_for('main.dashboard'))

    page = request.args.get('page', 1, type=int)
    # MODIFIED: Allow user to select items per page
    valid_per_page_options = [10, 20, 50, 100]
    default_per_page = current_app.config.get('ITEMS_PER_PAGE', 15) # Keep a general default
    if default_per_page not in valid_per_page_options:
         # Ensure default_per_page is one of the options, or pick the smallest if not
        default_per_page = valid_per_page_options[0] if not any(v > default_per_page for v in valid_per_page_options) else min(valid_per_page_options)

    per_page = request.args.get('per_page', default_per_page, type=int)
    if per_page not in valid_per_page_options:
        per_page = default_per_page # Fallback to default if invalid value is passed
    
    # Filter parameters
    sales_rep_id_filter = request.args.get('sales_rep_id_filter', '') # Empty string for 'Any' or 'All'
    crm_account_id_filter = request.args.get('crm_account_id_filter', '') # Empty string for 'Any' or 'All'
    status_filter = request.args.get('status_filter', '') # Empty string for 'Any' or 'All'

    page_title = "My Contacts"
    query = Contact.query
    is_manager = hasattr(current_user, 'sales_profile') and current_user.sales_profile and current_user.sales_profile.role == 'sales_manager'

    if is_manager:
        page_title = "All Contacts"
        # Managers can see all contacts by default, or filter by a specific sales rep
        if sales_rep_id_filter:
            if sales_rep_id_filter == 'unassigned':
                query = query.filter(Contact.sales_rep_id.is_(None))
            else:
                query = query.filter(Contact.sales_rep_id == sales_rep_id_filter)
    else:
        # Non-managers see only their own contacts
        query = query.filter(Contact.sales_rep_id == current_user.sales_profile.id)
        # Non-managers cannot filter by sales_rep_id, so sales_rep_id_filter is ignored for them in query building

    # Filter by CRM Account
    if crm_account_id_filter:
        if crm_account_id_filter == 'unassigned':
            query = query.filter(Contact.crm_account_id.is_(None))
        else:
            query = query.filter(Contact.crm_account_id == crm_account_id_filter)

    # Filter by Status
    if status_filter:
        query = query.filter(Contact.status == status_filter)

    # Ordering
    if is_manager:
        query = query.order_by(Contact.last_name, Contact.first_name)
    else:
        query = query.order_by(Contact.last_name, Contact.first_name) # Or specific order for user's contacts

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    contacts_on_page = pagination.items

    # Data for filter dropdowns
    sales_reps_for_filter = []
    if is_manager:
        sales_reps_for_filter = SalesUser.query.join(User).order_by(User.name).all()
    
    # For account filter, consider which accounts should be listable.
    # For now, all accounts. Could be refined to accounts relevant to the manager's team or user's accounts.
    accounts_for_filter = CrmAccount.query.order_by(CrmAccount.name).all()

    return render_template('crm/contacts.html', 
                           title=page_title, 
                           contacts=contacts_on_page, 
                           pagination=pagination,
                           is_manager=is_manager,
                           sales_reps_for_filter=sales_reps_for_filter,
                           accounts_for_filter=accounts_for_filter,
                           contact_statuses=CONTACT_STATUSES,
                           current_filters={ # Pass current filters back to the template
                               'sales_rep_id': sales_rep_id_filter,
                               'crm_account_id': crm_account_id_filter,
                               'status': status_filter
                           },
                           # ADDED: Pass per_page and options to template
                           current_per_page=per_page,
                           per_page_options=valid_per_page_options
                           )

@crm_bp.route('/contacts/new', methods=['GET', 'POST'])
@login_required
@sales_required
def create_contact():
    """Create a new contact for the current sales rep."""
    account_id = request.args.get('account_id', type=int)
    preselected_account = None
    if account_id:
        preselected_account = CrmAccount.query.filter_by(id=account_id, sales_rep_id=current_user.sales_profile.id).first()
        if not preselected_account:
            flash('Specified company not found or access denied.', 'warning')
            # Decide: redirect or just don't preselect? For now, just don't preselect.

    # Dynamically create the form class incorporating custom fields
    DynamicContactForm, dynamic_fields = create_dynamic_form_class(ContactForm, CustomFieldAppliesTo.CONTACT)

    form = DynamicContactForm(request.form if request.method == 'POST' else None, obj=contact)

    # --- MODIFICATION for contact form Company/Account dropdown ---
    # This logic is now handled inside ContactForm.__init__
    # current_crm_account_query = get_user_crm_accounts_query() 
    # if contact and contact.crm_account_id:
    #     if hasattr(current_user, 'sales_profile') and current_user.sales_profile.role == 'sales_manager':
    #         form.crm_account.query = current_crm_account_query.order_by(CrmAccount.name) # Manager sees all
    #     else:
    #         # Rep sees their own + current linked
    #         filter_condition = (CrmAccount.sales_rep_id == current_user.sales_profile.id) if hasattr(current_user, 'sales_profile') and current_user.sales_profile else false()
    #         filter_condition = or_((CrmAccount.id == contact.crm_account_id), filter_condition)
    #         form.crm_account.query = CrmAccount.query.filter(filter_condition).order_by(CrmAccount.name)
    # else:
    #     form.crm_account.query = current_crm_account_query.order_by(CrmAccount.name)
    # form.crm_account.query_factory = None # Disable factory
    # --- END MODIFICATION ---

    if form.validate_on_submit():
        # Global email uniqueness check
        if form.email.data:
            existing_contact = Contact.query.filter(Contact.email == form.email.data).first()
            if existing_contact:
                # Check if the user is an admin or sales manager (add this role check later if needed)
                # For now, strictly prevent duplicate creation for all users.
                flash(f'A contact with the email "{form.email.data}" already exists in the system (ID: {existing_contact.id}).', 'warning')
                # Optionally, redirect to the existing contact or re-render the form with the error.
                # For now, re-rendering the form is simpler.
                return render_template('crm/contact_form.html', form=form, title="Create New Contact", legend="New Contact Details", dynamic_fields=dynamic_fields) # Pass dynamic_fields for re-render

        try:
            new_contact = Contact(
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                email=form.email.data,
                phone_number=form.phone_number.data,
                job_title=form.job_title.data,
                crm_account_id=form.crm_account.data.id if form.crm_account.data else None,
                status=form.status.data,
                source=form.source.data,
                sales_rep_id=current_user.sales_profile.id
            )
            db.session.add(new_contact)
            db.session.commit() # Commit the contact first to get its ID

            # --- ADDED: Process and save custom field values ---
            for field_name, definition in dynamic_fields:
                if hasattr(form, field_name):
                    submitted_value = getattr(form, field_name).data
                    
                    # Handle different data types appropriately before saving
                    # For BooleanField, .data is True/False. Store as string or integer if needed.
                    # For DateField, .data is a datetime.date object. Convert to string.
                    value_to_store = None
                    if submitted_value is not None:
                        if definition.field_type == CustomFieldType.BOOLEAN:
                            value_to_store = str(submitted_value) # Store as 'True' or 'False'
                        elif definition.field_type == CustomFieldType.DATE and isinstance(submitted_value, date):
                            value_to_store = submitted_value.isoformat()
                        elif submitted_value: # For text, number, dropdown, ensure it's not just empty string before creating a record
                            value_to_store = str(submitted_value) # Store as string for simplicity for now
                        
                        # Only create a CustomFieldValue if there's a value to store
                        if value_to_store is not None and str(value_to_store).strip() != "":
                            custom_value = CustomFieldValue(
                                definition_id=definition.id,
                                contact_id=new_contact.id,
                                value=value_to_store
                            )
                            db.session.add(custom_value)
            # --- END ADDED ---

            db.session.commit() # Commit custom field values
            flash(f'Contact "{new_contact.full_name}" created successfully!', 'success')
            return redirect(url_for('crm.contacts'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating contact: {e}")
            flash('Error creating contact. Please check your input and try again.', 'error')
            
    # For GET request or validation failure
    # If it was a GET and we had a preselected account, ensure it's still set in the form for rendering
    if request.method == 'GET' and preselected_account:
        form.crm_account.data = preselected_account
        
    return render_template('crm/contact_form.html', form=form, title="Create New Contact", legend="New Contact Details", dynamic_fields=dynamic_fields) # Pass dynamic_fields

@crm_bp.route('/contacts/<int:contact_id>')
@login_required
@sales_required
def view_contact(contact_id):
    """View details of a specific contact, accessible by assigned rep, sales manager, or admin."""
    # --- MODIFIED: Original query line updated to include eager loading --- #
    query = Contact.query.options(
        db.joinedload(Contact.crm_account),
        db.joinedload(Contact.sales_rep).joinedload(SalesUser.user) 
    ).filter(Contact.id == contact_id)
    # --- END MODIFIED --- #

    # Check ONLY for Sales Manager role OR if the user is the assigned rep
    if not (hasattr(current_user, 'sales_profile') and current_user.sales_profile and \
            (current_user.sales_profile.role == 'sales_manager' or \
             (contact_id is not None and Contact.query.with_entities(Contact.sales_rep_id).filter_by(id=contact_id).scalar() == current_user.sales_profile.id))):
        # If not sales manager, and not the assigned sales rep, then deny access by ensuring query won't match unless assigned.
        query = query.filter(Contact.sales_rep_id == current_user.sales_profile.id) # This re-applies filter if needed       
    contact = query.first_or_404() 
    
    # Fetch related items
    notes = contact.notes.order_by(desc(Note.timestamp)).all() 
    call_logs = contact.call_logs.order_by(desc(CallLog.created_at)).all() 
    related_deals = sorted(list(contact.deals), key=lambda d: d.created_at, reverse=True) if contact.deals else []
    related_tasks = sorted(list(contact.crm_tasks), key=lambda t: t.created_at, reverse=True) if contact.crm_tasks else []
    
    note_form = NoteForm() 
    
    from sqlalchemy.orm import joinedload
    custom_values_query = contact.custom_field_values.options(joinedload(CustomFieldValue.definition))
    custom_fields_data = {val.definition.name: val.value for val in custom_values_query.all()}

    return render_template('crm/contact_detail.html', 
                           contact=contact, 
                           notes=notes, 
                           call_logs=call_logs, 
                           related_deals=related_deals, # Pass related deals
                           related_tasks=related_tasks, # Pass related tasks
                           note_form=note_form, # Pass form to template
                           title=contact.full_name,
                           custom_fields_data=custom_fields_data, # Pass custom fields data
                           generated_csrf_token=generate_csrf()) # Pass token

@crm_bp.route('/contacts/<int:contact_id>/edit', methods=['GET', 'POST'])
@login_required
@sales_required
def edit_contact(contact_id):
    """Edit an existing contact, including dynamic custom fields and owner assignment for managers."""
    contact_query = Contact.query.filter_by(id=contact_id)
    is_manager = hasattr(current_user, 'sales_profile') and current_user.sales_profile and current_user.sales_profile.role == 'sales_manager'

    if not is_manager:
        contact_query = contact_query.filter_by(sales_rep_id=get_current_sales_rep_id())
    
    contact = contact_query.first_or_404()

    DynamicContactForm, dynamic_fields = create_dynamic_form_class(ContactForm, CustomFieldAppliesTo.CONTACT)

    if request.method == 'POST':
        form = DynamicContactForm(request.form) # MODIFIED: Populate from formdata on POST
    else: # GET request
        form = DynamicContactForm(obj=contact) # MODIFIED: Populate from object on GET
        # Pre-populate custom fields for display on GET
        for field_name, definition in dynamic_fields:
            if hasattr(form, field_name):
                value_obj = CustomFieldValue.query.filter_by(
                    definition_id=definition.id, 
                    contact_id=contact.id
                ).first()
                if value_obj:
                    field = getattr(form, field_name)
                    if definition.field_type == CustomFieldType.BOOLEAN:
                        field.data = value_obj.value.lower() == 'true'
                    elif definition.field_type == CustomFieldType.DATE and value_obj.value:
                        try:
                            field.data = datetime.strptime(value_obj.value, '%Y-%m-%d').date()
                        except ValueError:
                            current_app.logger.warning(f"Could not parse date for custom field {definition.name} for contact {contact.id}: {value_obj.value}")
                            field.data = None
                    else: # Text, Number, Dropdown
                        field.data = value_obj.value
        
        # Pre-populate sales_rep_id for managers on GET
        if is_manager and hasattr(form, 'sales_rep_id'):
            if contact.sales_rep:
                 form.sales_rep_id.data = contact.sales_rep
            else:
                 form.sales_rep_id.data = None # Ensure "Unassigned" is shown if not set
        
        # Pre-populate crm_account field on GET
        if hasattr(form, 'crm_account'):
            if is_manager:
                form.crm_account.query = CrmAccount.query.order_by(CrmAccount.name).all()
            else:
                # For non-managers, the query is set up in ContactForm.__init__ based on get_user_crm_accounts_query()
                # and potential existing linked account. We just need to set the data.
                # The query logic inside ContactForm.__init__ should handle showing correct options.
                # We ensure the current value is pre-selected.
                pass # Query is handled by form init, data will be set by obj=contact
            # Pre-select current account if linked (obj=contact should handle this, but explicit can be a fallback)
            if contact.crm_account:
                form.crm_account.data = contact.crm_account


    if form.validate_on_submit(): # This is effectively for POST
        try:
            contact.first_name = form.first_name.data.strip()
            contact.last_name = form.last_name.data.strip() if form.last_name.data else None
            contact.email = form.email.data.strip() if form.email.data else None
            contact.phone_number = form.phone_number.data.strip()
            contact.job_title = form.job_title.data.strip() if form.job_title.data else None
            contact.status = form.status.data
            contact.source = form.source.data if form.source.data else None

            if hasattr(form, 'crm_account'):
                selected_account = form.crm_account.data
                contact.crm_account_id = selected_account.id if selected_account else None
            
            if is_manager and hasattr(form, 'sales_rep_id'):
                selected_sales_rep_from_form_field = form.sales_rep_id.data # This is what WTForms processed
                
                if selected_sales_rep_from_form_field is None:
                    raw_sales_rep_id = request.form.get('sales_rep_id')
                    # Check if raw_sales_rep_id is not None and not the typical blank value string for QuerySelectField
                    # The blank value can sometimes be an empty string or specific strings like '__None' depending on field setup.
                    if raw_sales_rep_id and raw_sales_rep_id not in ['', '__None']:
                        try:
                            sales_rep_id_int = int(raw_sales_rep_id)
                            fetched_sales_rep = SalesUser.query.get(sales_rep_id_int)
                            if fetched_sales_rep:
                                selected_sales_rep_from_form_field = fetched_sales_rep
                                current_app.logger.info(f"Manager edit_contact: form.sales_rep_id.data was None, but successfully fetched SalesUser ID {sales_rep_id_int} from request.form.")
                            else:
                                current_app.logger.warning(f"Manager edit_contact: form.sales_rep_id.data was None, raw form ID {raw_sales_rep_id} did not match any SalesUser.")
                        except ValueError:
                            current_app.logger.warning(f"Manager edit_contact: form.sales_rep_id.data was None, raw form ID {raw_sales_rep_id} is not a valid integer.")
                
                if selected_sales_rep_from_form_field: 
                    contact.sales_rep_id = selected_sales_rep_from_form_field.id
                    contact.sales_rep = selected_sales_rep_from_form_field 
                else: 
                    contact.sales_rep_id = None
                    contact.sales_rep = None 
            elif not is_manager and hasattr(form, 'sales_rep_id_hidden'):
                pass 

            db.session.add(contact)
            save_custom_field_values(form, CustomFieldAppliesTo.CONTACT, contact, dynamic_fields)
            db.session.commit()

            flash(f'Contact "{contact.full_name}" updated successfully!', 'success')
            return redirect(url_for('crm.view_contact', contact_id=contact.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating contact {contact_id}: {e}")
            flash(f'Error updating contact: {str(e)}.', 'danger')

    # If POST and validation failed, WTForms retains submitted data in 'form'.
    # The GET pre-population logic above handles initial form display.
    
    page_title = f"Edit Contact: {contact.full_name}"
    form_action_url = url_for('crm.edit_contact', contact_id=contact.id)

    return render_template('crm/contact_form.html', 
                           form=form, 
                           title=page_title, 
                           contact=contact,
                           form_action_url=form_action_url,
                           dynamic_fields=dynamic_fields,
                           editing=True)

@crm_bp.route('/contacts/<int:contact_id>/delete', methods=['POST'])
@login_required
@sales_required
def delete_contact(contact_id):
    """Delete a contact, accessible by assigned rep, sales manager, or admin."""
    query = Contact.query.filter_by(id=contact_id)
    if not (hasattr(current_user, 'sales_profile') and current_user.sales_profile and 
            (current_user.sales_profile.role == 'sales_manager' or 
             (Contact.query.with_entities(Contact.sales_rep_id).filter_by(id=contact_id).scalar() == current_user.sales_profile.id))):
        query = query.filter(Contact.sales_rep_id == current_user.sales_profile.id)        
    contact = query.first_or_404()
    
    try:
        contact_name = contact.full_name
        
        # Manually unlink associated CallLogs
        # Note: Associated Notes will be deleted due to cascade setting in Contact model
        linked_call_logs = CallLog.query.filter_by(contact_id=contact.id).all()
        for log in linked_call_logs:
            log.contact_id = None
            
        db.session.delete(contact)
        db.session.commit() # Commits unlinking and deletion
        flash(f'Contact "{contact_name}" was successfully deleted.', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting contact {contact_id}: {e}")
        flash('Error deleting contact. Please try again.', 'error')
        # On error, redirect back to contact detail view if possible, otherwise list
        return redirect(url_for('crm.view_contact', contact_id=contact.id))

    return redirect(url_for('crm.contacts')) # Redirect to contact list on success

@crm_bp.route('/contacts/<int:contact_id>/link-company', methods=['GET', 'POST'])
@login_required
@sales_required
def link_contact_to_company_form(contact_id):
    """Display a form to link/change a contact's company, accessible by assigned rep, sales manager, or admin."""
    query = Contact.query.filter_by(id=contact_id)
    if not (hasattr(current_user, 'sales_profile') and current_user.sales_profile and 
            (current_user.sales_profile.role == 'sales_manager' or 
             (Contact.query.with_entities(Contact.sales_rep_id).filter_by(id=contact_id).scalar() == current_user.sales_profile.id))):
        query = query.filter(Contact.sales_rep_id == current_user.sales_profile.id)        
    contact = query.first_or_404()
    form = LinkContactToCompanyForm(obj=contact) # obj=contact might not directly populate crm_account due to QuerySelectField behavior

    # Manually set the current company for the QuerySelectField on GET
    if request.method == 'GET' and contact.crm_account:
        form.crm_account.data = contact.crm_account

    if form.validate_on_submit():
        try:
            selected_account = form.crm_account.data
            contact.crm_account_id = selected_account.id if selected_account else None
            db.session.commit()
            if selected_account:
                flash(f'{contact.full_name} successfully linked to {selected_account.name}.', 'success')
            else:
                flash(f'{contact.full_name} successfully unlinked from any company.', 'success')
            return redirect(url_for('crm.view_contact', contact_id=contact.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error linking contact {contact_id} to company: {e}")
            flash('Error updating company link. Please try again.', 'error')

    return render_template('crm/link_contact_to_company_form.html', 
                           form=form, 
                           contact=contact, 
                           title=f"Link/Change Company for {contact.full_name}")

@crm_bp.route('/contacts/<int:contact_id>/notes/add', methods=['POST'])
@login_required
@sales_required
def add_note(contact_id):
    """Add a note to a specific contact, accessible by assigned rep, sales manager, or admin."""
    query = Contact.query.filter_by(id=contact_id)
    if not (hasattr(current_user, 'sales_profile') and current_user.sales_profile and 
            (current_user.sales_profile.role == 'sales_manager' or 
             (Contact.query.with_entities(Contact.sales_rep_id).filter_by(id=contact_id).scalar() == current_user.sales_profile.id))):
        query = query.filter(Contact.sales_rep_id == current_user.sales_profile.id)        
    contact = query.first_or_404()
    form = NoteForm() # NoteForm needs to be imported

    if form.validate_on_submit():
        try:
            note = Note(
                text=form.content.data, # Changed from form.text.data
                contact_id=contact.id,
                sales_rep_id=current_user.sales_profile.id
                # crm_account_id could be set if needed, e.g., contact.crm_account_id
            )
            db.session.add(note)
            db.session.commit()
            flash('Note added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding note to contact {contact_id}: {e}")
            flash('Error adding note. Please try again.', 'error')
    else:
        # Collect errors if validation fails
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", 'error')

    return redirect(url_for('crm.view_contact', contact_id=contact.id))

@crm_bp.route('/contacts/bulk-assign-rep', methods=['POST'])
@login_required
@sales_required
@csrf.exempt # ADDED: Exempt from global CSRF for this specific manual POST handling
def bulk_assign_rep():
    """Handle bulk assignment of sales representative to selected contacts."""
    current_app.logger.debug(f"BULK ASSIGN REP - Request Form DATA: {request.form}") # DEBUG LINE

    # We still expect a csrf_token in the form due to {{ csrf_token() }} in the template
    # Manual check can be added here if desired, but exemption handles the 400 error.
    # validate_csrf(request.form.get('csrf_token')) # Example manual validation

    if not (hasattr(current_user, 'sales_profile') and current_user.sales_profile and current_user.sales_profile.role == 'sales_manager'):
        flash('You do not have permission to perform this bulk action.', 'danger')
        return redirect(url_for('crm.contacts'))

    contact_ids = request.form.getlist('selected_contact_ids')
    new_sales_rep_id_str = request.form.get('bulk_assign_sales_rep_id')
    action = request.form.get('bulk_action')

    if action != 'assign_sales_rep':
        flash('Invalid bulk action specified.', 'warning')
        return redirect(url_for('crm.contacts'))

    if not contact_ids:
        flash('No contacts were selected for bulk assignment.', 'warning')
        return redirect(url_for('crm.contacts'))

    if not new_sales_rep_id_str: # This means "-- Select Sales Rep --" was chosen, which shouldn't happen if JS enables button correctly
        flash('No sales representative was selected for assignment.', 'warning')
        return redirect(url_for('crm.contacts'))

    target_sales_rep_id = None
    target_sales_rep_obj = None

    if new_sales_rep_id_str == '_unassigned_':
        target_sales_rep_id = None
        # target_sales_rep_obj remains None
    else:
        try:
            target_sales_rep_id = int(new_sales_rep_id_str)
            target_sales_rep_obj = SalesUser.query.get(target_sales_rep_id)
            if not target_sales_rep_obj:
                flash(f'Selected sales representative (ID: {target_sales_rep_id}) not found.', 'danger')
                return redirect(url_for('crm.contacts'))
        except ValueError:
            flash(f'Invalid sales representative ID format: {new_sales_rep_id_str}.', 'danger')
            return redirect(url_for('crm.contacts'))

    updated_count = 0
    error_count = 0
    processed_contact_ids = []

    for contact_id_str in contact_ids:
        try:
            contact_id = int(contact_id_str)
            contact = Contact.query.get(contact_id)
            if contact:
                # Managers can assign any contact to any rep or unassign
                contact.sales_rep_id = target_sales_rep_id
                contact.sales_rep = target_sales_rep_obj # Assign the SalesUser object or None
                db.session.add(contact)
                updated_count += 1
                processed_contact_ids.append(contact_id)
            else:
                current_app.logger.warning(f"Bulk assign: Contact ID {contact_id_str} not found.")
                error_count += 1
        except ValueError:
            current_app.logger.warning(f"Bulk assign: Invalid Contact ID {contact_id_str} received.")
            error_count += 1
        except Exception as e:
            current_app.logger.error(f"Bulk assign: Error processing contact ID {contact_id_str}: {e}")
            error_count += 1
            db.session.rollback() # Rollback for this specific contact error if needed, or rely on final commit/rollback
            # For safety, break or ensure this error is handled if partial success is not desired.

    if updated_count > 0:
        try:
            db.session.commit()
            assigned_to_name = target_sales_rep_obj.user.name if target_sales_rep_obj and target_sales_rep_obj.user else "Unassigned"
            flash(f'{updated_count} contacts successfully assigned to {assigned_to_name}.', 'success')
        except Exception as e_commit:
            db.session.rollback()
            current_app.logger.error(f"Bulk assign: Error committing changes: {e_commit}")
            flash('An error occurred while saving changes. Some assignments may not have been processed.', 'danger')
            error_count += updated_count # Consider these as errors if commit failed
            updated_count = 0
    
    if error_count > 0:
        flash(f'Could not process assignments for {error_count} selected records. Please check logs.', 'warning')

    # Preserve filters and pagination by redirecting with existing args
    redirect_url = url_for('crm.contacts', **request.args)
    return redirect(redirect_url)

# --- CrmAccount Routes --- #
@crm_bp.route('/accounts')
@login_required
@sales_required
def accounts():
    """List CRM accounts based on user role, now with pagination and filtering."""
    if not current_user.sales_profile:
        flash('Sales profile not found for this user.', 'error')
        return redirect(url_for('main.dashboard'))

    page = request.args.get('page', 1, type=int)
    
    valid_per_page_options = [10, 20, 50, 100]
    default_per_page = current_app.config.get('ITEMS_PER_PAGE_ACCOUNTS', 15) 
    if default_per_page not in valid_per_page_options:
        default_per_page = valid_per_page_options[0]

    per_page = request.args.get('per_page', default_per_page, type=int)
    if per_page not in valid_per_page_options:
        per_page = default_per_page
    
    # Filter parameters
    sales_rep_id_filter = request.args.get('sales_rep_id_filter', '') 
    status_filter = request.args.get('status_filter', '')

    page_title = "My Companies/Accounts"
    query = CrmAccount.query
    is_manager = hasattr(current_user, 'sales_profile') and current_user.sales_profile and current_user.sales_profile.role == 'sales_manager'

    if is_manager:
        page_title = "All CRM Companies/Accounts"
        # Managers can see all accounts by default, or filter by a specific sales rep
        if sales_rep_id_filter:
            if sales_rep_id_filter == 'unassigned':
                query = query.filter(CrmAccount.sales_rep_id.is_(None))
            else:
                query = query.filter(CrmAccount.sales_rep_id == sales_rep_id_filter)
    else:
        # Non-managers see only their own accounts
        query = query.filter(CrmAccount.sales_rep_id == current_user.sales_profile.id)
        # Non-managers cannot filter by sales_rep_id, so sales_rep_id_filter is ignored for them in query building

    # Filter by Status
    if status_filter:
        query = query.filter(CrmAccount.status == status_filter)

    # Ordering
    if is_manager:
        # Eager load sales_rep and user for managers to avoid N+1 queries in template
        from sqlalchemy.orm import joinedload
        query = query.options(
            joinedload(CrmAccount.sales_rep).joinedload(SalesUser.user)
        ).order_by(CrmAccount.name)
    else:
        query = query.order_by(CrmAccount.name)
    
    accounts_pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    user_accounts = accounts_pagination.items
    
    # Data for filter dropdowns
    sales_reps_for_filter = []
    if is_manager:
        sales_reps_for_filter = SalesUser.query.join(User).order_by(User.name).all()
    
    current_filters = {
        'sales_rep_id_filter': sales_rep_id_filter,
        'status_filter': status_filter
    }

    # --- EXISTING: Fetch Custom Fields --- 
    custom_field_defs_query = CustomFieldDefinition.query.filter_by(applies_to=CustomFieldAppliesTo.ACCOUNT).order_by(CustomFieldDefinition.name).all()
    custom_field_defs_dicts = [definition.to_dict() for definition in custom_field_defs_query]
    
    account_ids_on_page = [acc.id for acc in user_accounts]
    custom_field_values_for_page = {}
    if account_ids_on_page and custom_field_defs_dicts:
        values_query = CustomFieldValue.query.filter(
            CustomFieldValue.account_id.in_(account_ids_on_page),
            CustomFieldValue.definition_id.in_([d['id'] for d in custom_field_defs_dicts])
        ).all()
        
        for cfv in values_query:
            if cfv.account_id not in custom_field_values_for_page:
                custom_field_values_for_page[cfv.account_id] = {}
            custom_field_values_for_page[cfv.account_id][cfv.definition_id] = cfv.value
    # --- END EXISTING --- 
    
    return render_template('crm/account_list.html', 
                           accounts=user_accounts, 
                           pagination=accounts_pagination,
                           title=page_title, 
                           CRM_ACCOUNT_STATUSES=CRM_ACCOUNT_STATUSES, 
                           generated_csrf_token=generate_csrf(),
                           custom_field_definitions=custom_field_defs_dicts,
                           custom_field_values_data=custom_field_values_for_page,
                           is_manager=is_manager,
                           sales_reps_for_filter=sales_reps_for_filter,
                           current_filters=current_filters,
                           current_per_page=per_page,
                           per_page_options=valid_per_page_options
                           )

@crm_bp.route('/accounts/bulk-assign-rep', methods=['POST'])
@login_required
@sales_required
@csrf.exempt 
def bulk_assign_rep_accounts():
    """Handles bulk assignment of sales reps to accounts and cascades to linked contacts."""
    if not (hasattr(current_user, 'sales_profile') and current_user.sales_profile and current_user.sales_profile.role == 'sales_manager'):
        flash('You are not authorized to perform this bulk action.', 'danger')
        return redirect(url_for('crm.accounts'))

    selected_ids = request.form.getlist('selected_account_ids')
    action = request.form.get('bulk_action')
    new_sales_rep_id_str = request.form.get('bulk_assign_sales_rep_id')

    if not selected_ids:
        flash('No accounts selected for bulk action.', 'warning')
        return redirect(url_for('crm.accounts', **request.args))

    if action == 'assign_sales_rep':
        if not new_sales_rep_id_str:
            flash('No sales representative selected for assignment.', 'warning')
            return redirect(url_for('crm.accounts', **request.args))

        target_sales_rep_id = None
        target_sales_rep = None

        if new_sales_rep_id_str == '_unassigned_':
            target_sales_rep_id = None
        else:
            try:
                target_sales_rep_id = int(new_sales_rep_id_str)
                target_sales_rep = SalesUser.query.get(target_sales_rep_id)
                if not target_sales_rep:
                    flash(f"Invalid sales representative ID: {target_sales_rep_id}.", 'danger')
                    return redirect(url_for('crm.accounts', **request.args))
            except ValueError:
                flash(f"Invalid sales representative ID format: {new_sales_rep_id_str}.", 'danger')
                return redirect(url_for('crm.accounts', **request.args))

        accounts_to_update = CrmAccount.query.filter(CrmAccount.id.in_([int(id_str) for id_str in selected_ids])).all()
        
        updated_accounts_count = 0
        updated_contacts_count = 0 # Initialize counter for updated contacts

        for account in accounts_to_update:
            if account.sales_rep_id != target_sales_rep_id:
                account.sales_rep_id = target_sales_rep_id
                account.sales_rep = target_sales_rep 
                db.session.add(account) # Add account to session for update
                updated_accounts_count += 1

                # --- ADDED: Cascade to linked contacts ---
                contacts_linked_to_account = Contact.query.filter_by(crm_account_id=account.id).all()
                if contacts_linked_to_account:
                    current_app.logger.info(f"Bulk action: Account {account.id} sales rep changed to {target_sales_rep_id}. Updating {len(contacts_linked_to_account)} linked contacts.")
                    for contact_to_update in contacts_linked_to_account:
                        if contact_to_update.sales_rep_id != target_sales_rep_id:
                            contact_to_update.sales_rep_id = target_sales_rep_id
                            contact_to_update.sales_rep = target_sales_rep 
                            db.session.add(contact_to_update)
                            updated_contacts_count += 1
                # --- END ADDED ---
        
        if updated_accounts_count > 0 or updated_contacts_count > 0:
            try:
                db.session.commit()
                flash_messages = []
                rep_name_for_flash = target_sales_rep.user.name if target_sales_rep and target_sales_rep.user else "Unassigned"
                
                if updated_accounts_count > 0:
                    flash_messages.append(f'{updated_accounts_count} account(s) successfully assigned to {rep_name_for_flash}.')
                if updated_contacts_count > 0:
                    flash_messages.append(f'{updated_contacts_count} linked contact(s) were also reassigned to {rep_name_for_flash}.')
                
                if flash_messages:
                    flash(" ".join(flash_messages), 'success')
                elif updated_accounts_count == 0 and updated_contacts_count == 0: # Should be caught by the outer if, but as a safeguard
                    flash('No accounts or contacts required an update for the selected sales representative.', 'info')

            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error bulk assigning sales rep to accounts/contacts: {e}")
                flash('An error occurred while bulk assigning. Please try again.', 'danger')
        else: # No accounts needed an update in the first place
            flash('No accounts required an update for the selected sales representative.', 'info')
            
    else:
        flash(f'Unknown or unimplemented bulk action: {action}', 'warning')

    return redirect(url_for('crm.accounts', **request.args))

@crm_bp.route('/accounts/new', methods=['GET', 'POST'])
@login_required
@sales_required
def create_account():
    """Create a new CRM account, including dynamic custom fields."""
    # Dynamically create the form class
    DynamicAccountForm, dynamic_fields = create_dynamic_form_class(CrmAccountForm, CustomFieldAppliesTo.ACCOUNT)

    form = DynamicAccountForm(request.form) if request.method == 'POST' else DynamicAccountForm()

    if form.validate_on_submit(): # This covers the POST case
        # Remove old custom_data handling
        # custom_data_to_save = None
        # ... (old parsing logic) ...
        
        selected_status = form.status.data if form.status.data and form.status.data != '-' else None
        
        try:
            new_account = CrmAccount(
                name=form.name.data.strip(),
                website=form.website.data.strip() if form.website.data else None,
                industry=form.industry.data.strip() if form.industry.data else None,
                phone_number=form.phone_number.data.strip() if form.phone_number.data else None,
                address = form.address.data.strip() if form.address.data else None, # Keep general address
                status=selected_status, 
                # custom_data=custom_data_to_save, # <-- REMOVED old custom data
                sales_rep_id=get_current_sales_rep_id()
            )
            db.session.add(new_account)
            db.session.commit() # Commit account first to get ID

            # Save custom field values
            save_custom_field_values(form, CustomFieldAppliesTo.ACCOUNT, new_account, dynamic_fields)
            db.session.commit() # Commit custom field values

            flash(f'Account "{new_account.name}" created successfully!', 'success')
            return redirect(url_for('crm.accounts')) 
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating account: {e}")
            flash('Error creating account. Please check input and try again.', 'error')
            # Fall through to render the form again with errors
            
    # For GET request or validation failure
    return render_template('crm/account_form.html', form=form, title="Create New Company/Account", legend="New Account Details", dynamic_fields=dynamic_fields)

@crm_bp.route('/accounts/<int:account_id>')
@login_required
@sales_required
def view_account(account_id):
    """View account details, including custom fields."""
    query = CrmAccount.query.filter_by(id=account_id)
    if not current_user.sales_profile.role == 'sales_manager':
        query = query.filter_by(sales_rep_id=get_current_sales_rep_id())
    account = query.first_or_404()
    
    related_deals = account.deals.order_by(desc(Deal.created_at)).all()
    related_tasks = account.crm_tasks.order_by(desc(Task.created_at)).all()
    
    # Fetch recent notes from all contacts linked to this account
    recent_contact_notes = Note.query \
        .join(Contact, Note.contact_id == Contact.id) \
        .filter(Contact.crm_account_id == account.id) \
        .order_by(desc(Note.timestamp)) \
        .limit(5).all()
        
    # --- ADDED: Fetch and process custom field values --- #
    from sqlalchemy.orm import joinedload
    custom_values_query = account.custom_field_values.options(joinedload(CustomFieldValue.definition))
    custom_fields_data = {val.definition.name: val.value for val in custom_values_query.all()}
    # --- END ADDED --- #
    
    return render_template('crm/account_detail.html', 
                           account=account, 
                           related_deals=related_deals, 
                           related_tasks=related_tasks, 
                           recent_contact_notes=recent_contact_notes, # Pass recent notes
                           custom_fields_data=custom_fields_data, # <-- ADDED
                           title=account.name, 
                           generated_csrf_token=generate_csrf())

@crm_bp.route('/accounts/<int:account_id>/edit', methods=['GET', 'POST'])
@login_required
@sales_required
def edit_account(account_id):
    """Edit account, including dynamic custom fields and owner assignment for managers."""
    account_query = CrmAccount.query.filter_by(id=account_id)
    is_manager = hasattr(current_user, 'sales_profile') and current_user.sales_profile and current_user.sales_profile.role == 'sales_manager'
    
    if not is_manager:
        account_query = account_query.filter_by(sales_rep_id=get_current_sales_rep_id())
    
    account = account_query.first_or_404()

    DynamicAccountForm, dynamic_fields = create_dynamic_form_class(CrmAccountForm, CustomFieldAppliesTo.ACCOUNT)

    if request.method == 'POST':
        form = DynamicAccountForm(request.form) # MODIFIED: Populate from formdata on POST
    else: # GET request
        form = DynamicAccountForm(obj=account) # MODIFIED: Populate from object on GET
        # Pre-populate custom fields for display on GET
        for field_name, definition in dynamic_fields:
            if hasattr(form, field_name):
                value_obj = CustomFieldValue.query.filter_by(
                    definition_id=definition.id, 
                    account_id=account.id
                ).first()
                if value_obj:
                    field = getattr(form, field_name)
                    if definition.field_type == CustomFieldType.BOOLEAN:
                        field.data = value_obj.value.lower() == 'true'
                    elif definition.field_type == CustomFieldType.DATE and value_obj.value:
                        try:
                            field.data = datetime.strptime(value_obj.value, '%Y-%m-%d').date()
                        except ValueError:
                            current_app.logger.warning(f"Could not parse date for custom field {definition.name} for account {account.id}: {value_obj.value}")
                            field.data = None 
                    else: # Text, Number, Dropdown
                        field.data = value_obj.value
        
        # Pre-populate sales_rep_id for managers on GET
        if is_manager and hasattr(form, 'sales_rep_id'):
            if account.sales_rep:
                form.sales_rep_id.data = account.sales_rep
            else:
                form.sales_rep_id.data = None # Ensure "Unassigned" is shown if not set


    if form.validate_on_submit(): # This is effectively for POST
        try:
            original_sales_rep_id = account.sales_rep_id # Store original ID before any changes

            account.name = form.name.data.strip()
            account.website = form.website.data.strip() if form.website.data else None
            account.industry = form.industry.data.strip() if form.industry.data else None
            account.phone_number = form.phone_number.data.strip() if form.phone_number.data else None
            account.address = form.address.data.strip() if form.address.data else None
            
            selected_status = form.status.data if form.status.data and form.status.data != '-' else None
            account.status = selected_status

            sales_rep_changed_for_account = False
            new_account_sales_rep_obj = None # To store the SalesUser object if assigned

            if is_manager and hasattr(form, 'sales_rep_id'):
                selected_sales_rep_obj_from_form = form.sales_rep_id.data # This data is now from request.form (SalesUser object or None)
                
                new_sales_rep_id_for_account = None
                if selected_sales_rep_obj_from_form:
                    new_sales_rep_id_for_account = selected_sales_rep_obj_from_form.id
                    new_account_sales_rep_obj = selected_sales_rep_obj_from_form

                if account.sales_rep_id != new_sales_rep_id_for_account:
                    account.sales_rep_id = new_sales_rep_id_for_account
                    # Also update the relationship object for the account itself
                    account.sales_rep = new_account_sales_rep_obj 
                    sales_rep_changed_for_account = True
            
            elif not is_manager and hasattr(form, 'sales_rep_id_hidden'):
                # Non-manager, ensure ownership is not accidentally changed.
                pass 

            db.session.add(account) # Add account changes to session first

            # Cascade sales_rep_id change to linked contacts IF it changed for the account
            if sales_rep_changed_for_account:
                contacts_to_update = Contact.query.filter_by(crm_account_id=account.id).all()
                if contacts_to_update:
                    current_app.logger.info(f"Account {account.id} sales rep changed from {original_sales_rep_id} to {account.sales_rep_id}. Updating {len(contacts_to_update)} contacts.")
                    for contact_to_update in contacts_to_update:
                        contact_to_update.sales_rep_id = account.sales_rep_id
                        contact_to_update.sales_rep = new_account_sales_rep_obj # Assign the same SalesUser object or None
                        db.session.add(contact_to_update)
                    
                    rep_name_for_flash = new_account_sales_rep_obj.user.name if new_account_sales_rep_obj and new_account_sales_rep_obj.user else "Unassigned"
                    flash(f"{len(contacts_to_update)} linked contacts were also reassigned to {rep_name_for_flash}.", "info")

            save_custom_field_values(form, CustomFieldAppliesTo.ACCOUNT, account, dynamic_fields)
            db.session.commit()

            flash(f'Account "{account.name}" updated successfully!', 'success')
            return redirect(url_for('crm.view_account', account_id=account.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating account {account_id}: {e}")
            flash(f'Error updating account: {str(e)}.', 'danger')
            
    # If POST and validation failed, WTForms retains submitted data in 'form'.
    # The GET pre-population logic above handles initial form display.

    page_title = f"Edit Account: {account.name}"
    form_action_url = url_for('crm.edit_account', account_id=account.id)
    
    return render_template('crm/account_form.html', 
                           form=form, 
                           title=page_title, 
                           account=account,
                           form_action_url=form_action_url,
                           dynamic_fields=dynamic_fields,
                           editing=True)

@crm_bp.route('/accounts/<int:account_id>/select-contact-to-link', methods=['GET'])
@login_required
@sales_required
def select_contact_to_link_to_account(account_id):
    """Display select contact form, accessible by assigned rep, sales manager, or admin for the account."""
    account_query = CrmAccount.query.filter_by(id=account_id)
    is_sales_manager = hasattr(current_user, 'sales_profile') and current_user.sales_profile and current_user.sales_profile.role == 'sales_manager'
    
    if not is_sales_manager:
        account_query = account_query.filter_by(sales_rep_id=current_user.sales_profile.id)
    account = account_query.first_or_404()
    
    contact_base_query = Contact.query
    if not is_sales_manager:
        contact_base_query = contact_base_query.filter_by(sales_rep_id=current_user.sales_profile.id)

    linkable_contacts = contact_base_query.filter(
        or_(
            Contact.crm_account_id != account.id,
            Contact.crm_account_id == None
        )
    ).order_by(Contact.last_name, Contact.first_name).all()

    return render_template('crm/select_contact_for_account.html', 
                           account=account, 
                           contacts=linkable_contacts,
                           title=f"Link Contact to {account.name}",
                           generated_csrf_token=generate_csrf())

@crm_bp.route('/accounts/<int:account_id>/link-contact/<int:contact_id>', methods=['POST'])
@login_required
@sales_required
def link_contact_to_account(account_id, contact_id):
    """Link contact to account, accessible by assigned rep, sales manager, or admin for BOTH account and contact."""
    account_query = CrmAccount.query.filter_by(id=account_id)
    contact_query = Contact.query.filter_by(id=contact_id)
    is_sales_manager = hasattr(current_user, 'sales_profile') and current_user.sales_profile and current_user.sales_profile.role == 'sales_manager'

    if not is_sales_manager:
        account_query = account_query.filter_by(sales_rep_id=current_user.sales_profile.id)
        contact_query = contact_query.filter_by(sales_rep_id=current_user.sales_profile.id)

    account = account_query.first_or_404()
    contact = contact_query.first_or_404()

    if contact.crm_account_id == account.id:
        flash(f'{contact.full_name} is already linked to {account.name}.', 'info')
    else:
        try:
            # Store previous account name for the flash message if contact was previously linked
            old_account_name = contact.crm_account.name if contact.crm_account else None
            
            contact.crm_account_id = account.id
            db.session.commit()
            
            if old_account_name:
                flash(f'{contact.full_name} has been successfully re-linked from {old_account_name} to {account.name}!', 'success')
            else:
                flash(f'{contact.full_name} has been successfully linked to {account.name}!', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error linking contact {contact_id} to account {account_id}: {e}")
            flash('Error linking contact. Please try again.', 'error')
            
    return redirect(url_for('crm.view_account', account_id=account.id))

@crm_bp.route('/accounts/<int:account_id>/delete', methods=['POST'])
@login_required
@sales_required
def delete_account(account_id):
    """Delete account, accessible by assigned rep, sales manager, or admin."""
    query = CrmAccount.query.filter_by(id=account_id)
    if not (hasattr(current_user, 'sales_profile') and current_user.sales_profile and 
            (current_user.sales_profile.role == 'sales_manager' or 
             (CrmAccount.query.with_entities(CrmAccount.sales_rep_id).filter_by(id=account_id).scalar() == current_user.sales_profile.id))):
        query = query.filter(CrmAccount.sales_rep_id == current_user.sales_profile.id)
    account = query.first_or_404()
    
    try:
        # Unlink contacts before deleting the account
        # This ensures that if the account deletion fails for some reason after unlinking,
        # contacts are at least unlinked. Or, you could do it in one transaction.
        # For simplicity, we do it sequentially here.
        
        # Fetch all contacts linked to this account
        linked_contacts = Contact.query.filter_by(crm_account_id=account.id).all()
        for contact in linked_contacts:
            contact.crm_account_id = None
        # db.session.commit() # Commit unlinking separately or together with delete

        account_name = account.name
        db.session.delete(account)
        db.session.commit() # Commits both unlinking (if not committed above) and deletion
        flash(f'Account "{account_name}" and its contact links have been successfully deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting account {account_id}: {e}")
        flash('Error deleting account. Please try again.', 'error')
        return redirect(url_for('crm.view_account', account_id=account.id)) # Redirect back to detail view on error
        
    return redirect(url_for('crm.accounts')) # Redirect to account list on success

@crm_bp.route('/accounts/<int:account_id>/update-status', methods=['POST'])
@login_required
@sales_required
@csrf.exempt # Exempt from global CSRF if form isn't submitting it, but we'll check header
def update_account_status_inline(account_id):
    # Manual CSRF check from header
    csrf_token = request.headers.get('X-CSRFToken')
    try:
        validate_csrf(csrf_token) # validate_csrf needs to be imported from flask_wtf.csrf
    except ValidationError as e:
        current_app.logger.warning(f'CSRF validation failed for account status update: {e}')
        return jsonify({'success': False, 'message': 'Invalid CSRF token.'}), 403

    account_query = CrmAccount.query.filter_by(id=account_id)
    # Ensure the current user (if not a manager) owns this account
    if not current_user.sales_profile.role == 'sales_manager':
        account_query = account_query.filter_by(sales_rep_id=get_current_sales_rep_id())
    
    account = account_query.first()

    if not account:
        return jsonify({'success': False, 'message': 'Account not found or access denied.'}), 404

    data = request.get_json()
    new_status = data.get('status')

    if not new_status or new_status == "": # Allow unsetting status if "-- Select --" is chosen
        account.status = None
    elif new_status not in CRM_ACCOUNT_STATUSES: # CRM_ACCOUNT_STATUSES must be available here
        return jsonify({'success': False, 'message': f'Invalid status: {new_status}'}), 400
    else:
        account.status = new_status
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Status updated', 'new_status': account.status})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating account {account_id} status: {e}")
        return jsonify({'success': False, 'message': 'Error saving update to database.'}), 500

@crm_bp.route('/accounts/<int:account_id>/update-field', methods=['POST'])
@login_required
@sales_required
@csrf.exempt # Will validate CSRF from header
def update_account_field_inline(account_id):
    # Manual CSRF check from header
    csrf_token = request.headers.get('X-CSRFToken')
    try:
        validate_csrf(csrf_token)
    except ValidationError as e:
        current_app.logger.warning(f'CSRF validation failed for account field update: {e}')
        return jsonify({'success': False, 'message': 'Invalid CSRF token.'}), 403

    account_query = CrmAccount.query.filter_by(id=account_id)
    if not current_user.sales_profile.role == 'sales_manager':
        account_query = account_query.filter_by(sales_rep_id=get_current_sales_rep_id())
    
    account = account_query.first()

    if not account:
        return jsonify({'success': False, 'message': 'Account not found or access denied.'}), 404

    data = request.get_json()
    field_name = data.get('field')
    new_value = data.get('value', '').strip() # Default to empty string and strip

    # Whitelist of editable fields for security
    allowed_fields = ['name', 'phone_number', 'website', 'industry', 'address'] 
    if field_name not in allowed_fields:
        return jsonify({'success': False, 'message': f'Field {field_name} is not allowed for inline editing.'}), 400

    # Basic validation for phone_number as an example (can be expanded)
    if field_name == 'phone_number' and new_value:
        # Example: allow digits, spaces, +, -, (, )
        import re
        if not re.match(r'^[\d\s\+\-\(\)]*$', new_value):
            return jsonify({'success': False, 'message': 'Invalid characters in phone number.'}), 400
        if len(new_value) > 30:
             return jsonify({'success': False, 'message': 'Phone number is too long.'}), 400
    elif field_name == 'website' and new_value:
        # A very basic check. For robust validation, use a library or a more complex regex.
        if not (new_value.startswith('http://') or new_value.startswith('https://')) and '.' not in new_value:
            # Not a full URL and doesn't look like a domain
            # To make it more lenient, you might adjust this or rely on form validation for full edits
            pass # For now, allow simpler website entries, full validation on main form
        if len(new_value) > 255:
            return jsonify({'success': False, 'message': 'Website URL is too long.'}), 400
    elif new_value and len(new_value) > 255: # General length check for other string fields
        return jsonify({'success': False, 'message': f'{field_name.replace("_", " ").title()} is too long (max 255 chars).'}), 400


    try:
        setattr(account, field_name, new_value if new_value else None) # Set to None if empty string
        db.session.commit()
        return jsonify({'success': True, 'message': f'{field_name.replace("_", " ").title()} updated', 'new_value': getattr(account, field_name)})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating account {account_id} field {field_name}: {e}")
        return jsonify({'success': False, 'message': 'Error saving update to database.'}), 500

# --- CSV Import Route --- #
@crm_bp.route('/import', methods=['GET', 'POST'])
@login_required
@sales_required
def import_csv():
    """Handle CSV file uploads for importing contacts or accounts."""
    form = ImportCsvForm()
    if form.validate_on_submit():
        csv_file = form.csv_file.data
        import_type = form.import_type.data # 'contacts' or 'accounts'

        if csv_file and allowed_file(csv_file.filename):
            original_filename = secure_filename(csv_file.filename)
            # Ensure the upload folder exists
            upload_dir = os.path.join(current_app.root_path, UPLOAD_FOLDER)
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)
            
            unique_id = uuid.uuid4().hex
            temp_filename = f"{unique_id}_{original_filename}"
            temp_filepath = os.path.join(upload_dir, temp_filename)
            
            try:
                csv_file.save(temp_filepath)
                headers = []
                with open(temp_filepath, 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    try:
                        headers = next(reader)
                    except StopIteration:
                        flash('Uploaded CSV file is empty or has no headers.', 'danger')
                        os.remove(temp_filepath) 
                        return redirect(url_for('crm.import_csv'))
                
                if not headers:
                    flash('Could not read headers from CSV file.', 'danger')
                    os.remove(temp_filepath) 
                    return redirect(url_for('crm.import_csv'))

                session['csv_import_temp_path'] = temp_filepath
                session['csv_import_original_filename'] = original_filename
                session['csv_import_type'] = import_type
                session['csv_headers'] = headers

                target_fields_dict = CONTACT_IMPORT_FIELDS if import_type == 'contacts' else ACCOUNT_IMPORT_FIELDS
                applies_to_enum = CustomFieldAppliesTo.CONTACT if import_type == 'contacts' else CustomFieldAppliesTo.ACCOUNT
                custom_field_definitions = CustomFieldDefinition.query.filter_by(applies_to=applies_to_enum).order_by(CustomFieldDefinition.name).all()
                
                mapping_choices = [('_ignore_', '-- Ignore this column --')]
                mapping_choices.extend([(key, label) for key, label in target_fields_dict.items()])
                for cf_def in custom_field_definitions:
                    mapping_choices.append(
                        (f"custom_field_def_{cf_def.id}", f"Custom: {cf_def.name} ({cf_def.field_type.name.title()})")
                    )
                mapping_choices.append( ('_create_new_custom_field_', '+ Create a New Custom Field from this Column') )

                # --- ADDED: Fetch sales users for owner dropdown ---
                sales_users_list = db.session.query(SalesUser).join(User, SalesUser.user_id == User.id).filter(User.name != None).order_by(User.name).all()
                # --- END ADDED ---

                current_app.logger.info("---- Preparing to render confirm_csv_mapping.html ----")
                current_app.logger.info(f"  Form object type: {type(form)}")
                current_app.logger.info(f"  Original Filename: {original_filename}")
                current_app.logger.info(f"  Import Type: {import_type}")
                current_app.logger.info(f"  CSV Headers: {headers}")
                current_app.logger.info(f"  Target Fields: {target_fields_dict}")
                current_app.logger.info("---------------------------------------------------------")
                current_app.logger.info(f"  Sales Users for dropdown: {[(su.id, su.user.username) for su in sales_users_list]}") # Log fetched users

                return render_template('confirm_csv_mapping.html',
                                       form=form, 
                                       headers=headers, 
                                       import_type=import_type,
                                       mapping_choices=mapping_choices, 
                                       original_filename=original_filename,
                                       sales_users_list=sales_users_list) # <-- PASS sales_users_list

            except Exception as e:
                current_app.logger.error(f"Error during CSV upload/header reading: {e}")
                flash(f'An error occurred: {str(e)}', 'danger')
                if os.path.exists(temp_filepath): # ensure cleanup if file was saved
                    os.remove(temp_filepath)
                return redirect(url_for('crm.import_csv'))
        else:
            flash('Invalid file type. Please upload a CSV file.', 'danger')

    return render_template('crm/import_csv.html', form=form, title="Import Data from CSV")

@crm_bp.route('/process-mapped-import', methods=['POST'])
@login_required
@sales_required
def process_mapped_import():
    # Retrieve data from session
    temp_filepath = session.pop('csv_import_temp_path', None)
    original_filename = session.pop('csv_import_original_filename', None)
    import_type = session.pop('csv_import_type', None)
    csv_headers_from_session = session.pop('csv_headers', None) # Original headers for reference

    if not all([temp_filepath, original_filename, import_type, csv_headers_from_session]):
        flash('Import session expired or is invalid. Please try uploading again.', 'warning')
        return redirect(url_for('crm.import_csv'))

    if not os.path.exists(temp_filepath):
        flash(f'Temporary import file {original_filename} not found. It might have been already processed or an error occurred. Please re-upload.', 'danger')
        return redirect(url_for('crm.import_csv'))

    # Get mappings from the form (form fields will be like 'map_0', 'map_1', etc. for each header)
    # Example: header_mappings = {csv_headers_from_session[i]: request.form.get(f'map_{i}') for i in range(len(csv_headers_from_session))}
    header_mappings = {}
    new_custom_fields_to_create_details = {} # To store info about CFs to be created: {csv_header_index: {name: 'X', type: 'Y'}}

    for i, header in enumerate(csv_headers_from_session):
        mapped_to = request.form.get(f'map_{i}')
        if mapped_to == '_create_new_custom_field_':
            # If user chose to create a new custom field for this CSV header
            # The template should send back the original header name and the chosen field type
            # We expect fields like: new_custom_field_original_name_{i} and new_custom_field_type_{i}
            original_header_name = request.form.get(f'new_custom_field_original_name_{i}', header) # Fallback to header if not sent
            chosen_field_type_str = request.form.get(f'new_custom_field_type_{i}')
            
            current_app.logger.info(f"DEBUG: For CSV header '{original_header_name}' (index {i}), received new_custom_field_type: '{chosen_field_type_str}'") # <-- ADDED DEBUG LOG

            if not chosen_field_type_str:
                flash(f"Missing field type for new custom field based on CSV column '{original_header_name}'. This column will be ignored.", "warning")
                header_mappings[header] = '_ignore_' # Treat as ignore if type is missing
                continue
            
            try:
                # Convert string type to Enum. Ensure CustomFieldType is imported.
                field_type_enum = CustomFieldType(chosen_field_type_str.lower()) # Ensure lowercase for enum value matching
            except ValueError:
                flash(f"Invalid field type '{chosen_field_type_str}' for new custom field '{original_header_name}'. Defaulting to TEXT or ignoring.", "warning")
                # Default to TEXT or handle as error. For now, let's default if invalid, or you could make it an error.
                field_type_enum = CustomFieldType.TEXT 
            
            new_custom_fields_to_create_details[i] = {
                'original_header': original_header_name, 
                'field_type': field_type_enum, 
                'definition_id': None # Will be filled after creation
            }
            header_mappings[header] = f'_placeholder_for_new_cf_{i}' # Temporary placeholder, will be replaced by def ID

        elif mapped_to and mapped_to != '_ignore_': # If not explicitly ignored and not creating new
            header_mappings[header] = mapped_to
        # If mapped_to is '_ignore_' or None, it's implicitly ignored by not being in header_mappings

    if not header_mappings and not new_custom_fields_to_create_details:
        flash('No column mappings were provided. Nothing to import.', 'info')
        os.remove(temp_filepath) # Clean up temp file
        return redirect(url_for('crm.import_csv'))

    current_app.logger.info(f"Processing CSV import for: {original_filename}, type: {import_type}")
    current_app.logger.info(f"Header mappings: {header_mappings}")
    current_app.logger.info(f"New Custom Fields to create: {new_custom_fields_to_create_details}")

    # --- Create New Custom Field Definitions First (if any) ---
    created_custom_field_def_ids = {}
    import_type_enum = CustomFieldAppliesTo.CONTACT if import_type == 'contacts' else CustomFieldAppliesTo.ACCOUNT

    for csv_header_index, cf_details in new_custom_fields_to_create_details.items():
        original_csv_header = cf_details['original_header']
        field_type = cf_details['field_type']
        
        # Check for uniqueness before creating
        existing_def = CustomFieldDefinition.query.filter(
            func.lower(CustomFieldDefinition.name) == func.lower(original_csv_header),
            CustomFieldDefinition.applies_to == import_type_enum
        ).first()

        if existing_def:
            flash(f"A custom field named '{original_csv_header}' already exists for {import_type_enum.name.title()}. Data will be mapped to this existing field.", 'info')
            created_custom_field_def_ids[csv_header_index] = existing_def.id
            # Update the main header_mappings placeholder to use this existing definition ID
            header_mappings[original_csv_header] = f"custom_field_def_{existing_def.id}"
        else:
            try:
                new_definition = CustomFieldDefinition(
                    name=original_csv_header, # Use the original CSV header as the name
                    field_type=field_type,
                    applies_to=import_type_enum,
                    # options=None (add logic if creating dropdowns with options later)
                )
                db.session.add(new_definition)
                db.session.flush() # To get the ID
                created_custom_field_def_ids[csv_header_index] = new_definition.id
                # Update the main header_mappings placeholder
                header_mappings[original_csv_header] = f"custom_field_def_{new_definition.id}"
                flash(f"Successfully created new custom field: '{new_definition.name}' ({new_definition.field_type.name.title()}) for {import_type_enum.name.title()}.")
            except Exception as e_create_def:
                db.session.rollback()
                current_app.logger.error(f"Error creating new CustomFieldDefinition for '{original_csv_header}': {e_create_def}")
                flash(f"Could not create new custom field '{original_csv_header}'. This column might be ignored or cause errors.", 'danger')
                # Remove from header_mappings to ignore this column if creation failed
                if original_csv_header in header_mappings:
                    del header_mappings[original_csv_header]
    
    # Commit all newly created CustomFieldDefinitions if any success, or after loop if preferred
    try:
        db.session.commit() # Commit new definitions
    except Exception as e_commit_defs:
        db.session.rollback()
        current_app.logger.error(f"Error committing newly created custom field definitions: {e_commit_defs}")
        flash("Database error while saving new custom field definitions. Some might not have been created.", "danger")
        # Potentially re-evaluate header_mappings if commit failed for some defs

    # --- Actual Import Logic (adapted from previous import_csv) ---
    # sales_rep_id = current_user.sales_profile.id # Old way, will be replaced
    
    # --- Determine the Sales Rep ID for this import batch --- #
    assigned_owner_choice = request.form.get('import_owner_sales_rep_id')
    final_sales_rep_id_for_import = None # Default to None (unassigned)

    if assigned_owner_choice == '_current_user_' or not assigned_owner_choice:
        if hasattr(current_user, 'sales_profile') and current_user.sales_profile:
            final_sales_rep_id_for_import = current_user.sales_profile.id
        else:
            # This case should ideally not happen if route is protected by @sales_required
            # and user has a sales_profile. Log a warning if it does.
            current_app.logger.warning("CSV Import: Current user selected as owner, but no sales_profile found. Records might be unassigned or error.")
            # Decide a fallback: unassigned, or prevent import? For now, will likely be unassigned.
            pass 
    elif assigned_owner_choice == '_unassigned_':
        final_sales_rep_id_for_import = None
    else:
        try:
            potential_owner_id = int(assigned_owner_choice)
            # Validate this ID corresponds to an actual SalesUser
            owner_user = SalesUser.query.get(potential_owner_id)
            if owner_user:
                final_sales_rep_id_for_import = owner_user.id
            else:
                current_app.logger.warning(f"CSV Import: Specified owner ID '{potential_owner_id}' not found. Defaulting to current user or unassigned.")
                # Fallback to current user if possible, else unassigned
                if hasattr(current_user, 'sales_profile') and current_user.sales_profile:
                    final_sales_rep_id_for_import = current_user.sales_profile.id
                else:
                    final_sales_rep_id_for_import = None # Fallback to unassigned
        except ValueError:
            current_app.logger.warning(f"CSV Import: Invalid owner ID format '{assigned_owner_choice}'. Defaulting to current user or unassigned.")
            if hasattr(current_user, 'sales_profile') and current_user.sales_profile:
                final_sales_rep_id_for_import = current_user.sales_profile.id
            else:
                final_sales_rep_id_for_import = None # Fallback to unassigned
                
    current_app.logger.info(f"CSV Import: Final sales_rep_id for new records: {final_sales_rep_id_for_import}")
    # --- END Owner Determination --- #

    imported_count = 0
    skipped_count = 0
    error_count = 0
    errors_details = [] # Store details about errors
    processed_rows = 0

    try:
        with open(temp_filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f) # Use DictReader for easier access by header name
            
            # Validate that all mapped headers exist in the DictReader fieldnames
            # (though DictReader uses the first row, so this should be fine)

            for row_num, row_data in enumerate(reader, start=1): # Start from 1 for user-friendly row numbers
                processed_rows += 1
                try:
                    # Construct data dict based on mappings
                    data_to_import = {}
                    custom_data_parts = {} # For the old generic 'custom_data' field if still used
                    custom_field_values_to_create = [] # For new structured custom fields

                    for csv_col_name, model_field_key_or_custom_def_id in header_mappings.items():
                        if csv_col_name not in row_data:
                            errors_details.append(f"Row {row_num+1}: CSV column '{csv_col_name}' (mapped to '{model_field_key_or_custom_def_id}') not found in data row. Skipping row.")
                            raise ValueError(f"Missing column '{csv_col_name}' in row")
                        
                        value = row_data[csv_col_name].strip() if row_data[csv_col_name] else None

                        if model_field_key_or_custom_def_id.startswith('custom_field_def_'):
                            if value is not None: # Only process if there's a value
                                definition_id = int(model_field_key_or_custom_def_id.split('_')[-1])
                                # We'll create CustomFieldValue objects after the main entity is saved and has an ID.
                                # Store them temporarily.
                                custom_field_values_to_create.append({'definition_id': definition_id, 'value': value})
                        elif model_field_key_or_custom_def_id == 'custom_data': # Handle old generic custom_data
                            if value is not None:
                                custom_data_parts[csv_col_name] = value
                        elif value is not None: # Standard field
                            data_to_import[model_field_key_or_custom_def_id] = value
                   
                    # If custom_data_parts has anything (for the old generic field)
                    if custom_data_parts:
                        if len(custom_data_parts) == 1 and header_mappings.get(list(custom_data_parts.keys())[0]) == 'custom_data':
                            # If only one column was mapped to custom_data, use its value directly
                            val = list(custom_data_parts.values())[0]
                            try:
                                data_to_import['custom_data'] = json.loads(val) if val.startswith( ('{', '[') ) else val
                            except json.JSONDecodeError:
                                data_to_import['custom_data'] = val # store as raw string
                        else:
                             # Multiple columns mapped to be part of custom_data, store as a dict
                            data_to_import['custom_data'] = custom_data_parts 

                    if not data_to_import and not custom_data_parts: # Skip if row is essentially empty after mapping
                        skipped_count += 1
                        continue

                    # ---- Object Creation/Update ----
                    if import_type == 'contacts':
                        # Required fields for contact (minimal)
                        if not data_to_import.get('last_name') and not data_to_import.get('email') and not data_to_import.get('phone_number'): # Added phone_number as an option
                            errors_details.append(f"Row {row_num+1}: Contact must have at least a Last Name, Email, or Phone Number. Skipping.")
                            error_count += 1
                            continue

                        # Link to CrmAccount if 'crm_account_name' is provided and mapped
                        account_id_to_link = None
                        account_name_from_csv = data_to_import.pop('crm_account_name', None) # Remove from direct contact fields, get None if not present

                        if account_name_from_csv:
                            # Try to find existing account by name for the current sales rep
                            # MODIFIED: When checking for existing company, it should ideally check globally or based on permissions, not just current rep if a specific owner is chosen for import.
                            # For now, the auto-create will use the final_sales_rep_id_for_import.
                            # The logic for *finding* an existing company to link to might need more thought if it should bypass the new owner setting.
                            # Let's assume for now, finding is still scoped or global, but CREATION uses the new owner.
                            account = CrmAccount.query.filter(
                                func.lower(CrmAccount.name) == func.lower(account_name_from_csv)
                                # Consider if this filter needs to change based on who the new owner is.
                                # If importing for another user, should it only link to *their* existing companies?
                                # Or any company they have access to see? For now, let's keep it simpler:
                                # It tries to find globally or based on current user's team visibility (if implemented).
                                # The sales_rep_id on the CrmAccount itself will be used to determine ownership.
                            ).first() # This might need adjustment if a manager is importing for someone else.
                            
                            if account:
                                account_id_to_link = account.id
                                current_app.logger.info(f"Row {row_num+1}: Found existing company '{account.name}' (ID: {account.id}) to link for contact.")
                            else:
                                # --- Auto-create basic company if it doesn't exist --- 
                                try:
                                    current_app.logger.info(f"Row {row_num+1}: Company '{account_name_from_csv}' not found. Attempting to create new company with owner ID: {final_sales_rep_id_for_import}.")
                                    new_company_for_contact = CrmAccount(
                                        name=account_name_from_csv,
                                        sales_rep_id=final_sales_rep_id_for_import, # Assign determined owner
                                        status='New' 
                                    )
                                    db.session.add(new_company_for_contact)
                                    db.session.flush() # To get the ID of the new company
                                    account_id_to_link = new_company_for_contact.id
                                    flash(f"Created new company '{new_company_for_contact.name}' from contact import row {row_num+1}.", 'success-auto-create') # Use a distinct category for styling if needed
                                    current_app.logger.info(f"Row {row_num+1}: Successfully created new company '{new_company_for_contact.name}' (ID: {new_company_for_contact.id}).")
                                except Exception as e_create_company:
                                    db.session.rollback() # Rollback company creation part for this row
                                    current_app.logger.error(f"Row {row_num+1}: Error auto-creating company '{account_name_from_csv}': {e_create_company}")
                                    errors_details.append(f"Row {row_num+1}: Could not create company '{account_name_from_csv}'. Contact will be created without company link. Error: {str(e_create_company)[:100]}")
                                    # Fall through, account_id_to_link will remain None
                        
                        # Check for existing contact (e.g., by email if provided)
                        existing_contact = None
                        if data_to_import.get('email'):
                            # When checking for existing contact, should this also be global or owner-specific?
                            # If we import and assign to User B, an email duplicate check should ideally be global.
                            existing_contact = Contact.query.filter_by(email=data_to_import['email']).first() # Global check
                        
                        if existing_contact:
                            # Update existing contact (optional - for now, we skip if exists to avoid duplicates, or could update)
                            errors_details.append(f"Row {row_num+1}: Contact with email '{data_to_import['email']}' (ID: {existing_contact.id}, Owner: {existing_contact.sales_rep_id}) already exists. Skipped.")
                            skipped_count +=1
                            continue 

                        contact = Contact(
                            sales_rep_id=final_sales_rep_id_for_import, # Assign determined owner
                            crm_account_id=account_id_to_link,
                            **data_to_import 
                        )
                        db.session.add(contact)
                        db.session.flush() # Flush to get contact.id before creating linked CustomFieldValue

                        # Create CustomFieldValue entries
                        for cf_data in custom_field_values_to_create:
                            # Here, you might want to fetch the CustomFieldDefinition to check its type
                            # and convert/validate cf_data['value'] accordingly before saving.
                            # For simplicity now, saving as string.
                            cf_def_check = CustomFieldDefinition.query.get(cf_data['definition_id'])
                            if not cf_def_check:
                                errors_details.append(f"Row {row_num+1}: Custom field definition ID {cf_data['definition_id']} not found. Skipping custom field.")
                                continue

                            # Basic type conversion/validation (can be expanded)
                            processed_value_for_cf = str(cf_data['value']) # Default to string
                            if cf_def_check.field_type == CustomFieldType.BOOLEAN:
                                processed_value_for_cf = str(str(cf_data['value']).lower() in ['true', '1', 'yes', 'on'])
                            elif cf_def_check.field_type == CustomFieldType.DATE:
                                try:
                                    # Attempt to parse if it looks like a date, store as ISO string
                                    dt_obj = datetime.strptime(str(cf_data['value']), '%Y-%m-%d') # Example format
                                    processed_value_for_cf = dt_obj.date().isoformat()
                                except ValueError:
                                    try: # Try another common format like MM/DD/YYYY
                                        dt_obj = datetime.strptime(str(cf_data['value']), '%m/%d/%Y')
                                        processed_value_for_cf = dt_obj.date().isoformat()
                                    except ValueError:
                                        errors_details.append(f"Row {row_num+1}: Date format for custom field '{cf_def_check.name}' ('{cf_data['value']}') not recognized. Stored as text or skipped if critical.")
                                        # Decide: store as text, skip, or make this an error for the row?
                                        # For now, let's store as text if parsing fails, or you could make it stricter.
                                        processed_value_for_cf = str(cf_data['value']) 
                            elif cf_def_check.field_type == CustomFieldType.NUMBER:
                                try:
                                    int(cf_data['value']) # Validate it's an int
                                    processed_value_for_cf = str(cf_data['value']) # Store as string, consistent with CustomFieldValue.value
                                except ValueError:
                                     errors_details.append(f"Row {row_num+1}: Value for custom number field '{cf_def_check.name}' ('{cf_data['value']}') is not a valid number. Stored as text or skipped.")
                                     processed_value_for_cf = str(cf_data['value']) # Or skip

                            # Check against dropdown options if it's a dropdown
                            if cf_def_check.field_type == CustomFieldType.DROPDOWN:
                                if cf_def_check.options and 'options' in cf_def_check.options:
                                    if str(cf_data['value']) not in cf_def_check.options['options']:
                                        errors_details.append(f"Row {row_num+1}: Value '{cf_data['value']}' for dropdown custom field '{cf_def_check.name}' is not a valid option. Stored as provided or skipped.")
                                        # Decide: store anyway, or skip, or error? For now, store as provided.
                                        processed_value_for_cf = str(cf_data['value'])
                                else: # Dropdown field without defined options (should ideally not happen)
                                    processed_value_for_cf = str(cf_data['value'])

                            new_val = CustomFieldValue(
                                definition_id=cf_data['definition_id'],
                                contact_id=contact.id,
                                value=processed_value_for_cf
                            )
                            db.session.add(new_val)
                        
                        imported_count += 1

                    elif import_type == 'accounts':
                        if not data_to_import.get('name'):
                            errors_details.append(f"Row {row_num+1}: Account must have a Name. Skipping.")
                            error_count += 1
                            continue
                        
                        existing_account = CrmAccount.query.filter_by(name=data_to_import['name'], sales_rep_id=sales_rep_id).first()
                        if existing_account:
                            errors_details.append(f"Row {row_num+1}: Account with name '{data_to_import['name']}' already exists. Skipped.")
                            skipped_count += 1
                            continue
                            # TODO: Add update logic if desired in future

                        account = CrmAccount(
                            sales_rep_id=final_sales_rep_id_for_import, # Assign determined owner
                            **data_to_import
                        )
                        db.session.add(account)
                        db.session.flush() # Flush to get account.id

                        # Create CustomFieldValue entries
                        for cf_data in custom_field_values_to_create:
                            cf_def_check = CustomFieldDefinition.query.get(cf_data['definition_id'])
                            if not cf_def_check:
                                errors_details.append(f"Row {row_num+1}: Custom field definition ID {cf_data['definition_id']} not found for account. Skipping custom field.")
                                continue
                            
                            processed_value_for_cf = str(cf_data['value'])
                            if cf_def_check.field_type == CustomFieldType.BOOLEAN:
                                processed_value_for_cf = str(str(cf_data['value']).lower() in ['true', '1', 'yes', 'on'])
                            elif cf_def_check.field_type == CustomFieldType.DATE:
                                try:
                                    dt_obj = datetime.strptime(str(cf_data['value']), '%Y-%m-%d')
                                    processed_value_for_cf = dt_obj.date().isoformat()
                                except ValueError:
                                    try: 
                                        dt_obj = datetime.strptime(str(cf_data['value']), '%m/%d/%Y')
                                        processed_value_for_cf = dt_obj.date().isoformat()
                                    except ValueError:
                                        errors_details.append(f"Row {row_num+1}: Date format for custom field '{cf_def_check.name}' ('{cf_data['value']}') not recognized for account. Stored as text.")
                                        processed_value_for_cf = str(cf_data['value'])
                            elif cf_def_check.field_type == CustomFieldType.NUMBER:
                                try:
                                    int(cf_data['value'])
                                    processed_value_for_cf = str(cf_data['value'])
                                except ValueError:
                                     errors_details.append(f"Row {row_num+1}: Value for custom number field '{cf_def_check.name}' ('{cf_data['value']}') not valid for account. Stored as text.")
                                     processed_value_for_cf = str(cf_data['value'])
                            
                            if cf_def_check.field_type == CustomFieldType.DROPDOWN:
                                if cf_def_check.options and 'options' in cf_def_check.options:
                                    if str(cf_data['value']) not in cf_def_check.options['options']:
                                        errors_details.append(f"Row {row_num+1}: Value '{cf_data['value']}' for dropdown custom field '{cf_def_check.name}' is not a valid option for account. Stored as provided.")
                                        processed_value_for_cf = str(cf_data['value'])
                                else:
                                    processed_value_for_cf = str(cf_data['value'])

                            new_val = CustomFieldValue(
                                definition_id=cf_data['definition_id'],
                                account_id=account.id,
                                value=processed_value_for_cf
                            )
                            db.session.add(new_val)
                            
                        imported_count += 1
                   
                    # Commit per row or in batches? For simplicity, per row with try-except.
                    # Consider batch commits for very large files later.
                    try:
                        db.session.commit() 
                    except Exception as e_commit:
                        db.session.rollback()
                        current_app.logger.error(f"Error committing row {row_num+1} during CSV import: {e_commit}")
                        errors_details.append(f"Row {row_num+1}: Database error - {str(e_commit)[:100]}. Skipping.")
                        error_count += 1
                        # Reset imported_count for this row if it was incremented optimistically
                        if import_type == 'contacts' and 'contact' in locals(): imported_count -=1
                        if import_type == 'accounts' and 'account' in locals(): imported_count -=1 
                        
                except Exception as e_row:
                    # Catch errors for a specific row, log, and continue with the next row
                    current_app.logger.error(f"Error processing row {row_num+1} in {original_filename}: {e_row}")
                    # errors_details.append(f"Row {row_num+1}: {str(e_row)}. Skipped.") # Already handled if specific error
                    if not any(f"Row {row_num+1}" in err_detail for err_detail in errors_details):
                         errors_details.append(f"Row {row_num+1}: General processing error - {str(e_row)[:100]}. Skipped.")
                    error_count += 1
                    db.session.rollback() # Ensure rollback for this row's transaction

        flash(f'CSV Import Summary for "{original_filename}" ({import_type}):', 'info')
        flash(f'- Successfully imported: {imported_count}', 'success' if imported_count > 0 else 'info')
        flash(f'- Skipped (e.g., duplicates, missing required fields, or empty rows): {skipped_count + (processed_rows - imported_count - error_count)}', 'warning' if skipped_count > 0 else 'info')
        flash(f'- Errors encountered: {error_count}', 'danger' if error_count > 0 else 'info')

        if errors_details:
            flash('Error Details:', 'secondary')
            for err_detail in errors_details[:10]: # Show first 10 errors
                flash(err_detail, 'danger')
            if len(errors_details) > 10:
                flash(f'...and {len(errors_details) - 10} more errors (check logs for full details).', 'warning')
        
    except FileNotFoundError:
        current_app.logger.error(f"Temporary import file {temp_filepath} not found during processing.")
        flash(f'Error: Temporary import file {original_filename} seems to have been removed before processing could complete. Please try again.', 'danger')
    except Exception as e_general:
        db.session.rollback()
        current_app.logger.error(f"General error during mapped CSV import processing of {original_filename}: {e_general}")
        flash(f'A general error occurred during import: {str(e_general)}. Check logs.', 'danger')
    finally:
        # Clean up the temporary file
        if temp_filepath and os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
                current_app.logger.info(f"Successfully removed temporary import file: {temp_filepath}")
            except Exception as e_remove:
                current_app.logger.error(f"Error removing temporary import file {temp_filepath}: {e_remove}")

    return redirect(url_for('crm.import_csv'))

# --- Template Download Routes --- #
@crm_bp.route('/download-template/<import_type>')
@login_required
@sales_required
def download_template(import_type):
    """Generate and return a sample CSV template file."""
    si = io.StringIO()
    writer = csv.writer(si)
    
    if import_type == 'contacts':
        headers = ['first_name', 'last_name', 'email', 'phone_number', 'job_title', 'status', 'source', 'company_name', 'custom_notes']
        filename = 'contacts_template.csv'
    elif import_type == 'accounts':
        headers = ['name', 'website', 'phone_number', 'address', 'industry', 'status', 'custom_notes']
        filename = 'accounts_template.csv'
    else:
        flash('Invalid template type requested.', 'error')
        return redirect(url_for('crm.import_csv'))
        
    writer.writerow(headers)
    output = si.getvalue()
    si.close()
    
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition":
                 f"attachment; filename={filename}"}
    )

# --- Call Log Routes --- #
@crm_bp.route('/calls')
@login_required
@sales_required
def calls():
    """Page to display call logs and potentially the softphone UI"""
    return render_template('calls.html')

@crm_bp.route('/call-logs', methods=['GET'])
@login_required
@sales_required
def get_call_logs():
    """Fetch call log history and contacts for the current sales user, with filtering and pagination."""
    if not current_user.sales_profile:
        return jsonify({'success': False, 'message': 'Sales profile required'}), 403
        
    sales_rep_id = current_user.sales_profile.id
    
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int) # Default 15 items per page

    # Filter parameters
    direction_filter = request.args.get('direction')
    contact_id_filter = request.args.get('contact_id', type=int)
    outcome_filter = request.args.get('outcome')
    date_from_str = request.args.get('date_from')
    date_to_str = request.args.get('date_to')

    try:
        logs_query = CallLog.query.filter_by(sales_rep_id=sales_rep_id)

        if direction_filter and direction_filter in ['inbound', 'outbound']:
            logs_query = logs_query.filter(CallLog.direction == direction_filter)
        
        if contact_id_filter:
            # Ensure the contact belongs to the sales_rep for security/privacy
            contact_exists = Contact.query.filter_by(id=contact_id_filter, sales_rep_id=sales_rep_id).first()
            if contact_exists:
                logs_query = logs_query.filter(CallLog.contact_id == contact_id_filter)
            else:
                # Contact not found for this rep, so effectively no logs for this filter for this rep
                logs_query = logs_query.filter(CallLog.id == -1) # No results

        if outcome_filter and outcome_filter in [o[0] for o in CALL_OUTCOMES]:
            logs_query = logs_query.filter(CallLog.outcome == outcome_filter)
        
        if date_from_str:
            try:
                date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
                logs_query = logs_query.filter(func.date(CallLog.created_at) >= date_from)
            except ValueError:
                pass # Ignore invalid date format
        
        if date_to_str:
            try:
                date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
                logs_query = logs_query.filter(func.date(CallLog.created_at) <= date_to)
            except ValueError:
                pass # Ignore invalid date format

        logs_query = logs_query.order_by(CallLog.created_at.desc())
        
        # Paginate the query
        paginated_logs = logs_query.paginate(page=page, per_page=per_page, error_out=False)
        logs_for_page = paginated_logs.items
        
        # Fetch all contacts for this sales rep (for the filter dropdown)
        user_contacts = Contact.query.filter_by(sales_rep_id=sales_rep_id)\
                                .order_by(Contact.first_name, Contact.last_name).all()

        call_logs_data = [log.to_dict() for log in logs_for_page]
        contacts_data = [{'id': c.id, 'name': c.full_name} for c in user_contacts]
        call_outcomes_data = [{'value': val, 'label': lbl} for val, lbl in CALL_OUTCOMES]

        return jsonify({
            'success': True, 
            'call_logs': call_logs_data,
            'pagination': {
                'page': paginated_logs.page,
                'per_page': paginated_logs.per_page,
                'total_items': paginated_logs.total,
                'total_pages': paginated_logs.pages,
                'has_prev': paginated_logs.has_prev,
                'has_next': paginated_logs.has_next,
                'prev_num': paginated_logs.prev_num,
                'next_num': paginated_logs.next_num
            },
            'contacts': contacts_data,
            'call_outcomes': call_outcomes_data
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching CRM call logs: {str(e)}")
        return jsonify({'success': False, 'message': 'Error fetching call logs'}), 500

@crm_bp.route('/call-logs/<int:log_id>/link-contact', methods=['POST'])
@csrf.exempt # Exempt CSRF if called via basic JS fetch without CSRF token handling
@login_required
@sales_required
def link_call_log_contact(log_id):
    """Link a call log to a contact."""
    if not current_user.sales_profile:
        return jsonify({'success': False, 'message': 'Sales profile required'}), 403
    
    log = CallLog.query.get(log_id)
    
    # Validate: Log exists and belongs to the current sales rep
    if not log:
        return jsonify({'success': False, 'message': 'Call log not found'}), 404
    if log.sales_rep_id != current_user.sales_profile.id:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
    data = request.get_json()
    contact_id = data.get('contact_id')
    
    if not contact_id:
        return jsonify({'success': False, 'message': 'Missing contact_id'}), 400
        
    # Validate: Contact exists and belongs to the current sales rep
    contact = Contact.query.filter_by(id=contact_id, sales_rep_id=current_user.sales_profile.id).first()
    if not contact:
         return jsonify({'success': False, 'message': 'Contact not found or access denied'}), 404
         
    try:
        log.contact_id = contact.id
        db.session.commit()
        current_app.logger.info(f"Linked CallLog {log.id} to Contact {contact.id} for SalesRep {log.sales_rep_id}")
        return jsonify({
            'success': True, 
            'message': 'Call log linked successfully', 
            'contact_name': contact.full_name # Return name to update UI
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error linking call log {log_id} to contact {contact_id}: {e}")
        return jsonify({'success': False, 'message': 'Database error occurred'}), 500

@crm_bp.route('/call', methods=['POST'])
@csrf.exempt # Likely needed for AJAX calls from JS client
@login_required
@sales_required
def make_call():
    """Make an outbound call for a Sales User, optionally linking to a contact."""
    current_app.logger.info("=== Starting CRM make_call route ===")
    
    if not current_user.sales_profile:
         current_app.logger.error(f"User {current_user.id} lacks sales_profile for make_call")
         return jsonify({'success': False, 'message': 'Sales profile required'}), 403
    
    sales_rep_id = current_user.sales_profile.id
    is_manager = current_user.sales_profile.role == 'sales_manager' # Check if user is a manager

    data = request.get_json()
    if not data or 'to_number' not in data:
        return jsonify({'success': False, 'message': 'Missing to_number'}), 400
        
    to_number = data['to_number']
    record = data.get('record', False)
    contact_id_from_request = data.get('contact_id') # Get contact_id from request
    valid_contact_id_for_log = None

    # Validate contact_id if provided
    if contact_id_from_request:
        try:
            contact_id_int = int(contact_id_from_request)
            contact_query = Contact.query.filter_by(id=contact_id_int)
            # Managers can link to any contact, reps only their own
            if not is_manager:
                contact_query = contact_query.filter_by(sales_rep_id=sales_rep_id)
            
            contact_to_link = contact_query.first()
            if contact_to_link:
                valid_contact_id_for_log = contact_to_link.id
                current_app.logger.info(f"Call will be linked to Contact ID: {valid_contact_id_for_log}")
            else:
                current_app.logger.warning(f"Requested contact_id {contact_id_from_request} not found or access denied for sales_rep_id {sales_rep_id}.")
                # Optionally, you could return an error here if contact_id is mandatory or invalid
                # For now, we'll proceed without linking if contact is not valid, but log a warning.
        except ValueError:
            current_app.logger.warning(f"Invalid contact_id format received: {contact_id_from_request}. Must be an integer.")

    user_phone_number = current_user.sales_profile.phone_number
    if user_phone_number:
        from_number_to_use = user_phone_number
        current_app.logger.info(f"Using assigned sales number: {from_number_to_use}")
    else:
        from_number_to_use = current_app.config['TWILIO_PHONE_NUMBER']
        current_app.logger.info(f"Using default company number: {from_number_to_use}")
    
    current_app.logger.info(f"CRM call attempt from {from_number_to_use} to {to_number}")

    try:
        call_manager = CallManager()
        webhook_base = current_app.config['TWILIO_WEBHOOK_BASE_URL'].rstrip('/')
        
        twiml_params = urlencode({
            'DialTo': to_number, 
            'DialRecord': str(record).lower()
        })
        twiml_url = f"{webhook_base}/webhooks/voice?{twiml_params}"
        current_app.logger.info(f"Using TwiML URL: {twiml_url}")

        call = call_manager.client.calls.create(
            to=to_number,
            from_=from_number_to_use,
            url=twiml_url, 
            status_callback=f"{webhook_base}/webhooks/status",
            status_callback_event=['initiated', 'ringing', 'answered', 'completed']
        )
        call_sid = call.sid
        
        if call_sid:
            call_log = CallLog(
                call_sid=call_sid,
                status='initiated',
                direction='outbound',
                from_number=from_number_to_use, 
                to_number=to_number,
                sales_rep_id=sales_rep_id,
                contact_id=valid_contact_id_for_log  # Use the validated contact_id here
            )
            db.session.add(call_log)
            db.session.commit()
            current_app.logger.info(f"Created initial CRM call log for SID: {call_sid}, linked to contact_id: {valid_contact_id_for_log}")
            result = {'success': True, 'message': 'Call initiated', 'call_sid': call_sid}
        else:
             result = {'success': False, 'message': 'Failed to initiate call via Twilio'}

        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Error in CRM make_call: {str(e)}")
        return jsonify({'success': False, 'message': f'Error making call: {str(e)}'}), 500

# --- TASK CRUD OPERATIONS ---
@crm_bp.route('/tasks', methods=['GET', 'POST'])
@login_required
@sales_required
def manage_tasks():
    form = TaskForm()

    if not current_user.sales_profile:
        flash('Sales profile not found for this user.', 'error')
        return redirect(url_for('main.dashboard'))

    current_sales_rep_id = current_user.sales_profile.id
    is_manager = hasattr(current_user, 'sales_profile') and current_user.sales_profile.role == 'sales_manager'
    page_title = "My Tasks"
    today_date = date.today() # Get current date

    # Pre-fill form for GET requests if IDs are provided in query params
    if request.method == 'GET':
        preselected_deal_id = request.args.get('deal_id', type=int)
        preselected_contact_id = request.args.get('contact_id', type=int)
        preselected_account_id = request.args.get('account_id', type=int)

        if preselected_deal_id:
            deal_query = Deal.query.filter_by(id=preselected_deal_id)
            if not is_manager: 
                deal_query = deal_query.filter_by(sales_rep_id=current_sales_rep_id)
            deal_obj = deal_query.first()
            if deal_obj:
                form.deal_id.data = deal_obj
                if deal_obj.contact and not preselected_contact_id:
                    form.contact_id.data = deal_obj.contact
                if deal_obj.crm_account and not preselected_account_id:
                    form.crm_account_id.data = deal_obj.crm_account
            else:
                flash("Specified deal for new task not found or not accessible.", "warning")
        
        if preselected_contact_id:
            contact_query = Contact.query.filter_by(id=preselected_contact_id)
            if not is_manager: 
                contact_query = contact_query.filter_by(sales_rep_id=current_sales_rep_id)
            contact_obj = contact_query.first()
            if contact_obj:
                form.contact_id.data = contact_obj
                if contact_obj.crm_account and not preselected_account_id and not (form.crm_account_id.data and form.deal_id.data):
                    form.crm_account_id.data = contact_obj.crm_account
            else:
                flash("Specified contact for new task not found or not accessible.", "warning")
        
        if preselected_account_id:
            account_query = CrmAccount.query.filter_by(id=preselected_account_id)
            if not is_manager: 
                account_query = account_query.filter_by(sales_rep_id=current_sales_rep_id)
            account_obj = account_query.first()
            if account_obj:
                form.crm_account_id.data = account_obj
            elif not form.crm_account_id.data: 
                 flash("Specified account for new task not found or not accessible.", "warning")

    # Filter dropdowns based on role
    if is_manager:
        form.contact_id.query = Contact.query.order_by(Contact.first_name)
        form.crm_account_id.query = CrmAccount.query.order_by(CrmAccount.name)
        form.deal_id.query = Deal.query.order_by(Deal.name)
    else:
        form.contact_id.query = Contact.query.filter_by(sales_rep_id=current_sales_rep_id).order_by(Contact.first_name)
        form.crm_account_id.query = CrmAccount.query.filter_by(sales_rep_id=current_sales_rep_id).order_by(CrmAccount.name)
        form.deal_id.query = Deal.query.filter_by(sales_rep_id=current_sales_rep_id).order_by(Deal.name)

    if form.validate_on_submit():
        new_task = Task(
            title=form.title.data,
            description=form.description.data,
            due_date=form.due_date.data,
            status=form.status.data,
            priority=form.priority.data,
            sales_rep_id=current_sales_rep_id
        )
        if form.contact_id.data:
            contact_query = Contact.query.filter_by(id=form.contact_id.data.id)
            if not is_manager: 
                 contact_query = contact_query.filter_by(sales_rep_id=current_sales_rep_id)
            contact = contact_query.first()
            if contact: new_task.contact_id = contact.id
            else: flash('Selected contact is invalid or does not belong to you.', 'warning')
        
        if form.crm_account_id.data:
            account_query = CrmAccount.query.filter_by(id=form.crm_account_id.data.id)
            if not is_manager:
                account_query = account_query.filter_by(sales_rep_id=current_sales_rep_id)
            account = account_query.first()
            if account: new_task.crm_account_id = account.id
            else: flash('Selected account is invalid or does not belong to you.', 'warning')
        
        if form.deal_id.data:
            deal_query = Deal.query.filter_by(id=form.deal_id.data.id)
            if not is_manager: 
                deal_query = deal_query.filter_by(sales_rep_id=current_sales_rep_id)
            deal = deal_query.first()
            if deal: new_task.deal_id = deal.id
            else: flash('Selected deal is invalid or does not belong to you.', 'warning')
        
        db.session.add(new_task)
        db.session.commit()
        flash('Task created successfully!', 'success')
        return redirect(url_for('crm.manage_tasks'))

    # List tasks - use is_manager flag
    page = request.args.get('page', 1, type=int) # Added for pagination
    per_page = current_app.config.get('ITEMS_PER_PAGE', 15) # Added for pagination
    task_query = Task.query
    if is_manager: # Changed from is_manager_or_admin
        page_title = "All CRM Tasks"
        task_query = task_query.order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc())
    else:
        task_query = task_query.filter(Task.sales_rep_id == current_sales_rep_id)\
                               .order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc())
    
    task_pagination = task_query.paginate(page=page, per_page=per_page, error_out=False)
    tasks_list = task_pagination.items # Renamed from 'tasks' to avoid conflict with template var name
        
    csrf_token_value = generate_csrf()

    return render_template('crm/task_list.html', 
                           form=form, 
                           tasks=tasks_list, # Use the new variable name
                           pagination=task_pagination,
                           title=page_title,
                           TASK_STATUSES=TASK_STATUSES,
                           TASK_PRIORITIES=TASK_PRIORITIES,
                           today=today_date, # Pass today's date
                           csrf_token=csrf_token_value)

# Placeholder for edit task
@crm_bp.route('/task/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
@sales_required
def edit_task(task_id):
    """Edit task, accessible by assigned rep, sales manager, or admin."""
    query = Task.query.filter_by(id=task_id)
    current_sales_profile_id = get_current_sales_rep_id()
    is_manager = hasattr(current_user, 'sales_profile') and current_user.sales_profile.role == 'sales_manager'

    if not is_manager:
        query = query.filter_by(sales_rep_id=current_sales_profile_id)
    
    task = query.first_or_404()
    form = TaskForm(obj=task)

    # Filter choices for dropdowns based on role
    if is_manager:
        form.contact_id.query_factory = lambda: Contact.query.order_by(Contact.first_name).all()
        form.crm_account_id.query_factory = lambda: CrmAccount.query.order_by(CrmAccount.name).all()
        form.deal_id.query_factory = lambda: Deal.query.order_by(Deal.name).all()
    else: # Sales Rep - dropdowns should only show their own items
        form.contact_id.query_factory = lambda: Contact.query.filter_by(sales_rep_id=current_sales_profile_id).order_by(Contact.first_name).all()
        form.crm_account_id.query_factory = lambda: CrmAccount.query.filter_by(sales_rep_id=current_sales_profile_id).order_by(CrmAccount.name).all()
        form.deal_id.query_factory = lambda: Deal.query.filter_by(sales_rep_id=current_sales_profile_id).order_by(Deal.name).all()

    if form.validate_on_submit():
        task.title = form.title.data
        task.description = form.description.data
        task.due_date = form.due_date.data
        task.status = form.status.data
        task.priority = form.priority.data
        # sales_rep_id of the task itself does not change on edit here. 
        # Reassignment would be a separate feature.

        # Link to contact if selected - verify access
        if form.contact_id.data:
            contact_query = Contact.query.filter_by(id=form.contact_id.data.id)
            if not is_manager:
                 contact_query = contact_query.filter_by(sales_rep_id=current_sales_profile_id)
            contact = contact_query.first()
            if contact:
                task.contact_id = contact.id
            else:
                task.contact_id = None 
                flash('Selected contact is invalid or not accessible. Contact link removed.', 'warning')
        else:
            task.contact_id = None

        # Link to CRM account if selected - verify access
        if form.crm_account_id.data:
            account_query = CrmAccount.query.filter_by(id=form.crm_account_id.data.id)
            if not is_manager:
                account_query = account_query.filter_by(sales_rep_id=current_sales_profile_id)
            account = account_query.first()
            if account:
                task.crm_account_id = account.id
            else:
                task.crm_account_id = None
                flash('Selected account is invalid or not accessible. Account link removed.', 'warning')
        else:
            task.crm_account_id = None

        # Link to Deal if selected - verify access
        if form.deal_id.data:
            deal_query = Deal.query.filter_by(id=form.deal_id.data.id)
            if not is_manager:
                deal_query = deal_query.filter_by(sales_rep_id=current_sales_profile_id)
            deal = deal_query.first()
            if deal:
                task.deal_id = deal.id
            else:
                task.deal_id = None
                flash('Selected deal is invalid or not accessible. Deal link removed.', 'warning')
        else:
            task.deal_id = None
            
        db.session.commit()

    # For GET request, pre-populate QuerySelectFields if a value exists
    if task.contact_id:
        form.contact_id.data = Contact.query.get(task.contact_id)
    if task.crm_account_id:
        form.crm_account_id.data = CrmAccount.query.get(task.crm_account_id)
    if task.deal_id: # Pre-populate deal field
        form.deal_id.data = Deal.query.get(task.deal_id)

    return render_template('crm/task_form.html', 
                           form=form, 
                           title=f"Edit Task: {task.title}", 
                           task=task,
                           form_url=url_for('crm.edit_task', task_id=task.id)) # Pass URL for form action

# Placeholder for delete task
@crm_bp.route('/task/<int:task_id>/delete', methods=['POST'])
@login_required
@sales_required
@csrf.exempt 
def delete_task(task_id):
    """Delete task, accessible by assigned rep, sales manager, or admin."""
    token = request.form.get('csrf_token')
    try:
        validate_csrf(token)
    except ValidationError:
        flash('Invalid CSRF token. Task deletion failed.', 'danger')
        return redirect(url_for('crm.manage_tasks'))

    query = Task.query.filter_by(id=task_id)
    if not (hasattr(current_user, 'sales_profile') and current_user.sales_profile and 
            (current_user.sales_profile.role == 'sales_manager' or 
             (Task.query.with_entities(Task.sales_rep_id).filter_by(id=task_id).scalar() == get_current_sales_rep_id()))):
        query = query.filter(Task.sales_rep_id == get_current_sales_rep_id())        
    task = query.first_or_404()
    
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted successfully.', 'success')
    return redirect(url_for('crm.manage_tasks'))

# Route to quickly update task status (e.g., mark complete/open)
@crm_bp.route('/task/<int:task_id>/update_status', methods=['POST'])
@login_required
@sales_required
@csrf.exempt
def update_task_status(task_id):
    """Update task status, accessible by assigned rep, sales manager, or admin."""
    token = request.form.get('csrf_token')
    new_status = request.form.get('status')

    try:
        validate_csrf(token)
    except ValidationError:
        flash('Invalid CSRF token. Task update failed.', 'danger')
        return redirect(request.referrer or url_for('crm.manage_tasks'))

    query = Task.query.filter_by(id=task_id)
    if not (hasattr(current_user, 'sales_profile') and current_user.sales_profile and 
            (current_user.sales_profile.role == 'sales_manager' or 
             (Task.query.with_entities(Task.sales_rep_id).filter_by(id=task_id).scalar() == get_current_sales_rep_id()))):
        query = query.filter(Task.sales_rep_id == get_current_sales_rep_id())        
    task = query.first_or_404()

    if new_status not in [s[0] for s in TASK_STATUSES]:
        flash(f'Invalid status: {new_status}.', 'danger')
        return redirect(request.referrer or url_for('crm.manage_tasks'))

    task.status = new_status
    if new_status == 'Completed':
        task.completed_at = datetime.utcnow()
    else: # For other statuses, ensure completed_at is cleared if it was previously completed.
        task.completed_at = None 
        
    db.session.commit()
    flash(f'Task status updated to "{new_status}".', 'success')
    return redirect(request.referrer or url_for('crm.manage_tasks'))

# --- DEAL CRUD OPERATIONS --- #

@crm_bp.route('/deals', methods=['GET'])
@login_required
@sales_required
def list_deals():
    """List deals based on user role."""
    if not current_user.sales_profile:
        flash('Sales profile not found for this user.', 'error')
        return redirect(url_for('main.dashboard'))

    page = request.args.get('page', 1, type=int) # Added for pagination
    per_page = current_app.config.get('ITEMS_PER_PAGE', 15) # Added for pagination
    page_title = "My Deals"
    query = Deal.query

    # Check ONLY for Sales Manager role for elevated access
    if hasattr(current_user, 'sales_profile') and current_user.sales_profile and current_user.sales_profile.role == 'sales_manager':
        query = query.order_by(Deal.expected_close_date.asc().nulls_last(), Deal.created_at.desc())
        page_title = "All CRM Deals"
    else:
        # Sales Reps see only their own deals (or if user has no role/is not manager)
        sales_rep_id = current_user.sales_profile.id # Defined sales_rep_id here
        query = query.filter(Deal.sales_rep_id == sales_rep_id)\
                     .order_by(Deal.expected_close_date.asc().nulls_last(), Deal.created_at.desc())
    
    # Use pagination
    deals_pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    deals_list = deals_pagination.items # Get items for the current page

    return render_template('crm/deal_list.html', 
                           deals=deals_list, # Pass the list of deals for the current page
                           pagination=deals_pagination, # Pass pagination object
                           title=page_title,
                           DEAL_STAGES=DEAL_STAGES, # Pass for display/filtering
                           csrf_token=generate_csrf() # For potential inline actions
                           )

@crm_bp.route('/deals/new', methods=['GET', 'POST'])
@login_required
@sales_required
def create_deal():
    form = DealForm()
    sales_rep_id = get_current_sales_rep_id()
    
    if sales_rep_id is None:
        flash("Sales profile not found. Cannot create deal.", "error")
        return redirect(url_for('crm.list_deals'))

    # Check for pre-selected contact and/or account from query args
    preselected_contact_id = request.args.get('contact_id', type=int)
    preselected_account_id = request.args.get('account_id', type=int)

    if request.method == 'GET':
        if preselected_contact_id:
            contact_obj = Contact.query.filter_by(id=preselected_contact_id, sales_rep_id=sales_rep_id).first()
            if contact_obj:
                form.contact_id.data = contact_obj
                # If contact has an account, pre-select it as well, unless an account_id was also passed explicitly
                if contact_obj.crm_account and not preselected_account_id:
                    form.crm_account_id.data = contact_obj.crm_account
            else:
                flash("Specified contact for new deal not found or not accessible.", "warning")
        
        if preselected_account_id:
            account_obj = CrmAccount.query.filter_by(id=preselected_account_id, sales_rep_id=sales_rep_id).first()
            if account_obj:
                form.crm_account_id.data = account_obj
            elif not form.crm_account_id.data: # Only flash if not already set by contact
                flash("Specified account for new deal not found or not accessible.", "warning")

    # Query factories for dropdowns are already set in DealForm to filter by sales_rep_id
    
    if form.validate_on_submit():
        try:
            new_deal = Deal(
                name=form.name.data,
                description=form.description.data,
                amount=form.amount.data,
                stage=form.stage.data,
                expected_close_date=form.expected_close_date.data,
                probability=form.probability.data,
                sales_rep_id=sales_rep_id,
                crm_account_id=form.crm_account_id.data.id,
                contact_id=form.contact_id.data.id if form.contact_id.data else None
            )
            db.session.add(new_deal)
            db.session.commit()
            flash(f'Deal "{new_deal.name}" created successfully!', 'success')
            return redirect(url_for('crm.list_deals'))
        except Exception as e: # Added except block
            db.session.rollback()
            current_app.logger.error(f"Error creating deal: {e}")
            flash(f'Error creating deal: {str(e)}. Please check your input and try again.', 'error')

    return render_template('crm/deal_form.html',
                           form=form,
                           title="Create New Deal",
                           form_action_url=url_for('crm.create_deal'))

@crm_bp.route('/deal/<int:deal_id>', methods=['GET'])
@login_required
@sales_required
def view_deal(deal_id):
    """View deal details, accessible by assigned rep, sales manager, or admin."""
    sales_rep_id = get_current_sales_rep_id()
    if sales_rep_id is None:
        flash("Sales profile not found. Cannot view deal.", "error")
        return redirect(url_for('crm.list_deals'))

    query = Deal.query.filter_by(id=deal_id)
    if not (hasattr(current_user, 'sales_profile') and current_user.sales_profile and 
            (current_user.sales_profile.role == 'sales_manager' or 
             (Deal.query.with_entities(Deal.sales_rep_id).filter_by(id=deal_id).scalar() == sales_rep_id))):
        query = query.filter(Deal.sales_rep_id == sales_rep_id)
    deal = query.first_or_404()
    related_tasks = deal.crm_tasks.order_by(desc(Task.created_at)).all()
    
    recent_notes = []
    if deal.contact: # Check if a primary contact is associated with the deal
        # Fetch recent notes from this contact
        # Assuming Note model has 'timestamp' and 'contact_id'
        # And Note is imported: from ..models.note import Note
        # And desc is imported: from sqlalchemy import desc
        recent_notes = Note.query.filter_by(contact_id=deal.contact.id)\
                            .order_by(desc(Note.timestamp))\
                            .limit(10).all() # Limit to 10 most recent notes for example

    return render_template('crm/deal_detail.html', 
                           deal=deal, 
                           related_tasks=related_tasks,
                           recent_notes=recent_notes, # Pass fetched notes
                           title=deal.name,
                           DEAL_STAGES=DEAL_STAGES, # For display consistency if needed
                           csrf_token=generate_csrf() # For potential future actions like delete
                           )

@crm_bp.route('/deal/<int:deal_id>/edit', methods=['GET', 'POST'])
@login_required
@sales_required
def edit_deal(deal_id):
    """Edit deal, accessible by assigned rep, sales manager, or admin."""
    current_sales_profile_id = get_current_sales_rep_id()
    if current_sales_profile_id is None:
        flash("Sales profile not found. Cannot edit deal.", "error")
        return redirect(url_for('crm.list_deals'))

    query = Deal.query.filter_by(id=deal_id)
    is_sales_manager = hasattr(current_user, 'sales_profile') and current_user.sales_profile and current_user.sales_profile.role == 'sales_manager'

    if not is_sales_manager:
        query = query.filter_by(sales_rep_id=current_sales_profile_id)
    
    deal = query.first_or_404()
    form = DealForm(obj=deal)
    
    if is_sales_manager:
        form.crm_account_id.query_factory = lambda: CrmAccount.query.order_by(CrmAccount.name).all()
        form.contact_id.query_factory = lambda: Contact.query.order_by(Contact.first_name).all()
    else:
        # Defaults in DealForm filter by sales_rep_id of the current_user, which is correct for non-managers
        pass 

    if form.validate_on_submit():
        try:
            deal.name = form.name.data
            deal.description = form.description.data
            deal.amount = form.amount.data
            deal.stage = form.stage.data
            deal.expected_close_date = form.expected_close_date.data
            deal.probability = form.probability.data
            # sales_rep_id should not change on edit typically, unless reassignment is a feature
            deal.crm_account_id = form.crm_account_id.data.id
            deal.contact_id = form.contact_id.data.id if form.contact_id.data else None
            
            db.session.commit()
            flash(f'Deal "{deal.name}" updated successfully!', 'success')
            return redirect(url_for('crm.view_deal', deal_id=deal.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating deal {deal_id}: {e}")
            flash(f'Error updating deal: {str(e)}. Please check input and try again.', 'error')
    
    # For GET requests, ensure QuerySelectFields are correctly populated if obj was used
    # This is usually handled by WTForms if `obj` is passed correctly and field names match.
    # However, for QuerySelectField, you might need to explicitly set the data if it's not working automatically.
    if request.method == 'GET':
        form.crm_account_id.data = deal.crm_account # Pre-select the CrmAccount object
        form.contact_id.data = deal.contact       # Pre-select the Contact object

    return render_template('crm/deal_form.html',
                           form=form,
                           title=f"Edit Deal: {deal.name}",
                           form_action_url=url_for('crm.edit_deal', deal_id=deal.id),
                           deal=deal # Pass deal for context if needed in template (e.g. breadcrumbs)
                           )

@crm_bp.route('/deal/<int:deal_id>/delete', methods=['POST'])
@login_required
@sales_required
def delete_deal(deal_id):
    """Delete a deal, accessible by assigned rep, sales manager, or admin."""
    query = Deal.query.filter_by(id=deal_id)
    if not (hasattr(current_user, 'sales_profile') and current_user.sales_profile and 
            (current_user.sales_profile.role == 'sales_manager' or 
             (Deal.query.with_entities(Deal.sales_rep_id).filter_by(id=deal_id).scalar() == get_current_sales_rep_id()))):
        # This was using a direct filter_by(id, sales_rep_id), changing to conditional filter
        query = query.filter(Deal.sales_rep_id==get_current_sales_rep_id()) 
    
    deal = query.first_or_404()
    
    try:
        deal_name = deal.name
        # Before deleting a deal, consider related items:
        # - Tasks: If tasks are linked via deal_id, SQLAlchemy's default behavior 
        #   (if `nullable=True` on Task.deal_id and no `cascade` options like "all, delete-orphan") 
        #   is to set Task.deal_id to NULL. If `nullable=False`, it would raise an IntegrityError.
        #   If you want to delete tasks associated with the deal, you'd need to query and delete them first
        #   or set up `cascade="all, delete-orphan"` on the Deal.crm_tasks relationship.
        #   For now, let's assume tasks will be unlinked (deal_id set to NULL).

        db.session.delete(deal)
        db.session.commit()
        flash(f'Deal "{deal_name}" was successfully deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting deal {deal_id}: {e}")
        flash('Error deleting deal. Please try again.', 'error')
        return redirect(url_for('crm.view_deal', deal_id=deal.id)) # Redirect back to detail view on error
        
    return redirect(url_for('crm.list_deals')) # Redirect to deal list on success

# Ensure all original code is present, only rearranging sections 

# --- Custom Field Definition Routes --- #

@crm_bp.route('/custom-fields')
@login_required
@sales_required
def list_custom_field_definitions():
    """List all defined custom fields."""
    # Fetch all definitions, maybe order them
    definitions = CustomFieldDefinition.query.order_by(CustomFieldDefinition.applies_to, CustomFieldDefinition.name).all()
    
    return render_template('crm/custom_field_definition_list.html', 
                           definitions=definitions,
                           title="Manage Custom Fields")

@crm_bp.route('/custom-fields/new', methods=['GET', 'POST'])
@login_required
@sales_required
def create_custom_field_definition():
    """Create a new custom field definition."""
    form = CustomFieldDefinitionForm()
    if form.validate_on_submit():
        try:
            # Process options for dropdown
            options_json = None
            if form.field_type.data == CustomFieldType.DROPDOWN.value and form.options.data:
                options_list = [line.strip() for line in form.options.data.strip().split('\n') if line.strip()]
                options_json = {"options": options_list} # Store as JSON
            
            # Basic uniqueness check (within the same 'applies_to' scope)
            existing_def = CustomFieldDefinition.query.filter_by(
                name=form.name.data,
                applies_to=CustomFieldAppliesTo(form.applies_to.data)
            ).first()
            
            if existing_def:
                flash(f'A custom field named "{form.name.data}" already exists for {form.applies_to.data}. Please choose a different name.', 'warning')
            else:
                new_definition = CustomFieldDefinition(
                    name=form.name.data,
                    field_type=CustomFieldType(form.field_type.data),
                    applies_to=CustomFieldAppliesTo(form.applies_to.data),
                    options=options_json
                )
                db.session.add(new_definition)
                db.session.commit()
                flash(f'Custom field "{new_definition.name}" created successfully!', 'success')
                return redirect(url_for('crm.list_custom_field_definitions'))
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating custom field definition: {e}")
            flash(f'Error creating custom field: {str(e)}. Please check input and try again.', 'error')

    return render_template('crm/custom_field_definition_form.html',
                           form=form,
                           title="Create New Custom Field",
                           form_action_url=url_for('crm.create_custom_field_definition'))

@crm_bp.route('/custom-fields/<int:definition_id>/edit', methods=['GET', 'POST'])
@login_required
@sales_required
def edit_custom_field_definition(definition_id):
    """Edit an existing custom field definition."""
    definition = CustomFieldDefinition.query.get_or_404(definition_id)
    form = CustomFieldDefinitionForm(obj=definition)

    # When editing, the 'applies_to' and 'field_type' fields should be disabled
    # as changing them could corrupt existing data.
    # This is better handled in the template by greying them out or making them readonly.
    # For now, we just ensure their values are correctly repopulated.

    if request.method == 'GET':
        # Pre-populate options text area if it's a dropdown
        if definition.field_type == CustomFieldType.DROPDOWN and definition.options and 'options' in definition.options:
            form.options.data = '\n'.join(definition.options['options'])
        # Ensure enum values are correctly set for the form fields
        form.field_type.data = definition.field_type.value
        form.applies_to.data = definition.applies_to.value


    if form.validate_on_submit():
        try:
            # Name can be updated.
            # Type and Applies To should ideally not be changed if values exist.
            # For simplicity, we'll allow name and options to be changed.
            # More complex logic would be needed to handle type/applies_to changes with existing data.
            
            # Check if the name is being changed to one that already exists for the same 'applies_to'
            if form.name.data != definition.name:
                existing_def = CustomFieldDefinition.query.filter(
                    CustomFieldDefinition.name == form.name.data,
                    CustomFieldDefinition.applies_to == definition.applies_to, # Keep original applies_to
                    CustomFieldDefinition.id != definition_id
                ).first()
                if existing_def:
                    flash(f'A custom field named "{form.name.data}" already exists for {definition.applies_to.name.title()}. Please choose a different name.', 'warning')
                    return render_template('crm/custom_field_definition_form.html',
                                           form=form,
                                           title=f"Edit Custom Field: {definition.name}",
                                           form_action_url=url_for('crm.edit_custom_field_definition', definition_id=definition_id),
                                           editing=True,
                                           definition=definition)

            definition.name = form.name.data
            
            # Process options for dropdown if the type is dropdown
            # Note: We are not allowing change of field_type here for simplicity.
            # If it was a dropdown, options can be updated.
            if definition.field_type == CustomFieldType.DROPDOWN:
                if form.options.data:
                    options_list = [line.strip() for line in form.options.data.strip().split('\n') if line.strip()]
                    definition.options = {"options": options_list}
                else:
                    definition.options = None # Clear options if textarea is empty
            
            db.session.commit()
            flash(f'Custom field "{definition.name}" updated successfully!', 'success')
            return redirect(url_for('crm.list_custom_field_definitions'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating custom field definition {definition_id}: {e}")
            flash(f'Error updating custom field: {str(e)}. Please check input and try again.', 'error')

    return render_template('crm/custom_field_definition_form.html',
                           form=form,
                           title=f"Edit Custom Field: {definition.name}",
                           form_action_url=url_for('crm.edit_custom_field_definition', definition_id=definition_id),
                           editing=True, # Pass a flag to the template
                           definition=definition) # Pass definition for context


@crm_bp.route('/custom-fields/<int:definition_id>/delete', methods=['POST'])
@login_required
@sales_required
def delete_custom_field_definition(definition_id):
    """Delete a custom field definition and its associated values."""
    definition = CustomFieldDefinition.query.get_or_404(definition_id)
    
    # Before deleting the definition, we MUST delete all CustomFieldValue instances
    # that refer to this definition to avoid foreign key constraint violations.
    values_to_delete = CustomFieldValue.query.filter_by(definition_id=definition.id).all()
    
    try:
        for val in values_to_delete:
            db.session.delete(val)
        
        # After deleting associated values, delete the definition itself
        db.session.delete(definition)
        
        db.session.commit()
        flash(f'Custom field "{definition.name}" and all its associated data have been deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting custom field definition {definition_id}: {e}")
        flash(f'Error deleting custom field: {str(e)}. It might be in use or another issue occurred.', 'danger')
        
    return redirect(url_for('crm.list_custom_field_definitions'))


@crm_bp.route('/call-logs/<string:call_sid>/update-details', methods=['POST'])
@login_required
@sales_required
@csrf.exempt # Will validate CSRF from header manually
def update_call_log_details(call_sid):
    """Update notes and outcome for a specific call log."""
    # Manual CSRF check from header
    csrf_token_header = request.headers.get('X-CSRFToken')
    try:
        validate_csrf(csrf_token_header) 
    except ValidationError as e:
        current_app.logger.warning(f'CSRF validation failed for call log update: {e}')
        return jsonify({'success': False, 'message': 'Invalid CSRF token.'}), 403

    if not current_user.sales_profile:
        return jsonify({'success': False, 'message': 'Sales profile required'}), 403

    log = CallLog.query.filter_by(call_sid=call_sid).first()

    if not log:
        return jsonify({'success': False, 'message': 'Call log not found'}), 404
    
    if log.sales_rep_id != current_user.sales_profile.id:
        # Allow managers to edit any call log if that's a requirement, otherwise strict ownership.
        # For now, sticking to strict ownership by the sales_rep.
        # if not current_user.sales_profile.role == 'sales_manager':
        return jsonify({'success': False, 'message': 'Permission denied. You do not own this call log.'}), 403
        
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    new_notes = data.get('notes') # Allow notes to be None or empty string to clear them
    new_outcome = data.get('outcome')

    if new_notes is not None: # Check for presence, not just truthiness
        log.notes = new_notes
    
    if new_outcome is not None: # Check for presence
        valid_outcomes = [oc[0] for oc in CALL_OUTCOMES]
        if new_outcome == "" or new_outcome is None: # Allow unsetting the outcome
            log.outcome = None
        elif new_outcome not in valid_outcomes:
            return jsonify({'success': False, 'message': f'Invalid outcome: {new_outcome}. Must be one of {valid_outcomes}'}), 400
        else:
            log.outcome = new_outcome
            
    try:
        db.session.commit()
        current_app.logger.info(f"Updated details for CallLog SID {call_sid}. Notes: '{log.notes}', Outcome: '{log.outcome}'")
        return jsonify({
            'success': True, 
            'message': 'Call details updated successfully',
            'call_log': log.to_dict() # Return the updated log data
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating call log {call_sid} details: {e}")
        return jsonify({'success': False, 'message': 'Database error occurred while updating call details.'}), 500

@crm_bp.route('/call-logs/outcomes', methods=['GET'])
@login_required
# @sales_required # Not strictly necessary for just fetching a list, but can be added for consistency
def get_call_outcomes_list():
    return jsonify(success=True, outcomes=[{'value': val, 'label': lbl} for val, lbl in CALL_OUTCOMES])

# --- View/Edit Individual Call Log ---
@crm_bp.route('/call-log/<int:log_id>', methods=['GET', 'POST'])
@login_required
@sales_required
def view_edit_call_log(log_id):
    call_log = CallLog.query.filter_by(id=log_id, sales_rep_id=current_user.sales_profile.id).first_or_404()
    
    form = CallLogDetailForm(obj=call_log)
    # For QuerySelectField, we need to set the data attribute with the model instance if it exists
    if call_log.contact:
        form.contact_id.data = call_log.contact
    else:
        form.contact_id.data = None # Explicitly set to None if no contact is linked

    if form.validate_on_submit():
        try:
            call_log.outcome = form.outcome.data if form.outcome.data else None
            call_log.notes = form.notes.data.strip() if form.notes.data else None
            
            selected_contact = form.contact_id.data # This will be a Contact object or None
            call_log.contact_id = selected_contact.id if selected_contact else None
            
            call_log.updated_at = datetime.utcnow()
            db.session.add(call_log)
            db.session.commit()
            flash('Call log details updated successfully.', 'success')
            return redirect(url_for('crm.view_edit_call_log', log_id=call_log.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating call log {log_id}: {e}")
            flash('Error updating call log. Please try again.', 'error')

    # For GET request or if form validation fails, populate form with existing data if not already done by obj=call_log
    # This ensures that if a POST fails validation, the form is re-rendered with the submitted data
    # and also correctly populates the contact_id field for GET requests initially.
    if request.method == 'GET':
        form.outcome.data = call_log.outcome
        form.notes.data = call_log.notes
        # contact_id is handled by obj=call_log and explicit setting above for GET.

    return render_template('call_log_detail.html', call_log=call_log, form=form, title=f"Call Log: {call_log.call_sid}")

# Potentially near other call log related routes or utility routes
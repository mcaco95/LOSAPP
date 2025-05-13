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
from ..forms import ContactForm, NoteForm, CrmAccountForm, ImportCsvForm, TaskForm, DealForm, LinkContactToCompanyForm, CustomFieldDefinitionForm # Added LinkContactToCompanyForm and CustomFieldDefinitionForm
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
    """List contacts based on user role."""
    if not current_user.sales_profile:
        flash('Sales profile not found for this user.', 'error')
        return redirect(url_for('main.dashboard')) 

    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ITEMS_PER_PAGE', 15)
    page_title = "My Contacts"
    query = Contact.query

    # Check ONLY for Sales Manager role for elevated access
    if hasattr(current_user, 'sales_profile') and current_user.sales_profile and current_user.sales_profile.role == 'sales_manager':
        query = query.order_by(Contact.last_name, Contact.first_name)
        page_title = "All CRM Contacts"
    else:
        # Sales Reps see only their own contacts (or if user has no role/is not manager)
        query = query.filter(Contact.sales_rep_id == current_user.sales_profile.id)\
                     .order_by(Contact.last_name, Contact.first_name)
    
    # Use pagination
    contacts_pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    user_contacts = contacts_pagination.items
    
    return render_template('crm/contacts.html', 
                           contacts=user_contacts, 
                           pagination=contacts_pagination, # Pass pagination object
                           title=page_title,
                           generated_csrf_token=generate_csrf())

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

    # Pass preselected_account to the form if it exists, otherwise ContactForm handles it
    form = ContactForm(crm_account=preselected_account) if preselected_account else ContactForm()
    
    # Dynamically add custom fields to the form
    # The helper returns a list of (field_name, definition_object) tuples
    dynamic_fields = create_dynamic_form_class(ContactForm, CustomFieldAppliesTo.CONTACT)[1]

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
    """Edit an existing contact, including dynamic custom fields."""
    query = Contact.query.filter_by(id=contact_id)
    if not current_user.sales_profile.role == 'sales_manager':
        query = query.filter_by(sales_rep_id=get_current_sales_rep_id())
    contact = query.first_or_404()

    # Dynamically create the form class with custom fields
    DynamicContactForm, dynamic_fields = create_dynamic_form_class(ContactForm, CustomFieldAppliesTo.CONTACT)

    if request.method == 'POST':
        # --- POST Request Handling --- 
        # Instantiate the dynamic form with POST data
        form = DynamicContactForm(request.form)

        if form.validate():
            # Update standard fields (extracting from form.data)
            contact.first_name = form.first_name.data.strip()
            contact.last_name = form.last_name.data.strip()
            contact.email = form.email.data.strip() if form.email.data else None
            contact.phone_number = form.phone_number.data.strip() if form.phone_number.data else None
            contact.job_title = form.job_title.data.strip() if form.job_title.data else None
            contact.status = form.status.data
            contact.source = form.source.data
            contact.crm_account_id = form.crm_account.data.id if form.crm_account.data else None
            
            db.session.add(contact) # Add contact to session before custom fields
            # Process and save custom fields (using dynamic_fields list)
            save_custom_field_values(form, CustomFieldAppliesTo.CONTACT, contact, dynamic_fields)
            
            try:
                db.session.commit()
                flash(f'{contact.full_name} updated successfully!', 'success')
                return redirect(url_for('.view_contact', contact_id=contact.id))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error updating contact {contact_id}: {e}")
                flash('Error updating contact. Please check the data and try again.', 'danger')
        else:
            flash('Please correct the errors below.', 'warning')
            # Re-render using the same dynamic form instance (form) which now contains errors
            return render_template('crm/contact_form.html', form=form, title=f"Edit {contact.full_name}", legend="Edit Contact Details", contact_id=contact_id, dynamic_fields=dynamic_fields)
            
    else: # request.method == 'GET'
        # --- GET Request Handling --- 
        # Prepare initial data dictionary
        form_data = {
            # ... (standard fields from contact) ...
            'first_name': contact.first_name,
            'last_name': contact.last_name,
            'email': contact.email,
            'phone_number': contact.phone_number,
            'job_title': contact.job_title,
            'crm_account': contact.crm_account, # Pass the object for QuerySelectField
            'status': contact.status,
            'source': contact.source
        }
        # Fetch and add existing custom values (correctly typed) to form_data
        # ... (logic to populate form_data[field_name] = typed_value) ...
        from sqlalchemy.orm import joinedload
        values_query = CustomFieldValue.query.filter(
            CustomFieldValue.contact_id == contact.id
        ).options(joinedload(CustomFieldValue.definition))
        existing_values_list = values_query.all()
        for val in existing_values_list:
            field_name = f"custom_{val.definition_id}"
            definition = val.definition
            raw_value = val.value
            try:
                if definition.field_type == CustomFieldType.NUMBER:
                    form_data[field_name] = int(raw_value) if raw_value else None
                elif definition.field_type == CustomFieldType.DATE:
                    form_data[field_name] = datetime.strptime(raw_value, '%Y-%m-%d').date() if raw_value else None
                elif definition.field_type == CustomFieldType.BOOLEAN:
                    form_data[field_name] = str(raw_value).lower() in ['true', '1', 'yes', 'on']
                else: # TEXT, DROPDOWN
                    form_data[field_name] = raw_value
            except (ValueError, TypeError) as e:
                current_app.logger.warning(f"Error parsing existing custom field value for {field_name} (Def ID: {definition.id}, Value: '{raw_value}'): {e}")
                form_data[field_name] = None

        # Instantiate the dynamic form with the prepared data
        form = DynamicContactForm(data=form_data)
        
        # Render template with the dynamic form instance and the list of fields
        return render_template('crm/contact_form.html', form=form, title=f"Edit {contact.full_name}", legend="Edit Contact Details", contact_id=contact_id, dynamic_fields=dynamic_fields)

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

# --- CrmAccount Routes --- #
@crm_bp.route('/accounts')
@login_required
@sales_required
def accounts():
    """List CRM accounts based on user role."""
    if not current_user.sales_profile:
        flash('Sales profile not found for this user.', 'error')
        return redirect(url_for('main.dashboard'))

    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ITEMS_PER_PAGE', 15)
    page_title = "My Companies/Accounts"
    query = CrmAccount.query

    # Check ONLY for Sales Manager role for elevated access
    if hasattr(current_user, 'sales_profile') and current_user.sales_profile and current_user.sales_profile.role == 'sales_manager':
        # --- ADDED Optimization for Manager View ---
        from sqlalchemy.orm import joinedload
        from ..models.sales_user import SalesUser # Import SalesUser if not already imported at top
        query = query.options(
            joinedload(CrmAccount.sales_rep).joinedload(SalesUser.user)
        ).order_by(CrmAccount.name)
        # --- END ADDED --- 
        # query = query.order_by(CrmAccount.name) # Original line replaced by optimized query
        page_title = "All CRM Companies/Accounts"
    else:
        # Sales Reps see only their own accounts (or if user has no role/is not manager)
        query = query.filter(CrmAccount.sales_rep_id == current_user.sales_profile.id)\
                     .order_by(CrmAccount.name)

    # Use pagination
    accounts_pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    user_accounts = accounts_pagination.items
    
    # --- ADDED: Fetch Custom Fields --- 
    custom_field_defs_query = CustomFieldDefinition.query.filter_by(applies_to=CustomFieldAppliesTo.ACCOUNT).order_by(CustomFieldDefinition.name).all()
    # Convert definitions to dictionaries *before* passing to template
    custom_field_defs_dicts = [definition.to_dict() for definition in custom_field_defs_query]
    
    account_ids_on_page = [acc.id for acc in user_accounts]
    custom_field_values_for_page = {}
    if account_ids_on_page and custom_field_defs_dicts: # Check the dicts list
        # Fetch all values for the accounts on this page and for the relevant definitions in one go
        values_query = CustomFieldValue.query.filter(
            CustomFieldValue.account_id.in_(account_ids_on_page),
            CustomFieldValue.definition_id.in_([d['id'] for d in custom_field_defs_dicts]) # Use IDs from dicts
        ).all()
        
        # Organize them for easy lookup: {account_id: {definition_id: value_str, ...}, ...}
        for cfv in values_query:
            if cfv.account_id not in custom_field_values_for_page:
                custom_field_values_for_page[cfv.account_id] = {}
            custom_field_values_for_page[cfv.account_id][cfv.definition_id] = cfv.value
    # --- END ADDED --- 
    
    return render_template('crm/account_list.html', 
                           accounts=user_accounts, 
                           pagination=accounts_pagination, # Pass pagination object
                           title=page_title, 
                           CRM_ACCOUNT_STATUSES=CRM_ACCOUNT_STATUSES, 
                           generated_csrf_token=generate_csrf(),
                           custom_field_definitions=custom_field_defs_dicts, # <-- Pass the list of DICTS
                           custom_field_values_data=custom_field_values_for_page
                           )

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
    """Edit account, including dynamic custom fields."""
    query = CrmAccount.query.filter_by(id=account_id)
    if not current_user.sales_profile.role == 'sales_manager':
        query = query.filter_by(sales_rep_id=get_current_sales_rep_id())
    account = query.first_or_404()

    # Dynamically create the form class with custom fields
    DynamicAccountForm, dynamic_fields = create_dynamic_form_class(CrmAccountForm, CustomFieldAppliesTo.ACCOUNT)

    if request.method == 'POST':
        # --- POST Request Handling --- 
        form = DynamicAccountForm(request.form)

        if form.validate():
            # Remove old custom_data handling
            # custom_data_to_save = None
            # ... (old parsing logic) ...

            selected_status = form.status.data if form.status.data and form.status.data != '-' else None

            try:
                account.name = form.name.data.strip()
                account.website = form.website.data.strip() if form.website.data else None
                account.industry = form.industry.data.strip() if form.industry.data else None
                account.phone_number = form.phone_number.data.strip() if form.phone_number.data else None
                # Address is likely a JSON field or separate fields, handle as needed
                # Assuming address is simple text for now
                account.address = form.address.data.strip() if form.address.data else None # Keep general address
                account.status = selected_status
                # account.custom_data = custom_data_to_save # <-- REMOVED old custom data

                db.session.add(account) # Add account to session before custom fields
                # Process and save custom fields
                save_custom_field_values(form, CustomFieldAppliesTo.ACCOUNT, account, dynamic_fields)

                db.session.commit()
                flash(f'Account "{account.name}" updated successfully!', 'success')
                return redirect(url_for('crm.view_account', account_id=account.id))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error updating account {account_id}: {e}")
                flash('Error updating account. Please check input and try again.', 'error')
        else:
            flash('Please correct the errors below.', 'warning')
            return render_template('crm/account_form.html', form=form, title=f"Edit {account.name}", legend="Edit Account Details", account_id=account.id, dynamic_fields=dynamic_fields)

    else: # request.method == 'GET'
        # --- GET Request Handling --- 
        # Prepare initial data dictionary
        form_data = {
            'name': account.name,
            'website': account.website,
            'industry': account.industry,
            'phone_number': account.phone_number,
            'address': account.address, # Keep general address
            'status': account.status if account.status else '-' # Ensure status is populated
        }
        
        # Fetch existing custom values for the account
        from sqlalchemy.orm import joinedload
        values_query = CustomFieldValue.query.filter(
            CustomFieldValue.account_id == account.id
        ).options(joinedload(CustomFieldValue.definition))
        existing_values_list = values_query.all()
        for val in existing_values_list:
            field_name = f"custom_{val.definition_id}"
            definition = val.definition
            raw_value = val.value
            try:
                if definition.field_type == CustomFieldType.NUMBER:
                    form_data[field_name] = int(raw_value) if raw_value else None
                elif definition.field_type == CustomFieldType.DATE:
                    form_data[field_name] = datetime.strptime(raw_value, '%Y-%m-%d').date() if raw_value else None
                elif definition.field_type == CustomFieldType.BOOLEAN:
                    form_data[field_name] = str(raw_value).lower() in ['true', '1', 'yes', 'on']
                else: # TEXT, DROPDOWN
                    form_data[field_name] = raw_value
            except (ValueError, TypeError) as e:
                current_app.logger.warning(f"Error parsing existing account custom field value for {field_name}: {e}")
                form_data[field_name] = None

        # Instantiate the dynamic form with the prepared data
        form = DynamicAccountForm(data=form_data)

        return render_template('crm/account_form.html', form=form, title=f"Edit {account.name}", legend="Edit Account Details", account_id=account.id, dynamic_fields=dynamic_fields)

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
            upload_dir = os.path.join(current_app.root_path, UPLOAD_FOLDER) # Navigate up from app to project root then to instance
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)
            
            # Create a unique filename to avoid collisions
            unique_id = uuid.uuid4().hex
            temp_filename = f"{unique_id}_{original_filename}"
            temp_filepath = os.path.join(upload_dir, temp_filename)
            
            try:
                csv_file.save(temp_filepath)

                # Read only headers
                headers = []
                with open(temp_filepath, 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    try:
                        headers = next(reader)
                    except StopIteration:
                        flash('Uploaded CSV file is empty or has no headers.', 'danger')
                        os.remove(temp_filepath) # Clean up empty/invalid file
                        return redirect(url_for('crm.import_csv'))
                
                if not headers:
                    flash('Could not read headers from CSV file.', 'danger')
                    os.remove(temp_filepath) # Clean up
                    return redirect(url_for('crm.import_csv'))

                # Store info in session for the next step
                session['csv_import_temp_path'] = temp_filepath
                session['csv_import_original_filename'] = original_filename
                session['csv_import_type'] = import_type
                session['csv_headers'] = headers

                target_fields = CONTACT_IMPORT_FIELDS if import_type == 'contacts' else ACCOUNT_IMPORT_FIELDS
                
                # DEBUGGING: Log variables being passed to the template
                current_app.logger.info("---- Preparing to render confirm_csv_mapping.html ----")
                current_app.logger.info(f"  Form object type: {type(form)}")
                current_app.logger.info(f"  Original Filename: {original_filename}")
                current_app.logger.info(f"  Import Type: {import_type}")
                current_app.logger.info(f"  CSV Headers: {headers}")
                current_app.logger.info(f"  Target Fields: {target_fields}")
                current_app.logger.info("---------------------------------------------------------")

                # Render the new mapping confirmation page
                return render_template('confirm_csv_mapping.html',
                                       form=form, 
                                       headers=headers, 
                                       import_type=import_type,
                                       target_fields=target_fields,
                                       original_filename=original_filename)

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
    for i, header in enumerate(csv_headers_from_session):
        mapped_to = request.form.get(f'map_{i}')
        if mapped_to and mapped_to != '_ignore_': # If not explicitly ignored
            header_mappings[header] = mapped_to

    if not header_mappings:
        flash('No column mappings were provided. Nothing to import.', 'info')
        os.remove(temp_filepath) # Clean up temp file
        return redirect(url_for('crm.import_csv'))

    current_app.logger.info(f"Processing CSV import for: {original_filename}, type: {import_type}")
    current_app.logger.info(f"Header mappings: {header_mappings}")

    # --- Actual Import Logic (adapted from previous import_csv) ---
    sales_rep_id = current_user.sales_profile.id
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
                    custom_data_parts = {}

                    for csv_col_name, model_field_key in header_mappings.items():
                        if csv_col_name not in row_data:
                            # This case should ideally not happen if DictReader is used correctly with original headers
                            errors_details.append(f"Row {row_num+1}: CSV column '{csv_col_name}' (mapped to '{model_field_key}') not found in data row. Skipping row.")
                            # error_count +=1 # This will be caught by the outer try/except for the row
                            raise ValueError(f"Missing column '{csv_col_name}' in row")
                        
                        value = row_data[csv_col_name].strip() if row_data[csv_col_name] else None

                        if model_field_key == 'custom_data':
                            # If multiple columns are mapped to custom_data, we might need a strategy
                            # For now, assume only one column is mapped to 'custom_data' directly
                            # or we can accumulate them with the csv_col_name as key
                            # Let's use the original CSV column name as the key within custom_data
                            if value is not None:
                                custom_data_parts[csv_col_name] = value
                        elif value is not None: # Ensure empty strings are not processed as valid data for non-custom fields unless intended
                            data_to_import[model_field_key] = value
                   
                    # If custom_data_parts has anything, try to json.dumps it, or store as string
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
                        if not data_to_import.get('last_name') and not data_to_import.get('email'):
                            errors_details.append(f"Row {row_num+1}: Contact must have at least a Last Name or Email. Skipping.")
                            error_count += 1
                            continue

                        # Link to CrmAccount if 'crm_account_name' is provided and mapped
                        account_id_to_link = None
                        if 'crm_account_name' in data_to_import and data_to_import['crm_account_name']:
                            acc_name = data_to_import.pop('crm_account_name') # Remove from direct contact fields
                            account = CrmAccount.query.filter_by(name=acc_name, sales_rep_id=sales_rep_id).first()
                            if account:
                                account_id_to_link = account.id
                            else:
                                errors_details.append(f"Row {row_num+1}: Account '{acc_name}' not found for contact. Contact will be created without account linkage.")
                        
                        # Check for existing contact (e.g., by email if provided)
                        existing_contact = None
                        if data_to_import.get('email'):
                            existing_contact = Contact.query.filter_by(email=data_to_import['email'], sales_rep_id=sales_rep_id).first()
                        
                        if existing_contact:
                            # Update existing contact (optional - for now, we skip if exists to avoid duplicates, or could update)
                            # For simplicity in this pass, let's skip duplicates by email
                            errors_details.append(f"Row {row_num+1}: Contact with email '{data_to_import['email']}' already exists. Skipped.")
                            skipped_count +=1
                            continue 
                            # TODO: Add update logic if desired in future

                        contact = Contact(
                            sales_rep_id=sales_rep_id,
                            crm_account_id=account_id_to_link,
                            **data_to_import # Pass all other mapped fields
                        )
                        db.session.add(contact)
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
                            sales_rep_id=sales_rep_id,
                            **data_to_import
                        )
                        db.session.add(account)
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
from flask import Blueprint, render_template, redirect, request, url_for, jsonify, flash, current_app
from flask_login import login_required, current_user
from ..decorators import sales_required # Import the sales decorator
from ..models.sales_user import SalesUser 
from ..models.contact import Contact 
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
import logging # Added for logging
import re # For phone number normalization

# Define the blueprint for CRM phone functionalities
crm_phone_bp = Blueprint(
    'crm_phone', 
    __name__, 
    template_folder='../templates/crm', # Still uses the crm template folder
    url_prefix='/crm' # Keep the /crm prefix for consistency for now
)

log = logging.getLogger(__name__) # Added logger

# --- Utility Function for Phone Number Normalization ---
def normalize_phone_number(phone_number):
    """Remove common non-digit characters except leading +."""
    if not phone_number:
        return None
    # Keep leading '+' if present
    plus_prefix = ''
    if phone_number.startswith('+'):
        plus_prefix = '+'
        phone_number = phone_number[1:]
    # Remove non-digits
    normalized = re.sub(r'\D', '', phone_number)
    return plus_prefix + normalized

# --- Twilio Token ---
@crm_phone_bp.route('/token', methods=['GET'])
@login_required
@sales_required
def get_token():
    """Generate a Twilio Voice capability token for the sales user."""
    # Ensure the user has a sales profile
    if not hasattr(current_user, 'sales_profile') or not current_user.sales_profile:
        log.error(f"User {current_user.id} attempted to get CRM token without sales profile.")
        return jsonify(success=False, message='Sales profile required.'), 403
        
    sales_rep_id = current_user.sales_profile.id
    identity = f'sales-{sales_rep_id}' # Unique identity for the Twilio client
    log.info(f"Generated CRM token for user {current_user.email} with identity {identity}")

    try:
        account_sid = current_app.config['TWILIO_ACCOUNT_SID']
        api_key = current_app.config['TWILIO_API_KEY']
        api_secret = current_app.config['TWILIO_API_SECRET']
        twiml_app_sid = current_app.config['TWILIO_TWIML_APP_SID']

        access_token = AccessToken(account_sid, api_key, api_secret, identity=identity)

        # Create Voice grant
        voice_grant = VoiceGrant(
            outgoing_application_sid=twiml_app_sid,
            incoming_allow=True # Allow incoming calls using the identity
        )
        access_token.add_grant(voice_grant)

        # Return the token as JSON
        return jsonify(success=True, token=access_token.to_jwt(), identity=identity)

    except Exception as e:
        log.error(f"Error generating Twilio token for {identity}: {e}", exc_info=True)
        return jsonify(success=False, message=f'Could not generate token: {e}'), 500

# --- Phone Interface ---
@crm_phone_bp.route('/phone')
@login_required
@sales_required
def phone_interface():
    """Render the dedicated phone interface page."""
    # This route simply serves the HTML page which contains all the JS logic
    return render_template('crm/phone.html') 

# --- NEW: Caller Lookup Endpoint --- #
@crm_phone_bp.route('/lookup-number')
@login_required
@sales_required
def lookup_number():
    """Lookup a phone number to find associated Contact and Company."""
    phone_number_raw = request.args.get('phone_number')
    if not phone_number_raw:
        return jsonify(success=False, message="Missing 'phone_number' parameter."), 400

    log.info(f"Lookup requested for raw number: {phone_number_raw}")
    normalized_number = normalize_phone_number(phone_number_raw)
    log.info(f"Normalized number: {normalized_number}")

    if not normalized_number:
        return jsonify(success=False, message="Invalid phone number format."), 400

    # Query Contact model - search potentially with and without leading '+'
    # and compare against normalized DB numbers if needed (depends on how they are stored)
    # Simple approach first: assume DB numbers are stored reasonably clean.
    contact = Contact.query.filter(
        # Match exact normalized number
        Contact.phone_number == normalized_number
        # Or match number without leading '+' if query had one
        # (Handles cases where DB has +1... and query is 1... or vice-versa if normalized removes +)
        # This OR condition might need refinement based on how numbers are stored.
        # If numbers in DB are NOT consistently stored with '+', we might need 
        # func.replace(Contact.phone_number, '+', '') == normalized_number.lstrip('+') 
        # or similar complex normalization during query.
        # Keep it simple for now.
    ).first()

    if contact:
        log.info(f"Found contact: {contact.id} - {contact.full_name}")
        response_data = {
            'success': True,
            'contact_id': contact.id,
            'contact_name': contact.full_name,
            'company_id': contact.crm_account_id,
            'company_name': contact.crm_account.name if contact.crm_account else None,
            'owner_name': contact.sales_rep.user.name if contact.sales_rep and contact.sales_rep.user else 'N/A'
        }
        return jsonify(response_data)
    else:
        log.info(f"No contact found for number: {normalized_number}")
        # Optionally, could try searching CrmAccount phone numbers here too
        return jsonify(success=False, message="Contact not found."), 404 
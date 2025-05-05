from flask import Blueprint, render_template, redirect, request, url_for, jsonify, flash, current_app
from flask_login import login_required, current_user
from ..decorators import sales_required # Import the sales decorator
# Import necessary components
from .. import db, csrf
from ..services.call_manager import CallManager
from ..models.call_log import CallLog
from ..models.sales_user import SalesUser # Import SalesUser
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from datetime import datetime

# Define the blueprint
crm_bp = Blueprint(
    'crm', 
    __name__, 
    template_folder='../templates/crm', # Point to the crm templates directory
    url_prefix='/crm' # Set base URL prefix for all routes in this blueprint
)

@crm_bp.route('/dashboard')
@login_required
@sales_required
def dashboard():
    """CRM Dashboard - Landing page for sales users"""
    sales_profile = current_user.sales_profile 
    return render_template('dashboard.html', sales_profile=sales_profile)

@crm_bp.route('/contacts')
@login_required
@sales_required
def contacts():
    """Placeholder for CRM contacts page"""
    return render_template('contacts.html')

@crm_bp.route('/calls')
@login_required
@sales_required
def calls():
    """Page to display call logs and potentially the softphone UI"""
    return render_template('calls.html')

# --- Phone System Routes --- 

@crm_bp.route('/token', methods=['GET'])
#@csrf.exempt # Exemption might be needed depending on frontend implementation
@login_required
@sales_required
def get_token():
    """Generate a token for Twilio Voice JavaScript SDK for Sales Users"""
    account_sid = current_app.config['TWILIO_ACCOUNT_SID']
    api_key = current_app.config.get('TWILIO_API_KEY')
    api_secret = current_app.config.get('TWILIO_API_SECRET')
    twiml_app_sid = current_app.config.get('TWILIO_TWIML_APP_SID')
    
    if not all([account_sid, api_key, api_secret, twiml_app_sid]):
        current_app.logger.error("Missing Twilio Voice SDK configuration for CRM token")
        return jsonify({
            'success': False,
            'message': 'Server is not configured for browser-based calling'
        }), 500
    
    # Use sales_profile ID for identity
    identity = f"client:sales-{current_user.sales_profile.id}" 
    token = AccessToken(account_sid, api_key, api_secret, identity=identity)
    
    voice_grant = VoiceGrant(
        outgoing_application_sid=twiml_app_sid,
        incoming_allow=True # Allow incoming calls for sales reps if needed
    )
    token.add_grant(voice_grant)
    
    current_app.logger.info(f"Generated CRM token for user {current_user.email} with identity {identity}")
    
    return jsonify({
        'success': True,
        'token': token.to_jwt(),
        'identity': identity
    })

@crm_bp.route('/call', methods=['POST'])
@csrf.exempt # Likely needed for AJAX calls from JS client
@login_required
@sales_required
def make_call():
    """Make an outbound call for a Sales User"""
    current_app.logger.info("=== Starting CRM make_call route ===")
    
    if not current_user.sales_profile:
         current_app.logger.error(f"User {current_user.id} lacks sales_profile for make_call")
         return jsonify({'success': False, 'message': 'Sales profile required'}), 403
    
    sales_rep_id = current_user.sales_profile.id
    data = request.get_json()
    if not data or 'to_number' not in data:
        return jsonify({'success': False, 'message': 'Missing to_number'}), 400
        
    to_number = data['to_number']
    record = data.get('record', False)
    # The identity used by Twilio when dialing out from the browser
    from_identity = f"client:sales-{sales_rep_id}" 
    
    current_app.logger.info(f"CRM call attempt from {from_identity} to {to_number}")

    try:
        call_manager = CallManager()
        # TODO: Verify/Adapt CallManager.make_call signature if needed.
        # Assuming make_call handles logging internally or returns SID for logging here.
        # This might need adjustment based on CallManager implementation.
        
        # Option 1: CallManager logs the call with sales_rep_id (Ideal if CallManager is adapted)
        # result = call_manager.make_call(to_number=to_number, from_identity=from_identity, record=record, sales_rep_id=sales_rep_id)
        
        # Option 2: make_call only initiates, we log here (Closer to current operations.py)
        webhook_base = current_app.config['TWILIO_WEBHOOK_BASE_URL'].rstrip('/')
        call = call_manager.client.calls.create(
            to=to_number,
            from_=current_app.config['TWILIO_PHONE_NUMBER'], # Using the app's main Twilio number
            # This TwiML app URL needs to handle the 'client:sales-{id}' identity
            url=f"{webhook_base}/webhooks/voice", 
            status_callback=f"{webhook_base}/webhooks/status",
            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
            record=record
        )
        call_sid = call.sid
        
        if call_sid:
            # Create initial call log linked to the sales rep
            call_log = CallLog(
                call_sid=call_sid,
                status='initiated',
                direction='outbound',
                from_number=from_identity, # Log the client identity
                to_number=to_number,
                sales_rep_id=sales_rep_id, # Link to SalesUser
                created_at=datetime.utcnow()
            )
            db.session.add(call_log)
            db.session.commit()
            current_app.logger.info(f"Created initial CRM call log for SID: {call_sid}")
            result = {'success': True, 'message': 'Call initiated', 'call_sid': call_sid}
        else:
             result = {'success': False, 'message': 'Failed to initiate call via Twilio'}

        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Error in CRM make_call: {str(e)}")
        return jsonify({'success': False, 'message': f'Error making call: {str(e)}'}), 500

@crm_bp.route('/call-logs', methods=['GET'])
@login_required
@sales_required
def get_call_logs():
    """Fetch call log history for the current sales user"""
    if not current_user.sales_profile:
        return jsonify({'success': False, 'message': 'Sales profile required'}), 403
        
    sales_rep_id = current_user.sales_profile.id
    limit = request.args.get('limit', 20, type=int)
    
    try:
        logs = CallLog.get_sales_rep_calls(sales_rep_id=sales_rep_id)
        # Limit logs after fetching, or modify get_sales_rep_calls to accept limit
        limited_logs = logs[:limit]
        return jsonify({'success': True, 'call_logs': [log.to_dict() for log in limited_logs]})
    except Exception as e:
        current_app.logger.error(f"Error fetching CRM call logs: {str(e)}")
        return jsonify({'success': False, 'message': 'Error fetching call logs'}), 500

@crm_bp.route('/phone')
@login_required
@sales_required
def phone_interface():
    """Render the dedicated CRM phone interface page (for pop-up window)"""
    # Pass necessary info like user identity if needed by the template JS
    identity = f"client:sales-{current_user.sales_profile.id}"
    return render_template('phone.html', identity=identity)

# Add more CRM routes here later (e.g., deals, tasks) 
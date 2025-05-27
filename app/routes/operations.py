from flask import Blueprint, render_template, jsonify, request, current_app, url_for
from flask_login import login_required, current_user
from ..decorators import operations_required
from ..services.operations_service.twilio.call_manager import CallManager
from ..models.operations_user import OperationsUser
from .. import db, csrf
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.twiml.voice_response import VoiceResponse, Dial, Say, Parameter
from datetime import datetime, timedelta
from app.models.call_log import CallLog
from app.models.sales_user import SalesUser
from app.models.contact import Contact
from app.routes.crm_phone import normalize_phone_number
from app.models.user import User
from sqlalchemy import func, and_, or_
from app.models.samsara import SamsaraAlert, SamsaraAlertActivity

bp = Blueprint('operations', __name__)

@bp.route('/call', methods=['POST'])
@csrf.exempt
@login_required
@operations_required
def make_call():
    """Make an outbound call"""
    current_app.logger.info("=== Starting make_call route ===")
    current_app.logger.info(f"Current user: {current_user.email}")
    
    # Ensure user has an operations profile
    if not current_user.operations_profile:
        current_app.logger.info(f"Creating operations profile for user {current_user.id}")
        operations_profile = OperationsUser(
            user_id=current_user.id,
            role='operator',
            extension='100'  # Default extension
        )
        db.session.add(operations_profile)
        try:
            db.session.commit()
            current_app.logger.info(f"Created operations profile with ID: {operations_profile.id}")
        except Exception as e:
            current_app.logger.error(f"Failed to create operations profile: {str(e)}")
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Failed to create operations profile'}), 400
    
    current_app.logger.info(f"Request headers: {dict(request.headers)}")
    current_app.logger.info(f"Raw request data: {request.get_data(as_text=True)}")
    
    try:
        data = request.get_json()
        current_app.logger.info(f"Parsed JSON data: {data}")
    except Exception as e:
        current_app.logger.error(f"Failed to parse JSON: {str(e)}")
        return jsonify({'success': False, 'message': 'Invalid JSON data'}), 400
    
    if not data:
        current_app.logger.error("No JSON data received")
        return jsonify({'success': False, 'message': 'No data provided'}), 400
        
    to_number = data.get('to_number')
    record = data.get('record', False)
    
    current_app.logger.info(f"To number: {to_number}")
    current_app.logger.info(f"Record call: {record}")
    
    if not to_number:
        current_app.logger.error("No phone number provided")
        return jsonify({'success': False, 'message': 'Phone number is required'}), 400
    
    try:
        call_manager = CallManager()
        call_log_obj = call_manager.initiate_call(
            operator_id=current_user.operations_profile.id,
            to_number=to_number
        )

        success = bool(call_log_obj and call_log_obj.call_sid)
        message = 'Call initiated successfully' if success else 'Failed to initiate call'
        call_sid = call_log_obj.call_sid if success else None
        
        current_app.logger.info(f"Call attempt result - Success: {success}, Message: {message}, SID: {call_sid}")
        
        return jsonify({
            'success': success,
            'message': message,
            'call_sid': call_sid
        })
    except ValueError as ve:
        current_app.logger.error(f"Error in make_call (ValueError): {str(ve)}")
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        current_app.logger.error(f"Error in make_call: {str(e)}")
        return jsonify({'success': False, 'message': f'Error making call: {str(e)}'}), 400

@bp.route('/call/<call_sid>', methods=['GET'])
@csrf.exempt
@login_required
@operations_required
def get_call_status(call_sid):
    """Get status of a call"""
    call_manager = CallManager()
    success, status, duration = call_manager.get_call_status(call_sid)
    
    return jsonify({
        'success': success,
        'status': status,
        'duration': duration
    })

@bp.route('/call/<call_sid>', methods=['DELETE'])
@csrf.exempt
@login_required
@operations_required
def end_call(call_sid):
    """End an active call"""
    call_manager = CallManager()
    success = call_manager.end_call(call_sid)
    
    return jsonify({
        'success': success,
        'message': 'Call ended successfully' if success else 'Failed to end call'
    })

@bp.route('/calls/recent')
@login_required
@operations_required
def get_recent_calls():
    """Get recent calls for the current user"""
    try:
        # Query for this user's calls
        calls = CallLog.query.filter_by(
            operator_id=current_user.operations_profile.id
        ).order_by(
            CallLog.created_at.desc()
        ).limit(10).all()
        
        current_app.logger.info(f"Found {len(calls)} recent calls for operator {current_user.operations_profile.id}")
        
        # Transform calls to dictionary
        calls_data = []
        for call in calls:
            call_dict = {
                'id': call.id,
                'direction': call.direction,
                'status': call.status,
                'from_number': call.from_number,
                'to_number': call.to_number,
                'duration': call.duration,
                'timestamp': call.created_at.isoformat() if call.created_at else None
            }
            calls_data.append(call_dict)
        
        return jsonify({
            'success': True,
            'calls': calls_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error fetching recent calls: {str(e)}")
        return jsonify({
            'success': False,
            'calls': [],
            'error': str(e)
        })

@bp.route('/calls/metrics')
@login_required
@operations_required
def get_call_metrics():
    """Get call metrics for the current user"""
    current_app.logger.info("=== Fetching call metrics ===")
    current_app.logger.info(f"User ID: {current_user.id}")
    current_app.logger.info(f"Operations User ID: {current_user.operations_profile.id}")
    
    try:
        # Calculate metrics directly from the database
        total_calls = CallLog.query.filter_by(
            operator_id=current_user.operations_profile.id
        ).count()
        
        completed_calls = CallLog.query.filter_by(
            operator_id=current_user.operations_profile.id,
            status='completed'
        ).count()
        
        # Calculate completion rate
        completion_rate = (completed_calls / total_calls * 100) if total_calls > 0 else 0
        
        # Calculate average duration of completed calls
        completed_calls_with_duration = CallLog.query.filter(
            CallLog.operator_id == current_user.operations_profile.id,
            CallLog.status == 'completed',
            CallLog.duration.isnot(None)
        ).all()
        
        avg_duration = 0
        if completed_calls_with_duration:
            total_duration = sum(call.duration for call in completed_calls_with_duration)
            avg_duration = total_duration / len(completed_calls_with_duration)
        
        metrics = {
            'total_calls': total_calls,
            'completed_calls': completed_calls,
            'completion_rate': round(completion_rate, 1),
            'average_duration': round(avg_duration, 1)
        }
        
        current_app.logger.info(f"Call metrics: {metrics}")
        return jsonify(metrics)
        
    except Exception as e:
        current_app.logger.error(f"Error calculating call metrics: {str(e)}")
        current_app.logger.exception("Full exception:")
        return jsonify({
            'total_calls': 0,
            'completed_calls': 0,
            'completion_rate': 0,
            'average_duration': 0,
            'error': str(e)
        })

@bp.route('/webhooks/status', methods=['POST'])
@csrf.exempt
def call_status_callback():
    """Handle Twilio call status callbacks for both Ops and Sales"""
    current_app.logger.info("=== Call Status Update Webhook ===")
    
    # Extract data from the callback
    call_sid = request.form.get('CallSid')
    call_status = request.form.get('CallStatus')
    call_duration = request.form.get('CallDuration')
    from_number = request.form.get('From') # Could be client:operator-id or client:sales-id or phone number
    to_number = request.form.get('To')
    
    current_app.logger.info(f"Webhook data: SID={call_sid}, Status={call_status}, Duration={call_duration}, From={from_number}, To={to_number}")
    
    operator_id = None
    sales_rep_id = None
    
    # Determine user type and ID from the 'From' identity if it's a client call
    if from_number and from_number.startswith('client:'):
        identity_parts = from_number.split(':')
        if len(identity_parts) == 2:
            user_part = identity_parts[1]
            id_parts = user_part.split('-')
            if len(id_parts) == 2:
                user_type = id_parts[0]
                user_id_str = id_parts[1]
                try:
                    user_id = int(user_id_str)
                    if user_type == 'operator':
                        operator_id = user_id
                        # For browser calls, the actual from number is the Twilio number
                        from_number = current_app.config['TWILIO_PHONE_NUMBER'] 
                        current_app.logger.info(f"Identified Operator ID: {operator_id}")
                    elif user_type == 'sales':
                        sales_rep_id = user_id
                        # For browser calls, the actual from number is the Twilio number
                        from_number = current_app.config['TWILIO_PHONE_NUMBER'] 
                        current_app.logger.info(f"Identified Sales Rep ID: {sales_rep_id}")
                    else:
                        current_app.logger.warning(f"Unknown client type in From: {from_number}")
                except ValueError:
                    current_app.logger.warning(f"Invalid ID in From identity: {from_number}")
            else:
                 current_app.logger.warning(f"Could not parse ID from client identity: {from_number}")
        else:
             current_app.logger.warning(f"Could not parse type/ID from client identity: {from_number}")

    current_app.logger.info(f"Call {call_sid}: Status={call_status}, OpID={operator_id}, SalesID={sales_rep_id}")
    
    try:
        # Find the call log
        call_log = CallLog.query.filter_by(call_sid=call_sid).first()
        
        if call_log:
            # Update existing log
            call_log.status = call_status
            if call_duration:
                call_log.duration = int(call_duration)
            # Potentially update start/end times based on status
            if call_status == 'in-progress' and not call_log.start_time:
                call_log.start_time = datetime.utcnow()
            if call_status == 'completed' and not call_log.end_time:
                 call_log.end_time = datetime.utcnow()
                 # Recalculate duration if start_time exists and Twilio didn't provide duration
                 if call_log.start_time and not call_duration:
                     call_log.duration = int((call_log.end_time - call_log.start_time).total_seconds())
                 elif call_duration:
                      call_log.duration = int(call_duration)
            # Important: Ensure the correct user ID is linked if missing (e.g., for incoming calls)
            if call_log.operator_id is None and call_log.sales_rep_id is None:
                 if operator_id:
                     call_log.operator_id = operator_id
                 elif sales_rep_id:
                     call_log.sales_rep_id = sales_rep_id
            
        else:
            # Create new log if it doesn't exist (e.g., for incoming calls not logged initially)
            # We MUST have operator_id or sales_rep_id here to create a valid log
            if operator_id is None and sales_rep_id is None:
                 current_app.logger.error(f"Cannot create CallLog for SID {call_sid}: No operator or sales rep ID identified.")
                 # Return 200 OK to Twilio anyway to avoid retries
                 return '', 200 
            
            call_log = CallLog(
                call_sid=call_sid,
                from_number=from_number,
                to_number=to_number,
                status=call_status,
                operator_id=operator_id, # Will be None if sales_rep_id is set
                sales_rep_id=sales_rep_id, # Will be None if operator_id is set
                # Direction might be inferred or default needed
                direction = 'incoming' if to_number == current_app.config['TWILIO_PHONE_NUMBER'] else 'outbound' 
            )
            if call_duration:
                call_log.duration = int(call_duration)
            if call_status == 'in-progress':
                call_log.start_time = datetime.utcnow()
            db.session.add(call_log)
            current_app.logger.info(f"Created new CallLog for SID {call_sid} via status webhook.")
        
        db.session.commit()
        current_app.logger.info(f"Successfully processed status update for call {call_sid}")
        return '', 200
        
    except Exception as e:
        db.session.rollback() # Rollback on error
        current_app.logger.error(f"Error processing status callback for SID {call_sid}: {str(e)}")
        current_app.logger.exception("Full exception:")
        return '', 500 # Return 500 to indicate server error to Twilio

@bp.route('/webhooks/recording-status', methods=['POST'])
@csrf.exempt
def recording_status_callback():
    """Handle Twilio recording status callbacks."""
    call_sid = request.form.get('CallSid')
    recording_url = request.form.get('RecordingUrl')
    recording_status = request.form.get('RecordingStatus')
    
    current_app.logger.info(f"Recording status callback for CallSid: {call_sid}, Status: {recording_status}, URL: {recording_url}")

    if not call_sid or not recording_url:
        current_app.logger.warning("Recording status callback missing CallSid or RecordingUrl.")
        return '', 400 # Bad request

    if recording_status == 'completed': # Process only when recording is ready
        call_log = CallLog.query.filter_by(call_sid=call_sid).first()
        if call_log:
            try:
                call_log.recording_url = recording_url
                # Potentially add recording duration, size etc. if needed from request.form
                # call_log.recording_duration = request.form.get('RecordingDuration')
                db.session.commit()
                current_app.logger.info(f"Recording URL {recording_url} saved for CallLog SID {call_sid}")
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error saving recording URL for CallSid {call_sid}: {e}")
                return '', 500 # Internal server error
        else:
            current_app.logger.warning(f"CallLog not found for CallSid {call_sid} in recording_status_callback.")
            # Don't return 404 to Twilio, as it might retry. Log it and accept.
            
    return '', 200

@bp.route('/token', methods=['GET'])
@csrf.exempt
@login_required
@operations_required
def get_token():
    """Generate a token for Twilio Voice JavaScript SDK"""
    account_sid = current_app.config['TWILIO_ACCOUNT_SID']
    api_key = current_app.config.get('TWILIO_API_KEY')
    api_secret = current_app.config.get('TWILIO_API_SECRET')
    twiml_app_sid = current_app.config.get('TWILIO_TWIML_APP_SID')
    
    # Check if we have the required configuration
    if not all([account_sid, api_key, api_secret, twiml_app_sid]):
        current_app.logger.error("Missing Twilio Voice SDK configuration")
        return jsonify({
            'success': False,
            'message': 'Server is not configured for browser-based calling'
        }), 500
    
    # Create an Access Token
    token = AccessToken(
        account_sid,
        api_key,
        api_secret,
        identity=f"operator-{current_user.operations_profile.id}"
    )
    
    # Create a Voice grant and add to token
    voice_grant = VoiceGrant(
        outgoing_application_sid=twiml_app_sid,
        incoming_allow=True
    )
    token.add_grant(voice_grant)
    
    # Log the token generation
    current_app.logger.info(f"Generated token for user {current_user.email} with identity operator-{current_user.operations_profile.id}")
    
    # Return token as JSON
    return jsonify({
        'success': True,
        'token': token.to_jwt(),
        'identity': f"operator-{current_user.operations_profile.id}"
    })

@bp.route('/webhooks/voice', methods=['POST'])
@csrf.exempt
def voice_twiml():
    """Respond to Twilio webhook with TwiML for Voice SDK (Ops and Sales)"""
    current_app.logger.info("=== Voice TwiML Webhook Triggered ===")
    # Log all form data for debugging
    log_msg = "Request form data details:\n"
    for key, value in request.form.items():
        log_msg += f"  - {key}: {value}\n"
    current_app.logger.info(log_msg)

    response = VoiceResponse()
    call_sid = request.form.get('CallSid')
    from_number = request.form.get('From') # External number or client:identity
    to_number = request.form.get('To')     # Your Twilio number (incoming) or Destination (outbound TwiML param)
    direction = request.form.get('Direction') # 'incoming' or 'outbound-api', etc.
    
    # Check if it's an incoming call to one of your Twilio numbers
    is_incoming_call = direction == 'incoming' or (from_number and not from_number.startswith('client:'))

    if is_incoming_call:
        current_app.logger.info(f"Incoming call detected: From={from_number}, To={to_number}")
        # --- REVERTED TEMPORARY DEBUGGING ---
        # response.say("Debugging incoming call. If you hear this, Twilio is processing the call leg.")
        # current_app.logger.info(f"INCOMING_CALL_DEBUG: Responded with <Say> instead of <Dial client>")
        # --- END REVERTED TEMPORARY DEBUGGING ---

        # ORIGINAL LOGIC (restored):
        target_client = None
        normalized_incoming_from = normalize_phone_number(from_number)
        linked_contact_id = None
        if normalized_incoming_from:
            contact = Contact.query.filter_by(phone_number=normalized_incoming_from).first()
            if contact:
                linked_contact_id = contact.id
                current_app.logger.info(f"Incoming call from known Contact ID: {linked_contact_id} ({contact.full_name}) based on number {normalized_incoming_from}")
            else:
                current_app.logger.info(f"No contact found for incoming number {normalized_incoming_from}")

        if to_number:
            sales_user = SalesUser.query.filter_by(phone_number=to_number).first()
            if sales_user:
                target_client = f"client:sales-{sales_user.id}"
                current_app.logger.info(f"Routing incoming call to Sales User {sales_user.id} ({target_client}) based on dialed number {to_number}")
            else:
                ops_user = OperationsUser.query.filter_by(phone_number=to_number).first()
                if ops_user:
                    target_client = f"client:operator-{ops_user.id}"
                    current_app.logger.info(f"Routing incoming call to Ops User {ops_user.id} ({target_client}) based on dialed number {to_number}")
                else:
                    current_app.logger.warning(f"No user found with assigned phone number matching the dialed number: {to_number}")
        else:
             current_app.logger.warning("Incoming call webhook missing 'To' number (dialed Twilio number).")

        if target_client:
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            if not call_log:
                log_user_id = None
                log_sales_id = None
                if target_client.startswith("client:sales-"):
                    log_sales_id = int(target_client.split('-')[1])
                elif target_client.startswith("client:operator-"):
                     log_user_id = int(target_client.split('-')[1])

                call_log = CallLog(
                    call_sid=call_sid,
                    from_number=from_number,
                    to_number=to_number, 
                    status='ringing', 
                    direction='incoming',
                    operator_id=log_user_id,
                    sales_rep_id=log_sales_id,
                    contact_id=linked_contact_id
                )
                db.session.add(call_log)
                try:
                    db.session.commit()
                    current_app.logger.info(f"Logged incoming call {call_sid} routed to {target_client}")
                except Exception as e_commit:
                    db.session.rollback()
                    current_app.logger.error(f"Error logging incoming call {call_sid}: {e_commit}")
            
            dial = Dial(
                timeout=20,
                record='record-from-answer',
                recording_status_callback=url_for('operations.recording_status_callback', _external=True),
                recording_status_callback_event='completed',
                caller_id=from_number 
            )
            client = dial.client(target_client.split(':', 1)[1]) # Get client identity string
            client.parameter(name='parent_call_sid', value=call_sid) # Pass original CallSid
            response.append(dial)
        else:
            response.say("We could not connect your call at this time. Please try again later.")
            current_app.logger.info(f"Rejecting incoming call {call_sid} - no target client found for {to_number}")
    else: # Handle outbound calls initiated by device.connect()
        # Read parameters from request.form (sent by Twilio Voice SDK's Device.connect())
        # Note: 'To' here is the *destination* number for the outbound call
        outbound_to_number = request.form.get('To')
        record_call_param = request.form.get('Record', 'false').lower() == 'true'
        from_identity_raw = request.form.get('From', '') # Should be client:type-id
        contact_id_str = request.form.get('ContactID')

        current_app.logger.info(f"Outbound TwiML request: CallSid={call_sid}, FromIdentityRaw={from_identity_raw}, To(Destination)='{outbound_to_number}', Record={record_call_param}, ContactID={contact_id_str}")

        operator_id = None
        sales_rep_id = None
        parsed_contact_id = None
        determined_from_number_for_dial = current_app.config['TWILIO_PHONE_NUMBER'] # Default

        if contact_id_str:
            try:
                parsed_contact_id = int(contact_id_str)
            except ValueError:
                current_app.logger.warning(f"Outbound TwiML: Invalid ContactID format: {contact_id_str}")
                parsed_contact_id = None

        # Parse identity and determine caller ID (existing logic)
        if from_identity_raw and from_identity_raw.startswith('client:'):
            try:
                parts = from_identity_raw.split(':', 1) # Split only once
                if len(parts) == 2:
                    type_id_part = parts[1]
                    type_parts = type_id_part.split('-', 1)
                    if len(type_parts) == 2:
                        user_type = type_parts[0]
                        user_id = int(type_parts[1])

                        if user_type == 'sales':
                            sales_rep_profile = SalesUser.query.filter_by(id=user_id).first()
                            if sales_rep_profile:
                                sales_rep_id = user_id
                                if sales_rep_profile.phone_number:
                                    determined_from_number_for_dial = sales_rep_profile.phone_number
                                current_app.logger.info(f"Outbound: Sales rep {sales_rep_id} identified. Using caller ID: {determined_from_number_for_dial}")
                            else:
                                current_app.logger.warning(f"Outbound: Sales profile for ID {user_id} not found.")
                        elif user_type == 'operator':
                            ops_profile = OperationsUser.query.filter_by(id=user_id).first()
                            if ops_profile:
                                operator_id = user_id
                                if ops_profile.phone_number:
                                    determined_from_number_for_dial = ops_profile.phone_number
                                current_app.logger.info(f"Outbound: Operator {operator_id} identified. Using caller ID: {determined_from_number_for_dial}")
                            else:
                                current_app.logger.warning(f"Outbound: Operations profile for ID {user_id} not found.")
                        else:
                            current_app.logger.warning(f"Outbound: Unknown user type '{user_type}' in identity: {from_identity_raw}")
                    else:
                        current_app.logger.warning(f"Outbound: Could not parse type/ID from '{type_id_part}' in identity: {from_identity_raw}")
                else:
                    current_app.logger.warning(f"Outbound: Could not parse identity format: {from_identity_raw}")
            except ValueError:
                current_app.logger.warning(f"Outbound: Invalid user ID in identity: {from_identity_raw}")
            except Exception as e_parse:
                current_app.logger.error(f"Outbound: Error parsing identity '{from_identity_raw}': {e_parse}")
        else:
            current_app.logger.warning(f"Outbound: From identity not in 'client:type-id' format or missing: {from_identity_raw}")

        # Create/Update call log (moved logging here for outbound only)
        if call_sid:
            existing_log = CallLog.query.filter_by(call_sid=call_sid).first()
            if not existing_log:
                if operator_id or sales_rep_id: # Only log if we know who it's for
                    call_log = CallLog(
                        call_sid=call_sid,
                        from_number=determined_from_number_for_dial, # Log the caller ID used
                        to_number=outbound_to_number if outbound_to_number else "Unknown (TwiML)",
                        status='initiated',
                        direction='outbound',
                        operator_id=operator_id,
                        sales_rep_id=sales_rep_id,
                        contact_id=parsed_contact_id
                    )
                    db.session.add(call_log)
                    try:
                        db.session.commit()
                        current_app.logger.info(f"Created outbound call log via TwiML for SID {call_sid}")
                    except Exception as e_commit:
                        db.session.rollback()
                        current_app.logger.error(f"Error committing outbound CallLog in TwiML for SID {call_sid}: {e_commit}")
                else:
                    current_app.logger.warning(f"Not creating outbound CallLog for SID {call_sid} in TwiML: No user identified.")
            else:
                current_app.logger.info(f"Outbound call log for {call_sid} already exists, skipping creation in TwiML webhook.")
        else:
            current_app.logger.warning("No CallSid in outbound TwiML request, cannot create/update log.")

        # Generate TwiML for outbound call
        if outbound_to_number and (outbound_to_number.startswith('+') or outbound_to_number.startswith('client:')):
            dial_attrs = {
                'caller_id': determined_from_number_for_dial
            }
            if record_call_param:
                dial_attrs['record'] = 'record-from-answer'
                dial_attrs['recording_status_callback'] = url_for('operations.recording_status_callback', _external=True)
                dial_attrs['recording_status_callback_event'] = 'completed'
            else:
                dial_attrs['record'] = 'do-not-record'
            
            dial = Dial(**dial_attrs)
            
            if outbound_to_number.startswith('client:'):
                client_identifier = outbound_to_number.split(':', 1)[1]
                dial.client(client_identifier)
                current_app.logger.info(f"Outbound TwiML: Dialing client '{client_identifier}' with callerId {determined_from_number_for_dial}")
            else: # PSTN number
                dial.number(outbound_to_number)
                current_app.logger.info(f"Outbound TwiML: Dialing number '{outbound_to_number}' with callerId {determined_from_number_for_dial}")
            response.append(dial)
        else:
            current_app.logger.warning(f"Outbound TwiML: 'To' number '{outbound_to_number}' is invalid or missing. Saying fallback message.")
            response.say("The number you are trying to call is not valid, or was not provided. Please check the number and try again.")

    return str(response), 200, {'Content-Type': 'text/xml'}

@bp.route('/phone', methods=['GET'])
@login_required
@operations_required
def phone_interface():
    """Dedicated phone interface page that will be embedded in an iframe"""
    return render_template('operations/phone.html')

@bp.route('/users', methods=['GET'])
@login_required
@operations_required
def get_users():
    """Get list of users for assignment dropdowns"""
    try:
        # Get users who have operations profiles
        from ..models.operations_user import OperationsUser
        
        users = db.session.query(User).join(OperationsUser).filter(
            OperationsUser.user_id == User.id
        ).all()
        
        return jsonify({
            'status': 'success',
            'users': [{'id': user.id, 'name': user.name} for user in users]
        })
    except Exception as e:
        print(f"Error getting users: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to get users'
        }), 500

@bp.route('/kpis', methods=['GET'])
@login_required
@operations_required
def get_operations_kpis():
    """Get comprehensive KPI data for operations dashboard"""
    try:
        # Get today's date range
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        today_start = datetime.combine(today, datetime.min.time())
        yesterday_start = datetime.combine(yesterday, datetime.min.time())
        
        # Today's alerts
        today_alerts = SamsaraAlert.query.filter(
            func.date(SamsaraAlert.created_at) == today
        ).count()
        
        # Yesterday's alerts for comparison
        yesterday_alerts = SamsaraAlert.query.filter(
            func.date(SamsaraAlert.created_at) == yesterday
        ).count()
        
        # Status breakdowns (all active alerts)
        unassigned_alerts = SamsaraAlert.query.filter(
            and_(SamsaraAlert.assigned_to.is_(None), SamsaraAlert.status != 'resolved')
        ).count()
        
        in_progress_alerts = SamsaraAlert.query.filter(
            SamsaraAlert.status == 'in_progress'
        ).count()
        
        resolved_today = SamsaraAlert.query.filter(
            and_(
                SamsaraAlert.status == 'resolved',
                func.date(SamsaraAlert.updated_at) == today
            )
        ).count()
        
        critical_alerts = SamsaraAlert.query.filter(
            and_(SamsaraAlert.severity == 'critical', SamsaraAlert.status != 'resolved')
        ).count()
        
        escalated_alerts = SamsaraAlert.query.filter(
            SamsaraAlert.status == 'escalated'
        ).count()
        
        # Total active alerts for percentages
        total_active_alerts = SamsaraAlert.query.filter(
            SamsaraAlert.status != 'resolved'
        ).count()
        
        # Calculate percentages
        unassigned_percentage = round((unassigned_alerts / max(total_active_alerts, 1)) * 100, 1)
        critical_percentage = round((critical_alerts / max(total_active_alerts, 1)) * 100, 1)
        resolution_rate = round((resolved_today / max(today_alerts, 1)) * 100, 1)
        
        # Calculate average response time (time from created to first assignment)
        response_times = db.session.query(
            func.extract('epoch', SamsaraAlertActivity.timestamp - SamsaraAlert.created_at) / 60
        ).join(SamsaraAlert).filter(
            and_(
                SamsaraAlertActivity.activity_type == 'assignment',
                func.date(SamsaraAlert.created_at) == today
            )
        ).all()
        
        avg_response_time = 0
        if response_times:
            avg_response_time = round(sum([rt[0] for rt in response_times if rt[0]]) / len(response_times), 1)
        
        # Calculate average resolution time for resolved alerts today
        resolution_times = db.session.query(
            func.extract('epoch', SamsaraAlert.updated_at - SamsaraAlert.created_at) / 3600
        ).filter(
            and_(
                SamsaraAlert.status == 'resolved',
                func.date(SamsaraAlert.updated_at) == today
            )
        ).all()
        
        avg_resolution_hours = 0
        avg_resolution_minutes = 0
        if resolution_times:
            avg_resolution_hours_float = sum([rt[0] for rt in resolution_times if rt[0]]) / len(resolution_times)
            avg_resolution_hours = int(avg_resolution_hours_float)
            avg_resolution_minutes = int((avg_resolution_hours_float - avg_resolution_hours) * 60)
        
        # Calculate average age of escalated alerts
        escalated_ages = db.session.query(
            func.extract('epoch', func.now() - SamsaraAlert.created_at) / 3600
        ).filter(SamsaraAlert.status == 'escalated').all()
        
        avg_escalated_age = 0
        if escalated_ages:
            avg_escalated_age = round(sum([age[0] for age in escalated_ages if age[0]]) / len(escalated_ages), 1)
        
        # Active agents (users who have been assigned alerts today or have active alerts)
        active_agents = db.session.query(User.id).join(SamsaraAlert).filter(
            or_(
                func.date(SamsaraAlert.updated_at) == today,
                and_(SamsaraAlert.assigned_to.isnot(None), SamsaraAlert.status != 'resolved')
            )
        ).distinct().count()
        
        # Team efficiency (alerts per agent)
        team_efficiency = round(today_alerts / max(active_agents, 1), 1)
        
        return jsonify({
            'status': 'success',
            'kpis': {
                'today_alerts': today_alerts,
                'today_alerts_change': today_alerts - yesterday_alerts,
                'unassigned_alerts': unassigned_alerts,
                'unassigned_percentage': unassigned_percentage,
                'in_progress_alerts': in_progress_alerts,
                'avg_resolution_time': f"{avg_resolution_hours}h {avg_resolution_minutes}m",
                'resolved_today': resolved_today,
                'resolution_rate': resolution_rate,
                'critical_alerts': critical_alerts,
                'critical_percentage': critical_percentage,
                'escalated_alerts': escalated_alerts,
                'escalated_age': avg_escalated_age,
                'avg_response_time': avg_response_time,
                'active_agents': active_agents,
                'team_efficiency': team_efficiency
            }
        })
        
    except Exception as e:
        print(f"Error getting KPIs: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to get KPI data'
        }), 500 

@bp.route('/call-logs')
@login_required
@operations_required
def call_logs_page():
    """Call logs page"""
    return render_template('operations/call_logs.html')

@bp.route('/api/call-logs', methods=['GET'])
@login_required
@operations_required
def get_call_logs():
    """Get paginated call logs with filtering"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        direction = request.args.get('direction', '')
        status = request.args.get('status', '')
        date_range = request.args.get('date_range', '')
        recording = request.args.get('recording', '')
        search = request.args.get('search', '')
        
        # Base query for ALL operations calls (not just current user)
        # This will show calls from all operators
        query = CallLog.query.filter(CallLog.operator_id.isnot(None))
        
        # Apply filters
        if direction:
            query = query.filter(CallLog.direction == direction)
        
        if status:
            query = query.filter(CallLog.status == status)
        
        if recording == 'recorded':
            query = query.filter(CallLog.recording_url.isnot(None))
        elif recording == 'not_recorded':
            query = query.filter(CallLog.recording_url.is_(None))
        
        # Date range filtering
        if date_range:
            today = datetime.now().date()
            if date_range == 'today':
                query = query.filter(func.date(CallLog.created_at) == today)
            elif date_range == 'yesterday':
                yesterday = today - timedelta(days=1)
                query = query.filter(func.date(CallLog.created_at) == yesterday)
            elif date_range == 'week':
                week_start = today - timedelta(days=today.weekday())
                query = query.filter(CallLog.created_at >= week_start)
            elif date_range == 'month':
                month_start = today.replace(day=1)
                query = query.filter(CallLog.created_at >= month_start)
        
        # Search filtering
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    CallLog.from_number.ilike(search_term),
                    CallLog.to_number.ilike(search_term)
                )
            )
        
        # Order by most recent first
        query = query.order_by(CallLog.created_at.desc())
        
        # Paginate
        pagination = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        # Format call logs
        calls = []
        for call in pagination.items:
            # Determine display number and contact info
            display_number = call.to_number if call.direction == 'outbound' else call.from_number
            contact_name = None
            operator_name = 'Unknown'
            
            # Get operator name
            if call.operator_id:
                from app.models.operations_user import OperationsUser
                operator = OperationsUser.query.get(call.operator_id)
                if operator and operator.user:
                    operator_name = operator.user.name
            
            # Try to find contact info (you can enhance this with actual contact lookup)
            if hasattr(call, 'contact') and call.contact:
                contact_name = call.contact.full_name
            
            calls.append({
                'id': call.id,
                'call_sid': call.call_sid,
                'direction': call.direction,
                'from_number': call.from_number,
                'to_number': call.to_number,
                'display_number': display_number,
                'contact_name': contact_name,
                'operator_name': operator_name,
                'operator_id': call.operator_id,
                'status': call.status,
                'duration': call.duration or 0,
                'recording_url': call.recording_url,
                'created_at': call.created_at.isoformat() if call.created_at else None,
                'start_time': call.start_time.isoformat() if call.start_time else None,
                'end_time': call.end_time.isoformat() if call.end_time else None
            })
        
        return jsonify({
            'success': True,
            'calls': calls,
            'current_page': pagination.page,
            'total_pages': pagination.pages,
            'total_calls': pagination.total,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting call logs: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to get call logs'
        }), 500

@bp.route('/api/call-stats', methods=['GET'])
@login_required
@operations_required
def get_call_stats():
    """Get call statistics for the current user"""
    try:
        today = datetime.now().date()
        
        # Total calls
        total_calls = CallLog.query.filter_by(
            operator_id=current_user.operations_profile.id
        ).count()
        
        # Calls today
        calls_today = CallLog.query.filter_by(
            operator_id=current_user.operations_profile.id
        ).filter(func.date(CallLog.created_at) == today).count()
        
        # Completed calls
        completed_calls = CallLog.query.filter_by(
            operator_id=current_user.operations_profile.id,
            status='completed'
        ).count()
        
        # Completion rate
        completion_rate = round((completed_calls / max(total_calls, 1)) * 100, 1)
        
        # Average duration of completed calls
        completed_calls_with_duration = CallLog.query.filter(
            CallLog.operator_id == current_user.operations_profile.id,
            CallLog.status == 'completed',
            CallLog.duration.isnot(None)
        ).all()
        
        avg_duration = 0
        total_duration_today = 0
        if completed_calls_with_duration:
            total_duration = sum(call.duration for call in completed_calls_with_duration)
            avg_duration = round(total_duration / len(completed_calls_with_duration))
            
            # Calculate today's total duration
            today_calls = [call for call in completed_calls_with_duration 
                          if call.created_at and call.created_at.date() == today]
            if today_calls:
                total_duration_today = sum(call.duration for call in today_calls)
        
        # Recorded calls
        recorded_calls = CallLog.query.filter_by(
            operator_id=current_user.operations_profile.id
        ).filter(CallLog.recording_url.isnot(None)).count()
        
        # Recording rate
        recording_rate = round((recorded_calls / max(total_calls, 1)) * 100, 1)
        
        return jsonify({
            'success': True,
            'stats': {
                'total_calls': total_calls,
                'calls_today': calls_today,
                'completed_calls': completed_calls,
                'completion_rate': completion_rate,
                'avg_duration': avg_duration,
                'total_duration_today': total_duration_today,
                'recorded_calls': recorded_calls,
                'recording_rate': recording_rate
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting call stats: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to get call statistics'
        }), 500 

@bp.route('/log-call', methods=['POST'])
@csrf.exempt
@login_required
@operations_required
def log_call():
    """Log a call initiated from the browser phone interface"""
    try:
        data = request.get_json()
        to_number = data.get('to_number')
        call_sid = data.get('call_sid')
        direction = data.get('direction', 'outbound')
        
        if not to_number:
            return jsonify({
                'success': False,
                'message': 'Phone number is required'
            }), 400
        
        # Create call log entry
        call_log = CallLog(
            call_sid=call_sid,
            operator_id=current_user.operations_profile.id,
            from_number=current_app.config.get('TWILIO_PHONE_NUMBER', 'Browser'),
            to_number=to_number,
            direction=direction,
            status='initiated',
            created_at=datetime.utcnow()
        )
        
        db.session.add(call_log)
        db.session.commit()
        
        current_app.logger.info(f"Logged browser call: {call_sid} to {to_number} for operator {current_user.operations_profile.id}")
        
        return jsonify({
            'success': True,
            'call_log_id': call_log.id
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error logging call: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to log call'
        }), 500 
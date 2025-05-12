from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import login_required, current_user
from ..decorators import operations_required
from ..services.operations_service.twilio.call_manager import CallManager
from ..models.operations_user import OperationsUser
from .. import db, csrf
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.twiml.voice_response import VoiceResponse, Dial
from datetime import datetime
from app.models.call_log import CallLog
from app.models.sales_user import SalesUser

bp = Blueprint('operations', __name__)

@bp.route('/operations/call', methods=['POST'])
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

@bp.route('/operations/call/<call_sid>', methods=['GET'])
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

@bp.route('/operations/call/<call_sid>', methods=['DELETE'])
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

@bp.route('/operations/calls/recent')
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

@bp.route('/operations/calls/metrics')
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

@bp.route('/operations/token', methods=['GET'])
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
        target_client = None
        
        # Find user associated with the dialed Twilio number ('To')
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
            # Log the incoming call attempt before dialing client
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
                    status='ringing', # Indicate it's ringing the client
                    direction='incoming',
                    operator_id=log_user_id,
                    sales_rep_id=log_sales_id
                )
                db.session.add(call_log)
                try:
                    db.session.commit()
                    current_app.logger.info(f"Logged incoming call {call_sid} routed to {target_client}")
                except Exception as e_commit:
                    db.session.rollback()
                    current_app.logger.error(f"Error logging incoming call {call_sid}: {e_commit}")
            
            # Dial the target client
            dial = Dial(timeout=20) # Give 20 seconds for the client to answer
            dial.client(target_client.split(':', 1)[1]) # Pass identity without 'client:' prefix
            response.append(dial)
        else:
            # No user found for this number, or 'To' number missing
            response.say("We could not connect your call at this time. Please try again later.")
            # Optionally, use <Reject reason="busy"/> or <Reject reason="no-answer"/>
            # response.reject(reason='no-answer')
            current_app.logger.info(f"Rejecting incoming call {call_sid} - no target client found for {to_number}")

    else: # Handle outbound calls initiated by device.connect()
        # Read parameters from request.form (sent by Twilio Voice SDK's Device.connect())
        # Note: 'To' here is the *destination* number for the outbound call
        outbound_to_number = request.form.get('To')
        record_call_param = request.form.get('Record', 'false').lower() == 'true'
        from_identity_raw = request.form.get('From', '') # Should be client:type-id

        current_app.logger.info(f"Outbound TwiML request: CallSid={call_sid}, FromIdentityRaw={from_identity_raw}, To(Destination)='{outbound_to_number}', Record={record_call_param}")

        operator_id = None
        sales_rep_id = None
        determined_from_number_for_dial = current_app.config['TWILIO_PHONE_NUMBER'] # Default

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
                        sales_rep_id=sales_rep_id
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
            dial = Dial(
                caller_id=determined_from_number_for_dial, # Use the determined number
                record='record-from-answer' if record_call_param else 'do-not-record'
            )
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

    return str(response)

@bp.route('/phone', methods=['GET'])
@login_required
@operations_required
def phone_interface():
    """Dedicated phone interface page that will be embedded in an iframe"""
    return render_template('operations/phone.html') 
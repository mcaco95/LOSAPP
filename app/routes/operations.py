from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import login_required, current_user
from ..decorators import operations_required
from ..services.call_manager import CallManager
from ..models.operations_user import OperationsUser
from .. import db, csrf
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.twiml.voice_response import VoiceResponse, Dial
from datetime import datetime
from app.models.call_log import CallLog

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
        success, message, call_sid = call_manager.make_call(
            from_extension=current_user.operations_profile.extension,
            to_number=to_number,
            operations_user=current_user.operations_profile,
            record=record
        )
        
        current_app.logger.info(f"Call attempt result - Success: {success}, Message: {message}, SID: {call_sid}")
        
        if success and call_sid:
            # Create initial call log
            call_log = CallLog(
                call_sid=call_sid,
                status='initiated',
                direction='outbound',
                from_number=f"client:operator-{current_user.operations_profile.id}",
                to_number=to_number,
                operator_id=current_user.operations_profile.id,
                created_at=datetime.utcnow()
            )
            db.session.add(call_log)
            db.session.commit()
            current_app.logger.info(f"Created initial call log for SID: {call_sid}")
        
        return jsonify({
            'success': success,
            'message': message,
            'call_sid': call_sid
        })
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
    """Handle Twilio call status callbacks"""
    current_app.logger.info("=== Call Status Update ===")
    
    # Extract data from the callback
    call_sid = request.form.get('CallSid')
    call_status = request.form.get('CallStatus')
    call_duration = request.form.get('CallDuration')
    from_number = request.form.get('From')
    to_number = request.form.get('To')
    
    # Get operator ID from client identifier
    operator_id = None
    if from_number and from_number.startswith('client:operator-'):
        try:
            operator_id = int(from_number.replace('client:operator-', ''))
            # For browser calls, use the Twilio number as from_number
            from_number = current_app.config['TWILIO_PHONE_NUMBER']
        except ValueError:
            current_app.logger.warning(f"Invalid operator ID in From: {from_number}")
    
    current_app.logger.info(f"Call {call_sid}: {call_status} (Duration: {call_duration}s)")
    
    try:
        # Find or create call log
        call_log = CallLog.query.filter_by(call_sid=call_sid).first()
        
        if call_log:
            # Update existing log
            call_log.status = call_status
            if call_duration:
                call_log.duration = int(call_duration)
        else:
            # Create new log with only required parameters
            call_log = CallLog(
                operator_id=operator_id,
                call_sid=call_sid,
                from_number=from_number,
                to_number=to_number,
                status=call_status,
                direction='outbound'
            )
            if call_duration:
                call_log.duration = int(call_duration)
            db.session.add(call_log)
        
        db.session.commit()
        current_app.logger.info(f"Successfully processed status update for call {call_sid}")
        return '', 200
        
    except Exception as e:
        current_app.logger.error(f"Error processing status callback: {str(e)}")
        current_app.logger.exception("Full exception:")
        return '', 500

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
    """Respond to Twilio webhook with TwiML for Voice SDK"""
    current_app.logger.info("Voice webhook triggered")
    current_app.logger.info(f"Request form data: {request.form}")
    
    # Get parameters from the request
    to_number = request.form.get('To', '')
    from_identity = request.form.get('From', '')
    call_sid = request.form.get('CallSid')
    
    current_app.logger.info(f"Call {call_sid} from {from_identity} to {to_number}")
    
    try:
        # Extract operator ID from client identity
        operator_id = None
        if from_identity and from_identity.startswith('client:operator-'):
            try:
                operator_id = int(from_identity.replace('client:operator-', ''))
            except ValueError:
                current_app.logger.warning(f"Invalid operator ID in From: {from_identity}")
        
        # Create initial call log for browser calls
        if call_sid and operator_id and to_number:
            call_log = CallLog(
                operator_id=operator_id,
                call_sid=call_sid,
                from_number=current_app.config['TWILIO_PHONE_NUMBER'],  # Use actual phone number
                to_number=to_number,
                status='initiated',
                direction='outbound'
            )
            db.session.add(call_log)
            db.session.commit()
            current_app.logger.info(f"Created call log for browser call {call_sid}")
    except Exception as e:
        current_app.logger.error(f"Error creating call log: {str(e)}")
    
    # Create TwiML response
    response = VoiceResponse()
    
    try:
        # Check if it's a client-to-phone call
        if to_number and to_number.startswith('+'):
            # It's a call to a phone number
            current_app.logger.info(f"Making outbound call to {to_number}")
            dial = Dial(
                caller_id=current_app.config['TWILIO_PHONE_NUMBER'],
                record=request.form.get('Record', 'false').lower() == 'true'
            )
            dial.number(to_number)
            response.append(dial)
            current_app.logger.info(f"Dialing out to phone number: {to_number}")
        else:
            # Log why we hit the default case
            current_app.logger.warning(f"Unrecognized 'To' format or empty. To: '{to_number}'")
            current_app.logger.warning("Falling back to default message")
            response.say("Thanks for calling. This call is powered by Twilio Voice SDK.")
        
        return str(response)
        
    except Exception as e:
        current_app.logger.error(f"Error generating TwiML: {str(e)}")
        current_app.logger.exception("Full exception:")
        response = VoiceResponse()
        response.say("An error occurred while processing your call.")
        return str(response)

@bp.route('/webhooks/voice/outbound', methods=['POST'])
@csrf.exempt
def outbound_voice_twiml():
    """Handle outbound call TwiML for Voice SDK"""
    current_app.logger.info("=== Browser Call Initiated ===")
    
    # Get the number to call from the request
    to_number = request.form.get('To')
    from_identity = request.form.get('From', '')
    call_sid = request.form.get('CallSid')
    
    current_app.logger.info(f"Call {call_sid} from {from_identity} to {to_number}")
    
    if not to_number:
        current_app.logger.error("No 'To' number provided")
        response = VoiceResponse()
        response.say("No phone number provided.")
        return str(response)
    
    try:
        # Extract operator ID from client identity
        operator_id = None
        if from_identity and from_identity.startswith('client:operator-'):
            try:
                operator_id = int(from_identity.replace('client:operator-', ''))
            except ValueError:
                current_app.logger.warning(f"Invalid operator ID in From: {from_identity}")
        
        # Create initial call log with only required parameters
        if call_sid and operator_id:
            call_log = CallLog(
                operator_id=operator_id,
                call_sid=call_sid,
                from_number=from_identity,
                to_number=to_number,
                status='initiated',
                direction='outbound'
            )
            db.session.add(call_log)
            db.session.commit()
            current_app.logger.info(f"Created call log for browser call {call_sid}")
    except Exception as e:
        current_app.logger.error(f"Error creating call log: {str(e)}")
    
    # Create TwiML response
    response = VoiceResponse()
    dial = Dial(
        caller_id=current_app.config['TWILIO_PHONE_NUMBER'],
        record=request.form.get('Record', 'false') == 'true'
    )
    dial.number(to_number)
    response.append(dial)
    
    return str(response) 
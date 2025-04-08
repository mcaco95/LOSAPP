from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from twilio.twiml.voice_response import VoiceResponse, Dial
from flask import current_app, url_for
from datetime import datetime
from ..models.call_log import CallLog
from .. import db

class CallManager:
    def __init__(self):
        current_app.logger.info("Initializing Twilio client...")
        account_sid = current_app.config['TWILIO_ACCOUNT_SID']
        auth_token = current_app.config['TWILIO_AUTH_TOKEN']
        self.twilio_number = current_app.config['TWILIO_PHONE_NUMBER']
        
        current_app.logger.info(f"Using Twilio number: {self.twilio_number}")
        
        if not account_sid or not auth_token:
            current_app.logger.error("Twilio credentials not found!")
            raise ValueError("Twilio credentials not properly configured")
            
        self.client = Client(account_sid, auth_token)
        current_app.logger.info("Twilio client initialized successfully")

    def make_call(self, to_number, from_identity=None):
        """Make an outbound call using Twilio Client"""
        try:
            # Validate phone number format
            if not to_number.startswith('+'):
                to_number = '+' + to_number
                
            # Get the webhook URL for outbound calls
            webhook_base = current_app.config['TWILIO_WEBHOOK_BASE_URL'].rstrip('/')
            voice_url = f"{webhook_base}/operations/webhooks/voice/outbound"
            
            # Create the call
            call = self.client.calls.create(
                to=to_number,
                from_=current_app.config['TWILIO_PHONE_NUMBER'],
                url=voice_url,
                status_callback=f"{webhook_base}/operations/webhooks/status",
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                record=True if current_app.config.get('CALL_RECORDING_ENABLED') else False
            )
            
            # Log the call
            call_log = CallLog(
                call_sid=call.sid,
                from_number=current_app.config['TWILIO_PHONE_NUMBER'],
                to_number=to_number,
                direction='outbound',
                status=call.status,
                user_id=current_user.id if current_user else None
            )
            db.session.add(call_log)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Call initiated successfully',
                'call_sid': call.sid
            }
            
        except TwilioRestException as e:
            current_app.logger.error(f"Twilio error: {str(e)}")
            return {
                'success': False,
                'message': f"Failed to make call: {str(e)}",
                'error': str(e)
            }
        except Exception as e:
            current_app.logger.error(f"Error making call: {str(e)}")
            return {
                'success': False,
                'message': 'An unexpected error occurred',
                'error': str(e)
            }

    def get_call_status(self, call_sid):
        """
        Get the status of a call from Twilio.
        
        Args:
            call_sid: The Twilio Call SID
            
        Returns:
            tuple: (success, status, duration)
        """
        try:
            call = self.client.calls(call_sid).fetch()
            
            # Update call log with latest status
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            if call_log and call_log.status != call.status:
                call_log.status = call.status
                if call.status == 'completed':
                    call_log.duration = call.duration or 0
                db.session.commit()
                
            return True, call.status, call.duration
        except TwilioRestException as e:
            current_app.logger.error(f"Error fetching call status: {str(e)}")
            return False, "Error fetching status", 0

    def end_call(self, call_sid):
        """
        End an active call.
        
        Args:
            call_sid: The Twilio Call SID
            
        Returns:
            bool: Success status
        """
        try:
            call = self.client.calls(call_sid).update(status="completed")
            
            # Update call log
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            if call_log:
                call_log.status = 'completed'
                call_log.end_time = datetime.utcnow()
                if call_log.start_time:
                    duration = (call_log.end_time - call_log.start_time).total_seconds()
                    call_log.duration = int(duration)
                db.session.commit()
            
            return True
        except Exception as e:
            current_app.logger.error(f"Error ending call: {str(e)}")
            return False

    def get_recent_calls(self, operations_user_id, limit=10):
        """
        Get recent calls for an operations user.
        
        Args:
            operations_user_id: ID of the operations user
            limit: Maximum number of calls to return
            
        Returns:
            list: List of CallLog objects
        """
        return CallLog.query.filter_by(
            operator_id=operations_user_id
        ).order_by(
            CallLog.created_at.desc()
        ).limit(limit).all()

    def get_call_metrics(self, operations_user_id):
        """
        Get call metrics for an operations user.
        
        Args:
            operations_user_id: ID of the operations user
            
        Returns:
            dict: Call metrics
        """
        total_calls = CallLog.query.filter_by(operator_id=operations_user_id).count()
        completed_calls = CallLog.query.filter_by(
            operator_id=operations_user_id,
            status='completed'
        ).count()
        
        # Calculate average call duration
        calls_with_duration = CallLog.query.filter(
            CallLog.operator_id == operations_user_id,
            CallLog.duration > 0
        ).all()
        
        avg_duration = 0
        if calls_with_duration:
            total_duration = sum(call.duration for call in calls_with_duration)
            avg_duration = total_duration / len(calls_with_duration)

        return {
            'total_calls': total_calls,
            'completed_calls': completed_calls,
            'completion_rate': (completed_calls / total_calls * 100) if total_calls > 0 else 0,
            'average_duration': avg_duration
        }
        
    def handle_status_callback(self, call_sid, status, duration=None):
        """
        Handle status callback from Twilio
        
        Args:
            call_sid: The Twilio Call SID
            status: Call status from Twilio
            duration: Call duration (if available)
            
        Returns:
            bool: Success status
        """
        try:
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            if not call_log:
                current_app.logger.error(f"Call log not found for SID: {call_sid}")
                return False
                
            call_log.status = status
            
            if status == 'in-progress' and not call_log.start_time:
                call_log.start_time = datetime.utcnow()
                
            if status == 'completed' and not call_log.end_time:
                call_log.end_time = datetime.utcnow()
                if duration:
                    call_log.duration = int(duration)
                elif call_log.start_time:
                    call_log.duration = int((datetime.utcnow() - call_log.start_time).total_seconds())
                    
            db.session.commit()
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error handling status callback: {str(e)}")
            return False 
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from flask import current_app
import redis
from datetime import datetime
from .... import db

class CallManager:
    """Service for managing Twilio calls"""
    
    def __init__(self):
        self.client = Client(
            current_app.config['TWILIO_ACCOUNT_SID'],
            current_app.config['TWILIO_AUTH_TOKEN']
        )
        self.app_number = current_app.config['TWILIO_NUMBER']
        self.redis_client = redis.from_url(current_app.config['REDIS_URL'])
        
    def initiate_call(self, operator_id, to_number, from_number=None):
        """Initiate a new call"""
        from ...models.operations_user import OperationsUser
        from ...models.call_log import CallLog
        
        # Get operator
        operator = OperationsUser.query.get(operator_id)
        if not operator:
            raise ValueError("Invalid operator ID")
            
        # Use operator's assigned number or app number
        actual_from = from_number or operator.phone_number or self.app_number
        
        # Create call via Twilio
        call = self.client.calls.create(
            to=to_number,
            from_=actual_from,
            url=current_app.config['TWILIO_WEBHOOK_URL'],
            status_callback=current_app.config['TWILIO_STATUS_CALLBACK_URL']
        )
        
        # Log the call
        call_log = CallLog(
            operator_id=operator_id,
            call_sid=call.sid,
            from_number=actual_from,
            to_number=to_number
        )
        db.session.add(call_log)
        db.session.commit()
        
        return call_log
        
    def handle_incoming_call(self, request_data):
        """Handle incoming call webhook from Twilio"""
        response = VoiceResponse()
        
        # Basic call handling logic
        response.say("Welcome to Logistics One Source")
        response.pause(length=1)
        
        # Add to queue if no operator is immediately available
        response.enqueue('support')
        
        return str(response)
        
    def handle_status_callback(self, call_sid, status, duration=None):
        """Handle call status updates"""
        from ...models.call_log import CallLog
        
        call_log = CallLog.query.filter_by(call_sid=call_sid).first()
        if call_log:
            call_log.update_status(status, duration)
            
    def get_active_calls(self):
        """Get all currently active calls"""
        return self.client.calls.list(status='in-progress')
        
    def end_call(self, call_sid):
        """End an active call"""
        try:
            call = self.client.calls(call_sid).update(status='completed')
            return True
        except Exception as e:
            current_app.logger.error(f"Error ending call {call_sid}: {str(e)}")
            return False
            
    def start_recording(self, call_sid):
        """Start recording a call"""
        try:
            recording = self.client.calls(call_sid).recordings.create()
            return recording.sid
        except Exception as e:
            current_app.logger.error(f"Error starting recording for call {call_sid}: {str(e)}")
            return None
            
    def stop_recording(self, call_sid, recording_sid):
        """Stop recording a call"""
        try:
            self.client.calls(call_sid).recordings(recording_sid).update(status='stopped')
            return True
        except Exception as e:
            current_app.logger.error(f"Error stopping recording {recording_sid}: {str(e)}")
            return False 
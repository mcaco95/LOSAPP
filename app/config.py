import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv()

class Config:
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    
    # Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None or True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # OAuth Configuration
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://postgres:31012662@localhost:5432/los_referral'
    print(f"DEBUG: SQLALCHEMY_DATABASE_URI = '{SQLALCHEMY_DATABASE_URI}'")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }

    # Operations Module Configuration
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    
    # Twilio Configuration
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
    TWILIO_WEBHOOK_BASE_URL = os.environ.get('TWILIO_WEBHOOK_BASE_URL', 'https://your-domain.com')
    TWILIO_VOICE_WEBHOOK = f"{TWILIO_WEBHOOK_BASE_URL}/webhooks/voice"
    TWILIO_STATUS_CALLBACK = f"{TWILIO_WEBHOOK_BASE_URL}/webhooks/status"
    
    # Twilio Voice SDK Configuration
    TWILIO_API_KEY = os.environ.get('TWILIO_API_KEY')
    TWILIO_API_SECRET = os.environ.get('TWILIO_API_SECRET')
    TWILIO_TWIML_APP_SID = os.environ.get('TWILIO_TWIML_APP_SID')
    
    # Samsara Configuration
    SAMSARA_API_KEY = os.environ.get('SAMSARA_API_KEY')
    SAMSARA_API_BASE_URL = 'https://api.samsara.com/v1'
    
    # Cache Configuration
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Operations specific database settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'pool_recycle': 1800,
        'pool_pre_ping': True
    }
    
    # WebSocket Configuration
    WEBSOCKET_PING_INTERVAL = 25
    WEBSOCKET_PING_TIMEOUT = 120
    WEBSOCKET_MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB

    # Call Recording Settings
    CALL_RECORDING_ENABLED = os.environ.get('CALL_RECORDING_ENABLED', 'True').lower() == 'true'
    CALL_RECORDING_PATH = os.environ.get('CALL_RECORDING_PATH', 'recordings')

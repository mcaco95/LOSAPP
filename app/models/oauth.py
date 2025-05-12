from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from .. import db

class OAuth(OAuthConsumerMixin, db.Model):
    """Model for storing OAuth tokens"""
    __tablename__ = 'oauth'
    
    provider_user_id = db.Column(db.String(256), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User') 
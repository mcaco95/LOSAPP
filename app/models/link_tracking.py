from datetime import datetime
import re
from .. import db

class GlobalRedirect(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    redirect_url = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def __init__(self, redirect_url):
        # Ensure URL has protocol prefix
        if not re.match(r'^https?://', redirect_url):
            redirect_url = 'https://' + redirect_url
        self.redirect_url = redirect_url

    @classmethod
    def get_active_url(cls):
        active_redirect = cls.query.filter_by(is_active=True).order_by(cls.created_at.desc()).first()
        if not active_redirect:
            return '/'
        # Ensure URL has protocol prefix
        url = active_redirect.redirect_url
        if not re.match(r'^https?://', url):
            url = 'https://' + url
        return url

class LinkClick(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    visitor_ip = db.Column(db.String(45))  # IPv6 compatible
    user_agent = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('link_clicks', lazy='dynamic'))

    @classmethod
    def get_stats_for_user(cls, user_id):
        total_clicks = cls.query.filter_by(user_id=user_id).count()
        unique_ips = db.session.query(db.func.count(db.distinct(cls.visitor_ip))).filter_by(user_id=user_id).scalar()
        last_click = cls.query.filter_by(user_id=user_id).order_by(cls.timestamp.desc()).first()
        
        return {
            'total_clicks': total_clicks,
            'unique_visitors': unique_ips,
            'last_click': last_click.timestamp if last_click else None
        }

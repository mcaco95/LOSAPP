from datetime import datetime
import re
from user_agents import parse
from sqlalchemy.dialects.postgresql import JSONB
from .. import db
from ..services.points import PointService

class GlobalRedirect(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    redirect_url = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    redirect_metadata = db.Column(JSONB)  # Store additional redirect configuration in JSONB format

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
    
    # Geographic data
    country = db.Column(db.String(2))  # ISO country code
    city = db.Column(db.String(100))
    region = db.Column(db.String(100))
    
    # Device data
    device_type = db.Column(db.String(20))  # desktop/mobile/tablet
    tracking_metadata = db.Column(JSONB)  # Store additional tracking data in JSONB format
    
    # Relationships
    user = db.relationship('User', backref=db.backref('link_clicks', lazy='dynamic'))
    
    def set_device_type(self):
        """Parse user agent and set device type"""
        if self.user_agent:
            user_agent = parse(self.user_agent)
            if user_agent.is_mobile:
                self.device_type = 'mobile'
            elif user_agent.is_tablet:
                self.device_type = 'tablet'
            else:
                self.device_type = 'desktop'
        
        # Award points for the click
        try:
            # Check if this is a unique click (first time from this IP)
            is_unique = not LinkClick.query.filter_by(
                user_id=self.user_id,
                visitor_ip=self.visitor_ip
            ).filter(LinkClick.id != self.id).first()
            
            # Award points
            PointService.award_points_for_click(self.user_id, is_unique)
        except Exception as e:
            print(f"Error awarding points for click: {str(e)}")

    @classmethod
    def get_stats_for_user(cls, user_id):
        total_clicks = cls.query.filter_by(user_id=user_id).count()
        unique_ips = db.session.query(db.func.count(db.distinct(cls.visitor_ip))).filter_by(user_id=user_id).scalar()
        last_click = cls.query.filter_by(user_id=user_id).order_by(cls.timestamp.desc()).first()
        
        # Get device type breakdown
        device_stats = db.session.query(
            cls.device_type,
            db.func.count(cls.id)
        ).filter_by(user_id=user_id).group_by(cls.device_type).all()
        
        # Get top countries
        country_stats = db.session.query(
            cls.country,
            db.func.count(cls.id)
        ).filter_by(user_id=user_id).group_by(cls.country).all()
        
        # Get top cities
        city_stats = db.session.query(
            cls.city,
            cls.country,
            db.func.count(cls.id).label('count')
        ).filter_by(user_id=user_id)\
         .filter(cls.city.isnot(None))\
         .group_by(cls.city, cls.country)\
         .order_by(db.func.count(cls.id).desc())\
         .limit(5)\
         .all()
        
        # Ensure we return valid defaults for all fields
        device_breakdown = dict(device_stats) if device_stats else {'desktop': 0, 'mobile': 0, 'tablet': 0}
        country_breakdown = dict(country_stats) if country_stats else {}
        city_breakdown = [{'name': city, 'country': country, 'count': count} 
                         for city, country, count in city_stats] if city_stats else []
        
        # Ensure all device types exist in breakdown
        for device_type in ['desktop', 'mobile', 'tablet']:
            if device_type not in device_breakdown:
                device_breakdown[device_type] = 0
        
        return {
            'total_clicks': total_clicks or 0,
            'unique_visitors': unique_ips or 0,
            'last_click': last_click.timestamp if last_click else None,
            'device_breakdown': device_breakdown,
            'country_breakdown': country_breakdown,
            'city_breakdown': city_breakdown
        }

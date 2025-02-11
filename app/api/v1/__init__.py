from flask import Blueprint
from .routes.company import bp as company_bp
from .routes.points_rewards import bp as points_rewards_bp

bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')

# Register API route blueprints
bp.register_blueprint(company_bp, url_prefix='/company')
bp.register_blueprint(points_rewards_bp, url_prefix='/points-rewards')

# Import error handlers and other common API utilities here if needed

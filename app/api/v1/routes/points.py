from flask import request, jsonify
from flask_login import login_required
from app.services.points_service import PointService

@points_api.route('/trend')
@login_required
def get_points_trend():
    period = request.args.get('period', 'month')
    if period not in ['week', 'month', 'year']:
        return jsonify({'error': 'Invalid period'}), 400

    points_service = PointService()
    trend_data = points_service.get_points_trend(current_user.id, period=period)
    
    return jsonify(trend_data) 
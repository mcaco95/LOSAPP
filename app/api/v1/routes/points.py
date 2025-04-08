from flask import request, jsonify, Blueprint
from flask_login import login_required, current_user
from ...decorators import admin_required
from ...services.points import PointService

points_api = Blueprint('points_api', __name__, url_prefix='/api/v1/points-rewards/points')

@points_api.route('/trend')
@login_required
def get_points_trend():
    period = request.args.get('period', 'month')
    if period not in ['week', 'month', 'year']:
        return jsonify({'error': 'Invalid period'}), 400

    points_service = PointService()
    trend_data = points_service.get_points_trend(current_user.id, period=period)
    
    return jsonify(trend_data)

@points_api.route('/settings/click_points_enabled', methods=['POST'])
@login_required
@admin_required
def update_click_points_setting():
    """Enable or disable awarding points for referral link clicks"""
    try:
        data = request.get_json()
        
        if data is None or 'enabled' not in data:
            return jsonify({'error': 'Missing required parameter: enabled'}), 400
            
        enabled = data['enabled']
        
        # Update the setting
        success = PointService.set_click_points_enabled(enabled)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Click points setting updated successfully',
                'enabled': enabled
            })
        else:
            return jsonify({
                'error': 'Failed to update click points setting'
            }), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500 
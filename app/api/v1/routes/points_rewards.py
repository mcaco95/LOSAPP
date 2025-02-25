from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ....services.points import PointService
from ....services.reward import RewardService
from ....decorators import admin_required

bp = Blueprint('points_rewards_api', __name__)

# Points Routes
@bp.route('/points/config', methods=['GET'])
@admin_required
def get_point_config():
    """Get point configuration"""
    try:
        configs = PointService.get_all_point_configs()
        return jsonify(configs), 200
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/points/config', methods=['PUT'])
@admin_required
def update_point_config():
    """Update point configuration"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        results = {}
        for key, value in data.items():
            # Skip metadata key
            if key == 'metadata':
                continue
                
            # Get metadata if provided
            metadata = data.get('metadata')
            
            # Update the config
            config = PointService.update_point_value(key, value, metadata)
            if config:
                results[key] = config
        return jsonify(results), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/points/config/<int:config_id>', methods=['DELETE'])
@admin_required
def delete_point_config(config_id):
    """Delete point configuration"""
    try:
        result = PointService.delete_point_config(config_id)
        if result:
            return jsonify({'success': True}), 200
        return jsonify({'error': 'Configuration not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/points/summary', methods=['GET'])
@login_required
def get_points_summary():
    """Get user's points summary"""
    try:
        summary = PointService.get_user_points_summary(current_user.id)
        return jsonify(summary), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/points/distribution', methods=['GET'])
@admin_required
def get_points_distribution():
    """Get points distribution data for charts by time period"""
    period = request.args.get('period', 'month')
    try:
        distribution_data = PointService.get_points_distribution(period)
        return jsonify(distribution_data), 200
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

# Rewards Routes
@bp.route('/rewards', methods=['GET'])
@login_required
def list_rewards():
    """List available rewards"""
    try:
        # If user_id is provided, filter by user's available points
        include_user_filter = request.args.get('user_filter', 'false').lower() == 'true'
        user_id = current_user.id if include_user_filter else None
        rewards = RewardService.get_available_rewards(user_id)
        return jsonify(rewards), 200
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/rewards', methods=['POST'])
@admin_required
def create_reward():
    """Create a new reward"""
    data = request.get_json()
    
    if not data or 'name' not in data or 'points_required' not in data:
        return jsonify({'error': 'Name and points_required are required'}), 400
    
    try:
        reward = RewardService.create_reward(
            name=data['name'],
            points_required=data['points_required'],
            description=data.get('description'),
            metadata=data.get('metadata')
        )
        return jsonify(reward), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/rewards/<int:reward_id>', methods=['PUT'])
@admin_required
def update_reward(reward_id):
    """Update reward details"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        reward = RewardService.update_reward(reward_id, **data)
        return jsonify(reward), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/rewards/<int:reward_id>/redeem', methods=['POST'])
@login_required
def redeem_reward(reward_id):
    """Redeem a reward"""
    try:
        result = RewardService.award_reward(
            user_id=current_user.id,
            reward_id=reward_id,
            metadata=request.get_json()
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/user/rewards', methods=['GET'])
@login_required
def get_user_rewards():
    """Get user's earned rewards"""
    try:
        rewards = RewardService.get_user_rewards(current_user.id)
        return jsonify(rewards), 200
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/rewards/stats', methods=['GET'])
@admin_required
def get_reward_stats():
    """Get reward statistics"""
    try:
        stats = RewardService.get_reward_statistics()
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

# System Initialization
@bp.route('/system/initialize', methods=['POST'])
@admin_required
def initialize_systems():
    """Initialize points and rewards systems"""
    try:
        points_init = PointService.initialize_point_system()
        rewards_init = RewardService.initialize_reward_system()
        
        return jsonify({
            'points_initialized': points_init,
            'rewards_initialized': rewards_init
        }), 200
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

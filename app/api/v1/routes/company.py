from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ....services.company import CompanyService
from ....decorators import admin_required

bp = Blueprint('company_api', __name__)

@bp.route('/companies', methods=['POST'])
@login_required
def create_company():
    """Create a new company referral"""
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Company name is required'}), 400
    
    try:
        company = CompanyService.create_company(
            name=data['name'],
            user_id=current_user.id,
            status=data.get('status', 'new'),
            metadata=data.get('metadata')
        )
        return jsonify(company.to_dict()), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/companies/<int:company_id>/status', methods=['PUT'])
@admin_required
def update_company_status(company_id):
    """Update company status"""
    data = request.get_json()
    
    if not data or 'status' not in data:
        return jsonify({'error': 'New status is required'}), 400
    
    try:
        result = CompanyService.update_status(
            company_id=company_id,
            new_status=data['status'],
            metadata=data.get('metadata')
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/companies/<int:company_id>', methods=['GET'])
@login_required
def get_company(company_id):
    """Get company details"""
    try:
        company = CompanyService.get_company_details(company_id)
        # Only allow admin or the company's referrer to view details
        if not current_user.is_admin and company['user']['id'] != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        return jsonify(company), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/companies', methods=['GET'])
@login_required
def list_companies():
    """List companies with optional filters"""
    try:
        # Admin can see all companies, users can only see their own
        user_id = None if current_user.is_admin else current_user.id
        status = request.args.getlist('status')
        query = request.args.get('q')
        
        companies = CompanyService.search_companies(
            query_string=query,
            status=status if status else None,
            user_id=user_id
        )
        return jsonify(companies), 200
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/companies/stats', methods=['GET'])
@admin_required
def get_company_stats():
    """Get company statistics"""
    try:
        stats = CompanyService.get_company_statistics()
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/user/companies', methods=['GET'])
@login_required
def get_user_companies():
    """Get current user's companies"""
    try:
        status = request.args.getlist('status')
        companies = CompanyService.get_user_companies(
            user_id=current_user.id,
            status=status if status else None
        )
        return jsonify(companies), 200
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

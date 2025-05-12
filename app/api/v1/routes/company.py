from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ....services.company import CompanyService
from ....decorators import admin_required
from ....models.company import Company

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

# New API endpoints for modal functionality

@bp.route('/<int:company_id>', methods=['GET'])
@login_required
@admin_required
def get_company_details(company_id):
    """Get company details for modal display"""
    try:
        company = CompanyService.get_company_details(company_id)
        return jsonify({
            'success': True,
            'company': company
        }), 200
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@bp.route('/<int:company_id>/status', methods=['PUT'])
@login_required
@admin_required
def update_status(company_id):
    """Update company status from modal"""
    try:
        data = request.get_json()
        if not data or 'status' not in data:
            return jsonify({
                'success': False,
                'message': 'Status is required'
            }), 400
            
        notes = None
        if 'metadata' in data and 'notes' in data['metadata']:
            notes = data['metadata']['notes']
            
        result = CompanyService.update_status(
            company_id=company_id,
            new_status=data['status'],
            notes=notes
        )
        
        if not result['success']:
            return jsonify(result), 400
            
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@bp.route('/<int:company_id>/service-status', methods=['PUT'])
@login_required
@admin_required
def update_service_status(company_id):
    """Update service status for a company"""
    try:
        data = request.get_json()
        if not data or 'service' not in data or 'status' not in data:
            return jsonify({
                'success': False,
                'message': 'Service and status are required'
            }), 400
            
        company = Company.query.get(company_id)
        if not company:
            return jsonify({
                'success': False,
                'message': 'Company not found'
            }), 404
            
        # Validate service type matches company's service
        service = data['service']
        if service == 'safety' and company.service_type not in ['safety', 'both']:
            return jsonify({
                'success': False,
                'message': 'Company does not have safety service'
            }), 400
        elif service == 'recruitment' and company.service_type not in ['recruitment', 'both']:
            return jsonify({
                'success': False,
                'message': 'Company does not have recruitment service'
            }), 400
            
        # Update service status
        company.update_service_status(service, data['status'])
        
        return jsonify({
            'success': True,
            'message': f'{service.title()} service status updated successfully'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@bp.route('/<int:company_id>/recruitment-request', methods=['POST'])
@login_required
@admin_required
def add_recruitment_request(company_id):
    """Add a new recruitment request for a company"""
    try:
        data = request.get_json()
        if not data or 'position' not in data:
            return jsonify({
                'success': False,
                'message': 'Position is required'
            }), 400
            
        company = Company.query.get(company_id)
        if not company:
            return jsonify({
                'success': False,
                'message': 'Company not found'
            }), 404
            
        if company.service_type not in ['recruitment', 'both']:
            return jsonify({
                'success': False,
                'message': 'Company does not have recruitment service'
            }), 400
            
        # Add recruitment request
        request_index = company.add_recruitment_request(data)
        
        return jsonify({
            'success': True,
            'message': 'Recruitment request added successfully',
            'request_index': request_index
        }), 201
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@bp.route('/<int:company_id>/recruitment-request/<int:request_index>', methods=['PUT'])
@login_required
@admin_required
def update_recruitment_request(company_id, request_index):
    """Update an existing recruitment request"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
            
        company = Company.query.get(company_id)
        if not company:
            return jsonify({
                'success': False,
                'message': 'Company not found'
            }), 404
            
        if company.service_type not in ['recruitment', 'both']:
            return jsonify({
                'success': False,
                'message': 'Company does not have recruitment service'
            }), 400
            
        # Update recruitment request
        company.update_recruitment_request(request_index, data)
        
        return jsonify({
            'success': True,
            'message': 'Recruitment request updated successfully'
        }), 200
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@bp.route('/<int:company_id>/recruitment-request/<int:request_index>', methods=['DELETE'])
@login_required
@admin_required
def delete_recruitment_request(company_id, request_index):
    """Delete a recruitment request"""
    try:
        company = Company.query.get(company_id)
        if not company:
            return jsonify({
                'success': False,
                'message': 'Company not found'
            }), 404
            
        if company.service_type not in ['recruitment', 'both']:
            return jsonify({
                'success': False,
                'message': 'Company does not have recruitment service'
            }), 400
            
        # Delete recruitment request
        company.delete_recruitment_request(request_index)
        
        return jsonify({
            'success': True,
            'message': 'Recruitment request deleted successfully'
        }), 200
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@bp.route('/<int:company_id>/recruitment-requests', methods=['GET'])
@login_required
@admin_required
def get_recruitment_requests(company_id):
    """Get recruitment requests for a company"""
    try:
        company = Company.query.get(company_id)
        if not company:
            return jsonify({
                'success': False,
                'message': 'Company not found'
            }), 404
            
        if company.service_type not in ['recruitment', 'both']:
            return jsonify({
                'success': False,
                'message': 'Company does not have recruitment service'
            }), 400
            
        requests = company.recruitment_requests.get('requests', []) if company.recruitment_requests else []
        
        return jsonify({
            'success': True,
            'requests': requests
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@bp.route('/<int:company_id>/safety-config', methods=['PUT'])
@login_required
@admin_required
def update_safety_config(company_id):
    """Update safety configuration for a company"""
    try:
        data = request.get_json()
        if not data or 'truck_count' not in data or 'price_per_truck' not in data:
            return jsonify({
                'success': False,
                'message': 'Truck count and price per truck are required'
            }), 400
            
        company = Company.query.get(company_id)
        if not company:
            return jsonify({
                'success': False,
                'message': 'Company not found'
            }), 404
            
        # Update safety configuration
        company.truck_count = data['truck_count']
        company.price_per_truck = data['price_per_truck']
        company.save()
        
        return jsonify({
            'success': True,
            'message': 'Safety configuration updated successfully'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

from flask import Blueprint, render_template, redirect, request, url_for, flash, jsonify
from flask_login import login_required, current_user
from ..services.commission import CommissionService
from ..models.commission_partner import CommissionPartner
from ..models.commission import Commission
from ..decorators import admin_required
from .. import db

bp = Blueprint('commission', __name__, url_prefix='/commission')

# Partner Management Routes
@bp.route('/partners')
@login_required
def partners():
    """View commission partners"""
    # Check if current user is a partner
    is_partner = CommissionPartner.query.filter_by(user_id=current_user.id).first() is not None
    
    # Get referral code from URL if present
    referrer_code = request.args.get('ref')
    
    # If admin, show all partners
    if current_user.is_admin:
        partners_list = CommissionPartner.query.all()
        return render_template('commission/admin_partners.html', 
                              partners=partners_list, 
                              is_partner=is_partner)
    
    # If partner, show their network
    elif is_partner:
        partner = CommissionPartner.query.filter_by(user_id=current_user.id).first()
        network = CommissionService.get_partner_network(partner.id)
        return render_template('commission/my_network.html', 
                              network=network, 
                              is_partner=True)
    
    # If not a partner, show registration page
    else:
        return render_template('commission/register.html', 
                              is_partner=False,
                              referrer_code=referrer_code)

@bp.route('/register', methods=['POST'])
@login_required
def register_partner():
    """Register as a commission partner"""
    try:
        # Check if referred by someone
        referrer_code = request.form.get('referrer_code')
        referrer_id = None
        
        if referrer_code:
            # Find the referrer by their unique link
            from ..models.user import User
            referrer_user = User.query.filter_by(unique_link=referrer_code).first()
            if referrer_user:
                referrer_partner = CommissionPartner.query.filter_by(user_id=referrer_user.id).first()
                if referrer_partner:
                    referrer_id = referrer_partner.id
        
        # Register as partner
        partner = CommissionService.register_partner(
            user_id=current_user.id,
            referrer_id=referrer_id
        )
        
        flash('You have successfully registered as a commission partner!', 'success')
        return redirect(url_for('commission.dashboard'))
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('commission.partners'))

# Commission Dashboard Routes
@bp.route('/dashboard')
@login_required
def dashboard():
    """Commission partner dashboard"""
    # Check if user is a partner
    partner = CommissionPartner.query.filter_by(user_id=current_user.id).first()
    if not partner:
        flash('You need to register as a commission partner first.', 'warning')
        return redirect(url_for('commission.partners'))
    
    # Get commission summary
    summary = CommissionService.get_partner_commissions_summary(partner.id)
    
    # Get network stats
    network = CommissionService.get_partner_network(partner.id)
    
    return render_template('commission/dashboard.html', 
                          summary=summary, 
                          network=network,
                          partner=partner)

@bp.route('/commissions')
@login_required
def commissions():
    """View commission details"""
    # Check if user has any commissions
    # First, check if user is a partner
    partner = CommissionPartner.query.filter_by(user_id=current_user.id).first()
    
    if partner:
        # Get all commissions for this partner
        status_filter = request.args.get('status')
        commissions_list = Commission.get_partner_commissions(partner.id, status_filter)
    else:
        # Check if user has any temporary partner records for commissions
        temp_partner = CommissionPartner.query.filter_by(
            user_id=current_user.id
        ).filter(
            CommissionPartner.partner_metadata.contains({'temporary': True})
        ).first()
        
        if temp_partner:
            # Get commissions for the temporary partner
            status_filter = request.args.get('status')
            commissions_list = Commission.get_partner_commissions(temp_partner.id, status_filter)
        else:
            # No commissions found
            commissions_list = []
    
    return render_template('commission/commissions.html', 
                          commissions=commissions_list,
                          partner=partner)

# Admin Routes
@bp.route('/admin/partners')
@login_required
@admin_required
def admin_partners():
    """Admin view of all partners"""
    partners_list = CommissionPartner.query.all()
    return render_template('commission/admin_partners.html', partners=partners_list)

@bp.route('/admin/commissions')
@login_required
@admin_required
def admin_commissions():
    """Admin view of all commissions"""
    status_filter = request.args.get('status')
    if status_filter:
        commissions_list = Commission.query.filter_by(status=status_filter).order_by(Commission.created_at.desc()).all()
    else:
        commissions_list = Commission.query.order_by(Commission.created_at.desc()).all()
    
    return render_template('commission/admin_commissions.html', commissions=commissions_list)

@bp.route('/admin/commission/<int:commission_id>/mark-paid', methods=['POST'])
@login_required
@admin_required
def mark_commission_paid(commission_id):
    """Mark a commission as paid"""
    commission = Commission.query.get_or_404(commission_id)
    commission.mark_as_paid()
    flash(f'Commission #{commission_id} marked as paid.', 'success')
    return redirect(url_for('commission.admin_commissions'))

@bp.route('/admin/commission/<int:commission_id>/cancel', methods=['POST'])
@login_required
@admin_required
def cancel_commission(commission_id):
    """Cancel a commission"""
    commission = Commission.query.get_or_404(commission_id)
    reason = request.form.get('reason', 'Cancelled by admin')
    commission.cancel(reason)
    flash(f'Commission #{commission_id} cancelled.', 'success')
    return redirect(url_for('commission.admin_commissions'))

@bp.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_settings():
    """Admin view for commission settings"""
    from ..models.commission_settings import CommissionSettings
    
    # Initialize default settings if they don't exist
    CommissionSettings.initialize_default_settings()
    
    # Get current settings
    commission_settings = {
        'first_2_years_rate': CommissionSettings.get_value('first_2_years_rate', 0.10),
        'after_2_years_rate': CommissionSettings.get_value('after_2_years_rate', 0.025),
        'network_commission_rate': CommissionSettings.get_value('network_commission_rate', 0.025)
    }
    
    # If form is submitted, update the settings
    if request.method == 'POST':
        try:
            # Get values from form
            first_2_years = float(request.form.get('first_2_years_rate', 0.10))
            after_2_years = float(request.form.get('after_2_years_rate', 0.025))
            network_rate = float(request.form.get('network_commission_rate', 0.025))
            
            # Validate rates (must be between 0 and 1)
            if not (0 <= first_2_years <= 1 and 0 <= after_2_years <= 1 and 0 <= network_rate <= 1):
                raise ValueError("Commission rates must be between 0 and 1 (0% to 100%)")
            
            # Store settings in database
            CommissionSettings.set_value('first_2_years_rate', first_2_years)
            CommissionSettings.set_value('after_2_years_rate', after_2_years)
            CommissionSettings.set_value('network_commission_rate', network_rate)
            
            flash('Commission settings updated successfully!', 'success')
            
            # Update the displayed settings
            commission_settings = {
                'first_2_years_rate': first_2_years,
                'after_2_years_rate': after_2_years,
                'network_commission_rate': network_rate
            }
        except ValueError as e:
            flash(f'Error updating settings: {str(e)}', 'danger')
    
    return render_template('commission/admin_settings.html', settings=commission_settings)

# API Routes
@bp.route('/api/network')
@login_required
def api_network():
    """API endpoint to get partner network data"""
    partner = CommissionPartner.query.filter_by(user_id=current_user.id).first()
    if not partner:
        return jsonify({'error': 'Not a commission partner'}), 400
    
    network = CommissionService.get_partner_network(partner.id)
    return jsonify(network)

@bp.route('/api/summary')
@login_required
def api_summary():
    """API endpoint to get commission summary data"""
    partner = CommissionPartner.query.filter_by(user_id=current_user.id).first()
    if not partner:
        return jsonify({'error': 'Not a commission partner'}), 400
    
    summary = CommissionService.get_partner_commissions_summary(partner.id)
    return jsonify(summary) 
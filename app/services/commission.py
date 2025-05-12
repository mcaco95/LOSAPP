from datetime import datetime, timedelta
from sqlalchemy import func
from ..models.commission_partner import CommissionPartner
from ..models.commission import Commission
from ..models.user import User
from ..models.company import Company
from .. import db
from ..models.commission_settings import CommissionSettings

class CommissionService:
    """Service for handling commission-related operations"""
    
    @staticmethod
    def register_partner(user_id, referrer_id=None, commission_tier='standard', metadata=None):
        """Register a user as a commission partner"""
        # Check if user exists
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Check if user is already a partner
        existing_partner = CommissionPartner.query.filter_by(user_id=user_id).first()
        if existing_partner:
            raise ValueError(f"User {user_id} is already a commission partner")
        
        # Check if referrer exists if provided
        if referrer_id:
            referrer = CommissionPartner.query.get(referrer_id)
            if not referrer:
                raise ValueError(f"Referrer partner {referrer_id} not found")
        
        # Create new partner
        partner = CommissionPartner(
            user_id=user_id,
            referrer_id=referrer_id,
            commission_tier=commission_tier,
            metadata=metadata or {}
        )
        
        try:
            db.session.add(partner)
            db.session.commit()
            
            # Award points to the referrer for partner signup if applicable
            if referrer_id:
                from .points import PointService
                referrer_user_id = CommissionPartner.query.get(referrer_id).user_id
                PointService.award_points_for_partner_signup(referrer_user_id, user_id)
            
            return partner
        except Exception as e:
            db.session.rollback()
            raise ValueError(f"Error registering partner: {str(e)}")
    
    @staticmethod
    def create_commission(partner_id, company_id, service_type, is_initial_month=True, month_number=1):
        """Create a new commission entry"""
        # Check if partner exists
        partner = CommissionPartner.query.get(partner_id)
        if not partner:
            raise ValueError(f"Partner {partner_id} not found")
        
        # Check if company exists
        company = Company.query.get(company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")
        
        # Calculate commission amount
        amount = Commission.calculate_commission(
            partner_id=partner_id,
            company_id=company_id,
            service_type=service_type,
            is_initial_month=is_initial_month,
            month_number=month_number
        )
        
        # Create commission entry
        commission = Commission(
            partner_id=partner_id,
            company_id=company_id,
            amount=amount,
            service_type=service_type,
            is_initial_month=is_initial_month,
            month_number=month_number,
            status='pending'
        )
        
        try:
            db.session.add(commission)
            db.session.commit()
            return commission
        except Exception as e:
            db.session.rollback()
            raise ValueError(f"Error creating commission: {str(e)}")
    
    @staticmethod
    def get_partner_commissions_summary(partner_id):
        """Get summary of commissions for a partner"""
        partner = CommissionPartner.query.get(partner_id)
        if not partner:
            raise ValueError(f"Partner {partner_id} not found")
        
        # Get total commissions
        total_pending = db.session.query(func.sum(Commission.amount)).filter_by(
            partner_id=partner_id, status='pending').scalar() or 0
        
        total_paid = db.session.query(func.sum(Commission.amount)).filter_by(
            partner_id=partner_id, status='paid').scalar() or 0
        
        # Get recent commissions
        recent_commissions = Commission.query.filter_by(
            partner_id=partner_id).order_by(Commission.created_at.desc()).limit(5).all()
        
        # Get commission by service type
        professional_total = db.session.query(func.sum(Commission.amount)).filter_by(
            partner_id=partner_id, service_type='professional').scalar() or 0
        
        standard_total = db.session.query(func.sum(Commission.amount)).filter_by(
            partner_id=partner_id, service_type='standard').scalar() or 0
        
        return {
            'total_pending': total_pending,
            'total_paid': total_paid,
            'total_earned': total_pending + total_paid,
            'recent_commissions': [c.to_dict() for c in recent_commissions],
            'by_service_type': {
                'professional': professional_total,
                'standard': standard_total
            }
        }
    
    @staticmethod
    def get_partner_network(partner_id):
        """Get network of partners referred by this partner"""
        partner = CommissionPartner.query.get(partner_id)
        if not partner:
            raise ValueError(f"Partner {partner_id} not found")
        
        referred_partners = partner.referred_partners.all()
        
        network = []
        for referred in referred_partners:
            referred_data = referred.to_dict()
            # Add additional stats
            referred_data['total_commissions'] = db.session.query(
                func.sum(Commission.amount)).filter_by(partner_id=referred.id).scalar() or 0
            
            referred_data['active_companies'] = Company.query.filter_by(
                user_id=referred.user_id, status='client_signed').count()
            
            network.append(referred_data)
        
        return network
    
    @staticmethod
    def process_company_status_change(company_id, new_status):
        """Process commission-related actions when company status changes"""
        company = Company.query.get(company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")
        
        # Get the user who referred this company
        user = User.query.get(company.user_id)
        if not user:
            return None
            
        commissions_created = []
            
        # Handle different status changes
        if new_status == 'client_signed_up':
            # Create commission for safety service if active
            if company.safety_status == 'active':
                # Check if user is a commission partner
                partner = CommissionPartner.query.filter_by(user_id=user.id).first()
                
                if not partner:
                    # User is not a partner, create a temporary partner record
                    partner = CommissionPartner(
                        user_id=user.id,
                        commission_tier='standard',
                        metadata={'temporary': True, 'created_for_commission': True}
                    )
                    db.session.add(partner)
                    db.session.commit()
                
                # Create direct commission (10% for first month)
                commission = Commission(
                    partner_id=partner.id,
                    company_id=company.id,
                    amount=company.truck_count * company.price_per_truck * 0.10,
                    service_type='safety',
                    commission_type='safety',
                    is_initial_month=True,
                    month_number=1,
                    status='pending',
                    metadata={
                        'truck_count': company.truck_count,
                        'price_per_truck': company.price_per_truck
                    }
                )
                db.session.add(commission)
                commissions_created.append(commission)
                
                # If this user was referred by another partner, create a network commission (2.5%)
                if partner.referrer_id:
                    referrer_partner = CommissionPartner.query.get(partner.referrer_id)
                    if referrer_partner and referrer_partner.is_active:
                        network_commission = Commission(
                            partner_id=referrer_partner.id,
                            company_id=company.id,
                            amount=company.truck_count * company.price_per_truck * 0.025,
                            service_type='safety',
                            commission_type='safety',
                            is_initial_month=True,
                            month_number=1,
                            status='pending',
                            metadata={
                                'network_commission': True,
                                'referred_partner_id': partner.id,
                                'truck_count': company.truck_count,
                                'price_per_truck': company.price_per_truck
                            }
                        )
                        db.session.add(network_commission)
                        commissions_created.append(network_commission)
        
        return commissions_created
    
    @staticmethod
    def process_monthly_commissions():
        """Process monthly recurring commissions for active clients"""
        # Find all companies with active safety service
        active_companies = Company.query.filter(
            Company.status == 'client_signed_up',
            Company.safety_status == 'active'
        ).all()
        
        commissions_created = []
        for company in active_companies:
            # Check if the company has a payment date
            if not company.payment_date:
                continue
            
            # Calculate months since payment
            months_active = (datetime.utcnow() - company.payment_date).days // 30 + 1
            
            # Skip first month as it's handled separately
            if months_active <= 1:
                continue
            
            # Check if commission for this month already exists
            existing_commission = Commission.query.filter_by(
                company_id=company.id,
                month_number=months_active,
                commission_type='safety'
            ).first()
            
            if existing_commission:
                continue
            
            # Get the user who referred this company
            user = User.query.get(company.user_id)
            if not user:
                continue
                
            # Find or create a partner record for this user
            partner = CommissionPartner.query.filter_by(user_id=user.id).first()
            
            if not partner:
                # Create a temporary partner record
                partner = CommissionPartner(
                    user_id=user.id,
                    commission_tier='standard',
                    metadata={'temporary': True, 'created_for_commission': True}
                )
                db.session.add(partner)
                db.session.commit()
            
            # Create recurring commission with appropriate month number
            commission = Commission(
                partner_id=partner.id,
                company_id=company.id,
                amount=company.truck_count * company.price_per_truck * (0.10 if months_active <= 24 else 0.025),
                service_type='safety',
                commission_type='safety',
                is_initial_month=False,
                month_number=months_active,
                status='pending',
                metadata={
                    'truck_count': company.truck_count,
                    'price_per_truck': company.price_per_truck
                }
            )
            db.session.add(commission)
            commissions_created.append(commission)
            
            # If this user was referred by another partner, create a network commission (2.5%)
            if partner.referrer_id:
                referrer_partner = CommissionPartner.query.get(partner.referrer_id)
                if referrer_partner and referrer_partner.is_active:
                    network_commission = Commission(
                        partner_id=referrer_partner.id,
                        company_id=company.id,
                        amount=company.truck_count * company.price_per_truck * 0.025,  # Always 2.5%
                        service_type='safety',
                        commission_type='safety',
                        is_initial_month=False,
                        month_number=months_active,
                        status='pending',
                        metadata={
                            'network_commission': True,
                            'referred_partner_id': partner.id,
                            'truck_count': company.truck_count,
                            'price_per_truck': company.price_per_truck
                        }
                    )
                    db.session.add(network_commission)
                    commissions_created.append(network_commission)
        
        db.session.commit()
        return commissions_created 
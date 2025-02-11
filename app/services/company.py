from datetime import datetime
from ..models.company import Company
from ..models.user import User
from .points import PointService
from .. import db

class CompanyService:
    """Service for handling company-related operations"""

    @staticmethod
    def create_company(name, user_id, status='new', metadata=None):
        """Create a new company referral"""
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        company = Company(
            name=name,
            user_id=user_id,
            status=status,
            metadata=metadata or {}
        )
        
        try:
            db.session.add(company)
            db.session.commit()
            return company
        except Exception as e:
            db.session.rollback()
            raise ValueError(f"Error creating company: {str(e)}")

    @staticmethod
    def update_status(company_id, new_status, metadata=None):
        """Update company status and award points"""
        company = Company.query.get(company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")

        old_status = company.status
        
        # Update metadata if provided
        if metadata:
            if not company.metadata:
                company.metadata = {}
            company.metadata.update(metadata)

        try:
            # Update status and record in history
            company.update_status(new_status)
            
            # Award points for status change
            points_awarded = PointService.award_points_for_status(company_id, new_status)
            
            return {
                'company': company.to_dict(),
                'old_status': old_status,
                'new_status': new_status,
                'points_awarded': points_awarded
            }
        except Exception as e:
            db.session.rollback()
            raise ValueError(f"Error updating company status: {str(e)}")

    @staticmethod
    def get_company_details(company_id):
        """Get detailed company information"""
        company = Company.query.get(company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")

        return {
            **company.to_dict(),
            'user': {
                'id': company.user.id,
                'name': company.user.username,
                'email': company.user.email
            }
        }

    @staticmethod
    def get_user_companies(user_id, status=None):
        """Get companies for a specific user, optionally filtered by status"""
        query = Company.query.filter_by(user_id=user_id)
        
        if status:
            if isinstance(status, list):
                query = query.filter(Company.status.in_(status))
            else:
                query = query.filter_by(status=status)
        
        companies = query.order_by(Company.created_at.desc()).all()
        return [company.to_dict() for company in companies]

    @staticmethod
    def get_company_statistics():
        """Get overall company statistics"""
        total_companies = Company.query.count()
        
        # Get counts by status
        status_counts = db.session.query(
            Company.status,
            db.func.count(Company.id)
        ).group_by(Company.status).all()
        
        # Get top referrers
        top_referrers = db.session.query(
            User.id,
            User.email,
            db.func.count(Company.id).label('company_count')
        ).join(Company).group_by(User.id, User.email)\
         .order_by(db.func.count(Company.id).desc())\
         .limit(5).all()
        
        return {
            'total_companies': total_companies,
            'by_status': dict(status_counts),
            'top_referrers': [
                {
                    'user_id': user_id,
                    'email': email,
                    'company_count': count
                }
                for user_id, email, count in top_referrers
            ]
        }

    @staticmethod
    def search_companies(query_string, status=None, user_id=None):
        """Search companies with optional filters"""
        query = Company.query
        
        if query_string:
            search = f"%{query_string}%"
            query = query.filter(Company.name.ilike(search))
        
        if status:
            if isinstance(status, list):
                query = query.filter(Company.status.in_(status))
            else:
                query = query.filter_by(status=status)
        
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        companies = query.order_by(Company.created_at.desc()).all()
        return [company.to_dict() for company in companies]

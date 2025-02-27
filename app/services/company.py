from datetime import datetime
from ..models.company import Company
from ..models.user import User
from .points import PointService
from .. import db

class CompanyService:
    """Service for handling company-related operations"""

    @staticmethod
    def create_company(name, user_id, status='lead', metadata=None):
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
            
            # Award points for lead generation
            points_awarded = PointService.award_points_for_status(company.id, status)
            
            # Update the status history with the points (without changing status)
            if not company.company_metadata:
                company.company_metadata = {}
            if 'status_history' not in company.company_metadata:
                company.company_metadata['status_history'] = []
            
            # Record initial status with points
            company.company_metadata['status_history'][0]['points_awarded'] = points_awarded
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

        # Don't update if status hasn't changed
        if company.status == new_status:
            return {
                'company': company.to_dict(),
                'old_status': company.status,
                'new_status': new_status,
                'points_awarded': 0
            }

        old_status = company.status
        
        # Update metadata if provided
        if metadata:
            if not company.company_metadata:
                company.company_metadata = {}
            company.company_metadata.update(metadata)

        try:
            # Award points for status change first
            points_awarded = PointService.award_points_for_status(company_id, new_status)
            
            # Update status and record in history with the awarded points
            company.update_status(new_status, points_awarded)
            
            # Commit the transaction
            db.session.commit()
            
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
        result = []
        for company in companies:
            company_dict = company.to_dict()
            # Add user information
            if company.user:
                company_dict['user_name'] = company.user.name
                company_dict['user_email'] = company.user.email
            result.append(company_dict)
        return result

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
        query = Company.query.join(User)
        
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
        result = []
        for company in companies:
            company_dict = company.to_dict()
            # Add user information
            if company.user:
                company_dict['user_name'] = company.user.name
                company_dict['user_email'] = company.user.email
            result.append(company_dict)
        return result

    @staticmethod
    def get_recent_status_changes(limit=10):
        """Get recent company status changes"""
        from datetime import datetime
        
        companies = Company.query.order_by(Company.updated_at.desc()).limit(50).all()
        changes = []
        
        for company in companies:
            if not company.company_metadata or 'status_history' not in company.company_metadata:
                continue
                
            status_history = company.company_metadata.get('status_history', [])
            
            # Get the most recent status changes
            for change in reversed(status_history[-5:]):  # Look at the last 5 changes
                changes.append({
                    'company_id': company.id,
                    'company_name': company.name,
                    'user_id': company.user_id,
                    'user_name': company.user.username if company.user else 'Unknown',
                    'from_status': change.get('from'),
                    'to_status': change.get('to'),
                    'from_status_display': Company.get_status_display(change.get('from')),
                    'to_status_display': Company.get_status_display(change.get('to')),
                    'timestamp': change.get('timestamp'),
                    'points_awarded': change.get('points_awarded', 0)
                })
                
                if len(changes) >= limit:
                    break
            
            if len(changes) >= limit:
                break
                
        # Sort by timestamp (newest first)
        return sorted(
            changes,
            key=lambda x: datetime.fromisoformat(x['timestamp']) if x['timestamp'] else datetime.min,
            reverse=True
        )[:limit]

    @staticmethod
    def get_status_changes_history(limit=None):
        """Get history of company status changes with points awarded"""
        try:
            from ..models.company import Company
            from ..models.user import User

            changes = []
            companies = Company.query.all()

            for company in companies:
                if not company.company_metadata or 'status_history' not in company.company_metadata:
                    continue

                status_history = company.company_metadata['status_history']
                for entry in status_history:
                    # Skip entries without proper data
                    if not all(k in entry for k in ['from', 'to', 'timestamp']):
                        continue

                    # Use the points that were awarded at the time of the status change
                    points = entry.get('points_awarded', 0)

                    change = {
                        'company_name': company.name,
                        'user_name': company.user.username if company.user else 'Unknown',
                        'from_status': entry['from'],
                        'to_status': entry['to'],
                        'from_status_display': Company.get_status_display(entry['from']),
                        'to_status_display': Company.get_status_display(entry['to']),
                        'points_awarded': points,
                        'timestamp': entry['timestamp']
                    }
                    changes.append(change)

            # Sort by timestamp in descending order
            sorted_changes = sorted(
                changes,
                key=lambda x: x['timestamp'],
                reverse=True
            )

            # Apply limit if specified
            return sorted_changes[:limit] if limit else sorted_changes

        except Exception as e:
            print(f"Error getting status changes history: {str(e)}")
            return []

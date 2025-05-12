from datetime import datetime, timedelta
import random
from faker import Faker
from werkzeug.security import generate_password_hash
from app import db, create_app
from app.models.user import User
from app.models.company import Company
from app.models.commission_partner import CommissionPartner
from app.models.commission import Commission
from app.models.point_config import PointConfig
from app.models.link_tracking import LinkClick
from app.models.reward import Reward
from sqlalchemy import text

fake = Faker()

def cleanup_test_data():
    """Remove all test data before generating new data"""
    print("Cleaning up old test data...")
    
    # Delete in order of dependencies
    print("Deleting all commissions...")
    Commission.query.delete(synchronize_session=False)
    db.session.commit()
    
    print("Deleting link clicks...")
    LinkClick.query.delete(synchronize_session=False)
    db.session.commit()
    
    print("Deleting companies...")
    Company.query.delete(synchronize_session=False)
    db.session.commit()
    
    print("Deleting commission partners...")
    # First, get all partners
    all_partners = CommissionPartner.query.all()
    
    # Delete partners level by level (from leaves to root)
    while all_partners:
        # Find leaf partners (those who are not referrers to anyone)
        leaf_partner_ids = {p.id for p in all_partners}
        referrer_ids = {p.referrer_id for p in all_partners if p.referrer_id is not None}
        leaf_partner_ids = leaf_partner_ids - referrer_ids
        
        # Delete leaf partners
        if leaf_partner_ids:
            CommissionPartner.query.filter(CommissionPartner.id.in_(leaf_partner_ids)).delete(synchronize_session=False)
            db.session.commit()
            # Update the list of remaining partners
            all_partners = CommissionPartner.query.all()
        else:
            # If no leaf partners found but partners still exist, they must be in a cycle
            # Delete them all at once
            CommissionPartner.query.delete(synchronize_session=False)
            db.session.commit()
            break
    
    print("Deleting point transactions...")
    # Execute raw SQL to delete point transactions
    db.session.execute(text("DELETE FROM point_transaction"))
    db.session.commit()
    
    print("Deleting rewards...")
    # Delete any rewards
    if hasattr(db.Model, 'Reward'):
        db.session.execute(text("DELETE FROM reward"))
        db.session.commit()
    
    print("Deleting users (except admin and Nicolas)...")
    # Preserve admin and Nicolas users
    User.query.filter(~User.email.in_(['simon@logisticsonesource.com', 'nicolas@logisticsonesource.com'])).delete(synchronize_session=False)
    db.session.commit()
    
    print("Cleanup complete!")

def create_test_users(num_users=10):
    """Create test users with various roles"""
    users = []
    
    for _ in range(num_users):
        user = User(
            email=fake.email(),
            name=fake.name(),
            password_hash=generate_password_hash('test123'),
            created_at=datetime.utcnow(),
            is_admin=random.choice([True, False]),
            points=0,
            points_history={'transactions': []}
        )
        users.append(user)
        db.session.add(user)
    
    db.session.commit()
    return users

def create_nicolas_user():
    """Create or get Nicolas's user account"""
    nicolas = User.query.filter_by(email='nicolas@logisticsonesource.com').first()
    if not nicolas:
        nicolas = User(
            email='nicolas@logisticsonesource.com',
            name='Nicolas Morales',
            password_hash=generate_password_hash('123456'),
            created_at=datetime.utcnow(),
            is_admin=False,
            points=0,
            points_history={'transactions': []}
        )
        db.session.add(nicolas)
        db.session.commit()
        print("Created user nicolas@logisticsonesource.com")
    return nicolas

def create_commission_partners(users, num_partners=5):
    """Create commission partners with various configurations and referral relationships"""
    partners = []
    
    # Create Nicolas as the root partner
    nicolas = User.query.filter_by(email='nicolas@logisticsonesource.com').first()
    if not nicolas:
        raise Exception("Nicolas user not found! Please ensure create_nicolas_user() is called first.")
    
    root_partner = CommissionPartner(
        user_id=nicolas.id,
        commission_tier='standard',
        metadata={
            'payment_method': 'direct_deposit',
            'application_status': 'approved',
            'signup_completed': True,
            'approved_at': datetime.utcnow().isoformat(),
            'status': 'active'
        }
    )
    db.session.add(root_partner)
    db.session.flush()  # Flush to get the ID
    partners.append(root_partner)
    
    # Create remaining partners with referral relationships
    # Filter out Nicolas and admin from the users list for remaining partners
    remaining_users = [u for u in users if u.email not in ['nicolas@logisticsonesource.com', 'simon@logisticsonesource.com']]
    remaining_users = remaining_users[:num_partners-1]  # -1 because Nicolas is already a partner
    
    for i, user in enumerate(remaining_users):
        # Make most partners referred by Nicolas (80% chance)
        referrer = root_partner if random.random() < 0.8 else random.choice(partners[1:] or [root_partner])
        
        partner = CommissionPartner(
            user_id=user.id,
            commission_tier='standard',
            referrer_id=referrer.id,
            metadata={
                'payment_method': random.choice(['direct_deposit', 'check', 'paypal']),
                'referred_by': referrer.id,
                'application_status': 'approved',
                'signup_completed': True,
                'approved_at': datetime.utcnow().isoformat(),
                'status': 'active',
                'referral_details': {
                    'referrer_name': referrer.user.name,
                    'referral_date': datetime.utcnow().isoformat()
                }
            }
        )
        
        # Update user's points for partner signup
        user.points += PointConfig.get_value('status_partner_signup', 25)
        user.points_history['transactions'].append({
            'type': 'partner_signup',
            'points': PointConfig.get_value('status_partner_signup', 25),
            'timestamp': datetime.utcnow().isoformat(),
            'description': f'Partner program signup through {referrer.user.name}'
        })
        
        partners.append(partner)
        db.session.add(partner)
    
    db.session.commit()
    
    # Print partner network structure for verification
    print("\nPartner Network Structure:")
    print(f"Root Partner: {nicolas.name} (ID: {root_partner.id})")
    for partner in partners[1:]:
        referrer_name = CommissionPartner.query.get(partner.referrer_id).user.name
        print(f"- {partner.user.name} (ID: {partner.id}) → Referred by: {referrer_name}")
    
    return partners

def create_companies(users, num_companies=20):
    """Create test companies following a logical business flow"""
    companies = []
    contact_times = ['morning', 'afternoon', 'evening']
    
    # Get Nicolas's user ID
    nicolas = User.query.filter_by(email='nicolas@logisticsonesource.com').first()
    if not nicolas:
        raise Exception("Nicolas user not found!")
    
    # Helper function to create a company with proper status history
    def create_company_with_history(user_id, current_status, days_ago_created):
        status_flow = ['referral_form_completed', 'demo_scheduled', 'demo_completed', 'client_signed_up', 'client_renewed']
        current_idx = status_flow.index(current_status)
        
        # Create status history
        history = []
        base_date = datetime.utcnow() - timedelta(days=days_ago_created)
        for i in range(current_idx + 1):
            status = status_flow[i]
            history.append({
                'from': status_flow[i-1] if i > 0 else None,
                'to': status,
                'timestamp': (base_date + timedelta(days=i*5)).isoformat(),  # 5 days between status changes
                'points_awarded': 0
            })
        
        return {
            'name': fake.company()[:100],
            'user_id': user_id,
            'status': current_status,
            'company_metadata': {
            'industry': fake.job()[:50],
            'size': random.choice(['small', 'medium', 'large']),
            'region': fake.state(),
                'status_history': history
            },
            'created_at': base_date
        }
    
    # Create Nicolas's successful companies (older ones)
    successful_companies = [
        # Company 1: Safety only, large fleet
        {**create_company_with_history(nicolas.id, 'client_signed_up', 300),
         'safety_status': 'active',
         'recruitment_status': 'inactive',
         'truck_count': 40,
         'price_per_truck': 175.0},
        
        # Company 2: Safety only, medium fleet
        {**create_company_with_history(nicolas.id, 'client_signed_up', 240),
         'safety_status': 'active',
         'recruitment_status': 'inactive',
         'truck_count': 25,
         'price_per_truck': 150.0},
        
        # Company 3: Both services
        {**create_company_with_history(nicolas.id, 'client_renewed', 180),
         'safety_status': 'active',
         'recruitment_status': 'active',
         'truck_count': 15,
         'price_per_truck': 125.0,
         'recruitment_requests': {'requests': [
             {
                 'id': 1,
                 'role': 'Senior Driver',
                 'charge': 3500,
                 'status': 'completed',
                 'created_at': (datetime.utcnow() - timedelta(days=160)).isoformat(),
                 'updated_at': (datetime.utcnow() - timedelta(days=130)).isoformat()
             },
             {
                 'id': 2,
                 'role': 'Fleet Manager',
                 'charge': 4500,
                 'status': 'completed',
                 'created_at': (datetime.utcnow() - timedelta(days=90)).isoformat(),
                 'updated_at': (datetime.utcnow() - timedelta(days=60)).isoformat()
             }
         ]}},
        
        # Company 4: Recruitment only, multiple placements
        {**create_company_with_history(nicolas.id, 'client_signed_up', 150),
         'safety_status': 'inactive',
         'recruitment_status': 'active',
         'recruitment_requests': {'requests': [
             {
                 'id': 1,
                 'role': 'Operations Manager',
                 'charge': 4000,
                 'status': 'in_progress',
                 'created_at': (datetime.utcnow() - timedelta(days=30)).isoformat(),
                 'updated_at': datetime.utcnow().isoformat()
             },
             {
                 'id': 2,
                 'role': 'Logistics Coordinator',
                 'charge': 3000,
                 'status': 'in_progress',
                 'created_at': (datetime.utcnow() - timedelta(days=30)).isoformat(),
                 'updated_at': datetime.utcnow().isoformat()
             }
         ]}},
        
        # Company 5: Recruitment only, recent placement
        {**create_company_with_history(nicolas.id, 'client_signed_up', 90),
         'safety_status': 'inactive',
         'recruitment_status': 'active',
         'recruitment_requests': {'requests': [
             {
                 'id': 1,
                 'role': 'Safety Director',
                 'charge': 5000,
                 'status': 'completed',
                 'created_at': (datetime.utcnow() - timedelta(days=60)).isoformat(),
                 'updated_at': (datetime.utcnow() - timedelta(days=30)).isoformat()
             }
         ]}}
    ]
    
    # Create Nicolas's in-progress companies
    in_progress_companies = [
        # Company 6: Demo scheduled, interested in safety
        {**create_company_with_history(nicolas.id, 'demo_scheduled', 15),
         'safety_status': 'inactive',
         'recruitment_status': 'inactive',
         'truck_count': 30,  # Potential fleet size
         'price_per_truck': 150.0},
        
        # Company 7: Demo completed, interested in both services
        {**create_company_with_history(nicolas.id, 'demo_completed', 10),
         'safety_status': 'inactive',
         'recruitment_status': 'inactive',
         'truck_count': 20,
         'price_per_truck': 125.0,
         'recruitment_requests': {'requests': []}},
        
        # Company 8: Just signed up, setting up safety service
        {**create_company_with_history(nicolas.id, 'client_signed_up', 5),
         'safety_status': 'active',
         'recruitment_status': 'inactive',
         'truck_count': 35,
         'price_per_truck': 160.0}
    ]
    
    # Process and add all Nicolas's companies
    for company_data in (successful_companies + in_progress_companies):
        company = Company(
            name=company_data['name'],
            user_id=company_data['user_id'],
            status=company_data['status'],
            company_metadata=company_data['company_metadata'],
            contact_name=fake.name()[:100],
            email=fake.email()[:120],
            phone=fake.phone_number()[:20],
            service_type='both' if company_data.get('safety_status') == 'active' and company_data.get('recruitment_status') == 'active'
                        else 'safety' if company_data.get('safety_status') == 'active'
                        else 'recruitment' if company_data.get('recruitment_status') == 'active'
                        else None,
            preferred_contact_time=random.choice(contact_times),
            additional_info=fake.text(max_nb_chars=200),
            safety_status=company_data.get('safety_status', 'inactive'),
            recruitment_status=company_data.get('recruitment_status', 'inactive'),
            recruitment_requests=company_data.get('recruitment_requests', {'requests': []}),
            truck_count=company_data.get('truck_count', 0),
            price_per_truck=company_data.get('price_per_truck', 0),
            payment_date=company_data['created_at'] if company_data['status'] in ['client_signed_up', 'client_renewed'] else None
        )
        companies.append(company)
        db.session.add(company)
    
    # Create companies for referred partners (3 partners, 2 companies each)
    referred_partners = [p for p in CommissionPartner.query.all() if p.referrer_id and p.user_id != nicolas.id][:3]
    for partner in referred_partners:
        # Successful company for this partner
        successful = {
            **create_company_with_history(partner.user_id, 'client_signed_up', random.randint(60, 120)),
            'safety_status': 'active',
            'recruitment_status': 'active',
            'truck_count': random.randint(15, 35),
            'price_per_truck': random.uniform(125, 175),
            'recruitment_requests': {'requests': [
                {
                    'id': 1,
                    'role': fake.job(),
                    'charge': random.uniform(3000, 4500),
                    'status': 'completed',
                    'created_at': (datetime.utcnow() - timedelta(days=random.randint(30, 90))).isoformat(),
                    'updated_at': (datetime.utcnow() - timedelta(days=random.randint(5, 25))).isoformat()
                }
            ]}
        }
        
        # In-progress company for this partner
        in_progress = {
            **create_company_with_history(partner.user_id, random.choice(['demo_scheduled', 'demo_completed']), random.randint(5, 15)),
            'safety_status': 'inactive',
            'recruitment_status': 'inactive'
        }
        
        for company_data in [successful, in_progress]:
            company = Company(
                name=company_data['name'],
                user_id=company_data['user_id'],
                status=company_data['status'],
                company_metadata=company_data['company_metadata'],
                contact_name=fake.name()[:100],
                email=fake.email()[:120],
                phone=fake.phone_number()[:20],
                service_type='both' if company_data.get('safety_status') == 'active' and company_data.get('recruitment_status') == 'active'
                            else 'safety' if company_data.get('safety_status') == 'active'
                            else 'recruitment' if company_data.get('recruitment_status') == 'active'
                            else None,
                preferred_contact_time=random.choice(contact_times),
                additional_info=fake.text(max_nb_chars=200),
                safety_status=company_data.get('safety_status', 'inactive'),
                recruitment_status=company_data.get('recruitment_status', 'inactive'),
                recruitment_requests=company_data.get('recruitment_requests', {'requests': []}),
                truck_count=company_data.get('truck_count', 0),
                price_per_truck=company_data.get('price_per_truck', 0),
                payment_date=company_data['created_at'] if company_data['status'] in ['client_signed_up', 'client_renewed'] else None
        )
        companies.append(company)
        db.session.add(company)
    
    db.session.commit()
    
    # Print summary of Nicolas's companies
    nicolas_companies = [c for c in companies if c.user_id == nicolas.id]
    print(f"\nNicolas's Companies Summary:")
    print(f"Total companies: {len(nicolas_companies)}")
    print("Status breakdown:")
    for status in set(c.status for c in nicolas_companies):
        count = len([c for c in nicolas_companies if c.status == status])
        print(f"- {status}: {count}")
    print("Service type breakdown:")
    safety_count = len([c for c in nicolas_companies if c.safety_status == 'active'])
    recruitment_count = len([c for c in nicolas_companies if c.recruitment_status == 'active'])
    print(f"- Safety services: {safety_count}")
    print(f"- Recruitment services: {recruitment_count}")
    
    # Print summary of referred partner companies
    referred_companies = [c for c in companies if c.user_id != nicolas.id]
    print(f"\nReferred Partner Companies Summary:")
    print(f"Total companies: {len(referred_companies)}")
    print("Status breakdown:")
    for status in set(c.status for c in referred_companies):
        count = len([c for c in referred_companies if c.status == status])
        print(f"- {status}: {count}")
    
    return companies

def create_commissions(partners, companies):
    """Create test commissions with realistic patterns"""
    commissions = []
    
    # Helper function to create a commission
    def create_commission(partner_id, company_id, amount, service_type, commission_type, 
                        is_initial_month, month_number, status, metadata):
        commission = Commission(
            partner_id=partner_id,
            company_id=company_id,
            amount=amount,
            service_type=service_type,
            commission_type=commission_type,
            is_initial_month=is_initial_month,
            month_number=month_number,
            status=status,
            metadata=metadata
        )
        commissions.append(commission)
        db.session.add(commission)
    
    for company in companies:
        if company.status in ['client_signed_up', 'client_renewed']:
            # Find the actual partner for this company
            partner = CommissionPartner.query.filter_by(user_id=company.user_id).first()
            if not partner:
                continue
            
            # Create safety service commissions if active
            if company.safety_status == 'active':
                # Calculate months active
                months_active = ((datetime.utcnow() - company.payment_date).days // 30) + 1
                
                # Create commissions for each month
                for month in range(1, months_active + 1):
                    # Calculate commission amount (10% first 2 years, 2.5% after)
                    rate = 0.10 if month <= 24 else 0.025
                    amount = company.truck_count * company.price_per_truck * rate
                    
                    # Determine status (older ones more likely to be paid)
                    status = 'paid' if month < months_active - 1 or random.random() < 0.7 else 'pending'
                    
                    # Create direct commission
                    create_commission(
                partner_id=partner.id,
                company_id=company.id,
                        amount=amount,
                        service_type='safety',
                        commission_type='safety',
                        is_initial_month=(month == 1),
                        month_number=month,
                        status=status,
                        metadata={
                            'truck_count': company.truck_count,
                            'price_per_truck': company.price_per_truck
                        }
                    )
                    
                    # Create network commission if partner was referred
                    if partner.referrer_id:
                        create_commission(
                            partner_id=partner.referrer_id,
                            company_id=company.id,
                            amount=company.truck_count * company.price_per_truck * 0.025,
                            service_type='safety',
                            commission_type='safety',
                            is_initial_month=(month == 1),
                            month_number=month,
                            status=status,
                            metadata={
                                'network_commission': True,
                                'referred_partner_id': partner.id,
                                'truck_count': company.truck_count,
                                'price_per_truck': company.price_per_truck
                            }
                        )
            
            # Create recruitment commissions for completed requests
            if company.recruitment_status == 'active' and company.recruitment_requests:
                for request in company.recruitment_requests['requests']:
                    if request['status'] == 'completed':
                        # Determine status based on completion date
                        completed_date = datetime.fromisoformat(request['updated_at'])
                        status = 'paid' if (datetime.utcnow() - completed_date).days > 30 else 'pending'
                        
                        # Create direct commission (10%)
                        create_commission(
                partner_id=partner.id,
                company_id=company.id,
                            amount=request['charge'] * 0.10,
                            service_type='recruitment',
                            commission_type='recruitment',
                is_initial_month=True,
                month_number=1,
                            status=status,
                            metadata={
                                'recruitment_role': request['role'],
                                'recruitment_request_id': request['id'],
                                'charge': request['charge']
                            }
                        )
                        
                        # Create network commission if partner was referred (2.5%)
                if partner.referrer_id:
                            create_commission(
                        partner_id=partner.referrer_id,
                        company_id=company.id,
                                amount=request['charge'] * 0.025,
                                service_type='recruitment',
                                commission_type='recruitment',
                                is_initial_month=True,
                                month_number=1,
                                status=status,
                                metadata={
                                    'network_commission': True,
                                    'referred_partner_id': partner.id,
                                    'recruitment_role': request['role'],
                                    'recruitment_request_id': request['id'],
                                    'charge': request['charge']
                                }
                            )
    
    db.session.commit()
    
    # Print commission summary
    print("\nCommission Summary:")
    print(f"Total commissions: {len(commissions)}")
    
    # Summary for Nicolas
    nicolas = User.query.filter_by(email='nicolas@logisticsonesource.com').first()
    nicolas_partner = CommissionPartner.query.filter_by(user_id=nicolas.id).first()
    nicolas_commissions = [c for c in commissions if c.partner_id == nicolas_partner.id]
    
    print("\nNicolas's Commissions:")
    print(f"Total: {len(nicolas_commissions)}")
    print("By type:")
    safety_commissions = [c for c in nicolas_commissions if c.service_type == 'safety']
    recruitment_commissions = [c for c in nicolas_commissions if c.service_type == 'recruitment']
    print(f"- Safety: {len(safety_commissions)}")
    print(f"- Recruitment: {len(recruitment_commissions)}")
    print("By status:")
    paid_commissions = [c for c in nicolas_commissions if c.status == 'paid']
    pending_commissions = [c for c in nicolas_commissions if c.status == 'pending']
    print(f"- Paid: {len(paid_commissions)}")
    print(f"- Pending: {len(pending_commissions)}")
    
    # Calculate total earnings
    total_paid = sum(c.amount for c in paid_commissions)
    total_pending = sum(c.amount for c in pending_commissions)
    print(f"\nTotal earnings:")
    print(f"- Paid: ${total_paid:.2f}")
    print(f"- Pending: ${total_pending:.2f}")
    
    return commissions

def create_link_clicks(users, num_entries=100):
    """Create test link click data"""
    clicks = []
    
    for _ in range(num_entries):
        user = random.choice(users)
        click = LinkClick(
            user_id=user.id,
            visitor_ip=fake.ipv4(),
            user_agent=fake.user_agent()[:255],
            timestamp=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
            country=fake.country_code(),
            city=fake.city()[:100],
            region=fake.state()[:100],
            device_type=random.choice(['desktop', 'mobile', 'tablet']),
            tracking_metadata={
                'referrer': fake.uri(),
                'browser': fake.chrome(),
                'os': fake.windows_platform_token()
            }
        )
        click.set_device_type()
        clicks.append(click)
        db.session.add(click)
    
    db.session.commit()
    return clicks

def create_admin_user():
    """Create or get the main admin user"""
    admin = User.query.filter_by(email='simon@logisticsonesource.com').first()
    if not admin:
        admin = User(
            email='simon@logisticsonesource.com',
            name='Simon Admin',
            password_hash=generate_password_hash('123456'),
            created_at=datetime.utcnow(),
            is_admin=True,
            points=0,
            points_history={'transactions': []}
        )
        db.session.add(admin)
        db.session.commit()
        print("Created admin user simon@logisticsonesource.com")
    return admin

def main():
    """Main function to generate all test data"""
    app = create_app()
    with app.app_context():
        print("Starting test data generation...")
        
        # First, create/ensure admin user exists
        admin = create_admin_user()
        
        # Create Nicolas's user account
        nicolas = create_nicolas_user()
        
        # Then clean up any existing test data
        cleanup_test_data()
        
        print("Initializing point configurations...")
        PointConfig.initialize_defaults()
        
        print("Creating test users...")
        users = create_test_users(15)
        users.extend([admin, nicolas])  # Add admin and Nicolas to users list
        
        print("Creating commission partners...")
        partners = create_commission_partners(users, 7)
        
        print("Creating test companies...")
        companies = create_companies(users, 30)
        
        print("Creating test commissions...")
        commissions = create_commissions(partners, companies)
        
        print("Creating link click data...")
        clicks = create_link_clicks(users, 200)
        
        print("Test data generation complete!")
        print(f"Created:")
        print(f"- {len(users)} users")
        print(f"- {len(partners)} commission partners")
        print(f"- {len(companies)} companies")
        print(f"- {len(commissions)} commissions")
        print(f"- {len(clicks)} link clicks")

if __name__ == '__main__':
    main() 
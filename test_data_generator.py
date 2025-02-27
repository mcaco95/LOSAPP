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

fake = Faker()

def cleanup_test_data():
    """Remove all test data before generating new data"""
    print("Cleaning up old test data...")
    
    # Get test user IDs (users with test password)
    test_users = User.query.filter_by(password_hash=generate_password_hash('test123')).all()
    test_user_ids = [u.id for u in test_users]
    
    if test_user_ids:
        # Delete related data
        LinkClick.query.filter(LinkClick.user_id.in_(test_user_ids)).delete(synchronize_session=False)
        
        # Get commission partner IDs
        test_partners = CommissionPartner.query.filter(CommissionPartner.user_id.in_(test_user_ids)).all()
        test_partner_ids = [p.id for p in test_partners]
        
        if test_partner_ids:
            Commission.query.filter(Commission.partner_id.in_(test_partner_ids)).delete(synchronize_session=False)
            CommissionPartner.query.filter(CommissionPartner.id.in_(test_partner_ids)).delete(synchronize_session=False)
        
        # Delete companies
        Company.query.filter(Company.user_id.in_(test_user_ids)).delete(synchronize_session=False)
        
        # Finally delete test users
        User.query.filter(User.id.in_(test_user_ids)).delete(synchronize_session=False)
    
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

def create_commission_partners(users, num_partners=5):
    """Create commission partners with various configurations and referral relationships"""
    partners = []
    
    # Create the first partner (Nicolas) as the root partner
    root_user = users[0]
    root_user.name = "Nicolas Morales"  # Set specific name for root partner
    root_user.email = "nicolas@logisticonesource.com"
    root_partner = CommissionPartner(
        user_id=root_user.id,
        commission_tier='standard',
        metadata={
            'custom_rates': {
                'professional_first_2_years': 0.10,
                'professional_after_2_years': 0.025,
                'standard_first_2_years': 0.10,
                'standard_after_2_years': 0.025
            },
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
    remaining_users = users[1:num_partners]
    for i, user in enumerate(remaining_users):
        # Alternate between root partner and other partners as referrers
        referrer = root_partner if i % 2 == 0 else random.choice(partners[1:] or [root_partner])
        
        partner = CommissionPartner(
            user_id=user.id,
            commission_tier='standard',
            referrer_id=referrer.id,  # Set the referrer
            metadata={
                'custom_rates': {
                    'professional_first_2_years': 0.10,
                    'professional_after_2_years': 0.025,
                    'standard_first_2_years': 0.10,
                    'standard_after_2_years': 0.025
                },
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
    print(f"Root Partner: {root_user.name} (ID: {root_partner.id})")
    for partner in partners[1:]:
        referrer_name = CommissionPartner.query.get(partner.referrer_id).user.name
        print(f"- {partner.user.name} (ID: {partner.id}) → Referred by: {referrer_name}")
    
    return partners

def create_companies(users, num_companies=20):
    """Create test companies with various statuses"""
    companies = []
    statuses = ['lead', 'demo_scheduled', 'demo_completed', 'client_signed', 'renewed']
    service_types = ['professional', 'standard']
    contact_times = ['morning', 'afternoon', 'evening']
    
    for _ in range(num_companies):
        user = random.choice(users)
        metadata = {
            'industry': fake.job()[:50],
            'size': random.choice(['small', 'medium', 'large']),
            'region': fake.state(),
            'status_history': [{
                'from': None,
                'to': random.choice(statuses),
                'timestamp': datetime.utcnow().isoformat(),
                'points_awarded': 0
            }]
        }
        
        company = Company(
            name=fake.company()[:100],
            user_id=user.id,
            status=random.choice(statuses),
            metadata=metadata,
            contact_name=fake.name()[:100],
            email=fake.email()[:120],
            phone=fake.phone_number()[:20],
            service_type=random.choice(service_types),
            preferred_contact_time=random.choice(contact_times),
            additional_info=fake.text(max_nb_chars=200)
        )
        companies.append(company)
        db.session.add(company)
    
    db.session.commit()
    return companies

def create_commissions(partners, companies):
    """Create test commissions with various scenarios and statuses"""
    commissions = []
    
    for company in companies:
        if company.status in ['client_signed', 'renewed']:
            partner = random.choice(partners)
            
            # Create initial commission
            initial_amount = Commission.calculate_commission(
                partner_id=partner.id,
                company_id=company.id,
                service_type=company.service_type,
                is_initial_month=True,
                month_number=1
            )
            
            commission = Commission(
                partner_id=partner.id,
                company_id=company.id,
                amount=initial_amount,
                service_type=company.service_type,
                is_initial_month=True,
                month_number=1,
                status=random.choice(['pending', 'paid']),  # Mix of pending and paid
                metadata={}
            )
            commissions.append(commission)
            db.session.add(commission)
            
            # Create recurring commissions across different months/years
            for month in range(2, random.randint(3, 36)):  # Up to 3 years
                recurring_amount = Commission.calculate_commission(
                    partner_id=partner.id,
                    company_id=company.id,
                    service_type=company.service_type,
                    is_initial_month=False,
                    month_number=month
                )
                
                commission = Commission(
                    partner_id=partner.id,
                    company_id=company.id,
                    amount=recurring_amount,
                    service_type=company.service_type,
                    is_initial_month=False,
                    month_number=month,
                    status=random.choice(['pending', 'paid']),  # Mix of pending and paid
                    metadata={}
                )
                commissions.append(commission)
                db.session.add(commission)
                
                # Create network commissions for referrer if exists
                if partner.referrer_id:
                    network_amount = recurring_amount * 0.025  # 2.5% network commission
                    network_commission = Commission(
                        partner_id=partner.referrer_id,
                        company_id=company.id,
                        amount=network_amount,
                        service_type=company.service_type,
                        is_initial_month=False,
                        month_number=month,
                        status=random.choice(['pending', 'paid']),
                        metadata={'network_commission': True}
                    )
                    commissions.append(network_commission)
                    db.session.add(network_commission)
    
    db.session.commit()
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

def main():
    """Main function to generate all test data"""
    app = create_app()
    with app.app_context():
        print("Starting test data generation...")
        
        # First, clean up any existing test data
        cleanup_test_data()
        
        print("Initializing point configurations...")
        PointConfig.initialize_defaults()
        
        print("Creating test users...")
        users = create_test_users(15)
        
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
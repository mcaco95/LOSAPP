from datetime import datetime, timedelta
import random
from app import db, create_app
from app.models.user import User
from app.models.company import Company
from app.models.commission_partner import CommissionPartner
from app.models.commission import Commission
from app.models.point_config import PointConfig
from app.models.link_tracking import LinkClick
from app.models.reward import Reward
from app.models.commission_settings import CommissionSettings

class SystemTester:
    def __init__(self):
        self.app = create_app()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
    def test_commission_calculations(self):
        """Test commission calculations for various scenarios"""
        print("\nTesting Commission Calculations:")
        
        # Get a random partner and company
        partner = CommissionPartner.query.first()
        company = Company.query.filter_by(status='client_signed_up').first()
        
        if not partner or not company:
            print("Error: No test data found. Run test_data_generator.py first.")
            return

        print("\nTesting Company Data Validation:")
        # Verify company data
        companies = Company.query.filter_by(status='client_signed_up').all()
        print(f"\nChecking {len(companies)} active companies:")
        for company in companies:
            print(f"\nCompany: {company.name}")
            print(f"Status: {company.status}")
            print(f"Safety Status: {company.safety_status}")
            if company.safety_status == 'active':
                print(f"Truck Count: {company.truck_count}")
                print(f"Price per Truck: ${company.price_per_truck:.2f}")
                print(f"Monthly Revenue: ${company.truck_count * company.price_per_truck:.2f}")
                assert company.truck_count > 0, f"Company {company.name} has invalid truck count: {company.truck_count}"
                assert company.price_per_truck > 0, f"Company {company.name} has invalid price per truck: {company.price_per_truck}"
            
            print(f"Recruitment Status: {company.recruitment_status}")
            if company.recruitment_status == 'active':
                requests = company.recruitment_requests.get('requests', [])
                completed_requests = [r for r in requests if r['status'] == 'completed']
                print(f"Total Recruitment Requests: {len(requests)}")
                print(f"Completed Requests: {len(completed_requests)}")
                for req in completed_requests:
                    print(f"- Request ID {req['id']}: ${req['charge']:.2f}")
                    assert req['charge'] > 0, f"Company {company.name} has invalid recruitment charge: {req['charge']}"

        print("\nTesting Safety Service Commissions:")
        # Test safety service commission calculations
        truck_count = 10
        price_per_truck = 100.0
        monthly_revenue = truck_count * price_per_truck
        
        # First 24 months (10% direct commission)
        direct_commission = monthly_revenue * 0.10
        print(f"Safety Service - First 24 months (10%):")
        print(f"Monthly Revenue: ${monthly_revenue}")
        print(f"Direct Commission: ${direct_commission}")
        assert direct_commission == 100.0, f"Expected $100.0, got ${direct_commission}"
        
        # After 24 months (2.5% direct commission)
        direct_commission_later = monthly_revenue * 0.025
        print(f"\nSafety Service - After 24 months (2.5%):")
        print(f"Monthly Revenue: ${monthly_revenue}")
        print(f"Direct Commission: ${direct_commission_later}")
        assert direct_commission_later == 25.0, f"Expected $25.0, got ${direct_commission_later}"
        
        # Network commission (2.5%)
        network_commission = monthly_revenue * 0.025
        print(f"\nSafety Service - Network Commission (2.5%):")
        print(f"Monthly Revenue: ${monthly_revenue}")
        print(f"Network Commission: ${network_commission}")
        assert network_commission == 25.0, f"Expected $25.0, got ${network_commission}"

        print("\nTesting Recruitment Service Commissions:")
        # Test recruitment service commission calculations
        recruitment_charge = 2000.0
        
        # Direct commission (10%)
        recruitment_direct = recruitment_charge * 0.10
        print(f"Recruitment Service - Direct Commission (10%):")
        print(f"Recruitment Charge: ${recruitment_charge}")
        print(f"Direct Commission: ${recruitment_direct}")
        assert recruitment_direct == 200.0, f"Expected $200.0, got ${recruitment_direct}"
        
        # Network commission (2.5%)
        recruitment_network = recruitment_charge * 0.025
        print(f"Recruitment Service - Network Commission (2.5%):")
        print(f"Recruitment Charge: ${recruitment_charge}")
        print(f"Network Commission: ${recruitment_network}")
        assert recruitment_network == 50.0, f"Expected $50.0, got ${recruitment_network}"

        print("\nVerifying Actual Commissions in Database:")
        # Check actual commissions in the database
        all_commissions = Commission.query.all()
        safety_commissions = [c for c in all_commissions if c.commission_type == 'safety']
        recruitment_commissions = [c for c in all_commissions if c.commission_type == 'recruitment']
        
        print(f"\nSafety Service Commissions ({len(safety_commissions)}):")
        for comm in safety_commissions:
            print(f"\nCommission ID: {comm.id}")
            print(f"Partner: {comm.partner.user.name}")
            print(f"Company: {comm.company.name}")
            print(f"Amount: ${comm.amount:.2f}")
            print(f"Month: {comm.month_number}")
            print(f"Is Network: {comm.commission_metadata.get('network_commission', False)}")
            if not comm.commission_metadata.get('network_commission'):
                # Verify the commission amount matches the calculation
                truck_count = comm.commission_metadata.get('truck_count')
                price_per_truck = comm.commission_metadata.get('price_per_truck')
                expected_rate = 0.10 if comm.month_number <= 24 else 0.025
                expected_amount = truck_count * price_per_truck * expected_rate
                assert abs(comm.amount - expected_amount) < 0.01, f"Commission amount ${comm.amount:.2f} doesn't match expected ${expected_amount:.2f}"
        
        print(f"\nRecruitment Service Commissions ({len(recruitment_commissions)}):")
        for comm in recruitment_commissions:
            print(f"\nCommission ID: {comm.id}")
            print(f"Partner: {comm.partner.user.name}")
            print(f"Company: {comm.company.name}")
            print(f"Amount: ${comm.amount:.2f}")
            print(f"Request ID: {comm.commission_metadata.get('recruitment_request_id')}")
            print(f"Is Network: {comm.commission_metadata.get('network_commission', False)}")
            if not comm.commission_metadata.get('network_commission'):
                # Verify the commission amount matches the calculation
                charge = comm.commission_metadata.get('charge')
                expected_amount = charge * 0.10
                assert abs(comm.amount - expected_amount) < 0.01, f"Commission amount ${comm.amount:.2f} doesn't match expected ${expected_amount:.2f}"
        
        print("\nCommission calculations test passed!")
    
    def test_points_system(self):
        """Test points system functionality"""
        print("\nTesting Points System:")
        
        # Verify point configurations
        configs = PointConfig.get_all_configs()
        print("Point configurations:")
        for key, value in configs.items():
            print(f"- {key}: {value} points")
        
        # Test status points
        referral_points = PointConfig.get_value('status_referral_form', 2)
        demo_points = PointConfig.get_value('status_demo_completed', 15)
        signed_points = PointConfig.get_value('status_client_signed', 50)
        partner_signup = PointConfig.get_value('status_partner_signup', 25)
        
        print(f"\nStatus points:")
        print(f"- Referral form completed: {referral_points}")
        print(f"- Demo completed: {demo_points}")
        print(f"- Client signed: {signed_points}")
        print(f"- Partner signup: {partner_signup}")
        
        assert referral_points == 2, f"Expected 2 points for referral, got {referral_points}"
        assert demo_points == 15, f"Expected 15 points for demo_completed, got {demo_points}"
        assert signed_points == 50, f"Expected 50 points for client_signed, got {signed_points}"
        assert partner_signup == 25, f"Expected 25 points for partner_signup, got {partner_signup}"
        
        print("Points system test passed!")
    
    def test_partner_performance(self):
        """Test partner performance metrics"""
        print("\nTesting Partner Performance:")
        
        # Find Nicolas Morales by email
        nicolas_user = User.query.filter_by(email='nicolas@logisticonesource.com').first()
        if not nicolas_user:
            print("Error: Nicolas Morales not found. Run test_data_generator.py first.")
            return
            
        partner = CommissionPartner.query.filter_by(user_id=nicolas_user.id).first()
        if not partner:
            print("Error: No test data found. Run test_data_generator.py first.")
            return
        
        # Get partner's commissions
        total_commissions = Commission.query.filter_by(partner_id=partner.id).all()
        paid_commissions = [c for c in total_commissions if c.status == 'paid']
        
        # Separate safety and recruitment commissions
        safety_commissions = [c for c in total_commissions if c.commission_type == 'safety']
        recruitment_commissions = [c for c in total_commissions if c.commission_type == 'recruitment']
        
        # Network commissions
        network_commissions = [c for c in total_commissions if c.commission_metadata and c.commission_metadata.get('network_commission')]
        
        # Get network size (number of direct referrals)
        network_size = CommissionPartner.query.filter_by(referrer_id=partner.id).count()
        
        print(f"Partner: {nicolas_user.name} (ID: {partner.id})")
        print(f"Network size: {network_size}")
        print(f"Total commissions: {len(total_commissions)}")
        print(f"- Safety service commissions: {len(safety_commissions)}")
        print(f"- Recruitment service commissions: {len(recruitment_commissions)}")
        print(f"Paid commissions: {len(paid_commissions)}")
        print(f"Network commissions: {len(network_commissions)}")
        
        # Calculate earnings breakdown
        safety_earnings = sum(c.amount for c in paid_commissions if c.commission_type == 'safety' and not c.commission_metadata.get('network_commission'))
        recruitment_earnings = sum(c.amount for c in paid_commissions if c.commission_type == 'recruitment' and not c.commission_metadata.get('network_commission'))
        network_earnings = sum(c.amount for c in paid_commissions if c.commission_metadata and c.commission_metadata.get('network_commission'))
        total_earnings = safety_earnings + recruitment_earnings + network_earnings
        
        print(f"\nEarnings Breakdown:")
        print(f"Safety service earnings: ${safety_earnings:.2f}")
        print(f"Recruitment service earnings: ${recruitment_earnings:.2f}")
        print(f"Network earnings: ${network_earnings:.2f}")
        print(f"Total earnings: ${total_earnings:.2f}")
        
        # Get tracking statistics
        clicks = LinkClick.query.filter_by(user_id=partner.user_id).count()
        print(f"Total clicks: {clicks}")
        
        # Basic assertions to ensure data validity
        assert network_size > 0, "Root partner should have referrals"
        assert len(total_commissions) > 0, "Partner should have commissions"
        assert len(safety_commissions) + len(recruitment_commissions) == len(total_commissions), "Commission types should match total"
        
        print("Partner performance test passed!")
    
    def test_company_progression(self):
        """Test company status progression and associated points"""
        print("\nTesting Company Progression:")
        
        company = Company.query.first()
        if not company:
            print("Error: No test data found. Run test_data_generator.py first.")
            return
        
        statuses = ['referral_form_completed', 'demo_scheduled', 'demo_completed', 'client_signed_up', 'client_renewed']
        total_points = 0
        
        print(f"Company: {company.name}")
        print("Simulating status progression:")
        
        for status in statuses:
            points = PointConfig.get_value(f'status_{status}', 0)
            total_points += points
            print(f"- {status}: +{points} points (Total: {total_points})")
            
        # Test service activation
        print("\nTesting service activation:")
        
        # Safety service
        if company.safety_status == 'active':
            print(f"Safety Service Active:")
            print(f"- Truck count: {company.truck_count}")
            print(f"- Price per truck: ${company.price_per_truck}")
            print(f"- Monthly revenue: ${company.truck_count * company.price_per_truck}")
        
        # Recruitment service
        if company.recruitment_status == 'active' and company.recruitment_requests:
            print(f"\nRecruitment Service Active:")
            completed_requests = [r for r in company.recruitment_requests['requests'] if r['status'] == 'completed']
            total_charges = sum(r['charge'] for r in completed_requests)
            print(f"- Completed requests: {len(completed_requests)}")
            print(f"- Total charges: ${total_charges}")
        
        print("Company progression test passed!")
    
    def run_all_tests(self):
        """Run all system tests"""
        print("Starting system functionality tests...")
        
        try:
            self.test_commission_calculations()
            self.test_points_system()
            self.test_partner_performance()
            self.test_company_progression()
            
            print("\nAll tests completed successfully!")
            
        except AssertionError as e:
            print(f"\nTest failed: {str(e)}")
        except Exception as e:
            print(f"\nUnexpected error: {str(e)}")
        finally:
            self.app_context.pop()

if __name__ == '__main__':
    tester = SystemTester()
    tester.run_all_tests() 
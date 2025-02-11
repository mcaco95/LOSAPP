import pytest
from app import create_app, db
from app.models.user import User
from app.models.company import Company
from app.models.point_config import PointConfig
from app.models.reward import Reward, UserReward
from app.models.link_tracking import LinkClick
from app.services.points import PointService
from app.services.company import CompanyService
from app.services.reward import RewardService

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://localhost/los_test'
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def test_user(app):
    user = User(email='test@example.com', name='Test User')
    user.set_password('password123')
    db.session.add(user)
    db.session.commit()
    return user

def test_point_config_initialization(app):
    """Test point configuration initialization"""
    PointService.initialize_point_system()
    
    configs = PointConfig.get_all_configs()
    assert configs['click'] == 1
    assert configs['unique_click'] == 5
    assert configs['status_completed_form'] == 10
    assert configs['status_meeting_scheduled'] == 20
    assert configs['status_sold'] == 50
    assert configs['status_paid'] == 100

def test_reward_initialization(app):
    """Test reward system initialization"""
    RewardService.initialize_reward_system()
    
    rewards = Reward.query.all()
    assert len(rewards) == 3  # Bronze, Silver, Gold
    
    bronze = Reward.query.filter_by(name='Bronze Badge').first()
    assert bronze.points_required == 100
    
    gold = Reward.query.filter_by(name='Gold Badge').first()
    assert gold.points_required == 1000

def test_click_points(app, test_user):
    """Test points awarded for clicks"""
    PointService.initialize_point_system()
    
    # Regular click
    click = LinkClick(
        user_id=test_user.id,
        visitor_ip='127.0.0.1',
        user_agent='Mozilla/5.0'
    )
    db.session.add(click)
    click.set_device_type()
    db.session.commit()
    
    assert test_user.points == 1  # Regular click point
    
    # Another click from same IP (non-unique)
    click2 = LinkClick(
        user_id=test_user.id,
        visitor_ip='127.0.0.1',
        user_agent='Mozilla/5.0'
    )
    db.session.add(click2)
    click2.set_device_type()
    db.session.commit()
    
    assert test_user.points == 2  # Only regular click point added

def test_company_status_points(app, test_user):
    """Test points awarded for company status changes"""
    PointService.initialize_point_system()
    
    # Create company
    company = CompanyService.create_company(
        name='Test Company',
        user_id=test_user.id
    )
    
    # Update status to completed_form
    CompanyService.update_status(company.id, 'completed_form')
    assert test_user.points == 10
    
    # Update status to meeting_scheduled
    CompanyService.update_status(company.id, 'meeting_scheduled')
    assert test_user.points == 30  # 10 + 20
    
    # Update status to sold
    CompanyService.update_status(company.id, 'sold')
    assert test_user.points == 80  # 30 + 50

def test_reward_redemption(app, test_user):
    """Test reward redemption"""
    RewardService.initialize_reward_system()
    
    # Add points to user
    test_user.add_points(150, "Test points")
    
    # Get available rewards
    rewards = RewardService.get_available_rewards(test_user.id)
    assert len(rewards) == 1  # Should only see Bronze Badge (100 points)
    
    # Redeem reward
    bronze_badge = Reward.query.filter_by(name='Bronze Badge').first()
    result = RewardService.award_reward(test_user.id, bronze_badge.id)
    
    assert test_user.points == 50  # 150 - 100
    assert test_user.rewards_earned.count() == 1

def test_points_summary(app, test_user):
    """Test points summary generation"""
    PointService.initialize_point_system()
    RewardService.initialize_reward_system()
    
    # Add various points
    test_user.add_points(5, "Unique click")
    test_user.add_points(1, "Regular click")
    test_user.add_points(20, "Meeting scheduled")
    
    summary = PointService.get_user_points_summary(test_user.id)
    
    assert summary['total_points'] == 26
    assert len(summary['points_by_category']) == 3
    assert len(summary['recent_activity']) == 3
    assert len(summary['available_rewards']) == 0  # Not enough for Bronze Badge

def test_company_statistics(app, test_user):
    """Test company statistics"""
    # Create multiple companies
    company1 = CompanyService.create_company('Company 1', test_user.id)
    company2 = CompanyService.create_company('Company 2', test_user.id)
    
    CompanyService.update_status(company1.id, 'completed_form')
    CompanyService.update_status(company2.id, 'meeting_scheduled')
    
    stats = CompanyService.get_company_statistics()
    
    assert stats['total_companies'] == 2
    assert len(stats['by_status']) == 2
    assert len(stats['top_referrers']) == 1
    assert stats['top_referrers'][0]['company_count'] == 2

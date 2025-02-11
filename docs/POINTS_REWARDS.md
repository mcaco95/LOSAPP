# Points and Rewards System

## Overview

The Points and Rewards system allows sales representatives to earn points for various activities and redeem them for rewards. Points are awarded automatically for:

- Regular clicks on referral links
- Unique clicks (first time from an IP address)
- Company status changes (form completion, meeting scheduled, deal closed, etc.)

## Setup

1. Run the setup script:
```bash
python setup_points_rewards.py
```

This will:
- Run database migrations
- Initialize default point values
- Create default rewards

## Point Configuration

Default point values:
- Regular click: 1 point
- Unique click: 5 points
- Form completed: 10 points
- Meeting scheduled: 20 points
- Deal closed: 50 points
- Commission paid: 100 points

These values can be customized through the admin API.

## API Endpoints

### Points Management

#### Get Point Configuration (Admin)
```
GET /api/v1/points-rewards/points/config
```
Returns current point values for all actions.

#### Update Point Configuration (Admin)
```
PUT /api/v1/points-rewards/points/config
Content-Type: application/json

{
    "click": 2,
    "unique_click": 10,
    "status_completed_form": 15
    // ... other point values
}
```

#### Get User Points Summary
```
GET /api/v1/points-rewards/points/summary
```
Returns:
- Total points
- Points by category
- Recent activity
- Available rewards

### Rewards Management

#### List Available Rewards
```
GET /api/v1/points-rewards/rewards
```
Optional query parameter `user_filter=true` to show only rewards available to the current user.

#### Create Reward (Admin)
```
POST /api/v1/points-rewards/rewards
Content-Type: application/json

{
    "name": "Gold Badge",
    "description": "Digital badge for reaching gold tier",
    "points_required": 1000
}
```

#### Update Reward (Admin)
```
PUT /api/v1/points-rewards/rewards/{reward_id}
Content-Type: application/json

{
    "name": "Updated Name",
    "points_required": 1500,
    "is_active": true
}
```

#### Redeem Reward
```
POST /api/v1/points-rewards/rewards/{reward_id}/redeem
```

#### Get User's Earned Rewards
```
GET /api/v1/points-rewards/user/rewards
```

### Company Management

#### Create Company Referral
```
POST /api/v1/company/companies
Content-Type: application/json

{
    "name": "Company Name"
}
```

#### Update Company Status (Admin)
```
PUT /api/v1/company/companies/{company_id}/status
Content-Type: application/json

{
    "status": "meeting_scheduled"
}
```

#### List User's Companies
```
GET /api/v1/company/user/companies
```
Optional query parameter `status[]` to filter by status.

#### Get Company Statistics (Admin)
```
GET /api/v1/company/companies/stats
```

## Database Schema

### User Extensions
- `points`: Integer (Total points)
- `points_metadata`: JSONB (Points history and details)

### Company
- `name`: String
- `status`: String (new, completed_form, meeting_scheduled, sold, paid)
- `user_id`: Integer (FK to User)
- `payment_date`: DateTime
- `metadata`: JSONB

### PointConfig
- `key`: String (action identifier)
- `value`: Integer (points awarded)
- `metadata`: JSONB

### Reward
- `name`: String
- `description`: Text
- `points_required`: Integer
- `is_active`: Boolean
- `metadata`: JSONB

### UserReward
- `user_id`: Integer (FK to User)
- `reward_id`: Integer (FK to Reward)
- `earned_at`: DateTime
- `metadata`: JSONB

## Best Practices

1. Point Awards
   - Points are awarded automatically for clicks and status changes
   - All point transactions are recorded in user's points_metadata
   - Failed point awards are logged but don't block the main operation

2. Rewards
   - Keep reward point requirements achievable
   - Use the metadata field for additional reward details
   - Deactivate rewards instead of deleting them

3. Companies
   - Always update company status through the API to ensure points are awarded
   - Use metadata for additional tracking information
   - Status changes are recorded in company metadata

## Future Enhancements

1. Points System
   - Point expiration
   - Bonus point events
   - Point multipliers for special campaigns

2. Rewards System
   - Physical reward fulfillment tracking
   - Reward categories
   - Limited quantity rewards

3. Analytics
   - Point earning trends
   - Popular rewards
   - User engagement metrics

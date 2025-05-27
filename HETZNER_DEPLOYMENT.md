# Hetzner Server Deployment Guide for LOS App

This guide will help you deploy your LOS application to your Hetzner server.

## Server Information
- **Current Server**: CPX11 (5.161.185.159) - Ashburn, VA
- **Specs**: 2 vCPU, 2GB RAM, 40GB Disk
- **Cost**: $4.99/month
- **OS**: Ubuntu 22.04 (ubuntu-2gb-ash-1)

## Pre-Deployment Checklist

### 1. SSH Access to Your Server
```bash
# Connect to your Hetzner server
ssh root@5.161.185.159
# or if you have a different user:
ssh your-username@5.161.185.159
```

### 2. Check Current Server Status
```bash
# Check what's currently running
sudo netstat -tulpn | grep LISTEN
docker ps 2>/dev/null || echo "Docker not installed"
systemctl status nginx 2>/dev/null || echo "Nginx not running"
```

## Installation Steps

### 1. Install Docker (if not already installed)
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group (if not root)
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

### 2. Deploy Your Application

#### Option A: Using Git (Recommended)
```bash
# Clone your repository
git clone https://github.com/your-username/LOSAPP-6.0.git
cd LOSAPP-6.0

# Or if you already have it, update:
cd LOSAPP-6.0
git pull
```

#### Option B: Upload from Windows
```cmd
# From your Windows machine, upload the project
scp -r C:\Users\Usuario\Desktop\LOSAPP-6.0 root@5.161.185.159:/root/
```

### 3. Configure Environment
```bash
# Navigate to project directory
cd LOSAPP-6.0

# Create .env file
cp env.example .env
nano .env
```

**Update your .env file with these values:**
```env
# Database Configuration
POSTGRES_PASSWORD=31012662
DATABASE_URL=postgresql://postgres:31012662@postgres:5432/los_referral

# Flask configuration
FLASK_APP=app
FLASK_ENV=production

# Security
SECRET_KEY=here-is-a-secure-key-8a4c6d3e3f1b2a5d8c4a7f3b6a5d2c6f

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# Webhook Configuration (UPDATE THIS)
TWILIO_WEBHOOK_BASE_URL=http://5.161.185.159:8000

# All your existing API keys...
TWILIO_ACCOUNT_SID=ACe9000a728c60e9efd3d522fd4e53a8a6
TWILIO_AUTH_TOKEN=4ef86bad4ac26cdb362c3745ea45c0f6
TWILIO_PHONE_NUMBER=+17756183039
TWILIO_API_KEY=SKd4a225be4dd3344a13afb9b83b18300c
TWILIO_API_SECRET=2zxCAyxRIJsqgbB35DzzTNRFiRBpS36K
TWILIO_TWIML_APP_SID=APe42f1e65039e9d88186dc6bb7896a41f

SAMSARA_API_KEY=fpzgWkFgRZfmygr7yFAGSWnMaaXa3G
SENDGRID_API_KEY=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
SENDGRID_FROM_EMAIL=simon@logisticsonesource.com
```

### 4. Deploy the Application
```bash
# Make deployment script executable
chmod +x deploy.sh

# Deploy
./deploy.sh deploy
```

### 5. Configure Firewall
```bash
# Allow necessary ports
sudo ufw allow ssh
sudo ufw allow 8000
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable

# Check firewall status
sudo ufw status
```

## Port Configuration

Your application will use these ports:
- **8000**: Flask application (main app)
- **5432**: PostgreSQL (internal Docker network)
- **6379**: Redis (internal Docker network)
- **80/443**: Nginx (if using production profile)

## Database Migration

### Option 1: Start Fresh
```bash
# Deploy will create a new database
./deploy.sh deploy

# Setup admin user
docker-compose exec web flask setup-admin
```

### Option 2: Import Existing Data
```bash
# Upload your database backup to the server
scp database_backup.sql root@5.161.185.159:/root/LOSAPP-6.0/

# Import the data
docker-compose exec -T postgres psql -U postgres -d los_referral < database_backup.sql
```

## Access Your Application

After deployment:
- **Application**: http://5.161.185.159:8000
- **Health Check**: http://5.161.185.159:8000/health

## Update Webhook URLs

### 1. Twilio Console
Update your webhook URLs to:
- Voice: `http://5.161.185.159:8000/operations/webhooks/voice`
- Status: `http://5.161.185.159:8000/operations/webhooks/status`

### 2. Test Webhooks
```bash
# Test webhook endpoint
curl http://5.161.185.159:8000/health
```

## Monitoring and Maintenance

### Check Application Status
```bash
# Check running containers
docker-compose ps

# View logs
docker-compose logs -f

# Check specific service logs
docker-compose logs web
docker-compose logs postgres
```

### Backup Database
```bash
# Create backup
./deploy.sh backup

# Or manually
docker-compose exec postgres pg_dump -U postgres los_referral > backup_$(date +%Y%m%d).sql
```

### Update Application
```bash
# Pull latest changes
git pull

# Rebuild and restart
./deploy.sh update
```

## SSL Setup (Optional)

If you want to use a domain name:

### 1. Point Domain to Server
Point your domain A record to: `5.161.185.159`

### 2. Get SSL Certificate
```bash
# Install certbot
sudo apt install certbot

# Get certificate
sudo certbot certonly --standalone -d your-domain.com

# Create SSL directory
mkdir -p ssl
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/key.pem
sudo chown $USER:$USER ssl/*
```

### 3. Deploy with Nginx
```bash
# Update nginx.conf with your domain
nano nginx.conf
# Replace server_name _; with server_name your-domain.com;

# Deploy with production profile
docker-compose --profile production up -d
```

## Troubleshooting

### Common Issues

1. **Port 8000 already in use**
```bash
sudo netstat -tulpn | grep :8000
sudo kill -9 <PID>
```

2. **Docker permission denied**
```bash
sudo chown -R $USER:$USER /var/run/docker.sock
```

3. **Database connection issues**
```bash
docker-compose logs postgres
docker-compose restart postgres
```

### Performance Optimization

For your 2GB RAM server:
```bash
# Edit docker-compose.yml to limit memory usage
nano docker-compose.yml
```

Add memory limits:
```yaml
services:
  web:
    mem_limit: 512m
  postgres:
    mem_limit: 256m
  redis:
    mem_limit: 128m
```

## Cost Comparison

- **Render**: $20-100+/month
- **Hetzner CPX11**: $4.99/month
- **Savings**: 75-95% cost reduction! 💰

## Next Steps

1. **Deploy**: Run `./deploy.sh deploy`
2. **Test**: Access http://5.161.185.159:8000
3. **Configure**: Update Twilio webhooks
4. **Monitor**: Check logs and performance
5. **Backup**: Set up automated backups

Your LOS application will be running cost-effectively on Hetzner! 🚀 
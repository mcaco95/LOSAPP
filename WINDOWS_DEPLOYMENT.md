# Windows Docker Deployment Guide for LOS App

This guide will help you deploy your LOS (Logistics One Source) application on Windows using Docker Desktop, and then transfer it to your Hetzner server.

## Prerequisites for Windows Development

### 1. Install Docker Desktop
1. Download Docker Desktop from [https://www.docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
2. Install and restart your computer
3. Enable WSL 2 if prompted
4. Start Docker Desktop

### 2. Verify Installation
Open PowerShell or Command Prompt and run:
```cmd
docker --version
docker-compose --version
```

## Quick Start on Windows

### 1. Setup Environment
```cmd
# Navigate to your project directory
cd C:\Users\Usuario\Desktop\LOSAPP-6.0

# Copy environment template
copy env.example .env

# Edit the .env file with your actual values
notepad .env
```

### 2. Deploy Locally
```cmd
# Run the Windows deployment script
deploy.bat deploy

# Or manually:
docker-compose build --no-cache
docker-compose up -d
```

### 3. Access Your Application
- **Local Development**: http://localhost:8000
- **Health Check**: http://localhost:8000/health

## Windows Deployment Commands

```cmd
# Deploy application
deploy.bat deploy

# Stop all services
deploy.bat stop

# Restart services
deploy.bat restart

# View logs
deploy.bat logs

# Check service status
deploy.bat status

# Update application
deploy.bat update

# Backup database
deploy.bat backup

# Show help
deploy.bat help
```

## Environment Variables Setup

Edit your `.env` file with these important values:

```env
# Database Configuration
POSTGRES_PASSWORD=your_secure_database_password

# Security
SECRET_KEY=your-very-secure-secret-key-change-this-to-something-random

# Email Configuration (Gmail example)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com

# OAuth Configuration
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Twilio Configuration
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=your-twilio-phone-number
TWILIO_WEBHOOK_BASE_URL=https://your-domain.com

# Samsara Configuration
SAMSARA_API_KEY=your-samsara-api-key
```

## Testing Locally on Windows

### 1. Build and Test
```cmd
# Build the application
docker-compose build

# Start services
docker-compose up -d

# Check if everything is running
docker-compose ps

# View logs
docker-compose logs -f web
```

### 2. Access Services
- **Web Application**: http://localhost:8000
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### 3. Test Database Connection
```cmd
# Access PostgreSQL
docker-compose exec postgres psql -U postgres -d los_referral

# Test Redis
docker-compose exec redis redis-cli ping
```

## Transferring to Hetzner Server

### 1. Prepare Your Hetzner Server

SSH into your Hetzner server and install Docker:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Logout and login again
```

### 2. Transfer Your Application

Option A: Using Git (Recommended)
```bash
# On your Hetzner server
git clone <your-repository-url>
cd LOSAPP-6.0
```

Option B: Using SCP from Windows
```cmd
# From your Windows machine
scp -r C:\Users\Usuario\Desktop\LOSAPP-6.0 user@your-server-ip:/home/user/
```

### 3. Deploy on Hetzner Server

```bash
# On your Hetzner server
cd LOSAPP-6.0

# Make deployment script executable
chmod +x deploy.sh

# Copy your .env file (or create new one)
cp env.example .env
nano .env  # Edit with your production values

# Deploy
./deploy.sh deploy
```

## Production Configuration

### 1. Update Environment Variables for Production

```env
# Update these for production
TWILIO_WEBHOOK_BASE_URL=https://your-actual-domain.com
SECRET_KEY=generate-a-new-secure-key-for-production
POSTGRES_PASSWORD=use-a-strong-production-password
```

### 2. SSL Setup (Optional)

For production with SSL:

```bash
# Install certbot
sudo apt install certbot

# Get SSL certificate
sudo certbot certonly --standalone -d your-domain.com

# Create SSL directory
mkdir -p ssl

# Copy certificates
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/key.pem
sudo chown $USER:$USER ssl/*

# Deploy with Nginx
docker-compose --profile production up -d
```

## Troubleshooting Windows Issues

### 1. Docker Desktop Issues
```cmd
# Restart Docker Desktop
# Check if WSL 2 is enabled
wsl --list --verbose

# Update WSL if needed
wsl --update
```

### 2. Port Conflicts
```cmd
# Check what's using port 8000
netstat -ano | findstr :8000

# Kill process if needed (replace PID)
taskkill /PID <process-id> /F
```

### 3. File Permission Issues
```cmd
# Run PowerShell as Administrator if needed
# Or use Docker Desktop's file sharing settings
```

### 4. Build Issues
```cmd
# Clear Docker cache
docker system prune -a

# Rebuild without cache
docker-compose build --no-cache
```

## Database Migration from Render

### 1. Export from Render
```bash
# On Render or using their CLI
pg_dump $DATABASE_URL > render_backup.sql
```

### 2. Import to Your New Setup
```cmd
# Copy backup file to your project directory
# Then import
docker-compose exec -T postgres psql -U postgres -d los_referral < render_backup.sql
```

## Monitoring and Logs

### Windows Development
```cmd
# View all logs
docker-compose logs

# View specific service
docker-compose logs web
docker-compose logs postgres

# Follow logs in real-time
docker-compose logs -f
```

### Production Server
```bash
# Use the deployment script
./deploy.sh logs

# Or directly
docker-compose logs -f
```

## Performance Tips

### 1. Windows Development
- Allocate more resources to Docker Desktop in settings
- Use WSL 2 backend for better performance
- Close unnecessary applications

### 2. Production Server
- Use the optimized gunicorn configuration
- Monitor resource usage with `htop`
- Set up log rotation

## Security Checklist

### Before Going to Production:
- [ ] Change all default passwords
- [ ] Use strong SECRET_KEY
- [ ] Update all API keys
- [ ] Set up firewall rules
- [ ] Enable SSL certificates
- [ ] Configure backup strategy
- [ ] Test all functionality

## Cost Savings vs Render

By moving to Hetzner, you'll save significantly:
- **Render**: $20-100+/month depending on usage
- **Hetzner**: $5-20/month for equivalent resources
- **Savings**: 60-80% cost reduction

## Next Steps

1. **Test locally on Windows** using `deploy.bat deploy`
2. **Set up your Hetzner server** with Docker
3. **Transfer your application** using Git
4. **Deploy on production** using `./deploy.sh deploy`
5. **Configure your domain** and SSL
6. **Monitor and maintain** your application

Your LOS application is now ready for cost-effective deployment on Hetzner! 🚀 
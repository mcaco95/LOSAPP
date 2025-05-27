# Docker Deployment Guide for LOS App

This guide will help you deploy your LOS (Logistics One Source) application on your Hetzner server using Docker.

## Prerequisites

### 1. Server Requirements
- Ubuntu 20.04+ or similar Linux distribution
- At least 2GB RAM (4GB recommended)
- 20GB+ disk space
- Docker and Docker Compose installed

### 2. Install Docker on Hetzner Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Logout and login again for group changes to take effect
```

## Quick Start

### 1. Clone and Setup

```bash
# Clone your repository
git clone <your-repo-url>
cd LOSAPP-6.0

# Make deployment script executable
chmod +x deploy.sh

# Run deployment
./deploy.sh deploy
```

### 2. Configure Environment Variables

The deployment script will create a `.env` file from the template. Edit it with your actual values:

```bash
nano .env
```

**Important variables to update:**
- `POSTGRES_PASSWORD`: Strong database password
- `SECRET_KEY`: Random secret key for Flask sessions
- `TWILIO_*`: Your Twilio credentials
- `MAIL_*`: Email configuration
- `GOOGLE_CLIENT_*`: OAuth credentials
- `SAMSARA_API_KEY`: Samsara integration key

### 3. Access Your Application

- **Development**: http://your-server-ip:8000
- **Production with SSL**: https://your-domain.com (after SSL setup)

## Services Included

The Docker setup includes:

1. **PostgreSQL Database** (port 5432)
   - Persistent data storage
   - Automatic health checks

2. **Redis Cache** (port 6379)
   - Session storage
   - Caching layer

3. **Flask Web Application** (port 8000)
   - Main application server
   - Gunicorn WSGI server

4. **Nginx Reverse Proxy** (ports 80/443) - Optional
   - SSL termination
   - Static file serving
   - Rate limiting

## Deployment Commands

```bash
# Deploy application
./deploy.sh deploy

# Stop all services
./deploy.sh stop

# Restart services
./deploy.sh restart

# View logs
./deploy.sh logs

# Check service status
./deploy.sh status

# Update application
./deploy.sh update

# Backup database
./deploy.sh backup

# Show help
./deploy.sh help
```

## Production Deployment with SSL

### 1. Domain Setup
Point your domain to your Hetzner server IP address.

### 2. SSL Certificate
Create SSL certificates (using Let's Encrypt):

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
```

### 3. Update Nginx Configuration
Edit `nginx.conf` and replace `server_name _;` with `server_name your-domain.com;`

### 4. Deploy with Nginx
```bash
docker-compose --profile production up -d
```

## Environment Variables Reference

### Database
```env
POSTGRES_PASSWORD=your_secure_database_password
```

### Security
```env
SECRET_KEY=your-very-secure-secret-key-change-this-to-something-random
```

### Email Configuration
```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com
```

### OAuth
```env
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

### Twilio
```env
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=your-twilio-phone-number
TWILIO_WEBHOOK_BASE_URL=https://your-domain.com
TWILIO_API_KEY=your-twilio-api-key
TWILIO_API_SECRET=your-twilio-api-secret
TWILIO_TWIML_APP_SID=your-twiml-app-sid
```

### Samsara
```env
SAMSARA_API_KEY=your-samsara-api-key
```

## Monitoring and Maintenance

### Health Checks
The application includes health check endpoints:
- `http://your-server:8000/health` - Application health

### Logs
```bash
# View all logs
docker-compose logs

# View specific service logs
docker-compose logs web
docker-compose logs postgres
docker-compose logs redis

# Follow logs in real-time
docker-compose logs -f
```

### Database Management
```bash
# Access PostgreSQL
docker-compose exec postgres psql -U postgres -d los_referral

# Create database backup
./deploy.sh backup

# Restore from backup
docker-compose exec -T postgres psql -U postgres -d los_referral < backup_file.sql
```

### Updates
```bash
# Update application code
git pull
docker-compose build --no-cache
docker-compose up -d

# Or use the script
./deploy.sh update
```

## Troubleshooting

### Common Issues

1. **Port conflicts**
   ```bash
   # Check what's using ports
   sudo netstat -tulpn | grep :8000
   sudo netstat -tulpn | grep :5432
   ```

2. **Permission issues**
   ```bash
   # Fix Docker permissions
   sudo chown -R $USER:$USER .
   ```

3. **Database connection issues**
   ```bash
   # Check database logs
   docker-compose logs postgres
   
   # Test database connection
   docker-compose exec postgres pg_isready -U postgres
   ```

4. **Memory issues**
   ```bash
   # Check system resources
   free -h
   df -h
   
   # Restart services if needed
   ./deploy.sh restart
   ```

### Performance Optimization

1. **Increase worker processes** (edit `gunicorn.conf.py`):
   ```python
   workers = multiprocessing.cpu_count() * 2 + 1
   ```

2. **Database optimization** (edit `docker-compose.yml`):
   ```yaml
   postgres:
     command: postgres -c shared_preload_libraries=pg_stat_statements -c max_connections=200
   ```

3. **Redis memory limit**:
   ```yaml
   redis:
     command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
   ```

## Security Considerations

1. **Firewall Setup**
   ```bash
   # Install UFW
   sudo ufw enable
   
   # Allow SSH
   sudo ufw allow ssh
   
   # Allow HTTP/HTTPS
   sudo ufw allow 80
   sudo ufw allow 443
   
   # Block direct access to application port
   sudo ufw deny 8000
   ```

2. **Regular Updates**
   ```bash
   # Update system packages
   sudo apt update && sudo apt upgrade -y
   
   # Update Docker images
   docker-compose pull
   docker-compose up -d
   ```

3. **Backup Strategy**
   ```bash
   # Setup automated backups (add to crontab)
   0 2 * * * /path/to/your/app/deploy.sh backup
   ```

## Cost Optimization Tips

1. **Use smaller Docker images** - Already implemented with Alpine Linux
2. **Optimize resource limits** in `docker-compose.yml`
3. **Regular cleanup**:
   ```bash
   # Remove unused Docker resources
   docker system prune -a
   ```

## Support

If you encounter issues:
1. Check the logs: `./deploy.sh logs`
2. Verify service status: `./deploy.sh status`
3. Check the health endpoint: `curl http://localhost:8000/health`
4. Review this documentation for troubleshooting steps

## Migration from Render

To migrate your data from Render:

1. **Export database from Render**
2. **Import to new PostgreSQL**:
   ```bash
   docker-compose exec -T postgres psql -U postgres -d los_referral < render_backup.sql
   ```
3. **Update environment variables** with new server details
4. **Test all functionality** before switching DNS

Your application should now be running efficiently on your Hetzner server with significant cost savings compared to Render! 
#!/bin/bash

# LOS App Deployment Script for Hetzner Server
# This script helps deploy the dockerized Flask application

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_status "Docker and Docker Compose are installed."
}

# Check if .env file exists
check_env_file() {
    if [ ! -f .env ]; then
        print_warning ".env file not found. Creating from template..."
        if [ -f env.example ]; then
            cp env.example .env
            print_warning "Please edit .env file with your actual configuration values."
            print_warning "Especially update: POSTGRES_PASSWORD, SECRET_KEY, and API keys."
            read -p "Press Enter after you've updated the .env file..."
        else
            print_error "env.example file not found. Please create .env file manually."
            exit 1
        fi
    else
        print_status ".env file found."
    fi
}

# Build and start services
deploy() {
    print_status "Building Docker images..."
    docker-compose build --no-cache
    
    print_status "Starting services..."
    docker-compose up -d
    
    print_status "Waiting for services to be ready..."
    sleep 30
    
    # Check if services are running
    if docker-compose ps | grep -q "Up"; then
        print_status "Services are running!"
        
        # Run database migrations
        print_status "Running database migrations..."
        docker-compose exec web flask db upgrade || print_warning "Migration failed or no migrations to run"
        
        # Setup admin user
        print_status "Setting up admin user..."
        docker-compose exec web flask setup-admin || print_warning "Admin setup failed or already exists"
        
        print_status "Deployment completed successfully!"
        print_status "Your application should be available at:"
        print_status "  - HTTP: http://localhost:8000"
        print_status "  - With Nginx: http://localhost (if using production profile)"
        
    else
        print_error "Some services failed to start. Check logs with: docker-compose logs"
        exit 1
    fi
}

# Stop services
stop() {
    print_status "Stopping services..."
    docker-compose down
    print_status "Services stopped."
}

# Show logs
logs() {
    docker-compose logs -f
}

# Show status
status() {
    docker-compose ps
}

# Update application
update() {
    print_status "Updating application..."
    git pull
    docker-compose build --no-cache
    docker-compose up -d
    print_status "Application updated!"
}

# Backup database
backup() {
    print_status "Creating database backup..."
    BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"
    docker-compose exec postgres pg_dump -U postgres los_referral > "$BACKUP_FILE"
    print_status "Database backup created: $BACKUP_FILE"
}

# Show help
show_help() {
    echo "LOS App Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  deploy    - Build and deploy the application"
    echo "  stop      - Stop all services"
    echo "  restart   - Restart all services"
    echo "  logs      - Show application logs"
    echo "  status    - Show service status"
    echo "  update    - Update application from git and redeploy"
    echo "  backup    - Create database backup"
    echo "  help      - Show this help message"
    echo ""
    echo "Production deployment with Nginx:"
    echo "  docker-compose --profile production up -d"
}

# Main script logic
case "${1:-deploy}" in
    deploy)
        check_docker
        check_env_file
        deploy
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 5
        check_docker
        deploy
        ;;
    logs)
        logs
        ;;
    status)
        status
        ;;
    update)
        update
        ;;
    backup)
        backup
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac 
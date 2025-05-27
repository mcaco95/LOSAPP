@echo off
REM LOS App Deployment Script for Windows
REM This script helps deploy the dockerized Flask application

setlocal enabledelayedexpansion

REM Colors for output (limited in Windows)
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "NC=[0m"

REM Function to print status
:print_status
echo %GREEN%[INFO]%NC% %~1
goto :eof

:print_warning
echo %YELLOW%[WARNING]%NC% %~1
goto :eof

:print_error
echo %RED%[ERROR]%NC% %~1
goto :eof

REM Check if Docker is installed
:check_docker
docker --version >nul 2>&1
if errorlevel 1 (
    call :print_error "Docker is not installed. Please install Docker Desktop first."
    exit /b 1
)

docker-compose --version >nul 2>&1
if errorlevel 1 (
    call :print_error "Docker Compose is not installed. Please install Docker Desktop with Compose."
    exit /b 1
)

call :print_status "Docker and Docker Compose are installed."
goto :eof

REM Check if .env file exists
:check_env_file
if not exist .env (
    call :print_warning ".env file not found. Creating from template..."
    if exist env.example (
        copy env.example .env >nul
        call :print_warning "Please edit .env file with your actual configuration values."
        call :print_warning "Especially update: POSTGRES_PASSWORD, SECRET_KEY, and API keys."
        pause
    ) else (
        call :print_error "env.example file not found. Please create .env file manually."
        exit /b 1
    )
) else (
    call :print_status ".env file found."
)
goto :eof

REM Build and start services
:deploy
call :print_status "Building Docker images..."
docker-compose build --no-cache
if errorlevel 1 (
    call :print_error "Failed to build Docker images."
    exit /b 1
)

call :print_status "Starting services..."
docker-compose up -d
if errorlevel 1 (
    call :print_error "Failed to start services."
    exit /b 1
)

call :print_status "Waiting for services to be ready..."
timeout /t 30 /nobreak >nul

REM Check if services are running
docker-compose ps | findstr "Up" >nul
if errorlevel 1 (
    call :print_error "Some services failed to start. Check logs with: docker-compose logs"
    exit /b 1
)

call :print_status "Services are running!"

REM Run database migrations
call :print_status "Running database migrations..."
docker-compose exec web flask db upgrade
if errorlevel 1 (
    call :print_warning "Migration failed or no migrations to run"
)

REM Setup admin user
call :print_status "Setting up admin user..."
docker-compose exec web flask setup-admin
if errorlevel 1 (
    call :print_warning "Admin setup failed or already exists"
)

call :print_status "Deployment completed successfully!"
call :print_status "Your application should be available at:"
call :print_status "  - HTTP: http://localhost:8000"
call :print_status "  - With Nginx: http://localhost (if using production profile)"
goto :eof

REM Stop services
:stop
call :print_status "Stopping services..."
docker-compose down
call :print_status "Services stopped."
goto :eof

REM Show logs
:logs
docker-compose logs -f
goto :eof

REM Show status
:status
docker-compose ps
goto :eof

REM Update application
:update
call :print_status "Updating application..."
git pull
docker-compose build --no-cache
docker-compose up -d
call :print_status "Application updated!"
goto :eof

REM Backup database
:backup
call :print_status "Creating database backup..."
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "BACKUP_FILE=backup_%dt:~0,8%_%dt:~8,6%.sql"
docker-compose exec postgres pg_dump -U postgres los_referral > "%BACKUP_FILE%"
call :print_status "Database backup created: %BACKUP_FILE%"
goto :eof

REM Show help
:show_help
echo LOS App Deployment Script for Windows
echo.
echo Usage: %0 [COMMAND]
echo.
echo Commands:
echo   deploy    - Build and deploy the application
echo   stop      - Stop all services
echo   restart   - Restart all services
echo   logs      - Show application logs
echo   status    - Show service status
echo   update    - Update application from git and redeploy
echo   backup    - Create database backup
echo   help      - Show this help message
echo.
echo Production deployment with Nginx:
echo   docker-compose --profile production up -d
goto :eof

REM Main script logic
set "COMMAND=%~1"
if "%COMMAND%"=="" set "COMMAND=deploy"

if "%COMMAND%"=="deploy" (
    call :check_docker
    call :check_env_file
    call :deploy
) else if "%COMMAND%"=="stop" (
    call :stop
) else if "%COMMAND%"=="restart" (
    call :stop
    timeout /t 5 /nobreak >nul
    call :check_docker
    call :deploy
) else if "%COMMAND%"=="logs" (
    call :logs
) else if "%COMMAND%"=="status" (
    call :status
) else if "%COMMAND%"=="update" (
    call :update
) else if "%COMMAND%"=="backup" (
    call :backup
) else if "%COMMAND%"=="help" (
    call :show_help
) else if "%COMMAND%"=="--help" (
    call :show_help
) else if "%COMMAND%"=="-h" (
    call :show_help
) else (
    call :print_error "Unknown command: %COMMAND%"
    call :show_help
    exit /b 1
) 
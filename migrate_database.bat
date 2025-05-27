@echo off
REM Database Migration Script for LOS App
REM This script helps migrate your existing database to Docker

echo [INFO] LOS Database Migration Script
echo.

REM Check if pg_dump is available
pg_dump --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pg_dump not found. Please install PostgreSQL client tools.
    echo Download from: https://www.postgresql.org/download/windows/
    pause
    exit /b 1
)

echo [INFO] Creating backup of current database...
set BACKUP_FILE=los_database_backup_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%.sql
set BACKUP_FILE=%BACKUP_FILE: =0%

pg_dump postgresql://postgres:31012662@localhost:5432/los_referral > "%BACKUP_FILE%"
if errorlevel 1 (
    echo [ERROR] Failed to create database backup.
    pause
    exit /b 1
)

echo [INFO] Database backup created: %BACKUP_FILE%
echo.

echo [INFO] Starting Docker services...
docker-compose up -d postgres redis
if errorlevel 1 (
    echo [ERROR] Failed to start Docker services.
    pause
    exit /b 1
)

echo [INFO] Waiting for PostgreSQL to be ready...
timeout /t 15 /nobreak >nul

echo [INFO] Importing database backup to Docker...
docker-compose exec -T postgres psql -U postgres -d los_referral < "%BACKUP_FILE%"
if errorlevel 1 (
    echo [WARNING] Database import may have failed. Check logs.
)

echo [INFO] Starting web application...
docker-compose up -d web

echo.
echo [SUCCESS] Migration completed!
echo [INFO] Your application should be available at: http://localhost:8000
echo [INFO] Backup file saved as: %BACKUP_FILE%
echo.
pause 
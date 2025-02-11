import subprocess
import sys
import time

def run_command(command, description):
    print(f"\n=== {description} ===")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error during {description}:")
        print(result.stderr)
        sys.exit(1)
    
    print(result.stdout)
    return result.stdout

def main():
    print("Starting points and rewards system setup...")
    
    # Run database migrations
    run_command("flask db upgrade", "Running database migrations")
    
    # Wait a moment for the database to settle
    time.sleep(2)
    
    # Initialize points and rewards system
    run_command("flask init-points-rewards", "Initializing points and rewards system")
    
    print("\nSetup completed successfully!")
    print("\nAPI Endpoints available at:")
    print("  - /api/v1/points-rewards/points/config (Admin)")
    print("  - /api/v1/points-rewards/points/summary")
    print("  - /api/v1/points-rewards/rewards")
    print("  - /api/v1/company/companies")
    print("\nPoints are automatically awarded for:")
    print("  - Regular clicks")
    print("  - Unique clicks (per IP)")
    print("  - Company status changes")
    print("\nDefault rewards are initialized and can be customized through the API.")

if __name__ == "__main__":
    main()

import locale
import os
import psycopg2

# Attempt to set process locale to something that might influence C library behavior
# This is experimental on Windows for C libraries like libpq
try:
    # Try a generic UTF-8 locale if possible, or a basic C locale
    # Order of preference might matter
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    print(f"Attempted to set locale to en_US.UTF-8, current locale: {locale.getlocale(locale.LC_ALL)}")
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'C')
        print(f"Attempted to set locale to C, current locale: {locale.getlocale(locale.LC_ALL)}")
    except locale.Error as le:
        print(f"Failed to set locale: {le}")

# Also, try to clear some PostgreSQL specific env vars that might be read by libpq
# even if not set at the shell level, they could be inherited.
for var in ['PGCLIENTENCODING', 'PGUSER', 'PGPASSWORD', 'PGHOST', 'PGDATABASE', 'PGPORT', 'PGSERVICE', 'PGSYSCONFDIR', 'PGLOCALEDIR']:
    if var in os.environ:
        print(f"Clearing os.environ['{var}'] (was: {os.environ[var]})")
        del os.environ[var]


db_host = "localhost"
db_port = "5432"
db_name = "los_referral"
db_user = "postgres"
db_pass = "31012662" # Be careful with real passwords, this is from your example
client_enc = "utf8"

print(f"Attempting to connect with explicit parameters: user='{db_user}', host='{db_host}', port='{db_port}', dbname='{db_name}', client_encoding='{client_enc}'")

try:
    # Using keyword arguments for all parameters
    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_pass,
        host=db_host,
        port=db_port,
        client_encoding=client_enc
    )
    print("Connection successful!")
    conn.close()
except UnicodeDecodeError as ude:
    print(f"Caught UnicodeDecodeError: {ude}")
    try:
        print(f"Error details: encoding='{ude.encoding}', object_length={len(ude.object)}, start={ude.start}, end={ude.end}, reason='{ude.reason}'")
        problem_bytes = ude.object[ude.start:ude.end]
        print(f"Problematic bytes (hex): {problem_bytes.hex() if isinstance(problem_bytes, bytes) else 'N/A'}")
    except AttributeError:
        print("Could not retrieve detailed attributes from UnicodeDecodeError object.")
except Exception as e:
    print(f"Caught other error: {e}")
    print(f"Error type: {type(e)}") 
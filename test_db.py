from database import DatabaseManager
from dotenv import load_dotenv
import os
import psycopg2

load_dotenv()

print("Testing Database Connection...")
print(f"Host: {os.getenv('DB_HOST')}")
print(f"Port: {os.getenv('DB_PORT')}")
print(f"Database: {os.getenv('DB_NAME')}")
print(f"User: {os.getenv('DB_USER')}")  # Should be tanvir@ibos.io
print(f"Password: {'*' * len(os.getenv('DB_PASSWORD', ''))}")

# Direct test with psycopg2
try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=int(os.getenv('DB_PORT', 5432)),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    print("\n✅ Connection successful!")

    # Test query
    cur = conn.cursor()
    cur.execute("SELECT current_database(), current_user;")
    result = cur.fetchone()
    print(f"Connected to database: {result[0]}")
    print(f"Connected as user: {result[1]}")

    # List tables
    cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE' LIMIT 10;
                """)
    tables = cur.fetchall()
    print(f"\n📊 Found {len(tables)} tables:")
    for table in tables:
        print(f"  - {table[0]}")

    cur.close()
    conn.close()

except Exception as e:
    print(f"\n❌ Connection failed: {e}")
    print("\n💡 Please check:")
    print("1. Username is 'tanvir@ibos.io' (not 'postgres')")
    print("2. Password is correct from iBOSPg")
    print("3. Database name is 'airbytesdb'")
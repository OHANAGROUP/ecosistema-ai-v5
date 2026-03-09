import os
import psycopg2
from dotenv import load_dotenv

# Path to the .env file in the backend directory
env_path = os.path.join('backend', '.env')
load_dotenv(env_path, override=True)

db_url = os.environ.get('DATABASE_URL')
direct_url = os.environ.get('DIRECT_URL')

def test_conn(url, name):
    try:
        print(f"Testing {name}...")
        # Mask password in logs
        masked_url = url.replace(os.environ.get('DATABASE_URL').split(':')[2].split('@')[0], '****') if '@' in url else url
        print(f"URL: {masked_url}")
        
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()
        print(f"✅ {name} Success! DB Version: {version[0]}")
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ {name} Failed: {e}")
        return False

if __name__ == "__main__":
    s1 = test_conn(db_url, "DATABASE_URL")
    s2 = test_conn(direct_url, "DIRECT_URL")
    
    if s1 and s2:
        print("\n🚀 All connections verified. Ready for Prisma!")
    else:
        print("\n⚠️ Connection issues detected. Check your password and host.")

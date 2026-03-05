import os
import psycopg2
from dotenv import load_dotenv

env_path = os.path.join('backend', '.env')
load_dotenv(env_path, override=True)

password = "tdkyctnkskidfancguhv"
hosts = [
    "db.tnzfalnzxnzxqxtywtey.supabase.co",
    "aws-0-us-west-2.pooler.supabase.com"
]
ports = [5432, 6543]
users = ["postgres", "postgres.tnzfalnzxnzxqxtywtey"]

def test_conn(host, port, user, pwd):
    url = f"postgresql://{user}:{pwd}@{host}:{port}/postgres"
    try:
        print(f"Testing: {user}@{host}:{port}...")
        conn = psycopg2.connect(url, connect_timeout=5)
        print(f"✅ SUCCESS!")
        conn.close()
        return url
    except Exception as e:
        print(f"❌ FAILED: {str(e).strip()}")
        return None

if __name__ == "__main__":
    working_urls = []
    for host in hosts:
        for port in ports:
            for user in users:
                res = test_conn(host, port, user, password)
                if res: working_urls.append(res)
    
    if working_urls:
        print("\n🚀 WORKING URLS FOUND:")
        for u in working_urls: print(u)
    else:
        print("\n😭 NO WORKING CONNECTIONS FOUND.")

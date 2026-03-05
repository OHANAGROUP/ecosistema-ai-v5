import os
import asyncio
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv(override=True)

async def create_admin_user():
    url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    anon_key = os.environ.get("SUPABASE_KEY")
    
    print(f"DEBUG: SUPABASE_URL={url}")
    print(f"DEBUG: SERVICE_KEY_EXISTS={bool(service_key)}")
    print(f"DEBUG: ANON_KEY_EXISTS={bool(anon_key)}")
    
    if not url or not service_key:
        print("❌ Error: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set.")
        return

    supabase: Client = create_client(url, service_key)
    # Admin Credentials from Environment
    email = os.environ.get("ADMIN_EMAIL", "admin@alpa.cl")
    password = os.environ.get("ADMIN_PASSWORD")
    user_id = os.environ.get("ADMIN_USER_ID", "470ee4a9-4e3d-408b-8d8e-393244e93dab")
    org_id = os.environ.get("ADMIN_ORG_ID", "f8d8f8d8-f8d8-f8d8-f8d8-f8d8f8d8f8d8")

    if not password:
        print("❌ Error: ADMIN_PASSWORD environment variable is not set.")
        print("👉 Add ADMIN_PASSWORD to your .env file or Railway variables.")
        return

    print(f"Creating Admin User: {email}")
    
    try:
        # Create Auth User using the admin API
        res = supabase.auth.admin.create_user({
            "id": user_id,
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "organization_id": org_id,
                "role": "admin"
            }
        })
        print(f"✅ Admin user created/verified successfully.")
        print(f"Email: {email}")
        print(f"Organization ID: {org_id}")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"ℹ️  User {email} already exists.")
        else:
            print(f"❌ Error: {str(e)}")
            print("\nPRO TIP: This script requires the 'service_role' key to bypass RLS and Auth restrictions.")

if __name__ == "__main__":
    asyncio.run(create_admin_user())

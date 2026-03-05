import os
import asyncio
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

async def seed_data():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") # Use service role for seeding
    supabase: Client = create_client(url, key)

    org_id = os.environ.get("ADMIN_ORG_ID", "f8d8f8d8-f8d8-f8d8-f8d8-f8d8f8d8f8d8")
    
    print(f"Seeding Organization: {org_id}")
    
    # 1. Create Organization (snake_case)
    org_data = {
        "id": org_id,
        "name": "ALPA Construcciones S.A.",
        "slug": "alpa-holding",
        "settings": {
            "balance": {"total_cash": 15000000, "currency": "CLP"},
            "legal": {"tax_id": "76.123.456-K", "status": "active"},
            "rh": {"headcount": 45}
        }
    }
    supabase.table("organizations").upsert(org_data).execute()

    # 2. Create Project (snake_case)
    proj_id = "f111e4a9-4e3d-408b-8d8e-393244e93da1" # Standard UUID
    print(f"Seeding Project: {proj_id}")
    proj_data = {
        "id": proj_id,
        "organization_id": org_id,
        "nombre": "Torre Alpa - Santiago Centro",
        "presupuesto": 10000000,
        "estado": "Activo",
        "fecha_inicio": "2026-01-01"
    }
    supabase.table("projects").upsert(proj_data).execute()

    # 3. Add initial transactions (snake_case)
    print("Seeding Initial Transactions...")
    transactions = [
        {
            "id": "f222e4a9-4e3d-408b-8d8e-393244e93da2",
            "organization_id": org_id,
            "proyecto_id": proj_id,
            "monto": 5000000,
            "descripcion": "Cimentación y fundaciones",
            "categoria": "Obra Gruesa",
            "tipo": "Egreso",
            "fecha": datetime.utcnow().date().isoformat()
        },
        {
            "id": "f333e4a9-4e3d-408b-8d8e-393244e93da3",
            "organization_id": org_id,
            "proyecto_id": proj_id,
            "monto": 3500000,
            "descripcion": "Estructura metálica Nivel 1-3",
            "categoria": "Materiales",
            "tipo": "Egreso",
            "fecha": datetime.utcnow().date().isoformat()
        }
    ]
    supabase.table("transactions").upsert(transactions).execute()

    print("✅ Demo Data Seeded Correctly.")

if __name__ == "__main__":
    asyncio.run(seed_data())

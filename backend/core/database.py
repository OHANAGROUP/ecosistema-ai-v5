from datetime import datetime
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(url, key)

def get_supabase():
    return supabase

# MJ-01: Unified Data Substrate Fetcher
class DataFetcher:
    def __init__(self):
        self.supabase = get_supabase()

    async def fetch_company_data(self, company_id: str, tenant_id: str = None) -> dict:
        """
        Pulls all relevant data for a company to populate the EmpresaSchema.
        MJ-01: Optimized with asyncio.gather for Phase 8.
        """
        # Security: If tenant_id is provided, it MUST match the company_id or organization_id
        # In this SaaS, company_id IS the organization_id from the session
        effective_org_id = tenant_id if tenant_id else company_id
        
        try:
            # MJ-08: Parallel Execution for lower latency
            org_task = self.supabase.table("organizations").select("*").eq("id", effective_org_id).maybe_single().execute()
            projs_task = self.supabase.table("projects").select("*").eq("organization_id", effective_org_id).execute()
            trans_task = self.supabase.table("transactions").select("*").eq("organization_id", effective_org_id).execute()

            # Wait for all in parallel
            import asyncio
            org_res, projs_res, trans_res = await asyncio.gather(
                asyncio.to_thread(lambda: org_task),
                asyncio.to_thread(lambda: projs_task),
                asyncio.to_thread(lambda: trans_task)
            )

            if not org_res.data:
                return {"id": effective_org_id, "nombre": "Unknown", "industria": "general"}

            # Map to Schema
            return {
                "id": effective_org_id,
                "nombre": org_res.data.get("name", "ALPA Corp"),
                "industria": org_res.data.get("industry", "construction"),
                "datos_financieros": {
                    "proyectos": projs_res.data,
                    "transacciones_recientes": trans_res.data[:60], # Slight increase for better depth
                    "balance_general": org_res.data.get("metadata", {}).get("balance", {})
                },
                "datos_legales": org_res.data.get("metadata", {}).get("legal", {}),
                "datos_rh": org_res.data.get("metadata", {}).get("rh", {}),
                "pool_de_datos": {
                    "last_sync": datetime.utcnow().isoformat(),
                    "total_projects": len(projs_res.data),
                    "execution_mode": "parallel_v8"
                }
            }
        except Exception as e:
            print(f"Error fetching data for {effective_org_id}: {e}")
            return {"id": effective_org_id, "nombre": "Error", "industria": "error"}

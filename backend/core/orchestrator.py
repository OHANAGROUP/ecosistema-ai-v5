import asyncio
import logging
from datetime import datetime, timedelta
from .schemas import CycleContext
from .router import validate_semantic, route_agents
from agents.financiero import AgenteFinanciero
from agents.legal import AgenteLegal
from agents.rh import AgenteRH
from agents.arb import AgenteArb
from .database import get_supabase, DataFetcher

# MJ-07: Orchestrator Engine v5.0
class AgentOrchestrator:
    active_cycles = 0  # Contador de ciclos activos

    def __init__(self):
        self.supabase = get_supabase()
        self.fetcher = DataFetcher()

    async def broadcast_status(self, cycle_id: str, status: str, message: str):
        """MJ-09: Broadcast de estado puntual para 'Agent Mind'"""
        try:
            self.supabase.table("agent_cycles").update({
                "status": status,
                "current_message": message,
                "last_activity": datetime.utcnow().isoformat()
            }).eq("cycle_id", str(cycle_id)).execute()
        except: pass

    async def cleanup_orphan_cycles(self):
        """MJ-07 (V6): Cleanup de ciclos huérfanos cada 10 min"""
        ten_mins_ago = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        try:
            result = self.supabase.table("agent_cycles") \
                .update({"status": "orphan"}) \
                .filter("status", "eq", "started") \
                .filter("last_activity", "lt", ten_mins_ago) \
                .execute()
            logging.info(f"Cleanup ejecutado: {len(result.data)} ciclos huérfanos marcados.")
        except Exception as e:
            logging.error(f"Error en cleanup: {str(e)}")

    async def run_cycle(self, cycle_id: str, company_id: str, instruccion: str, tenant_id: str, mode: str = "fast"):
        """Workflow principal del ciclo de agentes con Sustrato de Datos Unificado"""
        print(f"Iniciando ciclo {cycle_id} para tenant {tenant_id} en modo {mode}")
        AgentOrchestrator.active_cycles += 1
        
        try:
            await self.broadcast_status(cycle_id, "started", "🔄 Recuperando sustrato de datos...")

            # 0. MJ-01: Sustrato de Datos Unificado — Fetch real de Supabase
            company_data = await self.fetcher.fetch_company_data(company_id, tenant_id=tenant_id)
            from .schemas import EmpresaSchema, CycleContext
            
            context = CycleContext(
                cycle_id=cycle_id,
                tenant_id=tenant_id,
                empresa=EmpresaSchema(**company_data),
                instruccion_ceo=instruccion,
                mode=mode
            )

            # 1. MJ-01: SK-VAL — Fail-fast si no hay datos
            await self.broadcast_status(cycle_id, "validating", "🔍 Validando suficiencia semántica (SK-VAL)...")
            validation = await validate_semantic(context)
            if not validation.passed:
                print(f"Ciclo {cycle_id} cancelado: {validation.reason} - Faltan: {validation.missing}")
                await self.broadcast_status(cycle_id, "failed_validation", f"❌ Falta de datos: {validation.missing}")
                return

            # 2. Routing
            await self.broadcast_status(cycle_id, "routing", "🔀 Enrutando agentes especializados...")
            selected_agents = await route_agents(context)
            
            # 3. Gather Paralelo (SK-OBJ)
            await self.broadcast_status(cycle_id, "processing", f"🤖 Agentes activos: {', '.join(selected_agents)}")
            tasks = []
            if "financiero" in selected_agents:
                tasks.append(AgenteFinanciero().run(context))
            if "legal" in selected_agents:
                tasks.append(AgenteLegal().run(context))
            if "rh" in selected_agents:
                tasks.append(AgenteRH().run(context))
                
            decisions = await asyncio.gather(*tasks)
            
            # 4. SK-ARB: Arbitraje y Síntesis
            await self.broadcast_status(cycle_id, "synthesizing", "⚖️ Arbitrando decisiones (SK-ARB)...")
            final_synthesis = await AgenteArb().run(context, decisions)
            
            # MJ-08: Persistencia de Síntesis Final
            try:
                self.supabase.table("agent_cycles").update({
                    "status": "completed",
                    "current_message": "✅ Ciclo completado exitosamente.",
                    "final_synthesis": final_synthesis.dict() if hasattr(final_synthesis, 'dict') else final_synthesis,
                    "last_activity": datetime.utcnow().isoformat()
                }).eq("cycle_id", str(cycle_id)).execute()
            except Exception as e:
                logging.error(f"Error persisting synthesis: {e}")
            
            print(f"Ciclo {context.cycle_id} completado con éxito")
            
        except Exception as e:
            logging.error(f"Error crítico en ciclo {cycle_id}: {str(e)}")
            await self.broadcast_status(cycle_id, "error", f"💥 Error: {str(e)}")
        finally:
            AgentOrchestrator.active_cycles -= 1

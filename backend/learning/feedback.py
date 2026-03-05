from ..core.schemas import CycleContext
from ..core.database import get_supabase
import logging

class LearningSystem:
    def __init__(self):
        self.supabase = get_supabase()

    async def get_p1_company_history(self, empresa_id: str, limit: int = 5):
        """
        P1: RAG Episódico - Carga las últimas decisiones de la empresa.
        """
        try:
            res = self.supabase.table("agent_decisions") \
                .select("*") \
                .eq("metadata->empresa_id", empresa_id) \
                .order("timestamp", desc=True) \
                .limit(limit) \
                .execute()
            return res.data
        except Exception as e:
            logging.error(f"Error cargando P1: {e}")
            return []

    async def get_p3_active_rules(self, tenant_id: str, query: str = ""):
        """
        MJ-06: Búsqueda Semántica de Reglas (pgvector simulado).
        """
        try:
            # En v5 real, esto usaría rpc('match_rules', {'embedding': query_vec, 'match_threshold': 0.7, 'match_count': 5})
            res = self.supabase.table("agent_rules") \
                .select("*") \
                .eq("tenant_id", tenant_id) \
                .eq("is_active", True) \
                .order("weight", desc=True) \
                .limit(5) \
                .execute()
            print(f"P3: Cargando top-5 reglas relevantes para: {query}")
            return res.data
        except Exception as e:
            logging.error(f"Error cargando P3: {e}")
            return []

    async def save_p2_feedback(self, decision_id: str, approved: bool):
        """
        P2: RLHF - Aprende del feedback (+0.08 aprobación / -0.12 rechazo).
        """
        # Lógica de actualización de pesos de reglas asociadas a la decisión
        pass

    async def p4_extract_patterns(self, cycle_id: str):
        """
        P4: Patrones - Análisis post-ciclo para sugerir nuevas reglas.
        """
        pass

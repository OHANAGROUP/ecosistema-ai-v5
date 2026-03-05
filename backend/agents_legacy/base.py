from ..core.schemas import CycleContext, AgentDecision
from abc import ABC, abstractmethod

class BaseAgent(ABC):
    @abstractmethod
    async def run(self, context: CycleContext) -> AgentDecision:
        pass

    async def persist_decision(self, decision: AgentDecision):
        # Implementar persistencia en Supabase
        from ..core.database import get_supabase
        supabase = get_supabase()
        
        data = {
            "cycle_id": str(decision.cycle_id),
            "tenant_id": str(decision.metadata.get("tenant_id", "default")),
            "agent_id": decision.agent_id,
            "decision": decision.decision,
            "confidence": decision.confidence,
            "metadata": decision.metadata
        }
        
        # Fire and forget (o await si es necesario para el flujo)
        supabase.table("agent_decisions").insert(data).execute()

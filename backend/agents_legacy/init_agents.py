from .base import BaseAgent
from ..core.schemas import CycleContext, AgentDecision

class AgenteFinanciero(BaseAgent):
    async def run(self, context: CycleContext) -> AgentDecision:
        # MJ-03: Aquí se enriquecería con historial directo en el futuro
        decision_text = f"Análisis financiero para {context.empresa.nombre}. Margen neto simulado: 15%."
        
        decision = AgentDecision(
            agent_id="financiero",
            cycle_id=context.cycle_id,
            decision=decision_text,
            confidence=0.92
        )
        
        await self.persist_decision(decision)
        return decision

# Similares para Legal y RH (esqueletos)
class AgenteLegal(BaseAgent):
    async def run(self, context: CycleContext) -> AgentDecision:
        decision = AgentDecision(
            agent_id="legal",
            cycle_id=context.cycle_id,
            decision="Análisis legal: Sin riesgos críticos detectados en Chile 2026.",
            confidence=0.88
        )
        await self.persist_decision(decision)
        return decision

class AgenteRH(BaseAgent):
    async def run(self, context: CycleContext) -> AgentDecision:
        decision = AgentDecision(
            agent_id="rh",
            cycle_id=context.cycle_id,
            decision="Análisis RH: Clima organizacional estable.",
            confidence=0.85
        )
        await self.persist_decision(decision)
        return decision

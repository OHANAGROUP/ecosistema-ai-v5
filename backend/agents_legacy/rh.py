from .base import BaseAgent
from ..core.schemas import CycleContext, AgentDecision
from ..core.llm import LLMClient
from ..learning.feedback import LearningSystem
from ..core.memory_bus import MemoryBus

class AgenteRH(BaseAgent):
    def __init__(self):
        self.llm = LLMClient()
        self.learning = LearningSystem()
        self.bus = MemoryBus()

    async def run(self, context: CycleContext) -> AgentDecision:
        # MJ-05: Escuchar señales del bus (ej. si financiero detectó costo laboral anómalo)
        signals = await self.bus.get_active_signals(str(context.cycle_id))
        
        history = await self.learning.get_p1_company_history(context.empresa.id)
        rules = await self.learning.get_p3_active_rules(context.tenant_id)
        
        system_prompt = f"Eres el Agente de Recursos Humanos v5.0.\nSeñales del Bus: {signals}\nHistorial: {history}\nReglas: {rules}"
        prompt = f"Instrucción: {context.instruccion_ceo}\nDatos RH: {context.empresa.datos_rh}"
        
        res = await self.llm.completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
        
        decision = AgentDecision(
            agent_id="rh",
            cycle_id=context.cycle_id,
            decision=f"[{res['source']}] {res['text']}",
            confidence=0.88 * res['confidence_adjustment']
        )
        
        await self.persist_decision(decision)
        return decision

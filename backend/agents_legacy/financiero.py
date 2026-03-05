from .base import BaseAgent
from ..core.schemas import CycleContext, AgentDecision
from ..core.llm import LLMClient
from ..learning.feedback import LearningSystem
from ..core.memory_bus import MemoryBus

class AgenteFinanciero(BaseAgent):
    def __init__(self):
        self.llm = LLMClient()
        self.learning = LearningSystem()
        self.bus = MemoryBus()

    async def run(self, context: CycleContext) -> AgentDecision:
        # Recuperar señales de otros agentes (si los hubiera)
        signals = await self.bus.get_active_signals(str(context.cycle_id))
        
        history = await self.learning.get_p1_company_history(context.empresa.id)
        rules = await self.learning.get_p3_active_rules(context.tenant_id)
        
        system_prompt = f"Eres el Agente Financiero v5.0.\nSeñales activas: {signals}\nHistorial: {history}\nReglas: {rules}"
        prompt = f"Instrucción: {context.instruccion_ceo}\nDatos: {context.empresa.datos_financieros}"
        
        res = await self.llm.completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
        
        # MJ-05: Publicar señal si detecta anomalía (Simulación)
        if "margen bajo" in res['text'].lower():
            await self.bus.publish_signal(
                agent_id="financiero",
                cycle_id=str(context.cycle_id),
                company_id=context.empresa.id,
                signal_type="costo_laboral_anomalo",
                value=0.25
            )
        
        decision = AgentDecision(
            agent_id="financiero",
            cycle_id=context.cycle_id,
            decision=f"[{res['source']}] {res['text']}",
            confidence=0.9 * res['confidence_adjustment']
        )
        
        await self.persist_decision(decision)
        return decision

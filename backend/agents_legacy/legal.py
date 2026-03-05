from .base import BaseAgent
from ..core.schemas import CycleContext, AgentDecision
from ..core.llm import LLMClient
from ..learning.feedback import LearningSystem

class AgenteLegal(BaseAgent):
    def __init__(self):
        self.llm = LLMClient()
        self.learning = LearningSystem()

    async def run(self, context: CycleContext) -> AgentDecision:
        history = await self.learning.get_p1_company_history(context.empresa.id)
        rules = await self.learning.get_p3_active_rules(context.tenant_id)
        
        system_prompt = f"Eres el Agente Legal v5.0.\nHistorial: {history}\nReglas: {rules}"
        prompt = f"Instrucción: {context.instruccion_ceo}\nDatos Legales: {context.empresa.datos_legales}"
        
        res = await self.llm.completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
        
        decision = AgentDecision(
            agent_id="legal",
            cycle_id=context.cycle_id,
            decision=f"[{res['source']}] {res['text']}",
            confidence=0.85 * res['confidence_adjustment']
        )
        
        await self.persist_decision(decision)
        return decision

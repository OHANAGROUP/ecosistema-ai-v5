from typing import List
from .base import BaseAgent
from ..core.schemas import CycleContext, AgentDecision

class AgenteArb(BaseAgent):
    async def run(self, context: CycleContext, decisions: List[AgentDecision]) -> AgentDecision:
        """MJ-07 (SK-ARB): Arbitraje y detección de incoherencias"""
        
        # 1. Cálculo de Coherencia
        confidencias = [d.confidence for d in decisions]
        if not confidencias:
            return AgentDecision(
                agent_id="arbitro",
                cycle_id=context.cycle_id,
                decision="No hay decisiones para arbitrar.",
                confidence=0.1
            )
            
        avg_confidence = sum(confidencias) / len(confidencias)
        
        # PJ-07: Consensus Boost (Reward multi-agent agreement on risks)
        risk_keywords = ["alerta", "crítico", "infracción", "ilegal", "riesgo", "detectado"]
        is_high_risk = all(any(w in d.decision.lower() for w in risk_keywords) for d in decisions)
        coherence_score = avg_confidence
        
        if is_high_risk and len(decisions) >= 3:
            coherence_score += 0.15 # Bonus por consenso interdisciplinario
            
        # Simulación de detección de conflictos (Omega Paradox)
        # Conflicto entre viabilidad financiera y prohibición legal
        has_binary_conflict = (any(any(w in d.decision.lower() for w in ["aprobado", "viable", "ok"]) for d in decisions) and 
                               any(any(w in d.decision.lower() for w in ["ilegal", "infracción", "prohibido"]) for d in decisions))
        
        if has_binary_conflict:
            coherence_score -= 0.5 # Penalización masiva para forzar HITL/revisión
        
        has_logic_conflict = any("no es viable" in d.decision.lower() for d in decisions) and \
                            any("aprobado" in d.decision.lower() for d in decisions)
        
        if has_logic_conflict:
            coherence_score -= 0.3 # Penalización por conflicto directo
            
        coherence_score = max(0.1, min(1.0, coherence_score))
        
        # 2. Síntesis
        combined = " | ".join([f"[{d.agent_id}]: {d.decision}" for d in decisions])
        status = "✅ COHERENTE" if coherence_score >= 0.7 else "⚠️ REQUIERE REVISIÓN"
        
        synthesis_text = f"[{status}] Score: {coherence_score:.2f} | {combined}"
        
        decision = AgentDecision(
            agent_id="arbitro",
            cycle_id=context.cycle_id,
            decision=synthesis_text,
            confidence=coherence_score,
            metadata={
                "coherence_score": coherence_score,
                "has_binary_conflict": has_binary_conflict,
                "has_logic_conflict": has_logic_conflict,
                "agent_count": len(decisions)
            }
        )
        
        await self.persist_decision(decision)
        return decision

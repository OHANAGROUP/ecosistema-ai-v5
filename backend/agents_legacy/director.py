import uuid
from typing import List, Dict, Any
from .base import BaseAgent
from .financiero import AgenteFinanciero
from .rh import AgenteRH
from .legal import AgenteLegal
from .arb import AgenteArb
from ..core.schemas import CycleContext, AgentDecision
from ..core.tools import TaxTools, BankTools, LegalTools

class DirectorAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.specialists = {
            "financial": AgenteFinanciero(),
            "rh": AgenteRH(),
            "legal": AgenteLegal()
        }
        self.arbiter = AgenteArb()

    async def run(self, context: CycleContext) -> AgentDecision:
        """EntryPoint para el Agente Director (Nivel 5)"""
        # En una implementación real, aquí se obtendrían los raw_data del ERP
        # Por ahora pasamos un dict vacío o manejamos la integración
        return AgentDecision(
            agent_id="director",
            cycle_id=context.cycle_id,
            decision="Director activo. Iniciando orquestación de especialistas...",
            confidence=1.0
        )

    async def run_audit_cycle(self, context: CycleContext, raw_kame_data: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta el ciclo completo de auditoría y acción."""
        run_id = str(uuid.uuid4())
        findings = []
        savings = []
        
        # 1. Triangulación con SII (Pilar 1: Verdad)
        sii_data = raw_kame_data.get("sii_snapshot", {})
        tax_delta = TaxTools.get_sii_delta(
            periodo=context.tenant_id, 
            er_total_neto=raw_kame_data.get("erp_cost_total", 0),
            sii_purchases_total=sii_data.get("purchases_total", 0)
        )
        
        if tax_delta["status"] == "CRITICAL":
            findings.append({
                "agent": "Director",
                "risk": "Critical",
                "desc": tax_delta["finding"],
                "impact": tax_delta["delta"]
            })

        # 2. Arbitraje Bancario (Pilar 2: Optimización)
        bank_analysis = BankTools.analyze_cash_arbitrage(raw_kame_data.get("bank_accounts", []))
        if bank_analysis["proposals"]:
            for prop in bank_analysis["proposals"]:
                findings.append({
                    "agent": "Director",
                    "risk": "High",
                    "desc": prop["desc"],
                    "impact": prop["amount"]
                })
            savings.append({
                "type": "Bank_Arbitrage",
                "amount": bank_analysis["estimated_monthly_saving"],
                "desc": "Ahorro por saneamiento de sobregiros."
            })

        # 3. Delegación a Especialistas (Pilar 3: Razonamiento)
        decisions = []
        # Solo delegamos si hay datos específicos
        dec_fin = await self.specialists["financial"].run(context)
        dec_rh = await self.specialists["rh"].run(context)
        dec_leg = await self.specialists["legal"].run(context)
        
        decisions.extend([dec_fin, dec_rh, dec_leg])

        # 4. Síntesis Arbitral
        final_decision = await self.arbiter.run(context, decisions)

        return {
            "run_id": run_id,
            "tenant_id": context.tenant_id,
            "coherence_score": final_decision.confidence,
            "synthesis": final_decision.decision,
            "findings": findings,
            "savings": savings,
            "metadata": final_decision.metadata
        }

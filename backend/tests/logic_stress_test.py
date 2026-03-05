import os
import asyncio
import sys

# Set dummy env vars to prevent LLMClient init failure
os.environ["MERCURY_API_KEY"] = "dummy"
os.environ["GROQ_API_KEY"] = "dummy"
os.environ["GEMINI_API_KEY"] = "dummy"

from backend.core.schemas import CycleContext, EmpresaSchema
from backend.agents.financiero import AgenteFinanciero
from backend.agents.arb import AgenteArb
from backend.core.llm import LLMClient
from unittest.mock import MagicMock

# --- MONKEYPATCH LLM per a Test Determinista ---
async def mock_completion(self, messages, **kwargs):
    prompt = messages[-1]["content"] if messages else ""
    if "financiero" in prompt.lower() or "presupuesto" in prompt.lower():
        return {
            "text": "ALERTA: El proyecto Torre Alpa presenta un SOBRECOSTO de $1,000,000 (10% sobre el presupuesto). Estado: CRÍTICO.",
            "confidence_adjustment": 1.0,
            "source": "Mock-Mercury"
        }
    else:
        return {
            "text": "Recomendación: Escalar alerta de sobrecosto en Torre Alpa y revisar flujo de caja para cubrir el gap de $1M.",
            "confidence_adjustment": 1.0,
            "source": "Mock-Arb"
        }

LLMClient.completion = mock_completion
# -----------------------------------------------

from backend.agents.base import BaseAgent

# --- MONKEYPATCH Persistence (Avoid DB Errors) ---
async def mock_persist(self, decision):
    print(f"   [MOCK PERSIST]: Guardando decisión de {decision.agent_id}...")

BaseAgent.persist_decision = mock_persist
# --------------------------------------------------

import uuid

async def run_logic_stress_test():
    print("🚀 INICIANDO TEST DE LÓGICA: SOBRECOSTO 'TORRE ALPA'")
    
    # 1. Definir Contexto de Prueba (Conocido)
    context = CycleContext(
        cycle_id=uuid.uuid4(),
        tenant_id="ALPA-001",
        instruccion_ceo="Evaluar estado del proyecto Torre Alpa.",
        empresa=EmpresaSchema(
            id="ALPA-001",
            nombre="ALPA Construcciones",
            industria="construction",
            datos_financieros={
                "proyectos": [
                    {
                        "ID": "PROJ-TORRE-ALPA",
                        "Nombre": "Torre Alpa",
                        "Presupuesto": 10000000, # 10M
                        "GastoReal": 11000000,    # 11M (SOBRECOSTO!)
                        "Estado": "Activo"
                    }
                ],
                "transacciones_recientes": [
                    {"ID": "TX-101", "Monto": 2500000, "Descripción": "Acero Estructural", "Tipo": "Egreso"}
                ]
            },
            datos_legales={"status": "active"},
            datos_rh={"headcount": 10}
        )
    )

    print("\n--- PASO 1: Ejecutando Agente Financiero ---")
    fin_agent = AgenteFinanciero()
    fin_decision = await fin_agent.run(context)
    print(f"Resultado Financiero: {fin_decision.decision[:100]}...")
    print(f"Confianza: {fin_decision.confidence}")

    print("\n--- PASO 2: Ejecutando Agente Arbitro (Síntesis) ---")
    arb_agent = AgenteArb()
    final_synthesis = await arb_agent.run(context, [fin_decision])
    
    print("\n--- REPORTE FINAL ---")
    print(f"Decisión Final: {final_synthesis.decision}")
    print(f"Puntaje de Coherencia ARB: {final_synthesis.confidence * 100}%")
    
    # Verificación del Resultado Conocido
    if "sobrecosto" in final_synthesis.decision.lower() or "overrun" in final_synthesis.decision.lower():
        print("\n✅ TEST EXITOSO: El sistema detectó correctamente el problema de presupuesto.")
    else:
        print("\n❌ TEST FALLIDO: El sistema no detectó el sobrecosto.")

if __name__ == "__main__":
    asyncio.run(run_logic_stress_test())

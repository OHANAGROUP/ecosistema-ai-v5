import asyncio
import os
import sys
import uuid
from unittest.mock import MagicMock, patch

# --- MOCKS PREVENTING API ERRORS ---
os.environ["MERCURY_API_KEY"] = "mock_key"
os.environ["GROQ_API_KEY"] = "mock_key"
os.environ["GEMINI_API_KEY"] = "mock_key"

# Add current directory to path
sys.path.append(os.getcwd())

from backend.core.schemas import CycleContext, EmpresaSchema, AgentDecision
from backend.agents.base import BaseAgent

# Mock BaseAgent.persist_decision for all agents
async def mock_persist(self, decision): pass
BaseAgent.persist_decision = mock_persist

# Mock MemoryBus and LearningSystem
from backend.core.memory_bus import MemoryBus
from backend.learning.feedback import LearningSystem

async def mock_publish(*args, **kwargs): pass
async def mock_get_signals(*args, **kwargs): return []
MemoryBus.publish_signal = mock_publish
MemoryBus.get_active_signals = mock_get_signals

async def mock_p1(*args, **kwargs): return []
async def mock_p3(*args, **kwargs): return []
LearningSystem.get_p1_company_history = mock_p1
LearningSystem.get_p3_active_rules = mock_p3

# Patch LLMClient entirely to prevent client instantiation
with patch('backend.core.llm.OpenAI'), patch('backend.core.llm.Groq'):
    from backend.agents.director import DirectorAgent
    from backend.core.llm import LLMClient

# Mock completion
async def mock_completion(self, messages, **kwargs):
    system = messages[0]["content"].lower()
    if "financial" in system or "financiero" in system:
        return {"text": "ANÁLISIS FINANCIERO: Gastos ERP subestimados frente a SII.", "confidence_adjustment": 0.9, "source": "Mock-Mercury"}
    elif "recursos humanos" in system or "rh" in system:
        return {"text": "ANÁLISIS RH: Staff normal.", "confidence_adjustment": 0.95, "source": "Mock-Mercury"}
    elif "legal" in system:
        return {"text": "ANÁLISIS LEGAL: Contratos vigentes para proveedores principales.", "confidence_adjustment": 0.9, "source": "Mock-Mercury"}
    else: # Arbiter
        return {"text": "SÍNTESIS: Riesgo crítico detectado por discrepancia SII.", "confidence_adjustment": 0.88, "source": "Mock-Arb"}

LLMClient.completion = mock_completion

async def run_director_test():
    print("🚀 EJECUTANDO TEST: DIRECTOR AGENT ORCHESTRATION")
    
    director = DirectorAgent()
    
    # 1. Mock Data (Simulating VAJ Holding scenario)
    raw_data = {
        "erp_cost_total": 1000000000, # $1,000M
        "sii_snapshot": {
            "purchases_total": 1373084226, # $1,373M (Delta de $373M)
        },
        "bank_accounts": [
            {"banco": "Santander", "saldo": -100000000}, # -$100M (Sobregiro)
            {"banco": "Banco de Chile", "saldo": 500000000} # $500M (Caja)
        ]
    }
    
    context = CycleContext(
        cycle_id=uuid.uuid4(),
        tenant_id="VAJ-HOLDING-001",
        instruccion_ceo="Auditoría mensual y saneamiento de caja.",
        empresa=EmpresaSchema(
            id="VAJ-001",
            nombre="Constructora VAJ",
            industria="Construction",
            datos_financieros={"status": "consolidated"},
            datos_legales={},
            datos_rh={},
            pool_de_datos={"status": "complete"}
        )
    )

    # 2. Run Cycle
    print("\n--- INICIANDO CICLO DE AUDITORÍA (DIRECTOR) ---")
    result = await director.run_audit_cycle(context, raw_data)

    # 3. Validation
    print("\n" + "="*50)
    print("🚀 RESULTADOS DEL DIRECTOR")
    print("="*50)
    print(f"ID del Run: {result['run_id']}")
    print(f"Coherencia Arbiter: {result['coherence_score'] * 100:.2f}%")
    
    print("\n--- RIESGOS DETECTADOS (Director + Herramientas) ---")
    for f in result['findings']:
        print(f"[-] [{f['agent']}] {f['risk']}: {f['desc']} (Impacto: ${f['impact']:,.0f})")
        
    print("\n--- AHORROS PROYECTADOS (ROI) ---")
    for s in result['savings']:
        print(f"[+] {s['type']}: ${s['amount']:,.0f} - {s['desc']}")

    # Final Checks
    triangulation_detected = any("SII" in f['desc'] for f in result['findings'])
    arbitrage_proposed = any("Santander" in f['desc'] for f in result['findings'])
    
    if triangulation_detected and arbitrage_proposed:
        print("\n✅ TEST PASSED: El Director orquestó la verdad y la acción.")
    else:
        print("\n❌ TEST FAILED: Alguna herramienta de acción no disparó.")

if __name__ == "__main__":
    asyncio.run(run_director_test())

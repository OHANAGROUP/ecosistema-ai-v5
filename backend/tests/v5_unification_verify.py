import asyncio
import os
import sys
from unittest.mock import MagicMock, AsyncMock, patch

# Añadir el path del backend para imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents import AgentOrchestrator, EmpresaSchema, InstruccionCEO, EmpresaMetadata, AgentDecision

async def test_unification():
    print("=== Iniciando Verificación de Unificación v5.0 ===")
    
    # 1. Mock Supabase
    mock_supabase = MagicMock()
    # Simular respuesta de vistas ETL
    mock_supabase.table().select().eq().eq().single().execute.return_value = MagicMock(data={
        "margen_bruto_pct": 0.18,
        "ingresos_mes": 50000000,
        "gastos_mes": 41000000,
        "empresa": "TestCorp",
        "n_empleados": 15,
        "tasa_rotacion": 0.05
    })
    
    # Simular otras llamadas (history, rules, etc)
    mock_supabase.table().select().eq().eq().eq().order().limit().execute.return_value = MagicMock(data=[])
    mock_supabase.table().insert().execute.return_value = MagicMock(data=[{"id": "mock_id"}])
    mock_supabase.rpc().execute.return_value = MagicMock(data=0)

    # 2. Mock LLM global (_llm)
    with patch("agents._llm") as mock_llm:
        mock_llm.complete_with_source = AsyncMock(return_value=("Mock Business Recommendation", "MOCK_LLM"))
        mock_llm.complete = AsyncMock(return_value='{"synthesis":"Todo OK","coherence_score":0.95}')

        # 3. Inicializar Orquestador
        print("[1/3] Inicializando Orquestador...")
        orchestrator = AgentOrchestrator(mock_supabase)
        
        # 4. Simular Ciclo
        print("[2/3] Ejecutando ciclo de prueba (Objetivo: Margen)...")
        cycle_id = "test-cycle-v5"
        organization_id = "test-org-alpa"
        company_id = "TestCorp"
        instruccion = "Analizar el margen de TestCorp y proponer mejoras en costos laborales"
        
        results = await orchestrator.run_cycle(
            cycle_id=cycle_id,
            company_id=company_id,
            instruccion=instruccion,
            organization_id=organization_id,
            mode="fast"
        )
        
        # 5. Validar Resultados
        print("[3/3] Validando resultados...")
        
        # Verificar que se activaron los agentes correctos
        activated = [k for k, v in results.items() if v]
        print(f"Agentes activados: {activated}")
        
        assert "financiero" in activated, "Agente Financiero debería haberse activado"
        assert "rh" in activated, "Agente RH debería haberse activado"
        
        for agent, decisions in results.items():
            for d in decisions:
                print(f" -> {agent.upper()}: {d.decision} (Confianza: {d.confidence})")
                assert d.organization_id == organization_id, f"organization_id no se propagó en {agent}"
                assert d.cycle_id == cycle_id, f"cycle_id no se propagó en {agent}"

    print("\n✅ Verificación exitosa: Nomenclatura, Routing y Propagación de IDs correctos.")

if __name__ == "__main__":
    asyncio.run(test_unification())

if __name__ == "__main__":
    asyncio.run(test_unification())

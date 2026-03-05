import json
import logging
from .schemas import CycleContext, ValidationResult
from .llm import LLMClient

# --- MJ-01: SK-VAL (Semantic Validation Layer) ---
REQUIRED_FIELDS = {
    "financiero": ["proyectos", "transacciones_recientes"],
    "legal": [], # Validamos presencia general del módulo
    "rh": []
}

async def validate_semantic(context: CycleContext) -> ValidationResult:
    """
    SK-VAL: Verifica si los datos en los módulos de Alpa SaaS son suficientes 
    para cumplir el objetivo del ciclo antes de llamar al LLM.
    """
    instruccion = context.instruccion_ceo.lower()
    empresa = context.empresa
    
    missing = []
    
    # Determinamos qué áreas son necesarias para validar
    areas_needed = []
    if any(k in instruccion for k in ["financiero", "margen", "rentabilidad", "roi", "caja"]):
        areas_needed.append("financiero")
    if any(k in instruccion for k in ["legal", "contrato", "riesgo", "cumplimiento"]):
        areas_needed.append("legal")
    if any(k in instruccion for k in ["personal", "rh", "nomina", "empleado"]):
        areas_needed.append("rh")
        
    # Si no detectamos área específica, validamos financiero por defecto (core del SaaS)
    if not areas_needed:
        areas_needed = ["financiero"]
        
    for area in areas_needed:
        # MJ-01: Fix field name mapping (Plurals/Singulars)
        field_name = f"datos_{area}"
        if area == "financiero": field_name = "datos_financieros"
        if area == "legal": field_name = "datos_legales"
        
        data_módulo = getattr(empresa, field_name, {})
        if not data_módulo:
            missing.append(f"modulo_{area}_vacio")
            continue
            
        # Validación granular de campos clave (Simulado)
        if area in REQUIRED_FIELDS:
            for field in REQUIRED_FIELDS[area]:
                if field not in data_módulo:
                    missing.append(f"{area}.{field}")

    if missing:
        return ValidationResult(
            passed=False, 
            missing=missing, 
            reason=f"SK-VAL detectó datos insuficientes en Alpa SaaS para procesar '{instruccion}'."
        )
    
    return ValidationResult(passed=True)

# --- CAPA DE ROUTING ---
INDUSTRY_ROUTING = {
    "retail": ["financiero", "rh"],
    "legal_firm": ["legal", "financiero"],
    "health": ["legal", "rh", "financiero"],
    "holding": ["financiero", "legal", "rh"]
}

async def route_agents(context: CycleContext):
    """
    MJ-04: Router Híbrido de 3 Capas
    """
    instruccion = context.instruccion_ceo.lower()
    
    # Capa 1: Keywords
    selected = set()
    if any(k in instruccion for k in ["plata", "dinero", "caja", "margen", "financiero"]):
        selected.add("financiero")
    if any(k in instruccion for k in ["contrato", "legal", "riesgo"]):
        selected.add("legal")
    if any(k in instruccion for k in ["rh", "empleado"]):
        selected.add("rh")
    
    if selected: return list(selected)
    
    # Capa 2: Industria
    industria = context.empresa.industria.lower()
    if industria in INDUSTRY_ROUTING:
        return INDUSTRY_ROUTING[industria]
    
    # Capa 3: LLM Routing (Solo en Modo Deep)
    if context.mode == "deep":
        llm = LLMClient()
        prompt = f"Basado en: '{context.instruccion_ceo}', responde SOLO un JSON list de agentes indispensables: ['financiero', 'legal', 'rh']."
        res = await llm.completion([{"role": "user", "content": prompt}])
        try:
            return json.loads(res['text'])
        except:
            pass # Fallback a financiero
            
    return ["financiero"]

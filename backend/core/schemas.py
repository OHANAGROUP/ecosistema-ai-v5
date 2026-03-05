from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from typing import List, Optional, Dict, Any
from datetime import datetime

class EmpresaSchema(BaseModel):
    id: str
    nombre: str
    industria: str
    datos_financieros: Dict[str, Any]
    datos_legales: Dict[str, Any]
    datos_rh: Dict[str, Any]
    pool_de_datos: Dict[str, Any] = Field(default_factory=dict)

class CycleContext(BaseModel):
    cycle_id: UUID = Field(default_factory=uuid4)
    tenant_id: Optional[str] = "default"
    empresa: EmpresaSchema
    instruccion_ceo: str
    mode: str = "fast" # "fast" or "deep"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
class AgentDecision(BaseModel):
    agent_id: str
    cycle_id: UUID
    decision: str
    confidence: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ValidationResult(BaseModel):
    passed: bool
    reason: Optional[str] = None
    missing: List[str] = Field(default_factory=list)

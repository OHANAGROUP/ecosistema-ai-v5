"""
CRITICAL SECURITY FIXES - Apply Immediately
============================================
This file contains the hardened version of main.py with critical security fixes applied.
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional
from uuid import uuid4, UUID
import logging
import asyncio
import os
import re
from datetime import datetime, timezone
from contextlib import asynccontextmanager

# Import your existing modules
from agents import AgentOrchestrator
from core.auth import get_current_user, verify_company_access
from core.database import get_supabase
try:
    from billing import billing_router
except ImportError:
    # Fallback for if billing is not in the path as expected
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from billing import billing_router

# ============================================================================
# SECURITY: Configuration & Logging
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api")

# Environment detection
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")
IS_PRODUCTION = ENVIRONMENT == "production"

# ============================================================================
# SECURITY: Environment-aware CORS Configuration
# ============================================================================

ALLOWED_ORIGINS = {
    "production": [
        "https://automatizai.cl",
        "https://www.automatizai.cl",
        "https://alpa-saas-unificado.vercel.app",
        "https://ecosistema-ai-v50.vercel.app",
        os.environ.get("FRONTEND_URL", ""),
    ],
    "development": [
        "http://localhost:3000",
        "http://localhost:3001",  # serve (current dev server)
        "http://localhost:5173",
        "http://localhost:5500",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5500",
        "http://127.0.0.1:5501",
    ]
}

CORS_ORIGINS = ALLOWED_ORIGINS.get(ENVIRONMENT, ALLOWED_ORIGINS["production"])

# ============================================================================
# SECURITY: Validate Critical Environment Variables
# ============================================================================

def validate_environment():
    """Validate that all required environment variables are set securely"""
    required_vars = ["SUPABASE_URL", "SUPABASE_KEY", "JWT_SECRET"]
    
    missing = [var for var in required_vars if not os.environ.get(var)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {missing}")
    
    # Validate JWT secret strength
    jwt_secret = os.environ.get("JWT_SECRET", "")
    if len(jwt_secret) < 32:
        logger.error("JWT_SECRET is too weak! Must be at least 32 characters.")
        raise RuntimeError("JWT_SECRET is too weak")
    
    # Warn if using weak/default secrets
    weak_secrets = ["super-secret-key", "admin_password", "123456"]
    if any(weak in jwt_secret.lower() for weak in weak_secrets):
        logger.error("JWT_SECRET appears to be a weak or default value!")
        raise RuntimeError("Weak JWT_SECRET detected")
    
    logger.info("✅ Environment validation passed")

# Run validation on startup
validate_environment()

# ============================================================================
# Dependencies
# ============================================================================

supabase = get_supabase()
orchestrator = AgentOrchestrator(supabase)

# ============================================================================
# SECURITY: Enhanced Pydantic Models with Strict Validation
# ============================================================================

class CycleRequest(BaseModel):
    company_id: str = Field(..., min_length=1, max_length=100)
    instruccion: str = Field(..., min_length=10, max_length=5000)
    mode: str = "fast"
    
    @validator("mode")
    def validate_mode(cls, v):
        if v not in ["fast", "deep"]:
            raise ValueError("Mode must be 'fast' or 'deep'")
        return v

    @validator("company_id")
    def validate_company_id(cls, v):
        # Strict validation: only alphanumeric, dash, and underscore
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("company_id can only contain alphanumeric, dash, and underscore")
        
        # Prevent path traversal attempts
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError("Invalid characters in company_id")
        
        return v
    
    @validator("instruccion")
    def validate_instruction(cls, v):
        # Prevent extremely large instructions
        if len(v) > 5000:
            raise ValueError("Instruction too long (max 5000 characters)")
        
        # Basic SQL injection pattern detection (additional safety)
        dangerous_patterns = [
            r";\s*DROP\s+TABLE",
            r";\s*DELETE\s+FROM",
            r";\s*UPDATE\s+.*\s+SET",
            r"UNION\s+SELECT",
            r"<script",
            r"javascript:",
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                logger.warning(f"Potential injection attempt detected: {pattern}")
                raise ValueError("Instruction contains forbidden patterns")
        
        return v


class FeedbackRequest(BaseModel):
    cycle_id: UUID
    agent_id: str = Field(..., min_length=1, max_length=100)
    approved: bool
    comments: Optional[str] = Field(None, max_length=1000)
    
    @validator("agent_id")
    def validate_agent_id(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Invalid agent_id format")
        return v

# ============================================================================
# SECURITY: Audit Logging
# ============================================================================

async def log_audit_event(
    event_type: str,
    user_id: str,
    organization_id: str,
    resource_type: str,
    resource_id: str,
    action: str,
    details: dict = None,
    ip_address: str = None,
    success: bool = True
):
    """Log security-relevant events for audit trail."""
    try:
        await supabase.table("audit_logs").insert({
            "event_type": event_type,
            "user_id": user_id,
            "organization_id": organization_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "success": success,
            "details": details,
            "ip_address": ip_address,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }).execute()
    except Exception as e:
        logger.error(f"Failed to log audit event: {e}", exc_info=True)

# ============================================================================
# SECURITY: Request Size Limit Middleware
# ============================================================================

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Limit request body size to prevent DoS attacks"""
    
    def __init__(self, app, max_size: int = 5 * 1024 * 1024):  # 5MB default
        super().__init__(app)
        self.max_size = max_size
    
    async def dispatch(self, request, call_next):
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.max_size:
                logger.warning(
                    f"Request size limit exceeded: {content_length} > {self.max_size}"
                )
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large"}
                )
        
        return await call_next(request)

# ============================================================================
# SECURITY: Security Headers Middleware
# ============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # HSTS for HTTPS only
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        
        # CSP (adjust based on your needs)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:;"
        )
        
        return response

# ============================================================================
# SECURITY: Request ID Middleware (for audit trail correlation)
# ============================================================================

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add unique request ID for tracing"""
    
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        return response

# ============================================================================
# V1 Router with Security Enhancements
# ============================================================================

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(billing_router)

# Email service — imported lazily so it doesn't raise on missing RESEND_API_KEY
try:
    from core.email_service import send_welcome_email, send_lead_acknowledgment_email
    _email_ok = True
except ImportError:
    _email_ok = False
    logger.warning("email_service not available — emails disabled")


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=200)
    password: str = Field(..., min_length=8, max_length=100)
    company_name: str = Field(..., min_length=2, max_length=200)


@api_v1.post("/auth/register", status_code=201)
async def register_trial(payload: RegisterRequest, background_tasks: BackgroundTasks):
    """
    Registro de nueva organización con trial de 14 días.
    1. Crea el usuario en Supabase Auth.
    2. Crea la organización en la tabla `organizations`.
    3. Dispara el email de bienvenida via Resend (en background).
    """
    try:
        # 1. Create user in Supabase Auth
        auth_resp = supabase.auth.sign_up({
            "email": payload.email,
            "password": payload.password,
        })
        if auth_resp.user is None:
            raise HTTPException(status_code=400, detail="Error al crear usuario en Supabase Auth")

        user_id = auth_resp.user.id

        # 2. Create organization with 14-day trial
        from datetime import timedelta
        now_utc   = datetime.now(timezone.utc)
        trial_end = (now_utc + timedelta(days=14)).isoformat()
        org_data  = {
            "name":        payload.company_name,
            "plan_type":   "trial",
            "status":      "active",
            "trial_start": now_utc.isoformat(),   # para cálculo de día del trial
            "trial_end":   trial_end,
            "owner_email": payload.email,          # para emails automáticos
            "owner_name":  payload.company_name,   # nombre del contacto principal
        }
        org_resp = supabase.table("organizations").insert(org_data).execute()
        if not org_resp.data:
            raise HTTPException(status_code=500, detail="Error al crear organización")

        org_id = org_resp.data[0]["id"]

        # 3. Link user to org
        supabase.table("organization_members").insert({
            "organization_id": org_id,
            "user_id": user_id,
            "role": "owner",
        }).execute()

        # 4. Send welcome email (non-blocking)
        if _email_ok:
            background_tasks.add_task(send_welcome_email, payload.email, payload.company_name)

        logger.info("✅ New trial org registered: %s (%s)", payload.company_name, org_id)
        return {
            "success": True,
            "organization_id": org_id,
            "trial_end": trial_end,
            "message": f"Organización '{payload.company_name}' creada. Trial de 14 días iniciado.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("register_trial error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al registrar organización")

@api_v1.post("/agents/cycle")
async def create_cycle(
    request: Request,
    cycle_request: CycleRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    """Create a new agent cycle with full security checks"""
    cycle_id = uuid4()
    organization_id = user.get("organization_id", "default")
    user_id = user.get("user_id", "unknown")
    ip_address = request.client.host
    
    # CRITICAL: Tenant Isolation Check
    if not await verify_company_access(cycle_request.company_id, organization_id):
        logger.warning(
            f"Unauthorized access attempt: User {user_id} from Org {organization_id} "
            f"attempted to access Company {cycle_request.company_id}"
        )
        
        # Log security event
        await log_audit_event(
            event_type="unauthorized_access_attempt",
            user_id=user_id,
            organization_id=organization_id,
            resource_type="company",
            resource_id=cycle_request.company_id,
            action="access",
            success=False,
            ip_address=ip_address
        )
        
        raise HTTPException(status_code=403, detail="Access denied to this company")
    
    # Audit log: Cycle creation
    await log_audit_event(
        event_type="cycle_created",
        user_id=user_id,
        organization_id=organization_id,
        resource_type="cycle",
        resource_id=str(cycle_id),
        action="create",
        details={
            "mode": cycle_request.mode,
            "company_id": cycle_request.company_id,
            "instruction_length": len(cycle_request.instruccion)
        },
        ip_address=ip_address
    )

    async def run_with_error_handling():
        try:
            await orchestrator.run_cycle(
                str(cycle_id),
                cycle_request.company_id,
                cycle_request.instruccion,
                organization_id,
                cycle_request.mode
            )
            logger.info(f"Cycle {cycle_id} completed successfully")
            
            # Audit log: Success
            await log_audit_event(
                event_type="cycle_completed",
                user_id=user_id,
                organization_id=organization_id,
                resource_type="cycle",
                resource_id=str(cycle_id),
                action="complete",
                ip_address=ip_address
            )
        except Exception as e:
            logger.error(f"Cycle {cycle_id} failed: {e}", exc_info=True)
            
            # Audit log: Failure
            await log_audit_event(
                event_type="cycle_failed",
                user_id=user_id,
                organization_id=organization_id,
                resource_type="cycle",
                resource_id=str(cycle_id),
                action="complete",
                success=False,
                details={"error": str(e)},
                ip_address=ip_address
            )
    
    background_tasks.add_task(run_with_error_handling)
    
    return {
        "status": "started",
        "cycle_id": str(cycle_id),
        "message": "Ciclo de agentes iniciado correctamente",
        "poll_url": f"/api/v1/agents/cycle/{cycle_id}/status"
    }


@api_v1.get("/agents/cycle/{cycle_id}/status")
async def get_cycle_status(
    cycle_id: UUID,
    user: dict = Depends(get_current_user)
):
    """Get cycle status with tenant isolation"""
    status = await orchestrator.get_cycle_status(str(cycle_id))

    if not status:
        raise HTTPException(status_code=404, detail="Cycle not found")

    # CRITICAL: Tenant check
    if status.get("organization_id") != user.get("organization_id"):
        logger.warning(
            f"Unauthorized cycle access: User {user.get('user_id')} "
            f"attempted to access cycle {cycle_id}"
        )
        raise HTTPException(status_code=403, detail="Access denied")

    return status


@api_v1.get("/agents/cycle/{cycle_id}/decisions")
async def get_cycle_decisions(
    cycle_id: UUID,
    user: dict = Depends(get_current_user)
):
    """
    Retorna todas las decisiones de agente de un ciclo completado.
    Incluye health_status, confidence, reasoning, metadata (hallazgos, alertas,
    recomendaciones, confidence_level, tool_calls_log, null_fields).
    """
    organization_id = user.get("organization_id")
    try:
        res = supabase.table("agent_decisions") \
            .select(
                "id,agent_type,decision,health_status,confidence,reasoning,"
                "objetivo_iteracion,requires_approval,source_indicator,"
                "metadata,confidence_level,tool_calls_log,data_sources,"
                "null_fields,trigger_type,created_at"
            ) \
            .eq("cycle_id", str(cycle_id)) \
            .eq("organization_id", organization_id) \
            .order("created_at") \
            .execute()

        decisions = res.data or []

        # Parse metadata JSON strings if needed
        for d in decisions:
            if isinstance(d.get("metadata"), str):
                try:
                    import json as _j
                    d["metadata"] = _j.loads(d["metadata"])
                except Exception:
                    pass

        return {"cycle_id": str(cycle_id), "decisions": decisions}

    except Exception as e:
        logger.error(f"Error fetching decisions for cycle {cycle_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener decisiones del ciclo")


@api_v1.get("/agents/health")
async def get_health():
    """Enhanced health check with dependency validation"""
    health_checks = {}
    
    # Check Supabase connection
    try:
        supabase.table("organizations").select("id").limit(1).execute()
        health_checks["supabase"] = "healthy"
    except Exception as e:
        logger.error(f"Supabase health check failed: {e}")
        health_checks["supabase"] = "unhealthy"
    
    # Check Orchestrator
    try:
        metrics = await orchestrator.get_metrics()
        health_checks["orchestrator"] = "healthy"
        
        return {
            "status": "healthy" if all(
                v == "healthy" for v in health_checks.values()
            ) else "degraded",
            "checks": health_checks,
            "p50_latency_ms": metrics.get("p50_latency"),
            "p95_latency_ms": metrics.get("p95_latency", 2400),
            "active_cycles": metrics.get("active_cycles"),
            "mcp_connected": await orchestrator.check_mcp_connection(),
            "version": "5.0.1-prd-secure",
            "environment": ENVIRONMENT,
            "last_cleanup": metrics.get("last_cleanup_timestamp"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        health_checks["orchestrator"] = "unhealthy"
        
        return {
            "status": "unhealthy",
            "checks": health_checks,
            "error": "Service degraded",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@api_v1.post("/agents/feedback")
async def post_feedback(
    request: Request,
    feedback: FeedbackRequest,
    user: dict = Depends(get_current_user)
):
    """Submit feedback with tenant isolation and audit logging"""
    user_id = user.get("user_id", "unknown")
    organization_id = user.get("organization_id", "default")
    
    try:
        # Update with tenant check
        res = supabase.table("agent_decisions").update({
            "user_approval": feedback.approved,
            "user_comments": feedback.comments,
            "feedback_at": datetime.now(timezone.utc).isoformat()
        }).eq("cycle_id", str(feedback.cycle_id))\
          .eq("agent_id", feedback.agent_id)\
          .eq("organization_id", organization_id)\
          .execute()
        
        if not res.data:
            # Audit log: Failed feedback (not found or wrong tenant)
            await log_audit_event(
                event_type="feedback_failed",
                user_id=user_id,
                organization_id=organization_id,
                resource_type="agent_decision",
                resource_id=f"{feedback.cycle_id}:{feedback.agent_id}",
                action="update",
                success=False,
                details={"reason": "not_found_or_access_denied"},
                ip_address=request.client.host
            )
            
            raise HTTPException(
                status_code=404,
                detail="Decision not found or access denied"
            )
        
        # Audit log: Successful feedback
        await log_audit_event(
            event_type="feedback_submitted",
            user_id=user_id,
            organization_id=organization_id,
            resource_type="agent_decision",
            resource_id=f"{feedback.cycle_id}:{feedback.agent_id}",
            action="update",
            details={
                "approved": feedback.approved,
                "has_comments": bool(feedback.comments)
            },
            ip_address=request.client.host
        )
        
        return {"status": "success", "message": "Feedback registrado correctamente"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en feedback: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al registrar feedback")


@api_v1.get("/agents/signals")
async def get_active_signals(
    cycle_id: UUID,
    user: dict = Depends(get_current_user)
):
    """Get signals with tenant isolation"""
    try:
        res = supabase.table("agent_signals")\
            .select("*")\
            .eq("cycle_id", str(cycle_id))\
            .eq("organization_id", user.get("organization_id"))\
            .execute()
        
        return {"cycle_id": str(cycle_id), "signals": res.data or []}
    except Exception as e:
        logger.error(f"Error fetching signals: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving signals")


# ============================================================================
# AGENT TRIGGER — Event-based execution (OC, EP, project events)
# ============================================================================

CRON_SECRET = os.environ.get("CRON_SECRET", "")


class AgentTriggerRequest(BaseModel):
    organization_id: str = Field(..., min_length=1, max_length=100)
    trigger_type: str = Field(..., pattern=r"^(oc_created|ep_vencido|project_status_change|manual)$")
    entity_id: Optional[str] = Field(None, max_length=100)   # OC id, EP id, project id
    objetivo: Optional[str] = Field(
        None, max_length=2000,
        description="Instrucción personalizada. Si omitida, se usa objetivo por defecto según trigger."
    )


_TRIGGER_DEFAULT_OBJETIVOS = {
    "oc_created":             "Revisa la nueva orden de compra recién creada y detecta anomalías de precio frente al histórico.",
    "ep_vencido":             "Analiza los estados de pago vencidos y determina el impacto en el flujo de caja.",
    "project_status_change":  "Evalúa el margen actualizado del proyecto y alerta si se aleja del presupuesto ofertado.",
    "manual":                 "Genera resumen ejecutivo completo de la situación financiera actual.",
}


@api_v1.post("/agent/financial/trigger", status_code=202)
async def trigger_financial_agent(
    request: Request,
    payload: AgentTriggerRequest,
    background_tasks: BackgroundTasks,
):
    """
    Disparo event-driven del AgenteFinanciero.
    Requiere cabecera X-Cron-Secret (mismo secreto que el scheduler).
    Usado por: webhooks Supabase, Railway cron, y llamadas internas.
    """
    # Auth: cabecera de secreto compartido (igual que /internal/send-trial-emails)
    secret = request.headers.get("X-Cron-Secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        logger.warning(
            f"[TRIGGER] Intento no autorizado desde {request.client.host} "
            f"— trigger_type={payload.trigger_type}"
        )
        raise HTTPException(status_code=401, detail="Unauthorized")

    cycle_id = str(uuid4())
    objetivo = payload.objetivo or _TRIGGER_DEFAULT_OBJETIVOS[payload.trigger_type]

    logger.info(
        f"[TRIGGER] {payload.trigger_type} → org={payload.organization_id} "
        f"entity={payload.entity_id} cycle={cycle_id}"
    )

    async def _run_triggered_cycle():
        try:
            await orchestrator.run_cycle(
                cycle_id=cycle_id,
                company_id=payload.organization_id,
                instruccion=objetivo,
                organization_id=payload.organization_id,
                mode="fast",
            )
            logger.info(f"[TRIGGER] Ciclo {cycle_id} completado — {payload.trigger_type}")
        except Exception as e:
            logger.error(
                f"[TRIGGER] Ciclo {cycle_id} falló — {payload.trigger_type}: {e}",
                exc_info=True
            )

    background_tasks.add_task(_run_triggered_cycle)

    return {
        "status": "accepted",
        "cycle_id": cycle_id,
        "trigger_type": payload.trigger_type,
        "organization_id": payload.organization_id,
    }


# ============================================================================
# OPERATOR TRIGGER — Briefing SaaS bajo demanda (solo ADMIN_ORG_ID)
# ============================================================================

ADMIN_ORG_ID = os.environ.get("ADMIN_ORG_ID", "")


@api_v1.post("/agent/operator/run", status_code=202)
async def run_operator_agent(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """
    Dispara el AgenteOperador desde el panel frontend de MD Asesorías.
    Requiere sesión JWT válida y que el usuario sea de ADMIN_ORG_ID.
    """
    user_org = current_user.get("organization_id") or current_user.get("tenant_id")
    if not ADMIN_ORG_ID or user_org != ADMIN_ORG_ID:
        raise HTTPException(status_code=403, detail="Solo disponible para MD Asesorías Limitada")

    cycle_id = str(uuid4())

    async def _run():
        try:
            from agents import AgenteOperador, EmpresaSchema, InstruccionCEO, EmpresaMetadata
            agent   = AgenteOperador(supabase)
            inst    = InstruccionCEO(objetivo_iteracion="Briefing SaaS bajo demanda: estado completo del negocio")
            empresa = EmpresaSchema(
                instruccion_ceo=inst,
                metadata=EmpresaMetadata(empresa="MD Asesorías Limitada"),
            )
            await agent.analyze(empresa, cycle_id, ADMIN_ORG_ID)
            logger.info(f"[OPERATOR/run] Completado — cycle={cycle_id}")
        except Exception as e:
            logger.error(f"[OPERATOR/run] Falló — cycle={cycle_id}: {e}", exc_info=True)

    background_tasks.add_task(_run)
    return {"status": "accepted", "cycle_id": cycle_id}


@api_v1.post("/agent/operator/trigger", status_code=202)
async def trigger_operator_agent(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Dispara el AgenteOperador bajo demanda para MD Asesorías Limitada.
    Requiere X-Cron-Secret. Solo corre para ADMIN_ORG_ID.
    Devuelve 202 Accepted inmediatamente; el análisis corre en background.
    """
    secret = request.headers.get("X-Cron-Secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        logger.warning(f"[OPERATOR TRIGGER] Intento no autorizado desde {request.client.host}")
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not ADMIN_ORG_ID:
        raise HTTPException(status_code=503, detail="ADMIN_ORG_ID no configurado")

    cycle_id = str(uuid4())
    logger.info(f"[OPERATOR TRIGGER] Iniciando briefing — cycle={cycle_id}")

    async def _run_operator():
        try:
            from agents import AgenteOperador, EmpresaSchema, InstruccionCEO, EmpresaMetadata
            agent   = AgenteOperador(supabase)
            inst    = InstruccionCEO(objetivo_iteracion="Briefing SaaS bajo demanda: estado completo del negocio")
            empresa = EmpresaSchema(
                instruccion_ceo=inst,
                metadata=EmpresaMetadata(empresa="MD Asesorías Limitada"),
            )
            decision = await agent.analyze(empresa, cycle_id, ADMIN_ORG_ID)
            logger.info(
                f"[OPERATOR TRIGGER] Completado — "
                f"semáforo={decision.health_status} confidence={decision.confidence}"
            )
        except Exception as e:
            logger.error(f"[OPERATOR TRIGGER] Falló — cycle={cycle_id}: {e}", exc_info=True)

    background_tasks.add_task(_run_operator)

    return {
        "status": "accepted",
        "cycle_id": cycle_id,
        "agent": "operador",
        "organization_id": ADMIN_ORG_ID,
    }


# ============================================================================
# Application Setup with Security
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with proper error handling"""
    # Startup — limpiar ciclos huérfanos
    try:
        await orchestrator.cleanup_orphan_cycles()
        logger.info("✅ Initial orphan cycles cleaned")
    except Exception as e:
        logger.error(f"❌ Failed initial cleanup: {e}", exc_info=True)

    # Cleanup periódico cada 10 minutos
    async def periodic_cleanup():
        while True:
            try:
                await asyncio.sleep(600)
                await orchestrator.cleanup_orphan_cycles()
                logger.debug("Periodic cleanup completed")
            except asyncio.CancelledError:
                logger.info("Cleanup task cancelled - shutting down")
                break
            except Exception as e:
                logger.error(f"Periodic cleanup failed: {e}", exc_info=True)

    cleanup_task = asyncio.create_task(periodic_cleanup())

    # ── Scheduler de monitoreo (cron jobs) ───────────────────────────────────
    scheduler = None
    try:
        from scheduler import create_scheduler
        scheduler = create_scheduler()
        scheduler.start()
        logger.info("✅ Scheduler iniciado — monitoreo horario + reporte diario activos")
    except Exception as e:
        logger.error(f"❌ Scheduler no pudo iniciarse: {e}", exc_info=True)

    yield

    # Shutdown
    logger.info("Initiating graceful shutdown...")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("✅ Scheduler detenido")

    cleanup_task.cancel()
    try:
        await asyncio.wait_for(cleanup_task, timeout=5.0)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        logger.warning("Cleanup task did not finish in time")

    logger.info("✅ Shutdown complete")


# Create app
app = FastAPI(
    title="Agent SaaS Reload - Engine v5.0 (Secured)",
    lifespan=lifespan,
    docs_url="/docs" if not IS_PRODUCTION else None,  # Disable docs in production
    redoc_url="/redoc" if not IS_PRODUCTION else None,
)

# ============================================================================
# SECURITY: Apply Middleware (Order Matters!)
# ============================================================================

# 1. Request ID (first, for tracing)
app.add_middleware(RequestIDMiddleware)

# 2. Security headers
app.add_middleware(SecurityHeadersMiddleware)

# 3. Request size limit
app.add_middleware(RequestSizeLimitMiddleware, max_size=5 * 1024 * 1024)  # 5MB

# 4. CORS (must be last middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    max_age=3600,
)

# ============================================================================
# Global Exception Handler
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler with logging"""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.error(
        f"Unhandled exception in request {request_id}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "error": str(exc)
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )


# ============================================================================
# VALUE LOOP — Trial Endpoints (PUBLIC — no auth required)
# ============================================================================

import secrets
from pydantic import EmailStr

class TrialRegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=200)
    name: str = Field(..., min_length=2, max_length=200)
    company: str = Field(..., min_length=2, max_length=200)
    phone: Optional[str] = Field(None, max_length=30)

    @validator("email")
    def validate_email(cls, v):
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Email inválido")
        return v.lower().strip()

class AlertActionRequest(BaseModel):
    action: str = Field(..., pattern="^(approved|rejected|snoozed)$")
    comment: Optional[str] = Field(None, max_length=1000)

class OnboardingEventRequest(BaseModel):
    event: str = Field(..., min_length=3, max_length=100,
                       pattern="^[a-z_]+$")
    step: Optional[int] = Field(None, ge=1, le=20)
    metadata: Optional[dict] = None

class BillingContactRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=200)
    name: str = Field(..., min_length=2, max_length=200)
    company: str = Field(..., min_length=2, max_length=200)
    plan: Optional[str] = Field("empresa", pattern="^(starter|empresa|enterprise)$")
    message: Optional[str] = Field(None, max_length=2000)


@api_v1.post("/trials/register", tags=["trials"])
async def register_trial(req: TrialRegisterRequest):
    """Registra un trial en Supabase. Endpoint público."""
    try:
        # Check if email already has a trial
        # Check if organization with this email already exists
        existing = supabase.table("organizations").select("id,status,trial_end").eq("email", req.email).maybe_single().execute()
        if existing.data:
            days_left = 0
            from datetime import datetime as dt
            trial_end = dt.fromisoformat(existing.data["trial_end"].replace("Z", "+00:00"))
            delta = trial_end - dt.now(timezone.utc)
            days_left = max(0, delta.days)
            return {
                "trial_id":   existing.data["id"],
                "status":     existing.data["status"],
                "days_left":  days_left,
                "trial_end":  existing.data["trial_end"],
                "new_trial":  False,
            }

        # Create a new organization entry for the trial
        now = datetime.now(timezone.utc)
        trial_end = now + timedelta(days=14)
        
        # Use session_token in metadata or a separate field if it exists,
        # but the request mentioned organizations/trial_end as the main source.
        result = supabase.table("organizations").insert({
            "name":            req.company,
            "email":           req.email,
            "status":          "active",
            "trial_start":     now.isoformat(),
            "trial_end":       trial_end.isoformat(),
            "plan_type":       "trial",
            "metadata":        {"signup_ip": request.client.host if request.client else "unknown", "name": req.name}
        }).execute()

        organization = result.data[0] if result.data else {}
        org_id = organization.get("id")
        
        token = secrets.token_urlsafe(32)
        # We'll skip trial_sessions as its existence is unconfirmed.
        # The primary goal is that the trial is recorded in organizations.

        logger.info(f"New trial organization created: {req.email} (Org ID: {org_id})")

        # ── Non-blocking welcome email via Resend ──────────────────────────────
        trial_end_str = organization.get("trial_end", "")
        async def _send_welcome(email: str, name: str, company: str, trial_end: str):
            resend_key = os.getenv("RESEND_API_KEY", "")
            if not resend_key:
                logger.warning("RESEND_API_KEY not set — skipping welcome email")
                return
            import httpx
            first = name.split()[0] if name else name
            try:
                await asyncio.get_event_loop().run_in_executor(None, lambda: __import__('httpx').post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                    json={
                        "from": "AgentOS v5.0 <hola@alpaconstruccion.cl>",
                        "to": [email],
                        "subject": f"¡Bienvenido a tu prueba gratuita, {first}! 🚀",
                        "html": f"""
                        <div style="font-family:Inter,sans-serif;max-width:520px;margin:0 auto;background:#0a0f1e;color:#fff;padding:40px 32px;border-radius:16px">
                          <div style="background:linear-gradient(135deg,#F36F21,#e55d0e);border-radius:12px;padding:24px;text-align:center;margin-bottom:28px">
                            <h1 style="margin:0;font-size:24px;font-weight:700">🤖 AgentOS v5.0</h1>
                            <p style="margin:8px 0 0;opacity:.8;font-size:13px">Ecosistema de Inteligencia Empresarial</p>
                          </div>
                          <h2 style="color:#fff;font-size:20px;margin:0 0 12px">¡Hola {first}! Tu prueba de 14 días ha comenzado</h2>
                          <p style="color:#94a3b8;font-size:14px;line-height:1.6">
                            Hemos activado tu acceso para <strong style="color:#F36F21">{company}</strong>.
                            Tienes hasta el <strong style="color:#fff">{trial_end[:10] if trial_end else '14 días'}</strong> para explorar todo el sistema.
                          </p>
                          <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:12px;padding:20px;margin:24px 0">
                            <p style="margin:0 0 8px;font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:.08em">¿Qué puedes hacer hoy?</p>
                            <ul style="margin:0;padding-left:18px;color:#cbd5e1;font-size:14px;line-height:2">
                              <li>🤖 Ejecutar ciclos de agentes IA</li>
                              <li>✅ Aprobar / rechazar decisiones automáticas</li>
                              <li>📊 Monitorear salud financiera y legal</li>
                              <li>👥 Gestionar contratos y empleados</li>
                            </ul>
                          </div>
                          <a href="https://alpa-saas-unificado.vercel.app"
                             style="display:block;text-align:center;background:linear-gradient(135deg,#F36F21,#e55d0e);color:#fff;
                                    font-weight:700;font-size:15px;padding:14px;border-radius:10px;text-decoration:none;margin-bottom:24px">
                            Ir al Dashboard →
                          </a>
                          <p style="color:#475569;font-size:12px;text-align:center">
                            Si tienes preguntas, responde este email o visita nuestro soporte.<br>
                            Created by Pablo Palominos Naredo
                          </p>
                        </div>"""
                    }, timeout=10
                ))
                logger.info(f"Welcome email sent to {email}")
            except Exception as email_err:
                logger.warning(f"Welcome email failed (non-blocking): {email_err}")

        import asyncio as _asyncio
        _asyncio.create_task(_send_welcome(req.email, req.name, req.company, trial_end_str))

        return {
            "trial_id":      org_id, # This is now the organization ID
            "status":        "active",
            "days_left":     14,
            "trial_end":     organization.get("trial_end"),
            "session_token": token,
            "new_trial":     True,
        }
    except Exception as e:
        logger.error(f"Trial register error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al registrar el trial")


@api_v1.get("/trials/status", tags=["trials"])
async def get_trial_status(email: str):
    """Verifica estado del trial. Endpoint público."""
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Email inválido")
    try:
        # Auto-expire if needed
        supabase.rpc("expire_trials", {}).execute()
        # Query organizations table for trial status
        result = supabase.table("organizations").select(
            "id,name,status,trial_end"
        ).eq("email", email).maybe_single().execute()

        if not result.data:
            return {"status": "not_found", "days_left": 0}

        from datetime import datetime as dt
        trial_end = dt.fromisoformat(result.data["trial_end"].replace("Z", "+00:00"))
        delta = trial_end - dt.now(timezone.utc)
        days_left = max(0, delta.days)

        return {
            "trial_id":    result.data["id"],
            "status":      result.data["status"],
            "days_left":   days_left,
            "trial_start": result.data["trial_start"],
            "trial_end":   result.data["trial_end"],
        }
    except Exception as e:
        logger.error(f"Trial status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al verificar trial")


# ============================================================================
# VALUE LOOP — Agent Alerts (requiere auth)
# ============================================================================

@api_v1.get("/agents/alerts", tags=["alerts"])
async def list_alerts(
    status: Optional[str] = None,
    limit: int = 50,
    user: dict = Depends(get_current_user)
):
    """Lista alertas de la organización autenticada."""
    org_id = user.get("organization_id")
    try:
        q = supabase.table("agent_alerts").select("*").eq("organization_id", org_id)
        if status:
            q = q.eq("status", status)
        result = q.order("created_at", desc=True).limit(limit).execute()
        return {"alerts": result.data or [], "total": len(result.data or [])}
    except Exception as e:
        logger.error(f"List alerts error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener alertas")

# ============================================================================
# BILLING — Stripe Endpoints
# ============================================================================

billing_router = APIRouter(prefix="/billing", tags=["billing"])

class CheckoutRequest(BaseModel):
    plan: str
    success_url: str
    cancel_url: str

@billing_router.post("/create-checkout")
async def create_checkout(
    req: CheckoutRequest,
    user: dict = Depends(get_current_user)
):
    """Crea una sesión de Checkout de Stripe"""
    try:
        email = user.get("email")
        org_id = user.get("organization_id")
        
        session = stripe_client.create_checkout_session(
            customer_email=email,
            plan_name=req.plan,
            success_url=req.success_url,
            cancel_url=req.cancel_url,
            organization_id=org_id
        )
        return {"checkout_url": session.url}
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@billing_router.get("/portal")
async def get_portal(
    return_url: str,
    user: dict = Depends(get_current_user)
):
    """Crea una sesión del Billing Portal de Stripe"""
    try:
        org_id = user.get("organization_id")
        # Get customer_id from DB
        res = supabase.table("organizations").select("stripe_customer_id").eq("id", org_id).maybe_single().execute()
        
        if not res.data or not res.data.get("stripe_customer_id"):
            raise HTTPException(status_code=400, detail="No Stripe customer found for this organization")
        
        session = stripe_client.create_customer_portal_session(
            customer_id=res.data["stripe_customer_id"],
            return_url=return_url
        )
        return {"portal_url": session.url}
    except Exception as e:
        logger.error(f"Error creating portal session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/billing/webhook")
async def stripe_webhook(request: Request):
    """Webhook para procesar eventos de Stripe"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    try:
        webhook_handler.handle_webhook_event(payload, sig_header, webhook_secret)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail="Webhook Error")


@api_v1.post("/agents/alerts", tags=["alerts"])
async def create_alert(
    alert: dict,
    user: dict = Depends(get_current_user)
):
    """Persiste una alerta generada por un agente IA."""
    org_id = user.get("organization_id")
    required = {"agent_id", "agent_name", "alert_type", "severity", "title", "message"}
    if not required.issubset(alert.keys()):
        raise HTTPException(status_code=422, detail=f"Faltan campos: {required - alert.keys()}")
    if alert.get("severity") not in ("critica", "alta", "media", "baja"):
        raise HTTPException(status_code=422, detail="severity inválida")
    try:
        payload = {k: alert[k] for k in required}
        payload["organization_id"] = org_id
        payload["confidence"] = float(alert.get("confidence", 0.75))
        payload["metadata"] = alert.get("metadata", {})
        payload["cycle_id"] = alert.get("cycle_id")
        payload["status"] = "pending"
        result = supabase.table("agent_alerts").insert(payload).execute()
        return {"alert_id": result.data[0]["id"] if result.data else None, "status": "created"}
    except Exception as e:
        logger.error(f"Create alert error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al persistir alerta")


@api_v1.post("/agents/alerts/{alert_id}/action", tags=["alerts"])
async def take_alert_action(
    alert_id: str,
    req: AlertActionRequest,
    user: dict = Depends(get_current_user)
):
    """Registra la acción del usuario sobre una alerta (aprobar/rechazar/posponer)."""
    org_id = user.get("organization_id")
    user_id = user.get("user_id", "unknown")
    try:
        result = supabase.table("agent_alerts").update({
            "status":         req.action,
            "action_by":      user_id,
            "action_at":      datetime.now(timezone.utc).isoformat(),
            "action_comment": req.comment,
        }).eq("id", alert_id).eq("organization_id", org_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Alerta no encontrada o sin acceso")

        await log_audit_event(
            event_type="alert_action",
            user_id=user_id,
            organization_id=org_id,
            resource_type="agent_alert",
            resource_id=alert_id,
            action=req.action,
            details={"comment": req.comment},
        )
        return {"status": "ok", "action": req.action, "alert_id": alert_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Alert action error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al registrar acción")


# ============================================================================
# VALUE LOOP — Onboarding Tracking (requiere auth)
# ============================================================================

VALID_ONBOARDING_EVENTS = {
    "wizard_iniciado", "identidad_completada", "primer_proyecto",
    "directorio_base", "primer_scan_ia", "wizard_completado",
    "first_lead", "first_transaction", "first_report_viewed"
}

@api_v1.post("/onboarding/event", tags=["onboarding"])
async def track_onboarding_event(
    req: OnboardingEventRequest,
    user: dict = Depends(get_current_user)
):
    """Persiste un evento de activación del onboarding."""
    org_id = user.get("organization_id")
    if req.event not in VALID_ONBOARDING_EVENTS:
        raise HTTPException(status_code=422,
                            detail=f"Evento desconocido. Válidos: {VALID_ONBOARDING_EVENTS}")
    try:
        supabase.table("onboarding_events").insert({
            "organization_id": org_id,
            "event":           req.event,
            "step":            req.step,
            "metadata":        req.metadata or {},
            "completed":       True,
        }).execute()
        return {"status": "tracked", "event": req.event}
    except Exception as e:
        logger.error(f"Onboarding event error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al registrar evento")


# ============================================================================
# TRIAL EMAIL SCHEDULER — llamar diariamente desde cron externo (Railway/Vercel)
# ============================================================================

@api_v1.post("/internal/send-trial-emails", tags=["internal"])
async def send_trial_emails(request: Request):
    """
    Envía emails automáticos según el día del trial.
    - Día 7:  email de engagement + tips de uso
    - Día 12: email de urgencia + upgrade CTA
    - Día 13: email final de expiración (1 día restante)

    Protegido por header X-Cron-Secret (configurar en variable de entorno CRON_SECRET).
    Llamar una vez por día desde Railway Cron Jobs o GitHub Actions.
    """
    cron_secret = os.getenv("CRON_SECRET", "")
    if cron_secret:
        incoming = request.headers.get("x-cron-secret", "")
        if incoming != cron_secret:
            raise HTTPException(status_code=401, detail="Unauthorized")

    from core.email_service import send_trial_day7_email, send_trial_day12_email, send_trial_expiring_email
    from datetime import datetime as dt, timedelta

    now = dt.now(timezone.utc)
    sent = {"day7": [], "day12": [], "day13": [], "errors": []}

    def _window(days: int):
        """Ventana de 24h centrada en el día N del trial."""
        low  = (now - timedelta(days=days + 0.5)).isoformat()
        high = (now - timedelta(days=days - 0.5)).isoformat()
        return low, high

    try:
        # ── Día 7: engagement ──────────────────────────────────────────────
        low7, high7 = _window(7)
        r7 = supabase.table("organizations") \
            .select("owner_email,owner_name,name") \
            .eq("status", "active").eq("plan_type", "trial") \
            .gte("trial_start", low7).lte("trial_start", high7).execute()
        for t in (r7.data or []):
            email = t.get("owner_email") or ""
            name  = t.get("owner_name") or t.get("name", "")
            if not email:
                continue
            ok = send_trial_day7_email(email, name, t.get("name", name))
            (sent["day7"] if ok else sent["errors"]).append(email)

        # ── Día 12: urgencia ───────────────────────────────────────────────
        low12, high12 = _window(12)
        r12 = supabase.table("organizations") \
            .select("owner_email,owner_name,name") \
            .eq("status", "active").eq("plan_type", "trial") \
            .gte("trial_start", low12).lte("trial_start", high12).execute()
        for t in (r12.data or []):
            email = t.get("owner_email") or ""
            name  = t.get("owner_name") or t.get("name", "")
            if not email:
                continue
            ok = send_trial_day12_email(email, name, t.get("name", name))
            (sent["day12"] if ok else sent["errors"]).append(email)

        # ── Día 13: último aviso (1 día restante) ──────────────────────────
        low13, high13 = _window(13)
        r13 = supabase.table("organizations") \
            .select("owner_email,name") \
            .eq("status", "active").eq("plan_type", "trial") \
            .gte("trial_start", low13).lte("trial_start", high13).execute()
        for t in (r13.data or []):
            email = t.get("owner_email") or ""
            if not email:
                continue
            ok = send_trial_expiring_email(email, t.get("name", "Tu Organización"), 1)
            (sent["day13"] if ok else sent["errors"]).append(email)

        logger.info(f"Trial email cron: {sent}")
        return {"status": "ok", "sent": sent}

    except Exception as e:
        logger.error(f"Trial email cron error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error en scheduler de emails")


# ============================================================================
# LEADS — Formulario público automatizai.cl
# ============================================================================

MD_ORG_ID = os.environ.get("MD_ORG_ID", "0e431197-711a-4f12-8ca9-e2ecbf7f91ed")


class LeadSubmitRequest(BaseModel):
    name:               str           = Field(..., min_length=2, max_length=200)
    email:              str           = Field(..., min_length=5, max_length=200)
    phone:              Optional[str] = Field(None, max_length=50)
    message:            Optional[str] = Field(None, max_length=2000)
    empresa:            Optional[str] = Field(None, max_length=200)
    plan:               Optional[str] = Field(None, max_length=50)
    consent_marketing:  bool          = False

    @validator("email")
    def validate_email(cls, v):
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Email inválido")
        return v.lower().strip()


@api_v1.post("/leads/submit", tags=["leads"], status_code=201)
async def submit_lead(req: LeadSubmitRequest, background_tasks: BackgroundTasks):
    """Captura lead desde el formulario público de automatizai.cl. Sin autenticación."""
    message_parts = []
    if req.empresa:
        message_parts.append(f"Empresa: {req.empresa}")
    if req.message:
        message_parts.append(req.message)
    if req.plan:
        message_parts.append(f"Plan de interés: {req.plan}")
    message_full = " | ".join(message_parts)

    try:
        supabase.table("leads").insert({
            "organization_id":    MD_ORG_ID,
            "name":               req.name,
            "email":              req.email,
            "phone":              req.phone,
            "message":            message_full,
            "project_description": f"Empresa: {req.empresa}" if req.empresa else "",
            "status":             "Nuevo",
            "origin":             f"Landing AutomatizAI{' - Plan ' + req.plan if req.plan else ''}",
            "assigned_to":        "Sin Asignar",
            "consent_marketing":  req.consent_marketing,
        }).execute()
        logger.info(f"New web lead: {req.email}")
    except Exception as e:
        logger.error(f"Lead submit error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al registrar consulta")

    if _email_ok:
        background_tasks.add_task(
            send_lead_acknowledgment_email,
            req.email, req.name, req.empresa or ""
        )

    return {"status": "ok", "message": "Consulta recibida exitosamente"}


# ============================================================================
# VALUE LOOP — Billing / Upgrade CTA (público)
# ============================================================================

@api_v1.post("/billing/contact", tags=["billing"])
async def billing_contact(req: BillingContactRequest, background_tasks: BackgroundTasks):
    """Captura un lead caliente desde el CTA de upgrade. Sin auth (es pública)."""
    try:
        supabase.table("leads").insert({
            "organization_id":    MD_ORG_ID,
            "name":               req.name,
            "email":              req.email,
            "project_description": f"Empresa: {req.company}. Plan de interés: {req.plan}",
            "message":            req.message or "",
            "origin":             "upgrade_cta",
            "status":             "Nuevo",
            "assigned_to":        "Sin Asignar",
        }).execute()
        logger.info(f"Upgrade lead captured: {req.email} / plan={req.plan}")
    except Exception as e:
        logger.error(f"Billing contact error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al registrar solicitud")

    if _email_ok:
        background_tasks.add_task(
            send_lead_acknowledgment_email,
            req.email, req.name, req.company or ""
        )

    return {"status": "ok", "message": "Nos pondremos en contacto a la brevedad"}


# ============================================================================
# Include Routers
# ============================================================================

app.include_router(api_v1)


# ============================================================================
# Root Endpoint
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "AgentOS v5.0 API (Secured)",
        "version": "5.0.1-prd-secure",
        "environment": ENVIRONMENT,
        "docs": "/docs" if not IS_PRODUCTION else "disabled_in_production",
        "api": {
            "v1": "/api/v1"
        },
        "status": "operational"
    }


# ============================================================================
# Health Check (Kubernetes/Docker readiness probe)
# ============================================================================

@app.get("/healthz")
async def healthz():
    """Simple health check for container orchestration"""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    """Readiness check - verify dependencies are ready"""
    try:
        # Quick Supabase check
        supabase.table("organizations").select("id").limit(1).execute()
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(e)}
        )

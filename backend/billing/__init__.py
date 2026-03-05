"""
billing/__init__.py
===================
APIRouter de facturación Stripe — ALPA SaaS v5.0

Endpoints expuestos:
    POST /api/v1/billing/create-checkout  → Crea una Stripe Checkout Session
    POST /api/v1/billing/webhook          → Procesa eventos de Stripe (firma verificada)
    GET  /api/v1/billing/portal           → Crea una sesión de Customer Portal
    GET  /api/v1/billing/plans            → Lista los planes disponibles (público)
"""

import os
import logging
import stripe
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional

from core.auth import get_current_user
from billing.stripe_client import create_checkout_session, create_customer_portal_session
from billing.webhook_handler import handle_webhook_event
from billing.plans import PLANS, get_price_id

logger = logging.getLogger("billing")

STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3001")

billing_router = APIRouter(prefix="/billing", tags=["Billing"])


# ── Request Models ─────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    plan: str = Field(..., description="Plan slug: starter | empresa | enterprise")
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@billing_router.get("/plans")
async def list_plans():
    """Lista todos los planes disponibles (público, sin auth)."""
    return {
        "plans": [
            {
                "slug": slug,
                "name": p["name"],
                "amount_uf": p["amount_uf"],
                "features": p["features"],
                "available": "placeholder" not in p["price_id"],
            }
            for slug, p in PLANS.items()
        ]
    }


@billing_router.post("/create-checkout")
async def create_checkout(
    body: CheckoutRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Crea una sesión de Stripe Checkout para suscripción.
    Devuelve la URL de pago para redirigir al usuario.
    """
    if not os.environ.get("STRIPE_SECRET_KEY"):
        raise HTTPException(
            status_code=503,
            detail="Stripe no está configurado. Contacta al administrador."
        )

    # Enterprise → no va a Stripe, va a ventas
    if body.plan.lower() == "enterprise":
        return {"checkout_url": f"mailto:ventas@alpa.cl?subject=Enterprise+Plan+-+{current_user.get('company', '')}"}

    try:
        price_id = get_price_id(body.plan)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    org_id = current_user.get("organization_id") or current_user.get("tenant_id")
    email = current_user.get("email", "")

    success_url = body.success_url or f"{FRONTEND_URL}/index.html?payment=success&plan={body.plan}"
    cancel_url = body.cancel_url or f"{FRONTEND_URL}/upgrade.html?payment=cancel"

    try:
        session = create_checkout_session(
            customer_email=email,
            plan_name=body.plan,
            success_url=success_url,
            cancel_url=cancel_url,
            organization_id=str(org_id) if org_id else "",
        )
        logger.info("Checkout session created: %s for org %s plan %s", session.id, org_id, body.plan)
        return {"checkout_url": session.url, "session_id": session.id}

    except stripe.error.InvalidRequestError as e:
        logger.error("Stripe invalid request: %s", e)
        raise HTTPException(status_code=400, detail=f"Error de Stripe: {e.user_message or str(e)}")
    except Exception as e:
        logger.error("Checkout error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error al crear sesión de pago")


@billing_router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Recibe y procesa eventos de Stripe (checkout.session.completed, etc.).
    La firma del webhook es verificada antes de procesar.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET no configurado — webhook rechazado")
        raise HTTPException(status_code=503, detail="Webhook no configurado")

    try:
        event = handle_webhook_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        logger.info("Webhook event processed: %s", event["type"])
        return {"received": True, "type": event["type"]}
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload inválido")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Firma de webhook inválida")
    except Exception as e:
        logger.error("Webhook error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error procesando webhook")


@billing_router.get("/portal")
async def billing_portal(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Genera una URL del Stripe Customer Portal para que el cliente gestione su suscripción.
    Requiere que la organización tenga un `stripe_customer_id`.
    """
    if not os.environ.get("STRIPE_SECRET_KEY"):
        raise HTTPException(status_code=503, detail="Stripe no configurado")

    from core.database import get_supabase
    supabase = get_supabase()

    org_id = current_user.get("organization_id") or current_user.get("tenant_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Sin organización en sesión")

    try:
        res = supabase.table("organizations").select("stripe_customer_id").eq("id", str(org_id)).maybe_single().execute()
        customer_id = res.data.get("stripe_customer_id") if res.data else None
    except Exception as e:
        logger.error("Error fetching org: %s", e)
        raise HTTPException(status_code=500, detail="Error consultando organización")

    if not customer_id:
        raise HTTPException(
            status_code=404,
            detail="No hay suscripción activa en Stripe para esta organización. Contrata un plan primero."
        )

    return_url = os.environ.get("FRONTEND_URL", "http://localhost:3001") + "/index.html"
    try:
        portal = create_customer_portal_session(customer_id=customer_id, return_url=return_url)
        return {"portal_url": portal.url}
    except Exception as e:
        logger.error("Portal session error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error al crear portal de cliente")

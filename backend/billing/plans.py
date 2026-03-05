"""
billing/plans.py
================
Definición de planes y sus Stripe Price IDs.
Configura estos valores en tu Stripe Dashboard (Test Mode para desarrollo).

Pasos:
  1. Crea en Stripe Dashboard > Products los 3 planes.
  2. Copia los Price IDs (price_xxx) en backend/.env.
  3. El sistema los leerá automáticamente desde las variables de entorno.
"""
import os

# ── Stripe Price IDs ────────────────────────────────────────────────────────
# Configura estos en backend/.env o en las variables de entorno de Railway/Vercel.
# Ejemplo:
#   STRIPE_PRICE_STARTER    = price_1Qxxx...
#   STRIPE_PRICE_EMPRESA    = price_1Qyyy...
#   STRIPE_PRICE_ENTERPRISE = price_1Qzzz...

PLANS: dict[str, dict] = {
    "starter": {
        "price_id": os.environ.get("STRIPE_PRICE_STARTER", "price_placeholder_starter"),
        "name": "Starter",
        "amount_uf": 2.0,
        "currency": "clp",
        "features": ["1 usuario admin", "Hasta 3 proyectos", "Agentes IA básicos"],
    },
    "empresa": {
        "price_id": os.environ.get("STRIPE_PRICE_EMPRESA", "price_placeholder_empresa"),
        "name": "Empresa",
        "amount_uf": 3.5,
        "currency": "clp",
        "features": ["Hasta 5 usuarios", "Proyectos ilimitados", "Agentes IA Nivel 5", "RLS multi-tenant"],
    },
    "enterprise": {
        "price_id": os.environ.get("STRIPE_PRICE_ENTERPRISE", "price_placeholder_enterprise"),
        "name": "Enterprise",
        "amount_uf": None,   # Precio a cotizar
        "currency": "clp",
        "features": ["Usuarios ilimitados", "Agentes personalizados", "SLA 99.9%", "Soporte 24/7"],
    },
}


def get_price_id(plan_slug: str) -> str:
    """Devuelve el Stripe Price ID para el plan dado. Lanza ValueError si no existe."""
    plan = PLANS.get(plan_slug.lower())
    if not plan:
        raise ValueError(f"Plan '{plan_slug}' no existe. Planes válidos: {list(PLANS.keys())}")
    if "placeholder" in plan["price_id"]:
        raise ValueError(
            f"El Price ID para '{plan_slug}' es un placeholder. "
            f"Configura STRIPE_PRICE_{plan_slug.upper()} en .env"
        )
    return plan["price_id"]

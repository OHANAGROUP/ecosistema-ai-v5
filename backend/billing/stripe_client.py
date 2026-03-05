import os
import stripe
from typing import Optional

# Stripe Configuration
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
stripe.api_key = STRIPE_SECRET_KEY

# Plan Configuration (Placeholder Price IDs - replace with real Stripe Price IDs)
PLANS = {
    "empresa": os.environ.get("STRIPE_PRICE_EMPRESA", "price_placeholder_empresa"),
    "enterprise": os.environ.get("STRIPE_PRICE_ENTERPRISE", "price_placeholder_enterprise")
}

def create_checkout_session(customer_email: str, plan_name: str, success_url: str, cancel_url: str, organization_id: str):
    """
    Creates a Stripe Checkout Session for a subscription.
    """
    price_id = PLANS.get(plan_name.lower())
    if not price_id:
        raise ValueError(f"Plan '{plan_name}' not found.")

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price': price_id,
            'quantity': 1,
        }],
        mode='subscription',
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=customer_email,
        metadata={
            "organization_id": organization_id,
            "plan_type": plan_name
        }
    )
    return session

def create_customer_portal_session(customer_id: str, return_url: str):
    """
    Creates a Stripe Customer Portal session for subscription management.
    """
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session

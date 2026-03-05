import logging
import stripe
from datetime import datetime, timezone
from core.database import get_supabase

logger = logging.getLogger("billing")
supabase = get_supabase()

def handle_webhook_event(payload, sig_header, webhook_secret):
    """
    Verifies and handles Stripe webhook events.
    """
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        logger.error(f"Invalid webhook payload: {e}")
        raise
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.error(f"Invalid webhook signature: {e}")
        raise

    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_completed(session)
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        handle_subscription_deleted(subscription)
    
    return event

def handle_checkout_completed(session):
    """
    Updates organization plan after a successful checkout.
    """
    metadata = session.get("metadata", {})
    org_id = metadata.get("organization_id")
    plan_type = metadata.get("plan_type")
    customer_id = session.get("customer")

    if not org_id or not plan_type:
        logger.warning(f"Missing metadata in checkout session {session.get('id')}")
        return

    try:
        # Update organization in Supabase
        supabase.table("organizations").update({
            "plan_type": plan_type,
            "stripe_customer_id": customer_id,
            "status": "active",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", org_id).execute()
        
        logger.info(f"Successfully updated organization {org_id} to plan {plan_type}")
    except Exception as e:
        logger.error(f"Failed to update organization {org_id}: {e}")

def handle_subscription_deleted(subscription):
    """
    Handles subscription deletion (cancellation).
    """
    customer_id = subscription.get("customer")
    
    try:
        # Find organization by stripe_customer_id
        res = supabase.table("organizations").select("id").eq("stripe_customer_id", customer_id).maybe_single().execute()
        if res.data:
            org_id = res.data["id"]
            # Downgrade to trial or mark as expired
            supabase.table("organizations").update({
                "plan_type": "free",
                "status": "expired",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", org_id).execute()
            logger.info(f"Subscription deleted for customer {customer_id}, org {org_id} downgraded.")
    except Exception as e:
        logger.error(f"Failed to handle subscription deletion for customer {customer_id}: {e}")

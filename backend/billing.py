"""
billing.py — Proxy for the billing package
==========================================
This file allows importing from 'billing' regardless of path resolution issues.
"""
from billing import billing_router

__all__ = ["billing_router"]

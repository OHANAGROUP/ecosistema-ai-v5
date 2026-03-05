from typing import Any
from .database import get_supabase

import logging

# MJ-05: Agent-to-Agent Memory Bus
class MemoryBus:
    def __init__(self):
        self.supabase = get_supabase()

    async def publish_signal(self, agent_id: str, cycle_id: str, company_id: str, signal_type: str, value: Any, importance: float = 0.5):
        """
        Publica una señal para que otros agentes la consuman durante el mismo ciclo.
        """
        data = {
            "cycle_id": cycle_id,
            "agent_id": agent_id,
            "company_id": company_id,
            "signal_type": signal_type,
            "value": value,
            "importance": importance
        }
        try:
            self.supabase.table("agent_signals").insert(data).execute()
        except Exception as e:
            logging.error(f"Error publicando en Memory Bus: {e}")

    async def get_active_signals(self, cycle_id: str):
        """
        Recupera todas las señales publicadas en el ciclo actual.
        """
        try:
            res = self.supabase.table("agent_signals").select("*").eq("cycle_id", cycle_id).execute()
            return res.data
        except Exception as e:
            logging.error(f"Error leyendo Memory Bus: {e}")
            return []

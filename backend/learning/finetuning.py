import json
from .database import get_supabase
from .schemas import AgentDecision
import os

class FineTuningPipeline:
    def __init__(self):
        self.supabase = get_supabase()

    async def export_training_data(self, tenant_id: str, min_confidence: float = 0.8):
        """
        MJ-09: Genera un archivo JSONL con decisiones aprobadas para fine-tuning.
        """
        try:
            # En v5 real, filtraríamos por approved=True (columna que se activaría en el dashboard)
            res = self.supabase.table("agent_decisions") \
                .select("*") \
                .filter("confidence", "gte", min_confidence) \
                .execute()
            
            dataset = []
            for d in res.data:
                entry = {
                    "messages": [
                        {"role": "system", "content": f"Eres un agente de {d['agent_id']}"},
                        {"role": "user", "content": "Instrucción original del ciclo..."}, # Necesitaría join con cycles
                        {"role": "assistant", "content": d['decision']}
                    ]
                }
                dataset.append(entry)
            
            file_path = f"training_data_{tenant_id}.jsonl"
            with open(file_path, "w", encoding="utf-8") as f:
                for entry in dataset:
                    f.write(json.dumps(entry) + "\n")
            
            return file_path
        except Exception as e:
            print(f"Error exportando dataset: {e}")
            return None

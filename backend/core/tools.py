import json
from typing import Dict, List, Any

class TaxTools:
    @staticmethod
    def get_sii_delta(periodo: str, er_total_neto: float, sii_purchases_total: float) -> Dict[str, Any]:
        """Compara el total neto del ERP contra el SII para detectar Utilidad Ficticia."""
        delta = sii_purchases_total - er_total_neto
        status = "CRITICAL" if delta > (er_total_neto * 0.1) else "NORMAL"
        return {
            "periodo": periodo,
            "erp_value": er_total_neto,
            "sii_value": sii_purchases_total,
            "delta": delta,
            "status": status,
            "finding": f"Punto Ciego detectado: SII reporta ${delta:,.0f} en costos no imputados en el ERP."
        }

    @staticmethod
    def classify_top_suppliers(purchases: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
        """Identifica los proveedores con mayor concentración de gasto."""
        # Simulación de lógica de agrupación
        sorted_suppliers = sorted(purchases, key=lambda x: x.get('monto', 0), reverse=True)
        return sorted_suppliers[:limit]

class BankTools:
    @staticmethod
    def analyze_cash_arbitrage(accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Cruza saldos bancarios para proponer saneamiento de sobregiros."""
        overdrafts = [a for a in accounts if a.get('saldo', 0) < 0]
        surplus = [a for a in accounts if a.get('saldo', 0) > 0]
        
        proposals = []
        for ov in overdrafts:
            needed = abs(ov['saldo'])
            for s in surplus:
                if s['saldo'] > needed:
                    proposals.append({
                        "from": s['banco'],
                        "to": ov['banco'],
                        "amount": needed,
                        "desc": f"Traspaso para sanear sobregiro en {ov['banco']}"
                    })
                    s['saldo'] -= needed
                    needed = 0
                    break
        
        return {
            "overdraft_count": len(overdrafts),
            "proposals": proposals,
            "estimated_monthly_saving": sum(abs(ov['saldo']) for ov in overdrafts) * 0.02
        }

class LegalTools:
    @staticmethod
    def check_f30_status(rut: str) -> Dict[str, Any]:
        """Simula validación de Certificado F30-1 (Deudas Previsionales)."""
        # Mock de base de datos de cumplimiento
        compliance_db = {
            "76.123.456-7": {"status": "DEBT", "amount": 4500000},
            "88.999.000-K": {"status": "CLEAN", "amount": 0}
        }
        return compliance_db.get(rut, {"status": "UNKNOWN", "amount": 0})

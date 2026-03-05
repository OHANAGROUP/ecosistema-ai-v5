#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
monitoring/alerts.py
====================
Sistema de Monitoreo y Alertas - Sistema de Agentes v5.0

Uso:
    # Monitoreo normal (ejecutar cada hora via cron/scheduler)
    python -m monitoring.alerts

    # Reporte diario completo
    python -m monitoring.alerts --daily

    # Solo un check puntual
    python -m monitoring.alerts --check critical_decisions

Cron job sugerido:
    0 * * * *   cd /path/to/project && python -m monitoring.alerts >> logs/monitoring.log 2>&1
    0 8 * * *   cd /path/to/project && python -m monitoring.alerts --daily  >> logs/daily.log 2>&1
"""

import os
import sys
import json
import argparse
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

# ── Config ─────────────────────────────────────────────────────────────────────
_root = Path(__file__).resolve().parents[1]
load_dotenv(_root / ".env")

SUPABASE_URL      = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY       = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")   # opcional
ALERT_EMAIL       = os.getenv("ALERT_EMAIL", "admin@alpa.cl")

# Umbrales configurables
CRITICAL_HOURS_THRESHOLD  = int(os.getenv("CRITICAL_HOURS_THRESHOLD", "24"))
MIN_CONFIDENCE_THRESHOLD  = float(os.getenv("MIN_CONFIDENCE_THRESHOLD", "0.50"))
MAX_SECURITY_EVENTS_HOUR  = int(os.getenv("MAX_SECURITY_EVENTS_HOUR", "5"))


# ── Helpers HTTP ───────────────────────────────────────────────────────────────

def _svc_headers() -> dict:
    return {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }


def _rest(path: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{path}"


def _query(table: str, params: dict) -> list:
    """GET a Supabase REST table with query params."""
    resp = requests.get(_rest(table), headers=_svc_headers(), params=params, timeout=15)
    if resp.status_code == 200:
        return resp.json()
    print(f"  [WARN] {table} query failed ({resp.status_code}): {resp.text[:120]}")
    return []


def _now_iso(delta_hours: int = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=delta_hours)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Alert Channels ─────────────────────────────────────────────────────────────

class AlertChannel:
    """Base class — override send() to add new destinations."""
    def send(self, severity: str, title: str, body: str): ...


class ConsoleChannel(AlertChannel):
    ICONS = {"critical": "[!!]", "warning": "[!!]", "info": "[ii]", "ok": "[OK]"}

    def send(self, severity: str, title: str, body: str):
        icon = self.ICONS.get(severity, "[??]")
        border = "=" * 60
        print(f"\n{border}\n{icon} {title}\n{border}\n{body}\n{border}\n")


class SlackChannel(AlertChannel):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, severity: str, title: str, body: str):
        if not self.webhook_url:
            return
        color = {"critical": "#FF0000", "warning": "#FFA500", "info": "#36A64F"}.get(severity, "#AAAAAA")
        payload = {
            "attachments": [{
                "color": color,
                "title": title,
                "text": body,
                "footer": f"Sistema de Agentes v5.0 | {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            }]
        }
        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            if resp.status_code != 200:
                print(f"  [WARN] Slack alert failed: {resp.text[:80]}")
        except Exception as e:
            print(f"  [WARN] Slack channel error: {e}")


class EmailChannel(AlertChannel):
    """Sends alert emails via the core email_service (Resend)."""

    def send(self, severity: str, title: str, body: str):
        """Generic alert email — for trial-specific emails use send_trial_alert()."""
        # Generic emails not implemented yet; trial emails go through send_trial_alert()
        pass

    @staticmethod
    def send_trial_alert(email: str, company: str, days_left: int) -> bool:
        try:
            from core.email_service import send_trial_expiring_email
            ok = send_trial_expiring_email(email, company, days_left)
            if ok:
                print(f"  [OK] Trial-expiry email enviado a {email} ({days_left}d restantes)")
            else:
                print(f"  [WARN] Email NO enviado a {email} (revisar RESEND_API_KEY)")
            return ok
        except ImportError:
            print("  [WARN] email_service no disponible — RESEND_API_KEY no configurada")
            return False
        except Exception as e:
            print(f"  [WARN] EmailChannel error: {e}")
            return False


# ── Build channel list from env ────────────────────────────────────────────────

def _build_channels() -> list[AlertChannel]:
    channels: list[AlertChannel] = [ConsoleChannel()]
    if SLACK_WEBHOOK_URL:
        channels.append(SlackChannel(SLACK_WEBHOOK_URL))
    return channels


def _alert(severity: str, title: str, body: str, channels: list[AlertChannel]):
    for ch in channels:
        ch.send(severity, title, body)


# ── Checks ─────────────────────────────────────────────────────────────────────

def check_critical_decisions(channels: list[AlertChannel]) -> int:
    """Alerta si hay decisiones críticas sin aprobar por más de N horas."""
    decisions = _query("agent_decisions", {
        "select": "id,decision,agent_type,empresa,health_status,decision_timestamp,confidence",
        "requires_approval": "eq.true",
        "health_status": "in.(critical,warning)",
        "decision_timestamp": f"lt.{_now_iso(CRITICAL_HOURS_THRESHOLD)}",
    })
    if not decisions:
        print(f"  [OK] Sin decisiones pendientes >{CRITICAL_HOURS_THRESHOLD}h")
        return 0

    lines = []
    for d in decisions:
        ts = d.get("decision_timestamp", "")
        lines.append(
            f"  - [{d['health_status'].upper()}] {d['decision']} "
            f"({d['agent_type']}/{d['empresa']})  ts={ts[:16]}"
        )

    _alert(
        "critical",
        f"ALERTA: {len(decisions)} decisiones sin aprobar >{CRITICAL_HOURS_THRESHOLD}h",
        "\n".join(lines),
        channels,
    )
    return len(decisions)


def check_failed_cycles(channels: list[AlertChannel]) -> int:
    """Alerta si hay ciclos fallidos en las últimas 6 horas."""
    cycles = _query("agent_cycles", {
        "select": "id,started_at,context,organization_id",
        "status": "eq.failed",
        "started_at": f"gt.{_now_iso(6)}",
    })
    if not cycles:
        print("  [OK] Sin ciclos fallidos en las ultimas 6h")
        return 0

    lines = [f"  - id={c['id'][:8]}... @ {c.get('started_at','')[:16]}" for c in cycles]
    _alert("warning", f"Ciclos fallidos: {len(cycles)} en las ultimas 6h", "\n".join(lines), channels)
    return len(cycles)


def check_security_events(channels: list[AlertChannel]) -> int:
    """Alerta si hay demasiados eventos sospechosos en la última hora."""
    logs = _query("audit_logs", {
        "select": "action,user_id,ip_address",
        "created_at": f"gt.{_now_iso(1)}",
    })
    suspicious = [
        l for l in logs
        if any(kw in l.get("action", "").upper() for kw in ("FAILED", "DENIED", "VIOLATION"))
    ]
    count = len(suspicious)
    if count <= MAX_SECURITY_EVENTS_HOUR:
        print(f"  [OK] Eventos de seguridad en 1h: {count} (<= {MAX_SECURITY_EVENTS_HOUR})")
        return count

    unique_ips = len({l.get("ip_address") for l in suspicious})
    _alert(
        "critical",
        f"SEGURIDAD: {count} eventos sospechosos en 1h ({unique_ips} IPs)",
        "\n".join([f"  - {l['action']} desde {l.get('ip_address', 'IP desconocida')}" for l in suspicious[:10]]),
        channels,
    )
    return count


def check_low_confidence(channels: list[AlertChannel]) -> int:
    """Alerta si hay muchas decisiones con confianza baja en 24h."""
    decisions = _query("agent_decisions", {
        "select": "id,decision,confidence,agent_type",
        "confidence": f"lt.{MIN_CONFIDENCE_THRESHOLD}",
        "decision_timestamp": f"gt.{_now_iso(24)}",
    })
    if not decisions:
        print(f"  [OK] Sin decisiones con confianza <{MIN_CONFIDENCE_THRESHOLD:.0%} en 24h")
        return 0

    avg_conf = sum(d.get("confidence", 0) for d in decisions) / len(decisions)
    _alert(
        "warning",
        f"Baja confianza: {len(decisions)} decisiones <{MIN_CONFIDENCE_THRESHOLD:.0%} en 24h",
        f"Confianza promedio: {avg_conf:.1%}\nRevisar reglas de agentes.",
        channels,
    )
    return len(decisions)


def check_trial_expirations(channels: list[AlertChannel]) -> int:
    """Alerta sobre trials que expiran pronto (3 días, 1 día o hoy)."""
    # Traemos trials activos
    trials = _query("trials", {
        "select": "id,email,company,trial_end,status",
        "status": "eq.active",
    })
    
    if not trials:
        return 0

    expiring_count = 0
    lines = []
    now = datetime.now(timezone.utc)
    email_ch = EmailChannel()

    for t in trials:
        try:
            # Parse trial_end (Supabase returns ISO)
            end_date = datetime.fromisoformat(t['trial_end'].replace('Z', '+00:00'))
            delta = end_date - now
            days_left = delta.days

            if days_left <= 3:
                expiring_count += 1
                status_msg = "EXPIRA HOY" if days_left < 1 else f"Expira en {days_left} dias"
                lines.append(f"  - [{status_msg}] {t.get('company', '?')} ({t.get('email', '?')})")

                # ── Send trial-expiry email ──────────────────────────────────
                email = t.get("email") or t.get("admin_email")
                company = t.get("company") or t.get("name", "Tu Organización")
                if email:
                    email_ch.send_trial_alert(email, company, days_left)

        except Exception as e:
            print(f"  [WARN] Error parsing trial_end for {t.get('email')}: {e}")

    if lines:
        _alert(
            "warning",
            f"REPORTE TRIALS: {expiring_count} pruebas por expirar",
            "\n".join(lines),
            channels
        )
    else:
        print("  [OK] No hay trials por expirar en los proximos 3 dias")

    return expiring_count


# ── Daily Report ───────────────────────────────────────────────────────────────

def daily_report(channels: list[AlertChannel]):
    """Genera y envía el reporte diario de actividad."""
    print("\n" + "=" * 60)
    print("REPORTE DIARIO - SISTEMA DE AGENTES")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    decisions = _query("agent_decisions", {
        "select": "health_status,confidence,requires_approval",
        "decision_timestamp": f"gt.{_now_iso(24)}",
    })
    cycles = _query("agent_cycles", {
        "select": "status,started_at",
        "started_at": f"gt.{_now_iso(24)}",
    })
    pending = _query("agent_approvals", {
        "select": "id",
        "status": "eq.pending",
    })

    d_total     = len(decisions)
    d_critical  = sum(1 for d in decisions if d.get("health_status") == "critical")
    d_warning   = sum(1 for d in decisions if d.get("health_status") == "warning")
    d_healthy   = sum(1 for d in decisions if d.get("health_status") == "healthy")
    avg_conf    = sum(d.get("confidence", 0) for d in decisions) / d_total if d_total else 0
    c_total     = len(cycles)
    c_completed = sum(1 for c in cycles if c.get("status") == "completed")
    c_failed    = sum(1 for c in cycles if c.get("status") == "failed")

    report_lines = [
        f"  Decisiones (24h): {d_total}",
        f"    - Criticas:      {d_critical}",
        f"    - Advertencias:  {d_warning}",
        f"    - Saludables:    {d_healthy}",
        f"    - Conf. promedio:{avg_conf:.1%}",
        f"  Ciclos (24h):     {c_total} ({c_completed} OK, {c_failed} fallidos)",
        f"  Aprobaciones pendientes: {len(pending)}",
    ]
    body = "\n".join(report_lines)
    print(body)
    severity = "critical" if d_critical > 0 or c_failed > 0 else "info"
    _alert(severity, "Reporte Diario - Sistema de Agentes", body, channels)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Monitor de alertas - Sistema de Agentes")
    parser.add_argument("--daily", action="store_true", help="Generar reporte diario")
    parser.add_argument("--check", choices=["critical_decisions", "failed_cycles",
                                             "security_events", "low_confidence", "trial_expirations"],
                        help="Ejecutar solo un check específico")
    args = parser.parse_args()

    if not SUPABASE_URL or not SERVICE_KEY:
        print("[ERROR] Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en .env")
        sys.exit(1)

    channels = _build_channels()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{ts}] Iniciando monitoreo...")

    if args.daily:
        daily_report(channels)
        return

    check_map = {
        "critical_decisions": check_critical_decisions,
        "failed_cycles":      check_failed_cycles,
        "security_events":    check_security_events,
        "low_confidence":     check_low_confidence,
        "trial_expirations":  check_trial_expirations,
    }

    if args.check:
        count = check_map[args.check](channels)
        sys.exit(1 if count > 0 else 0)

    # Run all checks
    results = {}
    for name, fn in check_map.items():
        print(f"\nCheck: {name}...")
        results[name] = fn(channels)

    total_issues = sum(results.values())
    print(f"\n[OK] Monitoreo completado — Issues encontrados: {total_issues}")
    for name, count in results.items():
        status = "[!!]" if count > 0 else "[OK]"
        print(f"  {status} {name}: {count}")

    sys.exit(1 if total_issues > 0 else 0)


if __name__ == "__main__":
    main()

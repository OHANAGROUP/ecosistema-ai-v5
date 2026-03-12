"""
scheduler.py — Cron jobs integrados en el proceso FastAPI
=========================================================
Corre dentro del mismo proceso de Railway (sin servicio extra).

Jobs activos:
  - Cada hora     → checks de monitoreo (trials, ciclos, seguridad, confianza)
  - Cada día 8am  → reporte diario completo (Chile/Santiago)

Dependencias: apscheduler (ya en requirements.txt)
"""

import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("scheduler")


# ── Jobs (síncronos — APScheduler los corre en ThreadPoolExecutor) ────────────

def _run_hourly_checks():
    """
    Ejecuta todos los checks de monitoreo.
    Corre cada hora. Si hay issues, alerta por consola y Slack (si SLACK_WEBHOOK_URL está configurado).
    """
    try:
        from monitoring.alerts import (
            _build_channels,
            check_critical_decisions,
            check_failed_cycles,
            check_security_events,
            check_low_confidence,
            check_trial_expirations,
        )

        channels = _build_channels()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        logger.info(f"[CRON] ▶ Checks horarios iniciados — {ts}")

        checks = [
            ("trial_expirations",  check_trial_expirations),   # envía emails automáticos
            ("failed_cycles",      check_failed_cycles),
            ("critical_decisions", check_critical_decisions),
            ("low_confidence",     check_low_confidence),
            ("security_events",    check_security_events),
        ]

        results = {}
        for name, fn in checks:
            try:
                results[name] = fn(channels)
            except Exception as e:
                logger.error(f"[CRON] Check '{name}' falló: {e}")
                results[name] = -1

        issues = sum(v for v in results.values() if v > 0)
        status = "⚠️  issues encontrados" if issues else "✅ todo OK"
        logger.info(f"[CRON] ■ Checks completados — {issues} {status}")
        for name, count in results.items():
            icon = "  [!!]" if count > 0 else "  [OK]"
            logger.info(f"{icon} {name}: {count}")

    except ImportError as e:
        logger.error(f"[CRON] Import error en monitoring: {e}")
    except Exception as e:
        logger.error(f"[CRON] Error inesperado en checks horarios: {e}", exc_info=True)


def _run_daily_report():
    """
    Genera el reporte diario de actividad de agentes.
    Corre a las 8:00am hora Chile (America/Santiago).
    """
    try:
        from monitoring.alerts import _build_channels, daily_report

        channels = _build_channels()
        logger.info("[CRON] ▶ Generando reporte diario...")
        daily_report(channels)
        logger.info("[CRON] ■ Reporte diario completado")

    except ImportError as e:
        logger.error(f"[CRON] Import error en daily_report: {e}")
    except Exception as e:
        logger.error(f"[CRON] Error en reporte diario: {e}", exc_info=True)


# ── Factory ───────────────────────────────────────────────────────────────────

def create_scheduler() -> AsyncIOScheduler:
    """
    Crea y configura el scheduler. Llamar .start() en el lifespan de FastAPI.
    """
    scheduler = AsyncIOScheduler(timezone="America/Santiago")

    # ── Job 1: Monitoreo horario ──────────────────────────────────────────────
    scheduler.add_job(
        _run_hourly_checks,
        trigger=IntervalTrigger(hours=1),
        id="hourly_checks",
        name="Monitoreo horario — trials + ciclos + seguridad",
        max_instances=1,       # nunca dos corriendo al mismo tiempo
        coalesce=True,         # si se acumularon, corre solo una vez
        misfire_grace_time=300  # si Railway reinicia, acepta hasta 5min de retraso
    )

    # ── Job 2: Reporte diario 8am ─────────────────────────────────────────────
    scheduler.add_job(
        _run_daily_report,
        trigger=CronTrigger(hour=8, minute=0, timezone="America/Santiago"),
        id="daily_report",
        name="Reporte diario 8:00am (Santiago)",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600  # acepta hasta 10min de retraso
    )

    logger.info("[SCHEDULER] Jobs registrados:")
    for job in scheduler.get_jobs():
        logger.info(f"  • {job.name} — próxima ejecución: {job.next_run_time}")

    return scheduler

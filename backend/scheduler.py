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
        try:
            from monitoring.alerts import (
                _build_channels,
                check_critical_decisions,
                check_failed_cycles,
                check_security_events,
                check_low_confidence,
                check_trial_expirations,
            )
        except ImportError:
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
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
        try:
            from monitoring.alerts import _build_channels, daily_report
        except ImportError:
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from monitoring.alerts import _build_channels, daily_report

        channels = _build_channels()
        logger.info("[CRON] ▶ Generando reporte diario...")
        daily_report(channels)
        logger.info("[CRON] ■ Reporte diario completado")

    except ImportError as e:
        logger.error(f"[CRON] Import error en daily_report: {e}")
    except Exception as e:
        logger.error(f"[CRON] Error en reporte diario: {e}", exc_info=True)


def _run_operator_briefing():
    """
    Ejecuta el AgenteOperador diariamente a las 7:30am.
    Genera el briefing de salud del negocio SaaS para MD Asesorías Limitada.
    Corre ANTES del reporte de 8am para que el dueño ya tenga el resumen al despertar.
    """
    import asyncio
    import os

    admin_org_id = os.getenv("ADMIN_ORG_ID", "")
    if not admin_org_id:
        logger.warning("[CRON] ADMIN_ORG_ID no configurado — AgenteOperador omitido")
        return

    try:
        from core.database import get_supabase
        from agents import AgenteOperador, EmpresaSchema, InstruccionCEO, EmpresaMetadata
        import uuid

        supabase  = get_supabase()
        agent     = AgenteOperador(supabase)
        cycle_id  = str(uuid.uuid4())
        inst_ceo  = InstruccionCEO(objetivo_iteracion="Briefing diario: salud del negocio SaaS")
        empresa   = EmpresaSchema(
            instruccion_ceo=inst_ceo,
            metadata=EmpresaMetadata(empresa="MD Asesorías Limitada"),
        )

        logger.info(f"[CRON] ▶ AgenteOperador iniciado — cycle={cycle_id}")

        # APScheduler corre en ThreadPoolExecutor — necesitamos un event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            decision = loop.run_until_complete(
                agent.analyze(empresa, cycle_id, admin_org_id)
            )
            logger.info(
                f"[CRON] ■ AgenteOperador completado — "
                f"semáforo={decision.health_status} confidence={decision.confidence}"
            )
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"[CRON] AgenteOperador falló: {e}", exc_info=True)


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
        misfire_grace_time=600
    )

    # ── Job 3: AgenteOperador 7:30am — briefing SaaS MD Asesorías ────────────
    scheduler.add_job(
        _run_operator_briefing,
        trigger=CronTrigger(hour=7, minute=30, timezone="America/Santiago"),
        id="operator_briefing",
        name="AgenteOperador 7:30am — briefing SaaS MD Asesorías",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
    )

    logger.info("[SCHEDULER] Jobs registrados:")
    for job in scheduler.get_jobs():
        logger.info(f"  • {job.name} — próxima ejecución: {job.next_run_time}")

    return scheduler

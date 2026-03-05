#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backup/backup.py
================
Backup de datos críticos del Sistema de Agentes v5.0.
Compatible con Windows. No requiere pg_dump.

Estrategia:
  - Exporta tablas críticas a JSON via Supabase REST (service role)
  - Comprime en .zip con fecha/hora
  - Retiene los últimos N backups locales
  - Notifica via Slack / console si está configurado

Uso:
    cd backend
    venv\\Scripts\\python.exe -m backup.backup
    venv\\Scripts\\python.exe -m backup.backup --tables organizations agent_rules
    venv\\Scripts\\python.exe -m backup.backup --verify
"""

import os
import sys
import json
import zipfile
import argparse
import requests
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# ── Config ─────────────────────────────────────────────────────────────────────
_root = Path(__file__).resolve().parents[1]
load_dotenv(_root / ".env")

SUPABASE_URL   = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY    = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SLACK_WEBHOOK  = os.getenv("SLACK_WEBHOOK_URL", "")
BACKUP_DIR     = Path(os.getenv("BACKUP_DIR", str(_root / "backups")))
RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))

# Tablas críticas a respaldar (en orden de dependencia)
CRITICAL_TABLES = [
    "organizations",
    "organization_members",
    "agent_rules",
    "agent_thresholds",
    "agent_cycles",
    "agent_decisions",
    "agent_approvals",
    "audit_logs",
]

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _svc_headers() -> dict:
    return {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }


def _rest(path: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{path}"


def _print(msg: str, level: str = "info"):
    icons = {"info": "[  ]", "ok": "[OK]", "warn": "[!!]", "error": "[XX]"}
    print(f"  {icons.get(level, '[  ]')} {msg}")


def _notify_slack(title: str, body: str, ok: bool = True):
    if not SLACK_WEBHOOK:
        return
    color = "#36A64F" if ok else "#FF0000"
    try:
        requests.post(SLACK_WEBHOOK, json={
            "attachments": [{"color": color, "title": title, "text": body,
                             "footer": f"Backup {TIMESTAMP}"}]
        }, timeout=10)
    except Exception:
        pass


# ── Export ─────────────────────────────────────────────────────────────────────

def export_table(table: str, page_size: int = 1000) -> list:
    """Descarga todos los registros de una tabla con paginación."""
    rows, offset = [], 0
    while True:
        resp = requests.get(
            _rest(f"{table}?select=*&offset={offset}&limit={page_size}"),
            headers=_svc_headers(),
            timeout=30,
        )
        if resp.status_code == 404:
            _print(f"{table}: tabla no encontrada — omitida", "warn")
            return []
        if resp.status_code != 200:
            _print(f"{table}: error {resp.status_code} — {resp.text[:80]}", "error")
            return []
        batch = resp.json()
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def run_backup(tables: list[str] | None = None) -> Path:
    """Exporta las tablas y las empaqueta en un .zip."""
    target_tables = tables or CRITICAL_TABLES
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    zip_path = BACKUP_DIR / f"backup_{TIMESTAMP}.zip"
    manifest = {
        "timestamp": TIMESTAMP,
        "supabase_url": SUPABASE_URL,
        "tables": {},
    }

    print(f"\n{'='*60}")
    print(f"  BACKUP - Sistema de Agentes v5.0")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for table in target_tables:
            _print(f"Exportando {table}...", "info")
            rows = export_table(table)
            data = json.dumps(rows, ensure_ascii=False, indent=2, default=str)
            zf.writestr(f"{table}.json", data)
            manifest["tables"][table] = {"rows": len(rows), "bytes": len(data)}
            _print(f"{table}: {len(rows)} filas", "ok")

        # Adjuntar manifest
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    size_kb = zip_path.stat().st_size // 1024
    _print(f"\nArchivo: {zip_path.name}  ({size_kb} KB)", "ok")

    # ── Cleanup: borrar backups viejos ─────────────────────────────────────────
    import time
    cutoff = time.time() - RETENTION_DAYS * 86400
    removed = 0
    for old in BACKUP_DIR.glob("backup_*.zip"):
        if old.stat().st_mtime < cutoff:
            old.unlink()
            removed += 1
    if removed:
        _print(f"Backups eliminados (>{RETENTION_DAYS} días): {removed}", "info")

    remaining = len(list(BACKUP_DIR.glob("backup_*.zip")))
    _print(f"Backups locales disponibles: {remaining}", "info")

    # ── Notificación ───────────────────────────────────────────────────────────
    total_rows = sum(t["rows"] for t in manifest["tables"].values())
    _notify_slack(
        f"Backup completado — {TIMESTAMP}",
        f"Tablas: {len(manifest['tables'])} | Filas: {total_rows} | Tamaño: {size_kb} KB",
        ok=True,
    )

    print(f"\n{'='*60}\n  [OK] BACKUP COMPLETADO\n{'='*60}\n")
    return zip_path


# ── Restore ────────────────────────────────────────────────────────────────────

def run_restore(zip_path: Path, tables: list[str] | None = None, dry_run: bool = False):
    """
    Restaura datos desde un .zip de backup.
    ADVERTENCIA: usa INSERT con upsert — no borra registros existentes.
    Para un reset completo, vacía las tablas primero en Supabase SQL Editor.
    """
    if not zip_path.exists():
        _print(f"Archivo no encontrado: {zip_path}", "error")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  RESTAURACION - {zip_path.name}")
    if dry_run:
        print(f"  [DRY RUN — no se escribira nada]")
    print(f"{'='*60}\n")

    if not dry_run:
        confirm = input("  ADVERTENCIA: esto upsert data en Supabase. Escriba 'SI': ")
        if confirm.strip() != "SI":
            print("  Operacion cancelada.")
            return

    with zipfile.ZipFile(zip_path, "r") as zf:
        manifest = json.loads(zf.read("manifest.json"))
        _print(f"Backup del: {manifest['timestamp']}", "info")

        restore_tables = tables or list(manifest["tables"].keys())

        for table in restore_tables:
            fname = f"{table}.json"
            if fname not in zf.namelist():
                _print(f"{table}: no encontrado en backup", "warn")
                continue

            rows = json.loads(zf.read(fname))
            _print(f"Restaurando {table}: {len(rows)} filas...", "info")

            if dry_run or not rows:
                _print(f"{table}: [DRY RUN] ok", "ok")
                continue

            # Upsert en lotes de 200
            batch_size = 200
            errors = 0
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                resp = requests.post(
                    _rest(table),
                    headers={**_svc_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
                    json=batch,
                    timeout=30,
                )
                if resp.status_code not in (200, 201):
                    _print(f"  Lote {i//batch_size+1} error {resp.status_code}: {resp.text[:80]}", "warn")
                    errors += 1

            level = "ok" if errors == 0 else "warn"
            _print(f"{table}: restaurado ({errors} errores de lote)", level)

    print(f"\n{'='*60}\n  Restauracion completada\n{'='*60}\n")


# ── Verify ─────────────────────────────────────────────────────────────────────

def run_verify():
    """Lista los backups locales y verifica integridad."""
    print(f"\n{'='*60}")
    print(f"  VERIFICACION DE BACKUPS")
    print(f"{'='*60}\n")

    zips = sorted(BACKUP_DIR.glob("backup_*.zip"), reverse=True)
    if not zips:
        _print("No hay backups locales en " + str(BACKUP_DIR), "warn")
        return

    for z in zips:
        size_kb = z.stat().st_size // 1024
        try:
            with zipfile.ZipFile(z, "r") as zf:
                bad = zf.testzip()
                manifest = json.loads(zf.read("manifest.json"))
            status = "[OK]" if not bad else "[!!]"
            tables_count = len(manifest.get("tables", {}))
            total_rows = sum(t["rows"] for t in manifest["tables"].values())
            print(f"  {status} {z.name}  {size_kb:>6} KB  {tables_count} tablas  {total_rows} filas")
        except Exception as e:
            print(f"  [XX] {z.name}  ERROR: {e}")

    print()
    _print(f"Backups encontrados: {len(zips)}", "info")
    _print(f"Directorio: {BACKUP_DIR}", "info")
    print()


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Backup/Restore — Sistema de Agentes v5.0")
    sub = parser.add_subparsers(dest="cmd")

    # backup
    bp = sub.add_parser("backup", help="Crear backup (default)")
    bp.add_argument("--tables", nargs="*", help="Tablas específicas (default: todas)")

    # restore
    rp = sub.add_parser("restore", help="Restaurar desde backup")
    rp.add_argument("file", help="Archivo .zip de backup")
    rp.add_argument("--tables", nargs="*", help="Tablas específicas")
    rp.add_argument("--dry-run", action="store_true", help="Sin escribir nada")

    # verify
    sub.add_parser("verify", help="Verificar backups locales")

    args = parser.parse_args()

    if not SUPABASE_URL or not SERVICE_KEY:
        print("[ERROR] Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en .env")
        sys.exit(1)

    cmd = args.cmd or "backup"

    if cmd == "backup":
        run_backup(getattr(args, "tables", None))
    elif cmd == "restore":
        run_restore(Path(args.file), getattr(args, "tables", None), args.dry_run)
    elif cmd == "verify":
        run_verify()
    else:
        # Default: backup
        run_backup()


if __name__ == "__main__":
    main()

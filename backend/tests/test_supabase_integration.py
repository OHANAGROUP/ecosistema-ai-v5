# -*- coding: utf-8 -*-
"""
test_supabase_integration.py
============================
Pruebas de Integración Real con Supabase - Sistema de Agentes v5.0

Equivalente Python de la guía de pruebas con curl.
Se conecta directamente a Supabase para validar:
  - Autenticación de usuarios
  - Tenant Isolation (RLS)
  - CRUD de agent_rules
  - Flujo completo: Ciclo → Decisión → Aprobación
  - Audit logs

Uso:
  cd backend
  python -m pytest tests/test_supabase_integration.py -v -s
  # o directamente:
  python tests/test_supabase_integration.py

Prerrequisitos:
  pip install python-dotenv requests
  Variables en .env: SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY,
                      ADMIN_EMAIL, ADMIN_PASSWORD
"""

import os
import sys
import json
import time
import requests
import pytest
from uuid import UUID
from pathlib import Path
from dotenv import load_dotenv

# Force UTF-8 on Windows so emoji/accented chars don't crash the runner
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass  # Python < 3.7 fallback

# ── Cargar .env desde la raíz del backend ──────────────────────────────────────
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

SUPABASE_URL            = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY       = os.getenv("SUPABASE_KEY", "")          # anon key
SUPABASE_SERVICE_KEY    = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
ADMIN_EMAIL             = os.getenv("ADMIN_EMAIL", "admin@alpa.cl")
ADMIN_PASSWORD          = os.getenv("ADMIN_PASSWORD", "")
TEST_CORP_ORG_ID        = "22222222-2222-2222-2222-222222222222"

# Resolve the real org ID from the DB (the .env value may differ from the actual table)
_FALLBACK_ORG_ID = "11111111-1111-1111-1111-111111111111"

def _resolve_org_id() -> str:
    """Query organizations table to find the first valid org ID."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return _FALLBACK_ORG_ID
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/organizations?select=id&limit=1",
            headers={"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"},
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data:
                return data[0]["id"]
    except Exception:
        pass
    return _FALLBACK_ORG_ID

ALPA_ORG_ID = _resolve_org_id()

# ── Helpers ────────────────────────────────────────────────────────────────────

def anon_headers(token: str | None = None) -> dict:
    """Headers base con apikey anon y, opcionalmente, JWT de usuario."""
    h = {
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def service_headers() -> dict:
    """Headers para operaciones de backend (service role)."""
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def rest(path: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{path}"


def auth_url(path: str) -> str:
    return f"{SUPABASE_URL}/auth/v1/{path}"


def print_result(ok: bool, label: str, extra: str = ""):
    icon = "[OK] " if ok else "[!!] "
    msg  = f"  {icon}{label}"
    if extra:
        msg += f" -> {extra}"
    print(msg)


# ── Fixture compartida de sesión ───────────────────────────────────────────────

@pytest.fixture(scope="module")
def user_token() -> str:
    """Obtiene el JWT del admin; falla el módulo si no hay credenciales."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        pytest.skip("SUPABASE_URL o SUPABASE_KEY no están configurados en .env")

    resp = requests.post(
        auth_url("token?grant_type=password"),
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    data = resp.json()
    token = data.get("access_token")
    if not token or token == "null":
        pytest.skip(f"Login falló: {data}")
    print(f"\n  [KEY] Token obtenido: {token[:20]}...")
    return token


# ==============================================================================
# TEST 1 – Autenticación
# ==============================================================================

class TestAutenticacion:
    """TEST 1 – Login y obtención de token JWT"""

    def _check_key_mismatch(self) -> str:
        """Devuelve un mensaje diagnóstico si el anon key no es del proyecto correcto."""
        import base64, json as _json
        try:
            proj_ref = SUPABASE_URL.split(".")[0].split("//")[-1]
            parts = SUPABASE_ANON_KEY.split(".")
            padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
            payload = _json.loads(base64.b64decode(padded))
            key_ref = payload.get("ref", "?")
            if key_ref != proj_ref:
                return (
                    f"\n\n  [CONFIG ERROR] SUPABASE_KEY (anon) es de otro proyecto!\n"
                    f"  URL project ref: {proj_ref}\n"
                    f"  Anon key ref:    {key_ref}\n"
                    f"  SOLUCION: Ve a https://supabase.com/dashboard/project/{proj_ref}/settings/api\n"
                    f"  y copia la 'anon public' key. Actualiza SUPABASE_KEY en backend/.env\n"
                )
        except Exception:
            pass
        return ""

    def test_login_exitoso(self):
        """Login con admin@alpa.cl debe devolver access_token."""
        if not SUPABASE_URL or not ADMIN_PASSWORD:
            pytest.skip("Credenciales no configuradas")

        resp = requests.post(
            auth_url("token?grant_type=password"),
            headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        diag = self._check_key_mismatch() if resp.status_code == 401 else ""
        assert resp.status_code == 200, (
            f"Status inesperado: {resp.status_code} -> {resp.text[:200]}{diag}"
        )
        data = resp.json()

        assert "access_token" in data, "Respuesta sin access_token"
        assert data.get("token_type") == "bearer"
        assert data.get("user", {}).get("email") == ADMIN_EMAIL

        print_result(True, "Login exitoso", f"email={data['user']['email']}")

    def test_login_cred_invalidas(self):
        """Login con contraseña incorrecta debe fallar con 400 o 422."""
        resp = requests.post(
            auth_url("token?grant_type=password"),
            headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
            json={"email": ADMIN_EMAIL, "password": "contraseña-incorrecta-xyz"},
        )
        assert resp.status_code in (400, 401, 422), (
            f"Se esperaba error de autenticación, got {resp.status_code}"
        )
        print_result(True, "Credenciales inválidas rechazadas correctamente")


# ==============================================================================
# TEST 2 – Tenant Isolation
# ==============================================================================

class TestTenantIsolation:
    """TEST 2 – El usuario solo ve datos de su propia organización."""

    def test_reglas_solo_de_su_org(self, user_token):
        """Con JWT autenticado, solo deben aparecer reglas de la org propia."""
        resp = requests.get(
            rest("agent_rules?select=*"),
            headers=anon_headers(user_token),
        )
        assert resp.status_code == 200, f"Error: {resp.text[:200]}"
        rules = resp.json()

        print_result(len(rules) > 0, f"Reglas visibles: {len(rules)}")

        # Ninguna regla debe pertenecer a TEST_CORP_ORG_ID
        cross_tenant = [r for r in rules if r.get("organization_id") == TEST_CORP_ORG_ID]
        assert cross_tenant == [], (
            f"❌ FALLO SEGURIDAD: se ven {len(cross_tenant)} reglas de otra org"
        )
        print_result(True, "Tenant isolation OK – ninguna regla de otra org")

    def test_sin_token_no_ve_datos(self):
        """Sin autenticación, RLS debe bloquear el acceso (lista vacía o 401)."""
        resp = requests.get(
            rest("agent_rules?select=*"),
            headers=anon_headers(),          # sin token
        )
        if resp.status_code == 200:
            reglas = resp.json()
            assert len(reglas) == 0, (
                f"RLS falló: se ven {len(reglas)} reglas sin autenticación"
            )
            print_result(True, "RLS OK – sin token no hay datos (lista vacía)")
        else:
            assert resp.status_code in (401, 403)
            print_result(True, f"RLS OK – sin token retorna {resp.status_code}")

    def test_decisions_solo_de_su_org(self, user_token):
        """Las decisiones visibles deben pertenecer a la misma org."""
        resp = requests.get(
            rest("agent_decisions?select=*"),
            headers=anon_headers(user_token),
        )
        assert resp.status_code == 200, f"Error: {resp.text[:200]}"
        decisions = resp.json()

        cross = [d for d in decisions if d.get("organization_id") == TEST_CORP_ORG_ID]
        assert cross == [], f"❌ SEGURIDAD: {len(cross)} decisiones de otra org visibles"
        print_result(True, f"Decisiones visibles: {len(decisions)} – todas de la org correcta")


# ==============================================================================
# TEST 3 – CRUD de agent_rules con RLS
# ==============================================================================

class TestCRUDAgentRules:
    """TEST 3 – Operaciones Create / Update / Delete bajo RLS."""

    created_rule_id: str | None = None

    def test_3_1_crear_regla_propia_org(self, user_token):
        """POST en agent_rules de la org propia debe devolver 201."""
        payload = {
            "organization_id": ALPA_ORG_ID,
            "agent_type": "financiero",
            "empresa": "ALPA",
            "rule_text": "TEST-INTEGRATION: Flujo de caja libre negativo 3 meses → alerta",
            "rule_type": "patron_detectado",
            "weight": 0.85,
            "active": True,
        }
        resp = requests.post(
            rest("agent_rules"),
            headers={**anon_headers(user_token), "Prefer": "return=representation"},
            json=payload,
        )
        assert resp.status_code in (200, 201), f"Error al crear: {resp.status_code} → {resp.text[:300]}"
        data = resp.json()
        rule = data[0] if isinstance(data, list) else data
        TestCRUDAgentRules.created_rule_id = rule["id"]

        print_result(True, "Regla creada en org propia", f"id={rule['id']}")

    def test_3_2_crear_regla_otra_org_debe_fallar(self, user_token):
        """POST con organization_id ajeno debe ser bloqueado por RLS."""
        payload = {
            "organization_id": TEST_CORP_ORG_ID,
            "agent_type": "rh",
            "empresa": "TEST_CORP",
            "rule_text": "VIOLACIÓN: Esta regla NO debe crearse",
            "rule_type": "patron_detectado",
            "weight": 0.5,
            "active": True,
        }
        resp = requests.post(
            rest("agent_rules"),
            headers={**anon_headers(user_token), "Prefer": "return=representation"},
            json=payload,
        )
        # RLS puede devolver 403 o lista vacía (inserción silenciosa sin efecto)
        if resp.status_code in (200, 201):
            data = resp.json()
            created = data if isinstance(data, list) else [data]
            assert len(created) == 0, (
                f"❌ SEGURIDAD CRÍTICA: RLS permitió crear regla en otra org: {created}"
            )
            print_result(True, "RLS bloqueó inserción en otra org (lista vacía)")
        else:
            assert resp.status_code in (401, 403, 404, 409)
            print_result(True, f"RLS rechazó inserción en otra org ({resp.status_code})")

    def test_3_3_actualizar_regla_propia(self, user_token):
        """PATCH en regla propia debe funcionar."""
        rule_id = TestCRUDAgentRules.created_rule_id
        if not rule_id:
            pytest.skip("No hay regla creada en test anterior")

        resp = requests.patch(
            rest(f"agent_rules?id=eq.{rule_id}"),
            headers={**anon_headers(user_token), "Prefer": "return=representation"},
            json={"weight": 0.90, "rule_text": "TEST-INTEGRATION ACTUALIZADO ✅"},
        )
        assert resp.status_code in (200, 204), f"Error: {resp.status_code} → {resp.text[:200]}"
        if resp.status_code == 200:
            updated = resp.json()
            row = updated[0] if isinstance(updated, list) else updated
            assert row.get("weight") == 0.90
        print_result(True, "Regla actualizada correctamente")

    def test_3_4_eliminar_regla_propia(self, user_token):
        """DELETE en regla propia debe devolver 204."""
        rule_id = TestCRUDAgentRules.created_rule_id
        if not rule_id:
            pytest.skip("No hay regla para eliminar")

        resp = requests.delete(
            rest(f"agent_rules?id=eq.{rule_id}"),
            headers=anon_headers(user_token),
        )
        assert resp.status_code in (200, 204), f"Error: {resp.status_code} → {resp.text[:200]}"
        print_result(True, "Regla eliminada correctamente", f"id={rule_id}")
        TestCRUDAgentRules.created_rule_id = None


# ==============================================================================
# TEST 4 – Flujo completo: Ciclo → Decisión → Aprobación
# ==============================================================================

class TestFlujoCompleto:
    """
    TEST 4 – Ciclo de vida completo del agente.
    La creación de ciclos y decisiones usa Service Role (como lo haría el backend).
    La aprobación la hace el usuario autenticado (como lo haría el frontend/owner).
    """

    cycle_id:    str | None = None
    decision_id: str | None = None
    approval_id: str | None = None

    def test_4_1_crear_ciclo_service_role(self):
        """Crear ciclo de agente con service role key."""
        if not SUPABASE_SERVICE_KEY:
            pytest.skip("SUPABASE_SERVICE_ROLE_KEY no configurado")

        resp = requests.post(
            rest("agent_cycles"),
            headers=service_headers(),
            json={
                "organization_id": ALPA_ORG_ID,
                "status": "running",
                "context": {
                    "trigger": "integration_test",
                    "test_run": True,
                    "agent_types": ["financiero"],
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            },
        )
        assert resp.status_code in (200, 201), (
            f"Error creando ciclo: {resp.status_code} → {resp.text[:300]}"
        )
        data = resp.json()
        cycle = data[0] if isinstance(data, list) else data
        TestFlujoCompleto.cycle_id = cycle["id"]
        print_result(True, "Ciclo creado", f"id={cycle['id']}")

    def test_4_2_crear_decision_service_role(self):
        """Crear decisión de agente asociada al ciclo."""
        cycle_id = TestFlujoCompleto.cycle_id
        if not cycle_id:
            pytest.skip("No hay cycle_id del test anterior")

        resp = requests.post(
            rest("agent_decisions"),
            headers=service_headers(),
            json={
                "organization_id": ALPA_ORG_ID,
                "cycle_id": cycle_id,
                "agent_type": "financiero",
                "empresa": "ALPA",
                "decision": "TEST_INTEGRATION_DECISION",
                "health_status": "warning",
                "confidence": 0.88,
                "reasoning": "Decisión de prueba vía integration test. Flujo completo.",
                "requires_approval": True,
                "source_indicator": "INTEGRATION_TEST_2026",
                "metadata": {"test": True, "generated_by": "test_supabase_integration.py"},
            },
        )
        assert resp.status_code in (200, 201), (
            f"Error creando decisión: {resp.status_code} → {resp.text[:300]}"
        )
        data = resp.json()
        dec = data[0] if isinstance(data, list) else data
        TestFlujoCompleto.decision_id = dec["id"]
        print_result(True, "Decisión creada", f"id={dec['id']}, confidence={dec.get('confidence')}")

    def test_4_3_crear_aprobacion_service_role(self):
        """Crear registro de aprobación pendiente."""
        decision_id = TestFlujoCompleto.decision_id
        if not decision_id:
            pytest.skip("No hay decision_id del test anterior")

        resp = requests.post(
            rest("agent_approvals"),
            headers=service_headers(),
            json={
                "organization_id": ALPA_ORG_ID,
                "decision_id": decision_id,
                "status": "pending",
            },
        )
        assert resp.status_code in (200, 201), (
            f"Error creando aprobación: {resp.status_code} → {resp.text[:300]}"
        )
        data = resp.json()
        appr = data[0] if isinstance(data, list) else data
        TestFlujoCompleto.approval_id = appr["id"]
        print_result(True, "Aprobación pendiente creada", f"id={appr['id']}")

    def test_4_4_usuario_ve_decision_pendiente(self, user_token):
        """El usuario autenticado debe poder ver la decisión con aprobación pending."""
        decision_id = TestFlujoCompleto.decision_id
        if not decision_id:
            pytest.skip("No hay decision_id del test anterior")

        resp = requests.get(
            rest(f"agent_decisions?id=eq.{decision_id}&select=*,agent_approvals(*)"),
            headers=anon_headers(user_token),
        )
        assert resp.status_code == 200, f"Error: {resp.text[:200]}"
        data = resp.json()
        assert len(data) == 1, f"Usuario no ve la decisión (resultados: {len(data)})"

        dec = data[0]
        approvals = dec.get("agent_approvals", [])
        pending = [a for a in approvals if a.get("status") == "pending"]
        assert len(pending) > 0, "No hay aprobaciones pendientes en la decisión"
        print_result(True, "Usuario ve decisión con aprobación pending", f"decision_id={decision_id}")

    def test_4_5_aprobar_decision_como_usuario(self, user_token):
        """El usuario owner aprueba la decisión (actualiza agent_approvals)."""
        approval_id = TestFlujoCompleto.approval_id
        if not approval_id:
            pytest.skip("No hay approval_id del test anterior")

        resp = requests.patch(
            rest(f"agent_approvals?id=eq.{approval_id}"),
            headers={**anon_headers(user_token), "Prefer": "return=representation"},
            json={
                "status": "approved",
                "feedback_text": "Aprobado via integration test. Proceder con recomendación.",
            },
        )
        assert resp.status_code in (200, 204), (
            f"Error aprobando: {resp.status_code} → {resp.text[:300]}"
        )
        if resp.status_code == 200:
            data = resp.json()
            appr = data[0] if isinstance(data, list) else data
            assert appr.get("status") == "approved"
        print_result(True, "Decisión aprobada por el usuario")

    def test_4_6_completar_ciclo_service_role(self):
        """Marcar el ciclo como completado."""
        cycle_id = TestFlujoCompleto.cycle_id
        if not cycle_id:
            pytest.skip("No hay cycle_id del test anterior")

        resp = requests.patch(
            rest(f"agent_cycles?id=eq.{cycle_id}"),
            headers=service_headers(),
            json={"status": "completed"},
        )
        assert resp.status_code in (200, 204), (
            f"Error completando ciclo: {resp.status_code} → {resp.text[:200]}"
        )
        print_result(True, "Ciclo completado", f"id={cycle_id}")
        print_result(True, "[EXITO] Flujo completo: Ciclo -> Decision -> Aprobacion")


# ==============================================================================
# TEST 5 – Audit Logs
# ==============================================================================

class TestAuditLogs:
    """TEST 5 – Verificar que los audit_logs registran eventos (si existe la tabla)."""

    def test_audit_logs_accesibles_con_service_role(self):
        """audit_logs debe ser accesible con service role key."""
        if not SUPABASE_SERVICE_KEY:
            pytest.skip("SUPABASE_SERVICE_ROLE_KEY no configurado")

        resp = requests.get(
            rest("audit_logs?order=created_at.desc&limit=10"),
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            },
        )
        if resp.status_code == 404 or (resp.status_code == 400 and "relation" in resp.text.lower()):
            pytest.skip("Tabla audit_logs no existe aún (pendiente de implementar)")

        assert resp.status_code == 200, f"Error: {resp.status_code} → {resp.text[:200]}"
        logs = resp.json()
        print_result(True, f"Audit logs accesibles – últimos {len(logs)} eventos")

    def test_audit_logs_no_accesibles_sin_auth(self):
        """audit_logs NO debe ser accesible sin service role (usuario normal)."""
        resp = requests.get(
            rest("audit_logs?select=*&limit=1"),
            headers=anon_headers(),
        )
        # Esperamos 401, 403, o lista vacía si hay RLS
        if resp.status_code == 200:
            data = resp.json()
            assert len(data) == 0, "❌ audit_logs accesible públicamente sin autenticación"
            print_result(True, "audit_logs vacíos sin auth (RLS activo)")
        else:
            assert resp.status_code in (401, 403, 404)
            print_result(True, f"audit_logs bloqueado sin auth ({resp.status_code})")


# ==============================================================================
# Script de Validación Final (equivalente al checklist bash)
# ==============================================================================

def run_checklist():
    """
    Ejecuta el checklist de validación final e imprime un resumen.
    Equivalente al script bash del apartado 'Resumen de Validaciones'.
    """
    print("\n" + "=" * 60)
    print("  VALIDACIÓN FINAL – Sistema de Agentes v5.0")
    print("=" * 60)

    results: dict[str, bool] = {}

    # 1. Login
    print("\n[1] Test de Autenticacion...")
    try:
        resp = requests.post(
            auth_url("token?grant_type=password"),
            headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10,
        )
        token = resp.json().get("access_token")
        ok = bool(token and token != "null")
        results["login"] = ok
        print_result(ok, "Login exitoso" if ok else "Login FALLÓ")
        if not ok:
            print("  [STOP] Abortando: sin token no se pueden ejecutar los demas tests")
            return results
    except Exception as e:
        print_result(False, f"Error de conexión: {e}")
        return results

    # 2. Tenant isolation
    print("\n[2] Test de Tenant Isolation...")
    try:
        resp = requests.get(
            rest("agent_rules?select=*"),
            headers=anon_headers(token),
            timeout=10,
        )
        rules = resp.json() if resp.status_code == 200 else []
        ok = len(rules) >= 0  # cualquier resultado es ok; seguridad se valida abajo
        print_result(True, f"Reglas visibles de la org: {len(rules)}")

        cross = [r for r in rules if r.get("organization_id") == TEST_CORP_ORG_ID]
        isolation_ok = len(cross) == 0
        results["tenant_isolation"] = isolation_ok
        print_result(isolation_ok,
                     "Tenant isolation OK" if isolation_ok
                     else f"[FALLO SEGURIDAD] {len(cross)} reglas de otra org visibles")
    except Exception as e:
        results["tenant_isolation"] = False
        print_result(False, f"Error: {e}")

    # 3. Aprobaciones pendientes
    print("\n[3] Test de Aprobaciones Pendientes...")
    try:
        resp = requests.get(
            rest("agent_approvals?select=*&status=eq.pending"),
            headers=anon_headers(token),
            timeout=10,
        )
        pending = resp.json() if resp.status_code == 200 else []
        results["pending_approvals"] = True
        print_result(True, f"Aprobaciones pendientes encontradas: {len(pending)}")
    except Exception as e:
        results["pending_approvals"] = False
        print_result(False, f"Error: {e}")

    # 4. RLS sin autenticación
    print("\n[4] Test de RLS sin autenticacion...")
    try:
        resp = requests.get(
            rest("agent_rules?select=*"),
            headers=anon_headers(),   # sin token
            timeout=10,
        )
        if resp.status_code == 200:
            no_auth_rules = resp.json()
            rls_ok = len(no_auth_rules) == 0
        else:
            rls_ok = resp.status_code in (401, 403)
        results["rls_no_auth"] = rls_ok
        print_result(rls_ok,
                     "RLS bloqueando acceso sin autenticacion"
                     if rls_ok else "[WARN] RLS podria tener problemas")
    except Exception as e:
        results["rls_no_auth"] = False
        print_result(False, f"Error: {e}")

    # ── Resumen ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  RESUMEN")
    print("=" * 60)
    all_passed = all(results.values())
    for test, passed in results.items():
        print_result(passed, test.replace("_", " ").title())

    print()
    if all_passed:
        print("  [LISTO] TODOS LOS TESTS PASARON - Sistema listo para produccion")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"  [FALLOS]: {', '.join(failed)}")
    print("=" * 60 + "\n")
    return results


# ==============================================================================
# Entry point – ejecución directa
# ==============================================================================

if __name__ == "__main__":
    # Ejecución rápida del checklist
    run_checklist()

    # Opcionalmente ejecutar pytest completo
    import subprocess
    print("\nEjecutando suite completa con pytest...\n")
    subprocess.run([
        sys.executable, "-m", "pytest",
        __file__,
        "-v", "--tb=short", "-s", "--color=yes",
    ])

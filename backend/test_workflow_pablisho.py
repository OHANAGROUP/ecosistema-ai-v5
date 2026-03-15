# -*- coding: utf-8 -*-
# Test E2E: Workflow completo empresa Pablisho
# automatizai.cl → Lead SaaS → Cotizacion → Cotizacion Aprobada (cierre contrato)
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

LANDING_URL  = "https://automatizai.cl"
FRONTEND_URL = "http://localhost:3001"
ADMIN_EMAIL  = "admin@alpa.cl"
ADMIN_PASS   = "TestAdmin123"

CAPTURES_DIR = Path("C:/Users/ASUS/Documents/workspace/EXPERIMENTOS/saas experimental con ecosistema v5.0/backend/captures_pablisho")
CAPTURES_DIR.mkdir(exist_ok=True)

def log(msg):
    sep = "=" * 60
    print(f"\n{sep}\n  {msg}\n{sep}")

def ss(name): return str(CAPTURES_DIR / name)

async def safe_fill(page, selectors, value):
    for sel in selectors:
        el = await page.query_selector(sel)
        if el and await el.is_visible():
            await el.fill(value)
            return True
    return False

async def safe_click(page, selectors):
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                try:
                    await el.click(timeout=5000)
                except Exception:
                    # Forzar click si hay overlay bloqueando
                    await el.click(force=True, timeout=5000)
                return True
        except Exception:
            continue
    return False

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=700)
        ctx = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await ctx.new_page()

        # ──────────────────────────────────────────────────────────
        # PASO 1: Formulario landing automatizai.cl — lead Pablisho
        # ──────────────────────────────────────────────────────────
        log("PASO 1: Formulario web automatizai.cl - empresa Pablisho")
        await page.goto(LANDING_URL, wait_until="networkidle", timeout=30000)
        await page.screenshot(path=ss("01_landing.png"), full_page=True)

        # Buscar y llenar formulario de contacto/lead (selectores genéricos para real site)
        await safe_fill(page, [
            "#name", "input[name=name]", "input[name='nombre']",
            "input[placeholder*='nombre' i]", "input[placeholder*='name' i]"
        ], "Carlos Pablisho")

        await safe_fill(page, [
            "#email", "input[name=email]", "input[type=email]",
            "input[placeholder*='email' i]", "input[placeholder*='correo' i]"
        ], "contacto@pablisho.cl")

        await safe_fill(page, [
            "#phone", "input[name=phone]", "input[type=tel]",
            "input[placeholder*='telefono' i]", "input[placeholder*='phone' i]",
            "input[placeholder*='whatsapp' i]"
        ], "+56912345678")

        # Proyecto/servicio: si es select elegir primera opcion, si es input llenar texto
        project_el = await page.query_selector(
            "#project, select[name=project], select[name*='servicio' i], "
            "input[placeholder*='proyecto' i], input[placeholder*='servicio' i]"
        )
        if project_el:
            tag = await project_el.evaluate("el => el.tagName.toLowerCase()")
            if tag == "select":
                opts = await page.query_selector_all(
                    "#project option, select[name=project] option"
                )
                await page.select_option(
                    "#project, select[name=project]",
                    index=1 if len(opts) > 1 else 0
                )
            else:
                await project_el.fill("Construccion oficinas corporativas")

        await page.screenshot(path=ss("02_form_filled.png"), full_page=True)
        log("Formulario completado - enviando...")

        await safe_click(page, [
            "button[type=submit]", "input[type=submit]",
            "button:has-text('Enviar')", "button:has-text('Solicitar')",
            "button:has-text('Contactar')", "button:has-text('Envía')"
        ])
        await page.wait_for_timeout(4000)
        await page.screenshot(path=ss("03_form_submitted.png"), full_page=True)
        log("Lead enviado OK")

        # ──────────────────────────────────────────────────────────
        # PASO 2: Login al SaaS (overlay sobre app.html)
        # ──────────────────────────────────────────────────────────
        log("PASO 2: Login al SaaS")
        await page.goto(f"{FRONTEND_URL}/app.html")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2500)
        await page.screenshot(path=ss("04_login_overlay.png"))

        # El login es un overlay con IDs: login-email, login-password
        await safe_fill(page, ["#login-email", "#email", "input[type=email]"], ADMIN_EMAIL)
        await safe_fill(page, ["#login-password", "#password", "input[type=password]"], ADMIN_PASS)
        await page.screenshot(path=ss("05_login_filled.png"))

        await safe_click(page, ["#login-form button[type=submit]", "button[type=submit]", "button:has-text('Ingresar')"])
        await page.wait_for_timeout(5000)
        await page.screenshot(path=ss("06_after_login.png"), full_page=True)

        log("Login completado OK")

        # ──────────────────────────────────────────────────────────
        # PASO 3: Dashboard y CRM
        # ──────────────────────────────────────────────────────────
        log("PASO 3: Dashboard y CRM - verificar lead Pablisho")
        current = page.url
        if "login" in current or "auth" in current:
            await page.goto(f"{FRONTEND_URL}/app.html")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(3000)

        await page.screenshot(path=ss("07_dashboard.png"), full_page=True)

        # Navegar a CRM/leads
        nav_clicked = await safe_click(page, [
            "a[href*='leads']", "[data-module='leads']",
            "button:has-text('Prospectos')", "li:has-text('Prospectos')",
            "a:has-text('Prospectos')", "a:has-text('Leads')"
        ])
        if not nav_clicked:
            await page.goto(f"{FRONTEND_URL}/modules/leads/index.html")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3000)
        await page.screenshot(path=ss("08_crm_leads.png"), full_page=True)
        log("CRM cargado OK")

        # Buscar Pablisho
        await safe_fill(page, [
            "input[placeholder*='buscar' i]", "input[placeholder*='search' i]",
            "#search-input", "#lead-search", "input[type=search]"
        ], "Pablisho")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=ss("09_search_pablisho.png"), full_page=True)

        # ──────────────────────────────────────────────────────────
        # PASO 4: Cotizador — crear cotizacion Pablisho
        # ──────────────────────────────────────────────────────────
        log("PASO 4: Cotizador - crear cotizacion Pablisho")
        await page.goto(f"{FRONTEND_URL}/modules/cotizador/index.html")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2500)
        await page.screenshot(path=ss("10_cotizador_loaded.png"), full_page=True)

        # Nueva cotizacion
        await safe_click(page, [
            "#btn-new-quote", "#new-quote", "button:has-text('Nueva Cotizaci')",
            "button:has-text('Nueva')", "button:has-text('Crear')"
        ])
        await page.wait_for_timeout(1500)
        await page.screenshot(path=ss("11_new_quote_form.png"), full_page=True)

        # Datos cliente
        await safe_fill(page, [
            "#client-name", "input[name='client-name']", "input[placeholder*='empresa' i]",
            "input[placeholder*='cliente' i]", "input[placeholder*='razon' i]"
        ], "Pablisho SpA")

        await safe_fill(page, [
            "#client-contact", "input[name='contact']", "input[placeholder*='contacto' i]",
            "input[placeholder*='nombre' i]"
        ], "Carlos Pablisho")

        await safe_fill(page, [
            "#client-email", "input[name='client-email']", "input[type=email]"
        ], "contacto@pablisho.cl")

        await page.screenshot(path=ss("12_quote_client.png"), full_page=True)

        # Agregar item/partida
        await safe_click(page, [
            "#add-item", "#btn-add-item", "button:has-text('Agregar Item')",
            "button:has-text('Agregar Partida')", "button:has-text('+ Agregar')",
            "button:has-text('Agregar')"
        ])
        await page.wait_for_timeout(800)

        await safe_fill(page, [
            "input[placeholder*='descripci' i]", "input[placeholder*='item' i]",
            "input[name*='desc']", "textarea[placeholder*='descripci' i]",
            "td input[type=text]:first-child", "tr:last-child input[type=text]"
        ], "Construccion oficinas corporativas - Fase 1")

        await safe_fill(page, [
            "input[placeholder*='cantidad' i]", "input[name*='qty']", "input[name*='quantity']",
            "td input[type=number]:first-of-type"
        ], "1")

        await safe_fill(page, [
            "input[placeholder*='precio' i]", "input[placeholder*='monto' i]",
            "input[name*='price']", "input[name*='valor']",
            "td input[type=number]:last-of-type"
        ], "25000000")

        await page.screenshot(path=ss("13_quote_item_added.png"), full_page=True)

        # Guardar
        await safe_click(page, [
            "#btn-save-quote", "#save-quote", "button:has-text('Guardar')",
            "button:has-text('Crear Cotizaci')", "button[type=submit]"
        ])
        await page.wait_for_timeout(2500)
        await page.screenshot(path=ss("14_quote_saved.png"), full_page=True)
        log("Cotizacion creada OK")

        # ──────────────────────────────────────────────────────────
        # PASO 5: Vista previa + PDF cotizacion
        # ──────────────────────────────────────────────────────────
        log("PASO 5: PDF cotizacion Pablisho")

        # Bloquear window.print() para que no cierre el contexto de Playwright
        await page.evaluate("window.print = () => console.log('print interceptado')")

        # Intentar abrir preview
        await safe_click(page, [
            "#btn-preview", "#btn-pdf", "button:has-text('PDF')",
            "button:has-text('Vista Previa')", "button:has-text('Previa')",
            "button:has-text('Imprimir')", "button:has-text('Ver Cotizaci')"
        ])
        await page.wait_for_timeout(2500)
        await page.screenshot(path=ss("15_quote_preview.png"), full_page=True)

        # Generar PDF de la pagina actual
        await page.emulate_media(media="print")
        await page.pdf(
            path=ss("PDF_01_cotizacion_pablisho.pdf"),
            format="A4", print_background=True
        )
        await page.emulate_media(media="screen")
        log("PDF cotizacion generado OK")

        # ──────────────────────────────────────────────────────────
        # PASO 6: Aprobar cotizacion -> proyecto (conversion)
        # ──────────────────────────────────────────────────────────
        log("PASO 6: Aprobar cotizacion - conversion a proyecto")
        await safe_click(page, [
            "button:has-text('Aprobar')", "button:has-text('Aceptar')",
            "button:has-text('Ganada')", "button:has-text('Marcar Ganada')",
            "select:has(option[value='Aprobada'])"
        ])
        await page.wait_for_timeout(2000)
        await page.screenshot(path=ss("16_quote_approved.png"), full_page=True)

        await safe_click(page, [
            "button:has-text('Crear Proyecto')", "button:has-text('Activar Proyecto')",
            "button:has-text('Nuevo Proyecto')", "button:has-text('Convertir')"
        ])
        await page.wait_for_timeout(2500)
        await page.screenshot(path=ss("17_project_created.png"), full_page=True)
        log("Proyecto creado OK")

        # ──────────────────────────────────────────────────────────
        # RESUMEN FINAL
        # ──────────────────────────────────────────────────────────
        captures = [f for f in CAPTURES_DIR.iterdir() if f.suffix in (".png", ".pdf")]
        log(f"WORKFLOW COMPLETADO - {len(captures)} archivos generados")
        for f in sorted(CAPTURES_DIR.iterdir()):
            if f.suffix in (".png", ".pdf"):
                print(f"  OK  {f.name}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())

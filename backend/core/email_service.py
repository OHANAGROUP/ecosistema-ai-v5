#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/email_service.py
=====================
Servicio de envío de emails via Resend API.

Variables de entorno requeridas:
    RESEND_API_KEY  — Clave de API de Resend (https://resend.com)
    EMAIL_FROM      — Dirección de envío (debe estar verificada en Resend)
                      Ejemplo: "ALPA SaaS <noreply@alpaconstruccioneingenieria.cl>"
"""

import os
import logging
import httpx
from pathlib import Path
from dotenv import load_dotenv

_root = Path(__file__).resolve().parents[1]
load_dotenv(_root / ".env")

logger = logging.getLogger("email_service")

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "AutomatizAI <contacto@automatizai.cl>")
RESEND_URL = "https://api.resend.com/emails"


def _send(to: str, subject: str, html: str) -> bool:
    """Enviar un email via Resend. Devuelve True si fue exitoso."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY no configurado. Email NO enviado a %s", to)
        return False

    payload = {
        "from": EMAIL_FROM,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    try:
        resp = httpx.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            timeout=10,
        )
        if resp.status_code in (200, 201):
            logger.info("✅ Email enviado a %s — ID: %s", to, resp.json().get("id"))
            return True
        else:
            logger.error("❌ Resend error %d: %s", resp.status_code, resp.text[:200])
            return False
    except Exception as e:
        logger.error("❌ Resend exception: %s", e)
        return False


# ── Email Templates ────────────────────────────────────────────────────────────

_BASE_STYLE = """
<style>
  body { font-family: 'Helvetica Neue', Arial, sans-serif; background: #f8fafc; margin: 0; padding: 0; }
  .container { max-width: 600px; margin: 40px auto; background: #fff; border-radius: 12px;
               box-shadow: 0 4px 24px rgba(0,0,0,.07); overflow: hidden; }
  .header { background: linear-gradient(135deg, #0a0f1e, #1a1f2e); padding: 32px 40px; text-align: center; }
  .header img { height: 32px; margin-bottom: 12px; }
  .header h1 { color: #fff; font-size: 22px; margin: 0; font-weight: 700; letter-spacing: -.3px; }
  .header p { color: #94a3b8; font-size: 13px; margin: 6px 0 0; }
  .body { padding: 40px; }
  .body p { color: #334155; font-size: 15px; line-height: 1.7; margin: 0 0 16px; }
  .btn { display: inline-block; background: #F36F21; color: #fff; font-weight: 700;
         font-size: 15px; padding: 14px 32px; border-radius: 8px; text-decoration: none;
         margin: 8px 0; }
  .badge { display: inline-block; background: #fef3c7; color: #92400e; font-size: 12px;
           font-weight: 700; padding: 4px 12px; border-radius: 99px; margin-bottom: 20px; }
  .footer { background: #f1f5f9; padding: 24px 40px; text-align: center; }
  .footer p { color: #94a3b8; font-size: 12px; margin: 0; }
  hr { border: none; border-top: 1px solid #e2e8f0; margin: 24px 0; }
</style>
"""


def send_lead_acknowledgment_email(to: str, name: str, empresa: str = "") -> bool:
    """Email de confirmación enviado al prospecto que llena el formulario de automatizai.cl."""
    first = name.split()[0] if name else "allí"
    empresa_str = f" de <strong>{empresa}</strong>" if empresa else ""
    subject = "Recibimos tu consulta — AutomatizAI.cl"
    html = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">{_BASE_STYLE}</head><body>
    <div class="container">
      <div class="header">
        <h1>AutomatizAI.cl</h1>
        <p>Agentes IA para PYMEs chilenas</p>
      </div>
      <div class="body">
        <span class="badge">Consulta Recibida</span>
        <p><strong>Hola {first},</strong></p>
        <p>Gracias por tu interés en AutomatizAI{empresa_str}. Recibimos tu consulta y
           uno de nuestros especialistas se pondrá en contacto contigo en las próximas
           <strong>24 horas hábiles</strong>.</p>
        <p>Mientras tanto, esto es lo que puedes hacer con AutomatizAI:</p>
        <ul style="color:#334155;font-size:15px;line-height:2;">
          <li>Agente Financiero: reportes y alertas de flujo de caja automáticos</li>
          <li>Agente RRHH: gestión de equipo y remuneraciones sin planillas</li>
          <li>Agente Legal: seguimiento de contratos y vencimientos</li>
          <li>Embudo de ventas: cotizaciones y seguimiento de clientes</li>
        </ul>
        <hr>
        <p>Si tienes alguna pregunta urgente, responde directamente este email.</p>
        <p style="color:#64748b;font-size:13px;">— Pablo Maldonado<br>MD Asesorías Limitada · AutomatizAI.cl</p>
      </div>
      <div class="footer">
        <p>MD Asesorías Limitada · automatizai.cl</p>
        <p>Recibiste este email porque enviaste una consulta en nuestro sitio web.</p>
      </div>
    </div>
    </body></html>
    """
    return _send(to, subject, html)


def send_welcome_email(to: str, company_name: str) -> bool:
    """Email de bienvenida enviado al registrar una organización nueva (trial 14 días)."""
    subject = "Bienvenido a AutomatizAI — Tu prueba de 14 días ha comenzado"
    html = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">{_BASE_STYLE}</head><body>
    <div class="container">
      <div class="header">
        <h1>AutomatizAI.cl</h1>
        <p>Agentes IA para PYMEs chilenas</p>
      </div>
      <div class="body">
        <span class="badge">Cuenta Activada</span>
        <p><strong>Hola {company_name},</strong></p>
        <p>Tu organización ha sido registrada exitosamente en <strong>AutomatizAI</strong>.
           Tu período de prueba <strong>gratuita de 14 días</strong> ya ha comenzado.</p>
        <p>Desde la plataforma puedes:</p>
        <ul style="color:#334155;font-size:15px;line-height:2;">
          <li>Crear Cotizaciones profesionales con folio automático</li>
          <li>Monitorear alertas de Agentes IA en tiempo real</li>
          <li>Emitir Órdenes de Compra y Estados de Pago</li>
          <li>Auditar todos los documentos con versionado completo</li>
        </ul>
        <hr>
        <p>Si tienes alguna pregunta, responde a este email y te ayudamos.</p>
        <p style="color:#64748b;font-size:13px;">— Equipo AutomatizAI</p>
      </div>
      <div class="footer">
        <p>MD Asesorías Limitada · automatizai.cl · {company_name}</p>
        <p>Puedes cancelar tu suscripción en cualquier momento desde la plataforma.</p>
      </div>
    </div>
    </body></html>
    """
    return _send(to, subject, html)


def send_trial_day7_email(to: str, name: str, company_name: str) -> bool:
    """Email de mid-trial enviado al día 7: engagement y tips de uso."""
    first = name.split()[0] if name else company_name
    subject = f"{first}, ¿ya usaste estos módulos? — Llevas 7 días en AutomatizAI"
    html = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">{_BASE_STYLE}</head><body>
    <div class="container">
      <div class="header">
        <h1>7 días con AutomatizAI</h1>
        <p>Agentes IA para PYMEs chilenas</p>
      </div>
      <div class="body">
        <span class="badge">📅 Día 7 de 14</span>
        <p><strong>Hola {first},</strong></p>
        <p>Ya llevas una semana explorando AgentOS. Te quedan <strong>7 días</strong> de prueba gratuita.</p>
        <p>Según nuestros datos, las funciones que más tiempo ahorran a las constructoras son las que menos se usan al inicio:</p>
        <div style="background:#f8fafc;border-left:4px solid #F36F21;padding:16px 20px;border-radius:0 8px 8px 0;margin:16px 0;">
          <p style="margin:0 0 8px;font-weight:700;color:#0f172a;">⌘K — Command Palette</p>
          <p style="margin:0;font-size:13px;color:#64748b;">Presiona ⌘K (o Ctrl+K) en cualquier pantalla. Accede a cualquier módulo en 1 segundo, sin navegar menús.</p>
        </div>
        <div style="background:#f8fafc;border-left:4px solid #F36F21;padding:16px 20px;border-radius:0 8px 8px 0;margin:16px 0;">
          <p style="margin:0 0 8px;font-weight:700;color:#0f172a;">🤖 Agentes IA — Ciclo Autónomo</p>
          <p style="margin:0;font-size:13px;color:#64748b;">Configura un agente para que revise facturas pendientes cada lunes y te avise solo si hay anomalías.</p>
        </div>
        <div style="background:#f8fafc;border-left:4px solid #F36F21;padding:16px 20px;border-radius:0 8px 8px 0;margin:16px 0;">
          <p style="margin:0 0 8px;font-weight:700;color:#0f172a;">📊 Cotizador — APU automático</p>
          <p style="margin:0;font-size:13px;color:#64748b;">Importa tu listado de precios una vez y el sistema genera el APU de cada ítem automáticamente.</p>
        </div>
        <hr>
        <p>¿Tienes alguna duda o quieres una demo personalizada? Responde este email.</p>
        <a href="https://automatizai.cl/app" class="btn">Continuar en el Dashboard →</a>
        <p style="color:#64748b;font-size:13px;">— Equipo AutomatizAI</p>
      </div>
      <div class="footer">
        <p>MD Asesorías Limitada · automatizai.cl</p>
        <p>Quedan 7 días de tu prueba gratuita.</p>
      </div>
    </div>
    </body></html>
    """
    return _send(to, subject, html)


def send_trial_day12_email(to: str, name: str, company_name: str) -> bool:
    """Email de conversión enviado al día 12: urgencia + upgrade CTA."""
    first = name.split()[0] if name else company_name
    subject = f"{first}, quedan 2 días — no pierdas tus datos de {company_name}"
    html = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">{_BASE_STYLE}</head><body>
    <div class="container">
      <div class="header" style="background:linear-gradient(135deg,#7f1d1d,#991b1b);">
        <h1>Quedan 2 días de tu prueba</h1>
        <p>AgentOS v5.0 — {company_name}</p>
      </div>
      <div class="body">
        <span class="badge" style="background:#fee2e2;color:#991b1b;">🚨 2 DÍAS RESTANTES</span>
        <p><strong>Hola {first},</strong></p>
        <p>Tu prueba gratuita de AgentOS termina en <strong>2 días</strong>. Si no activas un plan, tu cuenta pasará a modo solo-lectura y <strong>no podrás crear nuevas cotizaciones, órdenes ni registros</strong>.</p>
        <p>Todo lo que construiste en estos 12 días — cotizaciones, proyectos, historial — se mantiene <strong>30 días adicionales</strong> para que puedas exportar si decides no continuar.</p>
        <hr>
        <p style="font-weight:700;color:#0f172a;">¿Cuánto cuesta mantener el acceso?</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px;margin:16px 0;">
          <tr style="background:#f1f5f9;">
            <td style="padding:10px 14px;font-weight:700;">Starter</td>
            <td style="padding:10px 14px;color:#64748b;">Hasta 3 proyectos</td>
            <td style="padding:10px 14px;font-weight:700;color:#F36F21;">2 UF/mes</td>
          </tr>
          <tr>
            <td style="padding:10px 14px;font-weight:700;">Empresa</td>
            <td style="padding:10px 14px;color:#64748b;">Proyectos ilimitados + IA Nivel 5</td>
            <td style="padding:10px 14px;font-weight:700;color:#F36F21;">3,5 UF/mes</td>
          </tr>
          <tr style="background:#f1f5f9;">
            <td style="padding:10px 14px;font-weight:700;">Enterprise</td>
            <td style="padding:10px 14px;color:#64748b;">Usuarios ilimitados + SLA 99,9%</td>
            <td style="padding:10px 14px;font-weight:700;color:#F36F21;">Cotizar</td>
          </tr>
        </table>
        <a href="https://automatizai.cl/upgrade" class="btn" style="display:block;text-align:center;">
          Activar mi plan ahora
        </a>
        <hr>
        <p style="color:#64748b;font-size:13px;">¿Tienes dudas antes de decidir? Responde este email y te llamamos hoy.</p>
        <p style="color:#64748b;font-size:13px;">— Equipo AutomatizAI · MD Asesorías Limitada</p>
      </div>
      <div class="footer">
        <p>MD Asesorías Limitada · automatizai.cl</p>
        <p>Puedes cancelar en cualquier momento desde la plataforma.</p>
      </div>
    </div>
    </body></html>
    """
    return _send(to, subject, html)


def send_trial_expiring_email(to: str, company_name: str, days_left: int) -> bool:
    """Email de aviso enviado cuando el trial está próximo a expirar (3 días y 1 día)."""
    urgency = "🚨 URGENTE:" if days_left <= 1 else "⚠️ Aviso:"
    days_text = "HOY" if days_left < 1 else f"en {days_left} día{'s' if days_left > 1 else ''}"
    subject = f"{urgency} Tu prueba de ALPA SaaS expira {days_text}"
    badge_color = "#fee2e2" if days_left <= 1 else "#fef3c7"
    badge_text_color = "#991b1b" if days_left <= 1 else "#92400e"
    html = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">{_BASE_STYLE}</head><body>
    <div class="container">
      <div class="header">
        <h1>Tu prueba expira {days_text}</h1>
        <p>ALPA SaaS v5.0 — Gestión Empresarial Inteligente</p>
      </div>
      <div class="body">
        <span class="badge" style="background:{badge_color};color:{badge_text_color};">
          ⏳ {days_text.upper()}
        </span>
        <p><strong>Hola {company_name},</strong></p>
        <p>Tu período de prueba gratuita en <strong>ALPA SaaS v5.0</strong> expira <strong>{days_text}</strong>.</p>
        <p>Para mantener acceso a todas tus cotizaciones, datos históricos y agentes IA, activa tu plan <strong>Premium</strong> ahora:</p>
        <a href="https://automatizai.cl/upgrade" class="btn">
          Activar Plan Premium
        </a>
        <hr>
        <p style="color:#64748b;font-size:13px;">
          Si no activas tu plan, tu cuenta entrará en modo de solo-lectura.
          Tus datos estarán seguros por 30 días adicionales.
        </p>
        <p style="color:#64748b;font-size:13px;">— Equipo AutomatizAI</p>
      </div>
      <div class="footer">
        <p>MD Asesorías Limitada · automatizai.cl · {company_name}</p>
      </div>
    </div>
    </body></html>
    """
    return _send(to, subject, html)

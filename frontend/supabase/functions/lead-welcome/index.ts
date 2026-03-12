/**
 * LEAD WELCOME — Supabase Edge Function
 * ─────────────────────────────────────
 * Trigger: Database Webhook → INSERT on public.leads
 * Env vars needed (Supabase Dashboard → Project → Edge Functions → Secrets):
 *   RESEND_API_KEY   → get free key at resend.com (3.000 emails/mes gratis)
 *   SALES_EMAIL      → email del equipo de ventas para notificaciones
 *   FROM_EMAIL       → email verificado en Resend (ej: noreply@mdasesorias.cl)
 *
 * Deploy: supabase functions deploy lead-welcome --project-ref <tu-ref>
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY") ?? "";
const SALES_EMAIL    = Deno.env.get("SALES_EMAIL")    ?? "ventas@mdasesorias.cl";
const FROM_EMAIL     = Deno.env.get("FROM_EMAIL")      ?? "noreply@mdasesorias.cl";
const APP_URL        = "https://saas-experimental-con-ecosistema-v5.vercel.app";

// ── Helpers ──────────────────────────────────────────────────────────────────

async function sendEmail(to: string, subject: string, html: string) {
  if (!RESEND_API_KEY) {
    console.warn("[lead-welcome] RESEND_API_KEY no configurado — email omitido");
    return;
  }
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ from: `Ecosistema AI <${FROM_EMAIL}>`, to, subject, html }),
  });
  if (!res.ok) {
    const err = await res.text();
    console.error("[lead-welcome] Resend error:", err);
  }
}

// ── Email templates ───────────────────────────────────────────────────────────

function welcomeHtml(lead: Record<string, string>): string {
  const name  = lead.name || lead.nombre || "equipo";
  const first = name.split(" ")[0];
  const plan  = lead.origin?.includes("Plan") ? lead.origin.replace("Landing - ", "") : "";

  return `<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/></head>
<body style="margin:0;padding:0;background:#0a0b0d;font-family:'Helvetica Neue',Arial,sans-serif;">
  <div style="max-width:600px;margin:0 auto;padding:40px 20px;">

    <!-- Header -->
    <div style="border-bottom:2px solid #f5620f;padding-bottom:24px;margin-bottom:32px;">
      <span style="font-size:22px;font-weight:900;letter-spacing:4px;color:#e8e9eb;text-transform:uppercase;">
        ECOSISTEMA<span style="color:#f5620f;">AI</span>
        <span style="font-size:11px;color:#6b7280;font-weight:400;margin-left:8px;">v5.0</span>
      </span>
    </div>

    <!-- Body -->
    <h1 style="color:#e8e9eb;font-size:28px;font-weight:800;margin:0 0 12px;line-height:1.2;">
      Hola, ${first} 👋
    </h1>
    <p style="color:#9ca3af;font-size:15px;line-height:1.7;margin:0 0 24px;">
      Tu solicitud llegó. El equipo de <strong style="color:#e8e9eb;">MD Asesorías</strong> te contactará
      en <strong style="color:#f5620f;">menos de 24 horas</strong> para agendar tu demo personalizada.
    </p>

    ${plan ? `<div style="background:#1a1d24;border:1px solid #f5620f33;border-radius:8px;padding:16px 20px;margin-bottom:24px;">
      <p style="color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:2px;margin:0 0 4px;">Plan seleccionado</p>
      <p style="color:#f5620f;font-size:16px;font-weight:700;margin:0;">${plan}</p>
    </div>` : ""}

    <!-- CTA -->
    <div style="margin:32px 0;">
      <a href="${APP_URL}/register.html"
         style="display:inline-block;background:#f5620f;color:#0a0b0d;font-weight:800;font-size:13px;
                letter-spacing:2px;text-transform:uppercase;padding:14px 28px;border-radius:4px;
                text-decoration:none;">
        Iniciar prueba gratuita →
      </a>
    </div>

    <!-- What's included -->
    <div style="background:#111318;border-radius:8px;padding:24px;margin-bottom:32px;">
      <p style="color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:2px;margin:0 0 16px;">
        Tu prueba de 14 días incluye
      </p>
      ${["Todos los módulos activos",
         "4 agentes de IA especializados",
         "Soporte por WhatsApp durante el onboarding",
         "Migración de tus datos desde Excel",
         "Sin tarjeta de crédito requerida"
        ].map(f => `
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
          <span style="color:#f5620f;font-size:14px;">✓</span>
          <span style="color:#b8bcc8;font-size:14px;">${f}</span>
        </div>`).join("")}
    </div>

    <!-- Footer -->
    <div style="border-top:1px solid #1e2128;padding-top:24px;text-align:center;">
      <p style="color:#4b5563;font-size:12px;margin:0 0 8px;">
        ¿Tienes alguna pregunta ahora?
      </p>
      <a href="https://wa.me/56912345678?text=Hola%2C%20acabo%20de%20solicitar%20una%20demo"
         style="color:#25D366;font-size:13px;font-weight:600;text-decoration:none;">
        📱 WhatsApp: +569 1234 5678
      </a>
      <p style="color:#374151;font-size:11px;margin:20px 0 0;">
        MD Asesorías Ltda · <a href="${APP_URL}/privacidad.html" style="color:#4b5563;">Privacidad</a>
      </p>
    </div>
  </div>
</body>
</html>`;
}

function salesNotificationHtml(lead: Record<string, string>): string {
  const rows = [
    ["Nombre",  lead.name || lead.nombre || "—"],
    ["Email",   lead.email || "—"],
    ["Empresa", lead.project_description?.split("|")[0]?.replace("Empresa:", "").trim() || lead.empresa || "—"],
    ["Tamaño",  lead.project_description?.match(/Tamaño: ([^|]+)/)?.[1]?.trim() || "—"],
    ["Plan",    lead.origin?.includes("Plan") ? lead.origin.replace("Landing - ", "") : "Sin plan seleccionado"],
    ["Fuente",  lead.origin || lead.fuente || "—"],
    ["Fecha",   new Date().toLocaleString("es-CL", { timeZone: "America/Santiago" })],
  ];

  return `<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#0f1219;font-family:'Helvetica Neue',Arial,sans-serif;">
  <div style="max-width:600px;margin:0 auto;padding:32px 20px;">
    <div style="border-left:4px solid #f5620f;padding-left:16px;margin-bottom:28px;">
      <h1 style="color:#e8e9eb;font-size:20px;font-weight:800;margin:0 0 4px;">🔥 Nuevo lead entrante</h1>
      <p style="color:#6b7280;font-size:13px;margin:0;">Ecosistema AI v5.0 — Acción requerida</p>
    </div>
    <table style="width:100%;border-collapse:collapse;">
      ${rows.map(([k, v]) => `
      <tr>
        <td style="padding:10px 12px;background:#111318;color:#6b7280;font-size:12px;
                   text-transform:uppercase;letter-spacing:1px;width:120px;border-bottom:1px solid #1e2128;">${k}</td>
        <td style="padding:10px 12px;background:#111318;color:#e8e9eb;font-size:14px;
                   font-weight:600;border-bottom:1px solid #1e2128;">${v}</td>
      </tr>`).join("")}
    </table>
    <div style="margin-top:24px;display:flex;gap:12px;flex-wrap:wrap;">
      <a href="mailto:${lead.email}"
         style="background:#f5620f;color:#0a0b0d;font-weight:800;font-size:12px;letter-spacing:1px;
                text-transform:uppercase;padding:12px 20px;border-radius:4px;text-decoration:none;">
        Responder por email
      </a>
      <a href="https://wa.me/56?text=Hola%20${encodeURIComponent(lead.name || lead.nombre || '')}"
         style="background:#25D366;color:#fff;font-weight:800;font-size:12px;letter-spacing:1px;
                text-transform:uppercase;padding:12px 20px;border-radius:4px;text-decoration:none;">
        WhatsApp
      </a>
    </div>
  </div>
</body>
</html>`;
}

// ── Main handler ──────────────────────────────────────────────────────────────

serve(async (req: Request) => {
  // Health check
  if (req.method === "GET") {
    return new Response(JSON.stringify({ ok: true, fn: "lead-welcome" }), {
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    const body = await req.json();
    // Supabase DB Webhook sends: { type: "INSERT", record: {...}, ... }
    const lead: Record<string, string> = body.record ?? body;

    if (!lead.email) {
      return new Response(JSON.stringify({ error: "No email in payload" }), { status: 400 });
    }

    // Fire both emails in parallel
    await Promise.all([
      sendEmail(
        lead.email,
        "Tu solicitud llegó — Ecosistema AI v5.0",
        welcomeHtml(lead)
      ),
      sendEmail(
        SALES_EMAIL,
        `🔥 Nuevo lead: ${lead.name || lead.nombre || lead.email}`,
        salesNotificationHtml(lead)
      ),
    ]);

    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("[lead-welcome] Error:", err);
    return new Response(JSON.stringify({ error: String(err) }), { status: 500 });
  }
});

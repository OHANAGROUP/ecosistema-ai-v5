-- ============================================================================
-- monitoring_views.sql
-- Vistas de monitoreo para el sistema de agentes en producción
-- Ejecutar en Supabase SQL Editor con service role
-- ============================================================================

-- 0. Asegurar que la tabla audit_logs tenga la estructura completa (REPARACIÓN INTEGRAL)
DO $$ 
BEGIN
    -- Crear tabla si no existe
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'audit_logs') THEN
        CREATE TABLE public.audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_type TEXT,
            user_id UUID,
            organization_id UUID,
            resource_type TEXT,
            resource_id TEXT,
            action TEXT,
            success BOOLEAN DEFAULT true,
            details JSONB,
            ip_address TEXT,
            timestamp TIMESTAMPTZ DEFAULT NOW(),
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    ELSE
        -- Verificar y añadir columnas una por una si faltan
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'event_type') THEN
            ALTER TABLE public.audit_logs ADD COLUMN event_type TEXT;
        END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'user_id') THEN
            ALTER TABLE public.audit_logs ADD COLUMN user_id UUID;
        END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'organization_id') THEN
            ALTER TABLE public.audit_logs ADD COLUMN organization_id UUID;
        END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'resource_type') THEN
            ALTER TABLE public.audit_logs ADD COLUMN resource_type TEXT;
        END IF;
        
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'resource_id') THEN
            ALTER TABLE public.audit_logs ADD COLUMN resource_id TEXT;
        END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'action') THEN
            ALTER TABLE public.audit_logs ADD COLUMN action TEXT;
        END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'success') THEN
            ALTER TABLE public.audit_logs ADD COLUMN success BOOLEAN DEFAULT true;
        END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'details') THEN
            ALTER TABLE public.audit_logs ADD COLUMN details JSONB;
        END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'ip_address') THEN
            ALTER TABLE public.audit_logs ADD COLUMN ip_address TEXT;
        END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'timestamp') THEN
            ALTER TABLE public.audit_logs ADD COLUMN timestamp TIMESTAMPTZ DEFAULT NOW();
        END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_logs' AND column_name = 'created_at') THEN
            ALTER TABLE public.audit_logs ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW();
        END IF;
    END IF;
END $$;

-- 1. Eventos de Seguridad (últimos 30 días)
CREATE OR REPLACE VIEW public.v_security_events AS
SELECT 
    al.created_at,
    al.action,
    COALESCE(al.resource_type, 'system') AS table_name,
    al.resource_id,
    u.email           AS user_email,
    o.name            AS organization,
    al.ip_address,
    al.details,
    CASE 
        WHEN al.action ILIKE '%failed%'    THEN 'critical'
        WHEN al.action ILIKE '%denied%'    THEN 'warning'
        WHEN al.action ILIKE '%violation%' THEN 'critical'
        WHEN al.action = 'DELETE'          THEN 'warning'
        ELSE 'info'
    END AS severity
FROM public.audit_logs al
LEFT JOIN auth.users u         ON al.user_id         = u.id
LEFT JOIN public.organizations o ON al.organization_id = o.id
WHERE al.created_at > NOW() - INTERVAL '30 days'
ORDER BY al.created_at DESC;

-- 2. Decisiones Críticas Pendientes
CREATE OR REPLACE VIEW public.v_pending_critical_decisions AS
SELECT 
    ad.id,
    ad.agent_type,
    ad.empresa,
    ad.decision,
    ad.health_status,
    ad.confidence,
    ad.reasoning,
    ad.decision_timestamp,
    o.name  AS organization,
    aa.status AS approval_status,
    ROUND(
        EXTRACT(EPOCH FROM (NOW() - ad.decision_timestamp)) / 3600
    )::int AS hours_pending
FROM public.agent_decisions ad
JOIN  public.organizations    o  ON ad.organization_id = o.id
LEFT JOIN public.agent_approvals aa ON ad.id           = aa.decision_id
WHERE ad.requires_approval = true
  AND ad.health_status     IN ('critical', 'warning')
  AND (aa.status = 'pending' OR aa.status IS NULL)
ORDER BY 
    CASE ad.health_status WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
    ad.decision_timestamp;

-- 3. Ciclos Fallidos (últimos 7 días)
CREATE OR REPLACE VIEW public.v_failed_cycles AS
SELECT 
    ac.id,
    ac.started_at,
    ac.completed_at,
    ac.context,
    o.name AS organization,
    ROUND(
        EXTRACT(EPOCH FROM (ac.completed_at - ac.started_at)) / 60
    )::int AS duration_minutes
FROM public.agent_cycles ac
JOIN  public.organizations o ON ac.organization_id = o.id
WHERE ac.status = 'failed'
  AND ac.started_at > NOW() - INTERVAL '7 days'
ORDER BY ac.started_at DESC;

-- 4. Uso por Organización
CREATE OR REPLACE VIEW public.v_organization_usage AS
SELECT 
    o.name                                                        AS organization,
    COUNT(DISTINCT ar.id)                                         AS total_rules,
    COUNT(DISTINCT ac.id)                                         AS total_cycles,
    COUNT(DISTINCT ad.id)                                         AS total_decisions,
    COUNT(DISTINCT aa.id) FILTER (WHERE aa.status = 'pending')    AS pending_approvals,
    COUNT(DISTINCT ac.id) FILTER (WHERE ac.status = 'failed')     AS failed_cycles,
    ROUND(AVG(ad.confidence)::numeric, 2)                         AS avg_confidence,
    MAX(ac.started_at)                                            AS last_cycle_run
FROM public.organizations    o
LEFT JOIN public.agent_rules      ar ON o.id = ar.organization_id
LEFT JOIN public.agent_cycles     ac ON o.id = ac.organization_id
LEFT JOIN public.agent_decisions  ad ON o.id = ad.organization_id
LEFT JOIN public.agent_approvals  aa ON o.id = aa.organization_id
GROUP BY o.id, o.name
ORDER BY o.name;

-- Grant acceso de lectura desde el backend
GRANT SELECT ON public.v_security_events           TO service_role;
GRANT SELECT ON public.v_pending_critical_decisions TO service_role;
GRANT SELECT ON public.v_failed_cycles              TO service_role;
GRANT SELECT ON public.v_organization_usage         TO service_role;

-- Verificar
SELECT viewname FROM pg_views
WHERE schemaname = 'public'
  AND viewname LIKE 'v_%'
ORDER BY viewname;

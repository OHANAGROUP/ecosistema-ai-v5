-- ============================================================================
-- fix_agent_rls.sql
-- Corrige el tenant isolation en agent_rules y agent_decisions.
--
-- PROBLEMA: get_tenant_id() lee solo JWT metadata; cuando está vacío devuelve
-- NULL y las políticas USING (organization_id = NULL) son falsas para TODAS
-- las filas... pero si la tabla NO tiene política para authenticated, Supabase
-- permite ver todo (permissive by default when no policy matches).
--
-- SOLUCIÓN: Crear una función robusta que lea primero JWT, luego
-- organization_members (fallback DB), y aplicar políticas ALL sobre las
-- tablas de agentes.
-- ============================================================================

-- 1. Función robusta: JWT primero, luego tabla como fallback
CREATE OR REPLACE FUNCTION public.get_tenant_id() RETURNS uuid AS $$
  SELECT COALESCE(
    -- Intento 1: app_metadata en JWT (más seguro, lo setea el backend)
    NULLIF((auth.jwt() -> 'app_metadata' ->> 'organization_id'), '')::uuid,
    -- Intento 2: user_metadata en JWT
    NULLIF((auth.jwt() -> 'user_metadata' ->> 'organization_id'), '')::uuid,
    -- Fallback: consulta directa a organization_members (siempre funciona)
    (SELECT organization_id FROM public.organization_members
     WHERE user_id = auth.uid() LIMIT 1)
  );
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- 2. RLS en agent_rules
ALTER TABLE public.agent_rules ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation_agent_rules" ON public.agent_rules;
CREATE POLICY "tenant_isolation_agent_rules"
ON public.agent_rules FOR ALL
USING  (organization_id = public.get_tenant_id())
WITH CHECK (organization_id = public.get_tenant_id());

-- 3. RLS en agent_decisions
ALTER TABLE public.agent_decisions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation_agent_decisions" ON public.agent_decisions;
CREATE POLICY "tenant_isolation_agent_decisions"
ON public.agent_decisions FOR ALL
USING  (organization_id = public.get_tenant_id())
WITH CHECK (organization_id = public.get_tenant_id());

-- 4. RLS en agent_approvals
ALTER TABLE public.agent_approvals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation_agent_approvals" ON public.agent_approvals;
CREATE POLICY "tenant_isolation_agent_approvals"
ON public.agent_approvals FOR ALL
USING  (organization_id = public.get_tenant_id())
WITH CHECK (organization_id = public.get_tenant_id());

-- 5. RLS en agent_cycles
ALTER TABLE public.agent_cycles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation_agent_cycles" ON public.agent_cycles;
CREATE POLICY "tenant_isolation_agent_cycles"
ON public.agent_cycles FOR ALL
USING  (organization_id = public.get_tenant_id())
WITH CHECK (organization_id = public.get_tenant_id());

-- 6. Permisos mínimos para authenticated
GRANT SELECT, INSERT, UPDATE, DELETE ON public.agent_rules       TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.agent_decisions   TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.agent_approvals   TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.agent_cycles      TO authenticated;
GRANT ALL ON public.agent_rules       TO service_role;
GRANT ALL ON public.agent_decisions   TO service_role;
GRANT ALL ON public.agent_approvals   TO service_role;
GRANT ALL ON public.agent_cycles      TO service_role;

-- 7. Verificación
SELECT tablename, policyname, cmd, qual
FROM pg_policies
WHERE tablename IN ('agent_rules','agent_decisions','agent_approvals','agent_cycles')
ORDER BY tablename, cmd;

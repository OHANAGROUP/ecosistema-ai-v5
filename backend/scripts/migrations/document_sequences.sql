-- ============================================================
-- MIGRACIÓN: Correlativos Centralizados + Versiones
-- ALPA SaaS v5.0 — Semana 1-2
-- 
-- INSTRUCCIONES:
--   1. Abrir Supabase Dashboard → SQL Editor
--   2. Pegar y ejecutar este script completo
--   3. Verificar: SELECT * FROM document_sequences;
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- 1. TABLA: document_sequences
--    Controla correlativos por (org, tipo, año)
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS document_sequences (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID REFERENCES organizations(id) ON DELETE CASCADE,
    document_type    TEXT NOT NULL,   -- 'quote' | 'purchase_order' | 'payment_status'
    year             INTEGER NOT NULL,
    last_number      INTEGER DEFAULT 0,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, document_type, year)
);

-- Trigger para updated_at automático
CREATE OR REPLACE FUNCTION update_document_sequences_timestamp()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;$$;

DROP TRIGGER IF EXISTS trg_doc_seq_updated_at ON document_sequences;
CREATE TRIGGER trg_doc_seq_updated_at
    BEFORE UPDATE ON document_sequences
    FOR EACH ROW EXECUTE FUNCTION update_document_sequences_timestamp();

-- RLS
ALTER TABLE document_sequences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_sequences" ON document_sequences
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "org_isolation_sequences" ON document_sequences
    FOR ALL USING (organization_id = get_tenant_id());

-- ──────────────────────────────────────────────────────────────
-- 2. FUNCIÓN RPC: get_next_document_number
--    Atómica — safe para múltiples usuarios concurrentes
-- ──────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION get_next_document_number(
    p_org_id    UUID,
    p_doc_type  TEXT,
    p_year      INTEGER DEFAULT NULL
) RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_prefix     TEXT;
    v_next_num   INTEGER;
    v_year       INTEGER;
    v_type_code  TEXT;
    v_result     TEXT;
BEGIN
    -- Usar año actual si no se pasa
    v_year := COALESCE(p_year, EXTRACT(YEAR FROM NOW())::INTEGER);

    -- Obtener prefijo de la organización (default: ALPA)
    SELECT COALESCE(settings->>'prefix', 'ALPA')
    INTO v_prefix
    FROM organizations
    WHERE id = p_org_id;

    v_prefix := COALESCE(v_prefix, 'ALPA');

    -- Código de tipo de documento
    v_type_code := CASE p_doc_type
        WHEN 'purchase_order'  THEN 'OC'
        WHEN 'payment_status'  THEN 'EP'
        ELSE ''  -- 'quote' no lleva código extra
    END;

    -- Insertar o incrementar de forma atómica
    INSERT INTO document_sequences (organization_id, document_type, year, last_number)
    VALUES (p_org_id, p_doc_type, v_year, 1)
    ON CONFLICT (organization_id, document_type, year)
    DO UPDATE SET
        last_number = document_sequences.last_number + 1,
        updated_at  = NOW()
    RETURNING last_number INTO v_next_num;

    -- Formatear resultado
    IF v_type_code = '' THEN
        v_result := v_prefix || '-' || v_year || '-' || lpad(v_next_num::TEXT, 3, '0');
    ELSE
        v_result := v_prefix || '-' || v_type_code || '-' || v_year || '-' || lpad(v_next_num::TEXT, 3, '0');
    END IF;

    RETURN v_result;
END;
$$;

-- Dar acceso a usuarios autenticados (RLS de la tabla restringe por org)
GRANT EXECUTE ON FUNCTION get_next_document_number(UUID, TEXT, INTEGER) TO authenticated;

-- ──────────────────────────────────────────────────────────────
-- 3. TABLA: document_versions
--    Historial inmutable de cada versión guardada
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS document_versions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID REFERENCES organizations(id) ON DELETE CASCADE,
    document_number  TEXT NOT NULL,     -- ej. ALPA-2026-001
    document_type    TEXT NOT NULL,     -- 'quote' | 'purchase_order' | 'payment_status'
    version          INTEGER NOT NULL DEFAULT 1,
    data             JSONB NOT NULL,
    created_by_email TEXT,
    created_by_name  TEXT,
    change_summary   TEXT,              -- "Ajuste precio ítem 3, corrección RUT"
    is_current       BOOLEAN DEFAULT TRUE,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, document_number, version)
);

-- Índice parcial para consultar versión actual rápido
CREATE INDEX IF NOT EXISTS idx_doc_versions_current
    ON document_versions (organization_id, document_number)
    WHERE is_current = TRUE;

-- RLS
ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_versions" ON document_versions
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "org_isolation_versions" ON document_versions
    FOR ALL USING (organization_id = get_tenant_id());

-- ──────────────────────────────────────────────────────────────
-- 4. FUNCIÓN: save_document_version
--    Marca versiones anteriores como no-current + inserta nueva
-- ──────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION save_document_version(
    p_org_id         UUID,
    p_doc_number     TEXT,
    p_doc_type       TEXT,
    p_data           JSONB,
    p_created_by_email TEXT DEFAULT NULL,
    p_created_by_name  TEXT DEFAULT NULL,
    p_change_summary   TEXT DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_next_version  INTEGER;
    v_result        JSONB;
BEGIN
    -- Marcar versiones anteriores como no-current
    UPDATE document_versions
    SET is_current = FALSE
    WHERE organization_id = p_org_id
      AND document_number  = p_doc_number
      AND is_current       = TRUE;

    -- Calcular versión siguiente
    SELECT COALESCE(MAX(version), 0) + 1
    INTO v_next_version
    FROM document_versions
    WHERE organization_id = p_org_id
      AND document_number  = p_doc_number;

    -- Insertar nueva versión
    INSERT INTO document_versions
        (organization_id, document_number, document_type, version, data,
         created_by_email, created_by_name, change_summary, is_current)
    VALUES
        (p_org_id, p_doc_number, p_doc_type, v_next_version, p_data,
         p_created_by_email, p_created_by_name, p_change_summary, TRUE)
    RETURNING jsonb_build_object(
        'id',        id,
        'version',   version,
        'created_at', created_at
    ) INTO v_result;

    RETURN v_result;
END;
$$;

GRANT EXECUTE ON FUNCTION save_document_version(UUID, TEXT, TEXT, JSONB, TEXT, TEXT, TEXT) TO authenticated;

-- ──────────────────────────────────────────────────────────────
-- 5. VERIFICACIÓN
-- ──────────────────────────────────────────────────────────────

-- Correr estas queries para verificar que todo quedó bien:
SELECT 'document_sequences'  AS tabla, count(*) FROM document_sequences
UNION ALL
SELECT 'document_versions'   AS tabla, count(*) FROM document_versions;

-- Test rápido de la función (reemplaza TU_ORG_ID con un UUID real de organizations)
-- SELECT get_next_document_number('TU_ORG_ID'::UUID, 'quote');
-- SELECT get_next_document_number('TU_ORG_ID'::UUID, 'purchase_order');
-- SELECT get_next_document_number('TU_ORG_ID'::UUID, 'payment_status');

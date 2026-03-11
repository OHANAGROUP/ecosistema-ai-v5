-- ═══════════════════════════════════════════════════════
-- EstadoPago v4 — Migration: Add hierarchical EP fields
-- Ejecutar en: Supabase Dashboard → SQL Editor
-- Fecha: 2026-03-11
-- ═══════════════════════════════════════════════════════

-- 1. Columnas base del EP (árbol, columnas extra, estado, contrato)
ALTER TABLE public.projects
  ADD COLUMN IF NOT EXISTS ep_tree            JSONB         DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS ep_extra_cols      JSONB         DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS ep_status          TEXT          DEFAULT 'draft',
  ADD COLUMN IF NOT EXISTS ep_contract_amount NUMERIC(15,2) DEFAULT 0;

-- 2. Columnas de metadatos del documento EP (número, período, fecha)
ALTER TABLE public.projects
  ADD COLUMN IF NOT EXISTS ep_num             TEXT          DEFAULT '',
  ADD COLUMN IF NOT EXISTS ep_period          TEXT          DEFAULT '',
  ADD COLUMN IF NOT EXISTS ep_date            DATE          DEFAULT NULL;

-- 3. Verificar que las columnas existen
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'projects'
  AND column_name IN (
    'ep_tree','ep_extra_cols','ep_status',
    'ep_contract_amount','ep_num','ep_period','ep_date'
  )
ORDER BY column_name;

-- ─── NOTAS ───────────────────────────────────────────────
-- ep_tree          : árbol JSON del EstadoPago (Cap → Sub → Partida)
-- ep_extra_cols    : columnas dinámicas definidas por el usuario
-- ep_status        : 'draft' | 'sent' | 'approved'
-- ep_contract_amount: monto del contrato para % avance
-- ep_num           : número de documento EP (ej: ALPA-EP-001)
-- ep_period        : período del EP (ej: Marzo 2026)
-- ep_date          : fecha de emisión del EP
-- payment_statuses : campo legacy (array plano), conservado para compatibilidad
-- ─────────────────────────────────────────────────────────

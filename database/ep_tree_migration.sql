-- ═══════════════════════════════════════════════════════
-- EstadoPago v4 — Migration: Add hierarchical EP fields
-- Ejecutar en: Supabase Dashboard → SQL Editor
-- Fecha: 2026-03-11
-- ═══════════════════════════════════════════════════════

-- 1. Agregar columnas nuevas a la tabla projects
ALTER TABLE public.projects
  ADD COLUMN IF NOT EXISTS ep_tree         JSONB    DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS ep_extra_cols   JSONB    DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS ep_status       TEXT     DEFAULT 'draft',
  ADD COLUMN IF NOT EXISTS ep_contract_amount NUMERIC(15,2) DEFAULT 0;

-- 2. Verificar que las columnas existen
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'projects'
  AND column_name IN ('payment_statuses','ep_tree','ep_extra_cols','ep_status','ep_contract_amount')
ORDER BY column_name;

-- ─── NOTAS ───────────────────────────────────────────────
-- ep_tree          : árbol JSON del EstadoPago (Cap → Sub → Partida)
-- ep_extra_cols    : columnas dinámicas definidas por el usuario
-- ep_status        : 'draft' | 'sent' | 'approved'
-- ep_contract_amount: monto del contrato para % avance
-- payment_statuses : campo legacy (array plano), conservado para compatibilidad
-- ─────────────────────────────────────────────────────────

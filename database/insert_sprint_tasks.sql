-- Insert initial sprint tasks (Run in Supabase SQL Editor after creating the table)

INSERT INTO sprint_tasks (title, description, section, completed, order_index) VALUES
('CORS fix add Vercel prod URL to allowlist in main.py', 'Quick Win', 'quick', true, 1),
('Execute monitoring_views.sql in Supabase SQL Editor', 'Quick Win', 'quick', false, 2),

('Email bienvenida trigger Resend in register_trial()', 'Email Notifications', 'email', true, 1),
('Email trial expirando add to monitoring/alerts.py', 'Email Notifications', 'email', false, 2),

('Create frontend/modules/agentes/index.html', 'Frontend Module', 'fe', false, 1),
('List agent_decisions with status badges', 'Frontend Module Subtask', 'fe', false, 2),
('Aprobar / Rechazar buttons POST /api/v1/alerts/{id}/action', 'Frontend Module Subtask', 'fe', false, 3),
('Add nav link in index.html sidebar', 'Frontend Module', 'fe', false, 4),

('Metadata en PDF Cotizador', 'Metadatos PDF', 'meta', true, 1),
('Mostrar Version, Creado Por y Fecha en header/footer', 'Metadatos PDF Subtask', 'meta', true, 2),
('Metadata en PDF Ordenes', 'Metadatos PDF', 'meta', true, 3),
('Metadata en PDF Estados de Pago', 'Metadatos PDF', 'meta', true, 4),
('Modulo de Auditoria / Reportes', 'Auditoria', 'meta', true, 5),
('Vista centralizada de versiones en Supabase', 'Auditoria Subtask', 'meta', true, 6),

('Run: curl /api/v1/agents/health', 'Verification', 'verify', false, 1),
('Register trial check inbox for welcome email', 'Verification', 'verify', false, 2),
('Open agentes module confirm decisions list renders', 'Verification', 'verify', false, 3);

// ─── CONFIGURATION ───
const SCRIPT_URL = (window.SAAS_CONFIG && window.SAAS_CONFIG.backendUrl) ? window.SAAS_CONFIG.backendUrl : '';
const USER_SESSION_KEY = (window.SAAS_CONFIG && window.SAAS_CONFIG.sessionKey) ? window.SAAS_CONFIG.sessionKey : 'alpa_app_session_v1';

// ─── MODULE REGISTRY ───
const modules = {
    'dashboard':    { title: 'Dashboard Central',                   url: 'modules/dashboard/index.html',    icon: 'fa-gauge' },
    'manager':      { title: 'Control de Sprint',                   url: 'modules/manager/index.html',      icon: 'fa-microchip' },
    'agentes':      { title: 'Centro de Decisiones IA',             url: 'modules/agentes/index.html',      icon: 'fa-robot' },
    'leads':        { title: 'Gestión de Prospectos Web',           url: 'modules/leads/index.html',        icon: 'fa-users-viewfinder' },
    'directorio':   { title: 'Directorio de Clientes',              url: 'modules/directorio/index.html',   icon: 'fa-address-book' },
    'contabilidad': { title: 'Sistema Contable',                    url: 'modules/contabilidad/index.html', icon: 'fa-calculator' },
    'estados_pago': { title: 'Estado de Pago',                      url: 'modules/estados_pago/index.html', icon: 'fa-file-invoice-dollar' },
    'cotizador':    { title: 'Generador de Cotizaciones',           url: 'modules/cotizador/index.html',    icon: 'fa-file-invoice' },
    'ordenes':      { title: 'Órdenes de Compra',                   url: 'modules/ordenes/index.html',      icon: 'fa-cart-flatbed' },
    'inventario':   { title: 'Inventario / Bodega',                 url: 'modules/inventario/index.html',   icon: 'fa-boxes-stacked' },
    'auditoria':    { title: 'Auditoría / Log',                     url: 'modules/auditoria/index.html',    icon: 'fa-clock-rotate-left' },
    'settings':     { title: 'Configuración de Empresa',            url: 'settings.html',                   icon: 'fa-gears' },
};

// ─── TAB MANAGER ───
const TabManager = {
    tabs: [],
    active: null,

    open(key) {
        if (!modules[key]) return;
        if (!this.tabs.includes(key)) this.tabs.push(key);
        this.activate(key);
    },

    close(key, event) {
        if (event) event.stopPropagation();
        const idx = this.tabs.indexOf(key);
        if (idx === -1) return;
        this.tabs.splice(idx, 1);
        if (this.active === key) {
            const next = this.tabs[idx] || this.tabs[idx - 1] || this.tabs[0];
            if (next) { this.activate(next); } else { this.active = null; this._render(); }
        } else {
            this._render();
        }
    },

    activate(key) {
        this.active = key;
        this._loadIframe(key);
        this._updateRail(key);
        this._render();
    },

    _loadIframe(key) {
        const mod = modules[key];
        if (!mod) return;
        const iframe = document.getElementById('app-frame');
        if (iframe) iframe.src = mod.url + '?v=5.2-' + Date.now();
    },

    _updateRail(key) {
        document.querySelectorAll('.rail-item').forEach(el => el.classList.remove('active'));
        const el = document.getElementById('nav-' + key);
        if (el) el.classList.add('active');
    },

    _render() {
        const bar = document.getElementById('tab-bar');
        if (!bar) return;
        bar.innerHTML = this.tabs.map(key => {
            const mod = modules[key];
            const isActive = key === this.active;
            return `<div class="tab${isActive ? ' active' : ''}" onclick="TabManager.activate('${key}')">
                <i class="fa-solid ${mod.icon}"></i>
                ${mod.title}
                <span class="tab-close" onclick="TabManager.close('${key}',event)"><i class="fa-solid fa-xmark"></i></span>
            </div>`;
        }).join('');
    }
};

// ─── NAVIGATION ───
function loadModule(key) {
    TabManager.open(key);
}

// ─── SESSION ───
document.addEventListener('DOMContentLoaded', () => {
    checkSession();
});

function checkSession() {
    try {
        const session = JSON.parse(localStorage.getItem(USER_SESSION_KEY) || 'null');
        if (session && session.token) {
            unlockApp(session.user);
            updateGlobalBadges();
            setInterval(updateGlobalBadges, 300000);
        }
    } catch (e) { console.error("Invalid session", e); }
}

async function handleLogin(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerText;
    btn.innerText = 'Verificando...';
    btn.disabled = true;

    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;

    // 1. LOCAL USERS
    const users = (window.SAAS_CONFIG && SAAS_CONFIG.users) || [];
    const localUser = users.find(u => u.email.toLowerCase() === email.toLowerCase() && u.pass === password);
    if (localUser) {
        const session = {
            token: 'local-token-' + Date.now(),
            user: { name: localUser.name, role: localUser.role, email: localUser.email,
                    organization_id: (SAAS_CONFIG.defaultOrgId) || '00000000-0000-0000-0000-000000000000' }
        };
        localStorage.setItem(SAAS_CONFIG.sessionKey || USER_SESSION_KEY, JSON.stringify(session));
        unlockApp(session.user);
        window.location.reload();
        return;
    }

    // 2. SUPABASE
    if (window.SAAS_CONFIG && SAAS_CONFIG.mode === 'supa') {
        if (!window.AlpaCore || !AlpaCore.supabase) {
            alert("⚠ Error: El cliente de base de datos no está listo.");
            btn.innerText = originalText; btn.disabled = false; return;
        }
        try {
            const { data, error } = await AlpaCore.supabase.auth.signInWithPassword({ email, password });
            if (error) {
                let msg = 'Error de Acceso: ' + error.message;
                if (error.status === 400) msg = '❌ Correo o contraseña incorrectos.';
                if (error.message.includes('Email not confirmed')) msg = '📧 Debes confirmar tu correo electrónico.';
                alert(msg); btn.innerText = originalText; btn.disabled = false; return;
            }
            if (data.session) {
                const session = {
                    token: data.session.access_token,
                    user: {
                        name: data.user.user_metadata.full_name || data.user.email.split('@')[0],
                        role: data.user.app_metadata.role || 'User',
                        email: data.user.email,
                        organization_id: data.user.app_metadata.organization_id || data.user.user_metadata.organization_id
                    }
                };
                localStorage.setItem(SAAS_CONFIG.sessionKey || USER_SESSION_KEY, JSON.stringify(session));
                unlockApp(session.user);
                window.location.reload();
            }
        } catch (err) {
            alert("Error crítico durante el inicio de sesión.");
            btn.innerText = originalText; btn.disabled = false;
        }
        return;
    }

    // 3. REMOTE (GAS)
    try {
        const res = await fetch(SCRIPT_URL, {
            method: 'POST', redirect: 'follow',
            headers: { 'Content-Type': 'text/plain;charset=utf-8' },
            body: JSON.stringify({ action: 'login', payload: { email, password } })
        });
        const data = await res.json();
        if (data.status === 'success') {
            const sessionKey = (window.SAAS_CONFIG && SAAS_CONFIG.sessionKey) || USER_SESSION_KEY;
            localStorage.setItem(sessionKey, JSON.stringify({ token: data.token, user: data.user }));
            unlockApp(data.user);
            window.location.reload();
        } else {
            alert('Error de Acceso: ' + (data.message || 'Credenciales inválidas'));
            btn.innerText = originalText; btn.disabled = false;
        }
    } catch (err) {
        alert("Error de conexión con el servidor.");
        btn.innerText = originalText; btn.disabled = false;
    }
}

function unlockApp(user) {
    const overlay = document.getElementById('login-overlay');
    overlay.classList.add('opacity-0', 'pointer-events-none');
    setTimeout(() => overlay.style.display = 'none', 300);

    document.getElementById('main-app').classList.remove('blur-sm');

    const avatar = document.getElementById('user-avatar');
    if (avatar) avatar.innerText = user.name.slice(0, 2).toUpperCase();

    const tooltip = document.getElementById('rail-user-tooltip');
    if (tooltip) tooltip.textContent = user.name + ' · Cerrar sesión';

    // Admin Master
    const MD_ORG = '061dce6d-9765-4cc8-b8a2-44b3ce8fbd78';
    if (user.organization_id === MD_ORG || user.email?.includes('mdasesorias')) {
        const adminLink = document.getElementById('nav-admin');
        if (adminLink) adminLink.style.display = 'flex';
    }

    // Open default tab
    TabManager.open('dashboard');

    // Deferred init
    setTimeout(() => {
        if (window.OnboardingWizard) {
            OnboardingWizard.init();
            if (window.AlertService && !OnboardingWizard.state?.welcome) {
                AlertService.trackOnboarding('wizard_iniciado', 1).catch(() => {});
            }
        }
        if (window.TrialGuard) TrialGuard.check();
        _loadTrialIndicator();
        if (window.AlertService) AlertService.verifyTrialOnStartup();
    }, 800);

    if (window.AlpaCore) {
        AlpaCore.load().then(() => {
            if (window.AlpaBranding) AlpaBranding.apply();
            if (window.updateSidebarBadges) updateSidebarBadges();
            if (window.updateOnboardingPanel) updateOnboardingPanel();
        });
    }

    window.addEventListener('message', (event) => {
        if (!event.data) return;
        if (event.data.type === 'ALPA_NEW_LEAD') {
            _showLeadNotification(event.data);
            updateSidebarBadges();
        }
    });
}

function _showLeadNotification(data) {
    const n = document.createElement('div');
    n.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:9999;display:flex;align-items:center;gap:16px;padding:16px 24px;border-radius:16px;border:2px solid var(--orange);background:var(--surface);color:var(--text);box-shadow:0 8px 32px rgba(0,0,0,0.4)';
    n.innerHTML = `
        <div style="width:40px;height:40px;border-radius:50%;background:var(--orange);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:18px;color:white">!</div>
        <div>
            <p style="font-weight:700;font-size:13px;margin:0">SOLICITUD WEB RECIBIDA</p>
            <p style="font-size:12px;opacity:0.8;margin:0">${data.name} ha solicitado un presupuesto.</p>
        </div>`;
    document.body.appendChild(n);
    setTimeout(() => n.remove(), 10000);
}

function _loadTrialIndicator() {
    try {
        let trialData = JSON.parse(localStorage.getItem('agentOS_trial_v1') || 'null');
        if (!trialData?.trial_active) {
            const session = JSON.parse(localStorage.getItem(USER_SESSION_KEY) || 'null');
            const u = session?.user;
            if (u?.is_trial && u?.trial_ends_at) {
                trialData = { trial_active: true, trial_start: u.trial_starts_at || new Date(new Date(u.trial_ends_at).getTime() - 14*86400000).toISOString(), trial_end: u.trial_ends_at };
            }
        }
        if (!trialData?.trial_active) return;
        const daysLeft = Math.max(0, Math.ceil((new Date(trialData.trial_end).getTime() - Date.now()) / 86400000));
        const indicator = document.getElementById('trial-rail-indicator');
        const badge = document.getElementById('trial-days-badge');
        const label = document.getElementById('trial-days-label');
        if (indicator) indicator.classList.remove('hidden');
        if (badge) badge.textContent = daysLeft > 0 ? daysLeft + 'd' : '¡Exp!';
        if (label) label.textContent = daysLeft + ' días';
    } catch (e) {}
}

// ─── SYNC ───
async function triggerCloudSync() {
    const btn = document.getElementById('cloud-sync-btn');
    const orig = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-arrows-rotate fa-spin"></i> <span>SINCRO...</span>';
    btn.disabled = true;
    try {
        if (window.AlpaCore) await AlpaCore.load(true);
        await updateGlobalBadges();
        const iframe = document.getElementById('app-frame');
        if (iframe?.contentWindow) iframe.contentWindow.location.reload();
        btn.style.background = 'linear-gradient(135deg,#059669,#10b981)';
        btn.innerHTML = '<i class="fa-solid fa-circle-check"></i> <span>SINCRONIZADO</span>';
    } catch (e) {
        console.error("Sync error:", e);
        btn.innerHTML = orig;
    } finally {
        setTimeout(() => { btn.style.background = ''; btn.innerHTML = orig; btn.disabled = false; }, 3000);
    }
}

// ─── BADGES ───
async function updateGlobalBadges() {
    try {
        if (!window.AlpaHub) return;
        const result = await AlpaHub.execute('getMainDashboardMetrics') || {};
        const deuda = (result.cards || {}).partnerDebt || 0;
        const badge = document.getElementById('socios-debt-badge');
        const countEl = document.getElementById('socios-debt-count');
        if (badge) {
            if (deuda > 0) {
                badge.classList.remove('hidden'); badge.classList.add('flex');
                if (countEl) countEl.innerText = '$ ' + Math.round(deuda).toLocaleString('es-CL');
            } else {
                badge.classList.add('hidden'); badge.classList.remove('flex');
            }
        }
    } catch (e) { console.warn("Global badges update failed", e); }
}

window.updateSidebarBadges = function () {
    try {
        const badge = document.getElementById('leads-badge');
        if (window.AlpaCore && badge) {
            const count = (window.AlpaCore.getPendingLeads() || []).length;
            badge.innerText = count;
            badge.classList.toggle('hidden', count === 0);
        }
    } catch (e) {}
    try { updateGlobalBadges(); } catch (e) {}
};

window.updateOnboardingPanel = function () {
    if (!window.AlpaCore) return;
    updateGlobalProjectSelector();
    const status = AlpaCore.getOnboardingStatus();
    const bar = document.getElementById('onboarding-panel');
    if (!bar) return;
    if (status.percent >= 100) { bar.classList.add('hidden'); return; }
    bar.classList.remove('hidden');
    document.getElementById('onboarding-percent').innerText = status.percent + '%';
    document.getElementById('onboarding-progress-bar').style.width = status.percent + '%';
    const list = document.getElementById('onboarding-list');
    list.innerHTML = status.steps.filter(s => !s.done).map(s =>
        `<span style="font-size:10px;color:var(--muted);white-space:nowrap"><i class="fa-solid fa-circle" style="font-size:6px;margin-right:4px"></i>${s.label}</span>`
    ).join('');
};

// ─── PROJECT SELECTOR ───
function updateGlobalProjectSelector() {
    const sel = document.getElementById('global-project-selector');
    if (!sel || !window.AlpaCore) return;
    const projects = AlpaCore.getProjects() || [];
    sel.innerHTML = '<option value="all">TODOS LOS PROYECTOS</option>';
    projects.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id || p.ID;
        opt.textContent = p.name || p.Nombre;
        sel.appendChild(opt);
    });
    sel.value = localStorage.getItem('alpa_active_project_id') || 'all';
}

function handleGlobalProjectChange(projectId) {
    localStorage.setItem('alpa_active_project_id', projectId);
    const iframe = document.getElementById('app-frame');
    if (iframe?.contentWindow) iframe.contentWindow.postMessage({ type: 'alpa:projectSelected', projectId }, '*');
}

// ─── LOGOUT ───
function logout() {
    if (confirm('¿Cerrar sesión?')) {
        localStorage.removeItem(USER_SESSION_KEY);
        window.location.reload();
    }
}

// ─── HUB MESSAGE BUS ───
window.addEventListener('message', (event) => {
    if (!event.data?.action) return;
    const { action, module } = event.data;
    if (action === 'HUB_NAVIGATE') loadModule(module);
    else if (action === 'SYNC_THEME' && window.ThemeEngine) ThemeEngine.applyTheme(ThemeEngine.getActiveTheme());
    else if (action === 'triggerSidebarRefresh' || action === 'REFRESH_ORG_STATE') {
        if (window.AlpaCore) AlpaCore.load(true).then(() => {
            if (window.AlpaBranding) AlpaBranding.apply();
            if (window.updateSidebarBadges) updateSidebarBadges();
            if (window.updateOnboardingPanel) updateOnboardingPanel();
        });
    }
});

// ─── ENVIRONMENT BADGE ───
(function () {
    const badge = document.getElementById('env-badge');
    if (!badge) return;
    const mode = (window.SAAS_CONFIG && SAAS_CONFIG.mode) || 'local';
    if (mode === 'local') {
        badge.innerText = 'LOCAL';
        badge.style.cssText = 'background:rgba(245,158,11,0.15);color:#f59e0b;border:1px solid rgba(245,158,11,0.3);font-size:9px;font-weight:700;padding:2px 8px;border-radius:999px;letter-spacing:.08em;text-transform:uppercase';
        document.body.style.borderTop = '3px solid #f59e0b';
    } else if (mode === 'gas') {
        badge.innerText = 'VERCEL + GAS';
        badge.style.cssText = 'background:rgba(59,130,246,0.15);color:#3b82f6;border:1px solid rgba(59,130,246,0.3);font-size:9px;font-weight:700;padding:2px 8px;border-radius:999px;letter-spacing:.08em;text-transform:uppercase';
    } else if (mode === 'supa') {
        badge.innerText = 'VERCEL + SUPABASE';
        badge.style.cssText = 'background:rgba(16,185,129,0.12);color:#10b981;border:1px solid rgba(16,185,129,0.25);font-size:9px;font-weight:700;padding:2px 8px;border-radius:999px;letter-spacing:.08em;text-transform:uppercase';
    }
})();

console.log("%c ALPA HUB v5.2 — Icon Rail + Tabs ", "background:#7c3aed;color:white;font-size:15px;font-weight:bold;padding:4px 8px;border-radius:4px");

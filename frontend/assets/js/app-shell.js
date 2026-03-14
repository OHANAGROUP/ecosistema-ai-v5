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

// ─── MODULE SHORTCUTS ───
const MODULE_SHORTCUTS = {
    'dashboard':    'G D',
    'leads':        'G P',
    'contabilidad': 'G C',
    'agentes':      'G A',
    'manager':      'G S',
    'cotizador':    'G Q',
    'estados_pago': 'G E',
    'directorio':   'G R',
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
        this._updateNavLink(key);
        this._render();
        // Save to recent history
        const recent = JSON.parse(localStorage.getItem('alpa_recent_modules') || '[]');
        const updated = [key, ...recent.filter(k => k !== key)].slice(0, 8);
        localStorage.setItem('alpa_recent_modules', JSON.stringify(updated));
    },

    _loadIframe(key) {
        const mod = modules[key];
        if (!mod) return;
        const iframe = document.getElementById('app-frame');
        if (iframe) iframe.src = mod.url + '?v=5.3-' + Date.now();
    },

    _updateNavLink(key) {
        // Desktop top nav — primary links
        document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
        const navMore = document.querySelector('.nav-more');
        if (navMore) navMore.classList.remove('active');

        const el = document.getElementById('nav-' + key);
        if (el) {
            el.classList.add('active');
        } else if (navMore) {
            // Secondary module (in ··· Más dropdown) — highlight the Más button
            navMore.classList.add('active');
        }
        // Mobile bottom nav
        document.querySelectorAll('#mobile-bottom-nav a').forEach(a => a.classList.remove('active'));
        const mob = document.getElementById('mob-nav-' + key);
        if (mob) mob.classList.add('active');
    },

    _render() {
        const bar = document.getElementById('tab-bar');
        if (!bar) return;
        if (this.tabs.length === 0) {
            bar.innerHTML = '';
            bar.classList.add('empty');
            return;
        }
        bar.classList.remove('empty');
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

// ─── TOP NAV MENUS ───
function toggleMoreMenu(event) {
    if (event) event.stopPropagation();
    document.getElementById('nav-more-menu')?.classList.toggle('open');
}
function closeMoreMenu() {
    document.getElementById('nav-more-menu')?.classList.remove('open');
}
function toggleUserMenu(event) {
    if (event) event.stopPropagation();
    document.getElementById('nav-user-menu')?.classList.toggle('open');
}
function closeUserMenu() {
    document.getElementById('nav-user-menu')?.classList.remove('open');
}
function closeAllMenus() {
    closeMoreMenu();
    closeUserMenu();
    NotificationPanel.close();
}

// Close menus on outside click
document.addEventListener('click', (e) => {
    const moreWrap = document.getElementById('nav-more-wrap');
    if (moreWrap && !moreWrap.contains(e.target)) closeMoreMenu();

    const userWrap = document.getElementById('nav-user-wrap');
    if (userWrap && !userWrap.contains(e.target)) closeUserMenu();

    const notifPanel = document.getElementById('notif-panel');
    const notifBell = document.getElementById('notif-bell-wrap');
    if (notifPanel && notifBell && !notifPanel.contains(e.target) && !notifBell.contains(e.target)) {
        NotificationPanel.close();
    }
});

// ─── MOBILE DRAWER ───
function toggleMobileDrawer() {
    const drawer = document.getElementById('mobile-drawer');
    const overlay = document.getElementById('mobile-drawer-overlay');
    if (!drawer) return;
    drawer.classList.toggle('open');
    if (overlay) overlay.classList.toggle('open');
}

// ─── COMMAND PALETTE ───
const CommandPalette = {
    isOpen: false,
    selectedIdx: 0,
    _filtered: [],

    open() {
        this.isOpen = true;
        const overlay = document.getElementById('cmd-palette');
        if (!overlay) return;
        overlay.classList.remove('hidden');
        const input = document.getElementById('cmd-input');
        if (input) { input.value = ''; input.focus(); }
        this.selectedIdx = 0;
        this._render('');
    },

    close() {
        this.isOpen = false;
        document.getElementById('cmd-palette')?.classList.add('hidden');
    },

    toggle() { this.isOpen ? this.close() : this.open(); },

    search(query) {
        this.selectedIdx = 0;
        this._render(query);
    },

    handleKey(e) {
        const items = document.querySelectorAll('#cmd-results .cmd-item');
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            this.selectedIdx = Math.min(this.selectedIdx + 1, items.length - 1);
            this._highlightItem(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            this.selectedIdx = Math.max(this.selectedIdx - 1, 0);
            this._highlightItem(items);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            const selected = items[this.selectedIdx];
            if (selected) selected.click();
        } else if (e.key === 'Escape') {
            this.close();
        }
    },

    _highlightItem(items) {
        items.forEach((el, i) => el.classList.toggle('selected', i === this.selectedIdx));
        items[this.selectedIdx]?.scrollIntoView({ block: 'nearest' });
    },

    _render(query) {
        const results = document.getElementById('cmd-results');
        if (!results) return;
        const q = query.toLowerCase().trim();
        const allMods = Object.entries(modules).map(([key, mod]) => ({ key, ...mod }));
        const filtered = q
            ? allMods.filter(m => m.title.toLowerCase().includes(q) || m.key.includes(q))
            : allMods;

        let html = '';

        // Recent (only when no query)
        if (!q) {
            const recent = JSON.parse(localStorage.getItem('alpa_recent_modules') || '[]')
                .filter(k => modules[k]).slice(0, 4);
            if (recent.length > 0) {
                html += `<div class="cmd-group">
                    <div class="cmd-group-label">Recientes</div>
                    ${recent.map((key, i) => {
                        const mod = modules[key];
                        return `<div class="cmd-item${i === 0 ? ' selected' : ''}" onclick="CommandPalette.navigate('${key}')">
                            <i class="fa-solid ${mod.icon}"></i>
                            <span class="cmd-item-text">${mod.title}</span>
                            ${MODULE_SHORTCUTS[key] ? `<span class="cmd-shortcut">${MODULE_SHORTCUTS[key]}</span>` : ''}
                        </div>`;
                    }).join('')}
                </div>`;
            }
        }

        // Modules
        if (filtered.length > 0) {
            html += `<div class="cmd-group">
                <div class="cmd-group-label">${q ? 'Resultados' : 'Todos los módulos'}</div>
                ${filtered.map(mod => `
                    <div class="cmd-item" onclick="CommandPalette.navigate('${mod.key}')">
                        <i class="fa-solid ${mod.icon}"></i>
                        <span class="cmd-item-text">${mod.title}</span>
                        ${MODULE_SHORTCUTS[mod.key] ? `<span class="cmd-shortcut">${MODULE_SHORTCUTS[mod.key]}</span>` : ''}
                    </div>
                `).join('')}
            </div>`;
        } else if (q) {
            html += `<div class="cmd-empty">Sin resultados para "<strong>${q}</strong>"</div>`;
        }

        // Actions (only without query)
        if (!q) {
            html += `<div class="cmd-group">
                <div class="cmd-group-label">Acciones</div>
                <div class="cmd-item" onclick="triggerCloudSync(); CommandPalette.close()">
                    <i class="fa-solid fa-arrows-rotate"></i>
                    <span class="cmd-item-text">Sincronizar datos</span>
                </div>
                <div class="cmd-item" onclick="logout(); CommandPalette.close()">
                    <i class="fa-solid fa-right-from-bracket"></i>
                    <span class="cmd-item-text">Cerrar sesión</span>
                </div>
            </div>`;
        }

        results.innerHTML = html;
        // Highlight first
        if (!q) {
            const items = results.querySelectorAll('.cmd-item');
            this._highlightItem(items);
        }
    },

    navigate(key) {
        loadModule(key);
        this.close();
    }
};

// ─── NOTIFICATION PANEL ───
const NotificationPanel = {
    notifications: [],

    init() {
        this.notifications = JSON.parse(localStorage.getItem('alpa_notifications') || '[]');
        this._updateBadge();
    },

    add(data) {
        const notif = {
            id: Date.now(),
            title: 'SOLICITUD WEB RECIBIDA',
            body: `${data.name} ha solicitado un presupuesto.`,
            time: new Date().toISOString(),
            unread: true,
            action: 'leads'
        };
        this.notifications.unshift(notif);
        this.notifications = this.notifications.slice(0, 20);
        localStorage.setItem('alpa_notifications', JSON.stringify(this.notifications));
        this._updateBadge();
        this._showToast(notif);
    },

    toggle() {
        const panel = document.getElementById('notif-panel');
        if (!panel) return;
        if (panel.classList.contains('open')) {
            this.close();
        } else {
            panel.classList.add('open');
            this._render();
            // Mark all as read
            this.notifications = this.notifications.map(n => ({ ...n, unread: false }));
            localStorage.setItem('alpa_notifications', JSON.stringify(this.notifications));
            this._updateBadge();
        }
    },

    close() {
        document.getElementById('notif-panel')?.classList.remove('open');
    },

    clear() {
        this.notifications = [];
        localStorage.removeItem('alpa_notifications');
        this._updateBadge();
        this._render();
    },

    _render() {
        const list = document.getElementById('notif-list');
        if (!list) return;
        if (this.notifications.length === 0) {
            list.innerHTML = '<div class="notif-empty">Sin notificaciones recientes</div>';
            return;
        }
        list.innerHTML = this.notifications.slice(0, 10).map(n => {
            const time = _timeAgo(new Date(n.time));
            return `<div class="notif-item${n.unread ? ' unread' : ''}" onclick="loadModule('${n.action}'); NotificationPanel.close()">
                <div class="notif-item-title">${n.title}</div>
                <div class="notif-item-body">${n.body}</div>
                <div class="notif-item-time">${time}</div>
            </div>`;
        }).join('');
    },

    _updateBadge() {
        const unread = this.notifications.filter(n => n.unread).length;
        const count = document.getElementById('notif-count');
        if (count) {
            count.textContent = unread;
            count.classList.toggle('hidden', unread === 0);
        }
    },

    _showToast(notif) {
        const n = document.createElement('div');
        n.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:9999;display:flex;align-items:center;gap:14px;padding:14px 20px;border-radius:14px;border:1px solid var(--border);background:var(--surface);box-shadow:0 8px 32px rgba(0,0,0,0.5);cursor:pointer;max-width:320px';
        n.innerHTML = `
            <div style="width:36px;height:36px;border-radius:50%;background:var(--orange);display:flex;align-items:center;justify-content:center;font-size:16px;color:white;flex-shrink:0">
                <i class="fa-solid fa-bell"></i>
            </div>
            <div>
                <p style="font-weight:700;font-size:12px;margin:0;color:var(--text)">${notif.title}</p>
                <p style="font-size:11px;color:var(--muted);margin:2px 0 0">${notif.body}</p>
            </div>`;
        n.onclick = () => { loadModule('leads'); n.remove(); };
        document.body.appendChild(n);
        setTimeout(() => n.style.transition = 'opacity 0.5s', 8000);
        setTimeout(() => n.remove(), 9000);
    }
};

function _timeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    if (seconds < 60) return 'ahora mismo';
    if (seconds < 3600) return `hace ${Math.floor(seconds / 60)} min`;
    if (seconds < 86400) return `hace ${Math.floor(seconds / 3600)}h`;
    return `hace ${Math.floor(seconds / 86400)}d`;
}

// ─── KEYBOARD SHORTCUTS ───
document.addEventListener('keydown', e => {
    // Command palette
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        CommandPalette.toggle();
        return;
    }
    // Close overlays
    if (e.key === 'Escape') {
        if (CommandPalette.isOpen) { CommandPalette.close(); return; }
        closeAllMenus();
    }
});

// ─── SESSION ───
document.addEventListener('componentsLoaded', () => {
    NotificationPanel.init();
    _applyEnvBadge();
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

// ─── LOGIN ───
function showLoginError(msg) {
    const el = document.getElementById('login-error');
    if (el) { el.textContent = msg; el.classList.add('visible'); }
}
function clearLoginError() {
    document.getElementById('login-error')?.classList.remove('visible');
}

async function handleLogin(e) {
    e.preventDefault();
    clearLoginError();
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
            showLoginError('⚠ Error: El cliente de base de datos no está listo.');
            btn.innerText = originalText; btn.disabled = false; return;
        }
        try {
            const { data, error } = await AlpaCore.supabase.auth.signInWithPassword({ email, password });
            if (error) {
                let msg = 'Error de acceso: ' + error.message;
                if (error.status === 400) msg = 'Correo o contraseña incorrectos.';
                if (error.message.includes('Email not confirmed')) msg = 'Debes confirmar tu correo electrónico.';
                showLoginError(msg); btn.innerText = originalText; btn.disabled = false; return;
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
            showLoginError('Error crítico durante el inicio de sesión.');
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
            showLoginError(data.message || 'Credenciales inválidas.');
            btn.innerText = originalText; btn.disabled = false;
        }
    } catch (err) {
        showLoginError('Error de conexión con el servidor.');
        btn.innerText = originalText; btn.disabled = false;
    }
}

function unlockApp(user) {
    const overlay = document.getElementById('login-overlay');
    overlay.classList.add('opacity-0', 'pointer-events-none');
    setTimeout(() => overlay.style.display = 'none', 300);

    document.getElementById('main-app').classList.remove('blur-sm');

    // Update user info in nav
    const avatar = document.getElementById('user-avatar');
    if (avatar) avatar.innerText = user.name.slice(0, 2).toUpperCase();

    const nameEl = document.getElementById('nav-user-name');
    if (nameEl) nameEl.textContent = user.name.split(' ')[0]; // First name only

    const fullNameEl = document.getElementById('nav-user-fullname');
    if (fullNameEl) fullNameEl.textContent = user.name;

    const roleEl = document.getElementById('nav-user-role');
    if (roleEl) roleEl.textContent = user.role || 'Usuario';

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
            NotificationPanel.add(event.data);
            updateSidebarBadges();
        }
    });
}

// ─── TRIAL INDICATOR ───
function _loadTrialIndicator() {
    try {
        let trialData = JSON.parse(localStorage.getItem('agentOS_trial_v1') || 'null');
        if (!trialData?.trial_active) {
            const session = JSON.parse(localStorage.getItem(USER_SESSION_KEY) || 'null');
            const u = session?.user;
            if (u?.is_trial && u?.trial_ends_at) {
                trialData = { trial_active: true, trial_end: u.trial_ends_at };
            }
        }
        if (!trialData?.trial_active) return;
        const daysLeft = Math.max(0, Math.ceil((new Date(trialData.trial_end).getTime() - Date.now()) / 86400000));
        const indicator = document.getElementById('trial-nav-indicator');
        const badge = document.getElementById('trial-days-badge');
        if (indicator) indicator.classList.remove('hidden');
        if (badge) badge.textContent = daysLeft > 0 ? daysLeft + 'd' : '¡Expirado!';
    } catch (e) {}
}

// ─── SYNC ───
async function triggerCloudSync() {
    const btn = document.getElementById('cloud-sync-btn');
    const orig = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-arrows-rotate fa-spin"></i> <span>SYNC...</span>';
    btn.disabled = true;
    try {
        if (window.AlpaCore) await AlpaCore.load(true);
        await updateGlobalBadges();
        const iframe = document.getElementById('app-frame');
        if (iframe?.contentWindow) iframe.contentWindow.location.reload();
        btn.style.background = 'linear-gradient(135deg,#059669,#10b981)';
        btn.innerHTML = '<i class="fa-solid fa-circle-check"></i> <span>OK</span>';
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

// ─── LOGOUT (no confirm dialog) ───
function logout() {
    const sessionKey = (window.SAAS_CONFIG && SAAS_CONFIG.sessionKey) || USER_SESSION_KEY;
    localStorage.removeItem(sessionKey);
    window.location.reload();
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

// ─── ENVIRONMENT BADGE (runs after components are in DOM) ───
function _applyEnvBadge() {
    const badge = document.getElementById('env-badge');
    if (!badge) return;
    const mode = (window.SAAS_CONFIG && SAAS_CONFIG.mode) || 'local';
    if (mode === 'local') {
        badge.innerText = 'LOCAL';
        badge.style.cssText = 'background:rgba(245,158,11,0.15);color:#f59e0b;border:1px solid rgba(245,158,11,0.3);font-size:9px;font-weight:700;padding:2px 8px;border-radius:999px;letter-spacing:.08em;text-transform:uppercase;flex-shrink:0';
        document.body.style.borderTop = '3px solid #f59e0b';
    } else if (mode === 'gas') {
        badge.innerText = 'VERCEL + GAS';
        badge.style.cssText = 'background:rgba(59,130,246,0.15);color:#3b82f6;border:1px solid rgba(59,130,246,0.3);font-size:9px;font-weight:700;padding:2px 8px;border-radius:999px;letter-spacing:.08em;text-transform:uppercase;flex-shrink:0';
    } else if (mode === 'supa') {
        badge.innerText = 'VERCEL + SUPABASE';
        badge.style.cssText = 'background:rgba(16,185,129,0.12);color:#10b981;border:1px solid rgba(16,185,129,0.25);font-size:9px;font-weight:700;padding:2px 8px;border-radius:999px;letter-spacing:.08em;text-transform:uppercase;flex-shrink:0';
    }
}

console.log("%c ALPA HUB v5.3 — Top Nav + Command Palette ", "background:#7c3aed;color:white;font-size:15px;font-weight:bold;padding:4px 8px;border-radius:4px");

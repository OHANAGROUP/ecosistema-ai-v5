// --- CONFIGURATION ---
const SCRIPT_URL = (window.SAAS_CONFIG && window.SAAS_CONFIG.backendUrl) ? window.SAAS_CONFIG.backendUrl : '';
const USER_SESSION_KEY = (window.SAAS_CONFIG && window.SAAS_CONFIG.sessionKey) ? window.SAAS_CONFIG.sessionKey : 'alpa_app_session_v1';
const LOCAL_USERS = (window.SAAS_CONFIG && window.SAAS_CONFIG.users) ? window.SAAS_CONFIG.users : [];

function toggleMobileMenu() {
    const sidebar = document.getElementById('sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    const icon = document.querySelector('#mobile-toggle i');

    sidebar.classList.toggle('open');
    backdrop.classList.toggle('open');

    if (sidebar.classList.contains('open')) {
        icon.classList.remove('fa-bars');
        icon.classList.add('fa-xmark');
    } else {
        icon.classList.remove('fa-xmark');
        icon.classList.add('fa-bars');
    }
}

function updateGlobalProjectSelector() {
    const selector = document.getElementById('global-project-selector');
    if (!selector || !window.AlpaCore) return;

    const projects = AlpaCore.getProjects() || [];

    // Rebuild options but keep 'all'
    selector.innerHTML = '<option value="all" class="bg-primary text-white font-bold"> TODOS LOS PROYECTOS</option>';

    projects.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id || p.ID;
        opt.textContent = ` ${p.name || p.Nombre}`;
        opt.className = "bg-primary text-white font-bold";
        selector.appendChild(opt);
    });

    // Restore selection if exists
    const saved = localStorage.getItem('alpa_active_project_id');
    if (saved) selector.value = saved;
    else selector.value = 'all';
}

function handleGlobalProjectChange(projectId) {
    localStorage.setItem('alpa_active_project_id', projectId);

    const frame = document.getElementById('app-frame');
    if (frame && frame.contentWindow) {
        frame.contentWindow.postMessage({
            type: 'alpa:projectSelected',
            projectId: projectId
        }, '*');
    }

    console.log("Global Project Changed:", projectId);
}

// Initialize Core and Session
document.addEventListener('DOMContentLoaded', async () => {
    checkSession();
});

function checkSession() {
    const sessionJSON = localStorage.getItem(USER_SESSION_KEY);
    if (sessionJSON) {
        try {
            const session = JSON.parse(sessionJSON);
            if (session && session.token) {
                unlockApp(session.user);
                updateGlobalBadges();
                setInterval(updateGlobalBadges, 300000); // Refresh every 5 min
            }
        } catch (e) {
            console.error("Invalid session", e);
        }
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button');
    const originalText = btn.innerText;
    btn.innerText = 'Verificando...';
    btn.disabled = true;

    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;

    // 1. VERIFICACIÓN LOCAL (Prioritaria para Despliegue Rápido)
    const users = SAAS_CONFIG.users || [];
    const localUser = users.find(u => u.email.toLowerCase() === email.trim().toLowerCase() && u.pass === password);

    if (localUser) {
        console.log("Acceso Permitido (Base Local):", localUser.name);
        const mockSession = {
            token: 'local-token-' + Date.now(),
            user: {
                name: localUser.name,
                role: localUser.role,
                email: localUser.email,
                organization_id: (window.SAAS_CONFIG && window.SAAS_CONFIG.defaultOrgId) || '00000000-0000-0000-0000-000000000000'
            }
        };
        const sessionKey = SAAS_CONFIG.sessionKey || 'alpa_app_session_v1';
        localStorage.setItem(sessionKey, JSON.stringify(mockSession));

        unlockApp(mockSession.user);
        window.location.reload();
        return;
    }

    // 2. SUPABASE AUTH (Multi-Tenant)
    if (SAAS_CONFIG.mode === 'supa') {
        if (!window.AlpaCore || !AlpaCore.supabase) {
            console.error("Supabase Client NOT initialized. Check keys in config.js.");
            alert("⚠ Error: El cliente de base de datos no está listo.");
            btn.innerText = originalText;
            btn.disabled = false;
            return;
        }

        try {
            const { data, error } = await AlpaCore.supabase.auth.signInWithPassword({
                email: email.trim(),
                password: password,
            });

            if (error) {
                let alertMsg = 'Error de Acceso (Supabase): ' + error.message;
                if (error.message === 'Invalid login credentials' || error.status === 400) {
                    alertMsg = '❌ Error: El correo o la contraseña son incorrectos.\n\nPor favor verifica tus datos o contacta a soporte si crees que es un error.';
                } else if (error.message.includes('Email not confirmed') || error.status === 401) {
                    alertMsg = '📧 Error: Debes confirmar tu correo electrónico.\n\nRevisa tu bandeja de entrada o spam. Supabase requiere confirmación de email por defecto.';
                }

                alert(alertMsg);
                btn.innerText = originalText;
                btn.disabled = false;
                return;
            }

            if (data.session) {
                const sessionData = {
                    token: data.session.access_token,
                    user: {
                        name: data.user.user_metadata.full_name || data.user.email.split('@')[0],
                        role: data.user.app_metadata.role || 'User',
                        email: data.user.email,
                        organization_id: data.user.app_metadata.organization_id || data.user.user_metadata.organization_id
                    }
                };

                const sessionKey = SAAS_CONFIG.sessionKey || 'alpa_app_session_v1';
                localStorage.setItem(sessionKey, JSON.stringify(sessionData));

                unlockApp(sessionData.user);
                window.location.reload();
                return;
            }
        } catch (err) {
            console.error("Critical Auth Error:", err);
            alert("Error crítico durante el inicio de sesión.");
            btn.innerText = originalText;
            btn.disabled = false;
            return;
        }
        return; // Guard to prevent falling into GAS
    }

    // 3. REMOTE FETCH (Respaldo Online - Solo si NO es supa mode)
    try {
        const response = await fetch(SCRIPT_URL, {
            method: 'POST',
            redirect: 'follow',
            headers: { 'Content-Type': 'text/plain;charset=utf-8' },
            body: JSON.stringify({
                action: 'login',
                payload: { email, password }
            })
        });

        const data = await response.json();

        if (SAAS_CONFIG.mode === 'local') {
            const user = (SAAS_CONFIG.users || []).find(u => u.email === email);
            if (user) {
                console.warn("ALPA SECURITY: Local login used without password validation (Demo Mode).");
                const sessionData = { token: 'mock_local_token', user: user };
                localStorage.setItem(SAAS_CONFIG.sessionKey, JSON.stringify(sessionData));
                unlockApp(user);
                return;
            } else {
                alert('Usuario no encontrado en la lista local.');
                btn.innerText = originalText;
                btn.disabled = false;
            }
            return;
        }

        if (data.status === 'success') {
            const sessionData = {
                token: data.token,
                user: data.user
            };
            const sessionKey = SAAS_CONFIG.sessionKey || 'alpa_app_session_v1';
            localStorage.setItem(sessionKey, JSON.stringify(sessionData));
            unlockApp(sessionData.user);
            updateGlobalBadges();
            window.location.reload();
        } else {
            alert('Error de Acceso: ' + (data.message || 'Credenciales inválidas'));
            btn.innerText = originalText;
            btn.disabled = false;
        }

    } catch (error) {
        console.error("Login Check Error", error);
        alert("Error de conexión con el servidor.");
        btn.innerText = originalText;
        btn.disabled = false;
    }
}

function unlockApp(user) {
    // Hide Overlay
    const overlay = document.getElementById('login-overlay');
    overlay.classList.add('opacity-0', 'pointer-events-none');
    setTimeout(() => { overlay.style.display = 'none'; }, 300);

    // Unblur App
    document.getElementById('main-app').classList.remove('blur-sm');

    document.getElementById('user-avatar').innerText = user.name.slice(0, 2).toUpperCase();

    // Mostrar Admin Master solo para cuenta MD Asesorias
    const MD_ORG = '061dce6d-9765-4cc8-b8a2-44b3ce8fbd78';
    if (user.organization_id === MD_ORG || user.email?.includes('mdasesorias')) {
        const adminLink = document.getElementById('nav-admin');
        if (adminLink) adminLink.style.display = 'flex';
    }

    // Trigger Onboarding Wizard + Trial Guard + Backend Verification
    setTimeout(() => {
        if (window.OnboardingWizard) {
            OnboardingWizard.init();
            if (window.AlertService && !OnboardingWizard.state?.welcome) {
                AlertService.trackOnboarding('wizard_iniciado', 1).catch(() => { });
            }
        }
        if (window.TrialGuard) TrialGuard.check();
        _loadTrialBanner();
        if (window.AlertService) AlertService.verifyTrialOnStartup();
    }, 800);

    if (window.AlpaCore) {
        AlpaCore.load().then(() => {
            console.log("ALPA CORE: Organization state ready.");

            if (window.AlpaBranding) AlpaBranding.apply();

            if (window.updateSidebarBadges) {
                updateSidebarBadges();
            }
            if (window.updateOnboardingPanel) {
                updateOnboardingPanel();
            }
        });
    }

    // WEB LEAD LISTENER & THEME SYNC
    window.addEventListener('message', (event) => {
        if (event.data && event.data.action === 'SYNC_THEME') {
            if (window.ThemeEngine) {
                ThemeEngine.applyTheme(ThemeEngine.getActiveTheme());
            }
        } else if (event.data && event.data.type === 'ALPA_NEW_LEAD') {
            console.log("Nuevo prospecto desde la web:", event.data);

            const notification = document.createElement('div');
            notification.className = 'fixed bottom-6 right-6 bg-primary text-white px-6 py-4 rounded-2xl shadow-2xl z-[9999] animate-bounce flex items-center gap-4 border-2 border-accent';
            notification.innerHTML = `
                <div class="bg-accent text-white rounded-full w-10 h-10 flex items-center justify-center font-bold text-xl">!</div>
                <div>
                    <p class="font-bold text-sm tracking-tight text-white">SOLICITUD WEB RECIBIDA</p>
                    <p class="text-xs opacity-90 text-white">${event.data.name} ha solicitado un presupuesto.</p>
                </div>
            `;
            document.body.appendChild(notification);
            setTimeout(() => notification.remove(), 10000);

            updateSidebarBadges();
        }
    });
}

function _loadTrialBanner() {
    try {
        let trialData = JSON.parse(localStorage.getItem('agentOS_trial_v1') || 'null');

        if (!trialData || !trialData.trial_active) {
            const session = JSON.parse(localStorage.getItem(USER_SESSION_KEY) || 'null');
            const u = session?.user;
            if (u?.is_trial && u?.trial_ends_at) {
                trialData = {
                    trial_active: true,
                    trial_start: u.trial_starts_at || new Date(new Date(u.trial_ends_at).getTime() - 14 * 86400000).toISOString(),
                    trial_end: u.trial_ends_at,
                };
            }
        }

        if (!trialData || !trialData.trial_active) return;

        const now = Date.now();
        const end = new Date(trialData.trial_end).getTime();
        const start = new Date(trialData.trial_start).getTime();
        const total = end - start;
        const remaining = end - now;

        if (remaining <= 0) {
            document.getElementById('trial-days-badge').textContent = '¡Expirado!';
            document.getElementById('trial-progress-bar').style.width = '0%';
            document.getElementById('trial-progress-bar').classList.remove('from-orange-500');
            document.getElementById('trial-progress-bar').classList.add('from-red-600');
        } else {
            const daysLeft = Math.ceil(remaining / (1000 * 60 * 60 * 24));
            const pct = Math.max(2, (remaining / total) * 100).toFixed(0);
            document.getElementById('trial-days-badge').textContent = `${daysLeft}d`;
            document.getElementById('trial-progress-bar').style.width = `${pct}%`;
        }

        document.getElementById('trial-sidebar-banner').classList.remove('hidden');
    } catch (e) {
        // Silent fail — non-trial user
    }
}

async function triggerCloudSync() {
    const btn = document.getElementById('cloud-sync-btn');
    const originalHTML = btn.innerHTML;
    const originalClass = btn.className;

    btn.innerHTML = '<i class="fa-solid fa-arrows-rotate fa-spin"></i> <span>SINCRO...</span>';
    btn.className = "flex items-center gap-2 bg-indigo-500 text-white px-4 py-2 rounded-xl text-xs font-bold transition-all animate-pulse";
    btn.disabled = true;

    try {
        if (window.AlpaCore) await AlpaCore.load(true);
        await updateGlobalBadges();

        const frame = document.getElementById('app-frame');
        if (frame && frame.contentWindow) {
            frame.contentWindow.location.reload();
        }

        btn.className = "flex items-center gap-2 bg-emerald-600 text-white px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-lg shadow-emerald-600/20";
        btn.innerHTML = '<i class="fa-solid fa-circle-check"></i> <span>SINCRONIZADO</span>';
    } catch (e) {
        console.error("Sync error:", e);
        btn.innerHTML = originalHTML;
        btn.className = originalClass;
    } finally {
        setTimeout(() => {
            btn.className = originalClass;
            btn.innerHTML = originalHTML;
            btn.disabled = false;
        }, 3000);
    }
}

async function updateGlobalBadges() {
    try {
        if (!window.AlpaHub) return;
        const result = await AlpaHub.execute('getMainDashboardMetrics') || {};
        const metrics = result.cards || {};

        const badge = document.getElementById('socios-debt-badge');
        const countEl = document.getElementById('socios-debt-count');
        const deuda = metrics.partnerDebt || 0;
        const numTx = metrics.partnerDebtCount || 0;

        if (badge) {
            if (deuda > 0) {
                badge.classList.remove('hidden');
                badge.classList.add('flex');
                if (countEl) countEl.innerText = '$ ' + Math.round(deuda).toLocaleString('es-CL');
                badge.title = `${numTx} transaccion(es) pendiente(s) de reembolso a socios`;
            } else {
                badge.classList.add('hidden');
                badge.classList.remove('flex');
            }
        }
    } catch (e) {
        console.warn("Global badges update failed", e);
    }
}

window.updateSidebarBadges = function () {
    try {
        const badge = document.getElementById('leads-badge');
        if (window.AlpaCore && badge) {
            const leads = window.AlpaCore.getPendingLeads();
            const count = leads.length;
            if (count > 0) {
                badge.innerText = count;
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        }
    } catch (e) { }

    try { updateGlobalBadges(); } catch (e) { console.warn('Socios badge refresh error', e); }
};

window.updateOnboardingPanel = function () {
    if (!window.AlpaCore) return;
    updateGlobalProjectSelector();

    const status = AlpaCore.getOnboardingStatus();
    const container = document.getElementById('onboarding-panel');
    if (!container) return;

    container.classList.remove('hidden');
    document.getElementById('onboarding-percent').innerText = status.percent + '%';
    document.getElementById('onboarding-progress-bar').style.width = status.percent + '%';

    const list = document.getElementById('onboarding-list');
    list.innerHTML = status.steps.map(step => `
        <div class="flex items-center gap-2 text-[10px] ${step.done ? 'text-emerald-400' : 'text-blue-200/60'}">
            <i class="fa-solid ${step.done ? 'fa-circle-check' : 'fa-circle'}"></i>
            <span class="${step.done ? 'line-through opacity-50' : ''}">${step.label}</span>
        </div>
    `).join('');
};

function logout() {
    if (confirm('¿Cerrar sesión?')) {
        localStorage.removeItem(USER_SESSION_KEY);
        window.location.reload();
    }
}

console.log("%c ALPA CORE v3.2.0 LOADED ", "background: #F36F21; color: white; font-size: 20px; font-weight: bold;");

// --- NAVIGATION LOGIC ---
const modules = {
    'dashboard': { title: 'Dashboard Central', url: 'modules/dashboard/index.html' },
    'manager': { title: 'Control de Sprint', url: 'modules/manager/index.html' },
    'agentes': { title: 'Centro de Decisiones IA', url: 'modules/agentes/index.html' },
    'leads': { title: 'Gestión de Prospectos Web', url: 'modules/leads/index.html' },
    'directorio': { title: 'Directorio de Clientes y Proveedores', url: 'modules/directorio/index.html' },
    'contabilidad': { title: 'Sistema Contable', url: 'modules/contabilidad/index.html' },
    'estados_pago': { title: 'Estado de Pago', url: 'modules/estados_pago/index.html' },
    'cotizador': { title: 'Generador de Cotizaciones', url: 'modules/cotizador/index.html' },
    'ordenes': { title: 'Ordenes de Compra', url: 'modules/ordenes/index.html' },
    'inventario': { title: 'Gestión de Inventario', url: 'modules/inventario/index.html' },
    'settings': { title: 'Configuración de Empresa', url: 'settings.html' }
};

function loadModule(moduleName) {
    console.log("HUB NAVIGATION: Loading module ->", moduleName);
    const module = modules[moduleName];
    if (!module) return;

    const version = "3.2.0-" + Date.now(); // Forced cache bypass

    const iframe = document.getElementById('app-frame');
    iframe.src = module.url + "?v=" + version;

    document.getElementById('page-title').innerText = module.title;

    document.querySelectorAll('.sidebar-link').forEach(link => {
        link.classList.remove('active');
        link.style.borderLeft = 'none';
        link.style.paddingLeft = '16px';
    });

    const activeLink = document.getElementById('nav-' + moduleName);
    if (activeLink) {
        activeLink.classList.add('active');
    }
}

// Secure Hub Communication Handler
window.addEventListener('message', (event) => {
    if (!event.data || !event.data.action) return;
    const { action, module } = event.data;

    if (action === 'HUB_NAVIGATE') {
        loadModule(module);
    } else if (action === 'triggerSidebarRefresh' || action === 'REFRESH_ORG_STATE') {
        console.log("ALPA HUB: Received refresh request", action);
        if (window.AlpaCore) {
            AlpaCore.load(true).then(() => {
                if (window.AlpaBranding) AlpaBranding.apply();
                if (window.updateSidebarBadges) window.updateSidebarBadges();
                if (window.updateOnboardingPanel) window.updateOnboardingPanel();
            });
        }
    }
});

// --- ENVIRONMENT BADGE LOGIC ---
(function () {
    const badge = document.getElementById('env-badge');
    if (!badge) return;

    const mode = (window.SAAS_CONFIG && window.SAAS_CONFIG.mode) || 'local';

    if (mode === 'local') {
        badge.innerText = 'MODO LOCAL';
        badge.className = 'absolute top-4 right-6 px-3 py-1 rounded-full text-[10px] font-bold z-50 bg-orange-100 text-orange-700 border border-orange-200';
        document.body.style.borderTop = '4px solid #F36F21';
    } else if (mode === 'gas') {
        badge.innerText = 'VERCEL + GOOGLE';
        badge.className = 'absolute top-4 right-6 px-3 py-1 rounded-full text-[10px] font-bold z-50 bg-blue-600 text-white';
        document.body.style.borderTop = '4px solid #3b82f6';
    } else if (mode === 'supa') {
        badge.innerText = 'VERCEL + SUPABASE';
        badge.className = 'absolute top-4 right-6 px-3 py-1 rounded-full text-[10px] font-bold z-50 bg-emerald-600 text-white';
        document.body.style.borderTop = '4px solid #10b981';
    }
})();

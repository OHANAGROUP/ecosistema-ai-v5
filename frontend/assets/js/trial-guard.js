/**
 * TRIAL GUARD v1.0
 * 
 * Manages the 14-day trial lifecycle with:
 *   Days 14-8   Normal (sidebar badge)
 *   Days 7-4    Warning (daily toast)
 *   Days 3-1    Urgency (modal on open)
 *   Day 0       Hard block (full overlay)
 *
 * Usage: TrialGuard.check()   call after unlockApp()
 */

const TrialGuard = (() => {
    const TRIAL_KEY = 'agentOS_trial_v1';
    const TOAST_KEY = 'agentOS_trial_toast_v1';   // sessionStorage
    const MODAL_KEY = 'agentOS_trial_modal_v1';   // sessionStorage

    //  Public API 
    function check() {
        const trial = _getTrial();
        if (!trial) return; // Not a trial user

        const daysLeft = _getDaysLeft(trial);
        const state = _getState(daysLeft);

        _updateSidebarBadge(daysLeft, state);

        if (state === 'expired') {
            _showExpiredBlock(trial);
        } else if (state === 'red') {
            _showToast(daysLeft, 'red');
            if (!sessionStorage.getItem(MODAL_KEY)) {
                setTimeout(() => _showUrgencyModal(daysLeft), 1800);
                sessionStorage.setItem(MODAL_KEY, '1');
            }
        } else if (state === 'yellow') {
            if (!sessionStorage.getItem(TOAST_KEY)) {
                setTimeout(() => _showToast(daysLeft, 'yellow'), 2500);
                sessionStorage.setItem(TOAST_KEY, '1');
            }
        }
    }

    //  State Logic 
    function _getState(daysLeft) {
        if (daysLeft <= 0) return 'expired';
        if (daysLeft <= 3) return 'red';
        if (daysLeft <= 7) return 'yellow';
        return 'green';
    }

    function _getDaysLeft(trial) {
        const end = new Date(trial.trial_end).getTime();
        return Math.ceil((end - Date.now()) / (1000 * 60 * 60 * 24));
    }

    function _getTrial() {
        try {
            const d = JSON.parse(localStorage.getItem(TRIAL_KEY) || 'null');
            return (d && d.trial_active) ? d : null;
        } catch { return null; }
    }

    //  Sidebar Badge 
    function _updateSidebarBadge(daysLeft, state) {
        const banner = document.getElementById('trial-sidebar-banner');
        const badge = document.getElementById('trial-days-badge');
        const bar = document.getElementById('trial-progress-bar');
        if (!banner || !badge) return;

        banner.classList.remove('hidden');

        const colors = {
            green: { badge: 'bg-green-500', bar: 'from-green-500 to-emerald-400', border: 'rgba(34,197,94,0.3)', bg: 'rgba(34,197,94,0.07)' },
            yellow: { badge: 'bg-yellow-500', bar: 'from-yellow-400 to-orange-400', border: 'rgba(234,179,8,0.35)', bg: 'rgba(234,179,8,0.07)' },
            red: { badge: 'bg-red-500', bar: 'from-red-500 to-orange-500', border: 'rgba(239,68,68,0.4)', bg: 'rgba(239,68,68,0.09)' },
            expired: { badge: 'bg-gray-500', bar: 'from-gray-600 to-gray-500', border: 'rgba(100,100,100,0.3)', bg: 'rgba(0,0,0,0.1)' }
        };

        const c = colors[state] || colors.green;

        // Reset badge classes
        badge.className = `text-[10px] font-bold text-white px-2 py-0.5 rounded-full ${c.badge}`;
        badge.textContent = daysLeft <= 0 ? 'Expirado' : `${daysLeft}d`;

        // Progress bar
        if (bar) {
            const total = 14 * 24 * 60 * 60 * 1000;
            const trial = _getTrial();
            const remaining = trial ? new Date(trial.trial_end).getTime() - Date.now() : 0;
            const pct = Math.max(0, Math.min(100, (remaining / total) * 100));
            bar.className = `h-full bg-gradient-to-r ${c.bar} rounded-full transition-all duration-1000`;
            bar.style.width = `${pct.toFixed(1)}%`;
        }

        // Banner color
        banner.style.background = c.bg;
        banner.style.borderColor = c.border;

        // Pulse animation on red/expired
        if (state === 'red' || state === 'expired') {
            banner.style.animation = 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite';
        }
    }

    //  Toast Notification 
    function _showToast(daysLeft, state) {
        const existing = document.getElementById('trial-toast');
        if (existing) existing.remove();

        const isRed = state === 'red';
        const msg = isRed
            ? ` Solo te quedan <strong>${daysLeft} da${daysLeft !== 1 ? 's' : ''}</strong> de prueba! Contrata ahora y no pierdas tus datos.`
            : ` Tu prueba gratuita vence en <strong>${daysLeft} das</strong>. Aprovecha antes de que termine!`;

        const toast = document.createElement('div');
        toast.id = 'trial-toast';
        toast.style.cssText = `
            position:fixed; bottom:80px; right:20px; z-index:9990;
            max-width:340px; padding:14px 18px; border-radius:14px;
            background:${isRed ? 'linear-gradient(135deg,#7f1d1d,#450a0a)' : 'linear-gradient(135deg,#713f12,#431407)'};
            border:1px solid ${isRed ? 'rgba(239,68,68,0.5)' : 'rgba(234,179,8,0.4)'};
            color:white; font-size:13px; line-height:1.5;
            box-shadow:0 8px 32px rgba(0,0,0,0.4);
            animation:slideInRight 0.4s cubic-bezier(0.34,1.56,0.64,1);
        `;
        toast.innerHTML = `
            <div style="display:flex;align-items:flex-start;gap:10px;">
                <div style="flex:1">${msg}</div>
                <button onclick="this.closest('#trial-toast').remove()" style="background:none;border:none;color:rgba(255,255,255,0.5);cursor:pointer;font-size:18px;line-height:1;padding:0;margin-top:-2px"></button>
            </div>
            <div style="margin-top:10px;display:flex;gap:8px;">
                <a href="upgrade.html" style="flex:1;text-align:center;background:${isRed ? '#dc2626' : '#d97706'};color:white;border-radius:8px;padding:7px 12px;font-size:12px;font-weight:700;text-decoration:none">
                    Contratar ahora 
                </a>
                <button onclick="this.closest('#trial-toast').remove()" style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);color:rgba(255,255,255,0.6);border-radius:8px;padding:7px 12px;font-size:12px;cursor:pointer">
                    Ms tarde
                </button>
            </div>
        `;

        document.body.appendChild(toast);

        // Auto-remove after 12 seconds
        setTimeout(() => { if (toast.parentNode) toast.remove(); }, 12000);
    }

    //  Urgency Modal (Days 31) 
    function _showUrgencyModal(daysLeft) {
        const overlay = document.createElement('div');
        overlay.id = 'trial-urgency-modal';
        overlay.style.cssText = `
            position:fixed;inset:0;z-index:9995;
            display:flex;align-items:center;justify-content:center;
            background:rgba(0,0,0,0.75);backdrop-filter:blur(6px);
            animation:fadeIn 0.3s ease;
        `;

        overlay.innerHTML = `
            <div style="
                background:linear-gradient(135deg,#1a0505,#1f0a0a);
                border:1px solid rgba(239,68,68,0.4);
                border-radius:24px;padding:40px;max-width:460px;width:90%;
                text-align:center;color:white;
                box-shadow:0 0 60px rgba(239,68,68,0.25);
                animation:scaleIn 0.4s cubic-bezier(0.34,1.56,0.64,1);
            ">
                <div style="font-size:52px;margin-bottom:16px"></div>
                <div style="background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);border-radius:100px;display:inline-block;padding:4px 16px;font-size:11px;font-weight:700;color:#f87171;text-transform:uppercase;letter-spacing:1px;margin-bottom:20px">
                    Prueba expira en ${daysLeft} da${daysLeft !== 1 ? 's' : ''}
                </div>
                <h2 style="font-size:24px;font-weight:800;margin-bottom:10px">Tu prueba est por terminar!</h2>
                <p style="color:rgba(255,255,255,0.6);font-size:14px;line-height:1.6;margin-bottom:28px">
                    Tienes <strong style="color:#f87171">${daysLeft} da${daysLeft !== 1 ? 's' : ''}</strong> antes de que se congele tu acceso.<br>
                    Contrata ahora y conserva todos tus datos, alertas y configuraciones.
                </p>

                <div style="background:rgba(255,255,255,0.04);border-radius:12px;padding:16px;margin-bottom:24px;text-align:left">
                    <div style="font-size:12px;color:rgba(255,255,255,0.4);font-weight:600;margin-bottom:10px;text-transform:uppercase;letter-spacing:1px">Incluye en el plan completo:</div>
                    <div style="font-size:13px;line-height:2;color:rgba(255,255,255,0.75)">
                         &nbsp;Agentes IA sin lmite de ciclos<br>
                         &nbsp;Backup automtico en Supabase<br>
                         &nbsp;Multi-usuario y RLS por empresa<br>
                         &nbsp;Soporte prioritario
                    </div>
                </div>

                <div style="display:flex;gap:10px;">
                    <a href="upgrade.html" style="flex:1;background:linear-gradient(135deg,#dc2626,#991b1b);color:white;border-radius:12px;padding:14px;font-size:14px;font-weight:700;text-decoration:none;display:block;text-align:center;">
                         Contratar Ahora
                    </a>
                </div>
                <button onclick="document.getElementById('trial-urgency-modal').remove()" style="
                    margin-top:14px;background:none;border:none;color:rgba(255,255,255,0.3);
                    cursor:pointer;font-size:12px;text-decoration:underline;
                ">Continuar con mi prueba (${daysLeft}d restantes)</button>
            </div>
        `;

        document.body.appendChild(overlay);
    }

    //  Hard Block Overlay (Expired) 
    function _showExpiredBlock(trial) {
        // Remove existing app access
        const mainApp = document.getElementById('main-app');
        if (mainApp) {
            mainApp.style.filter = 'blur(8px)';
            mainApp.style.pointerEvents = 'none';
            mainApp.style.userSelect = 'none';
        }

        const block = document.createElement('div');
        block.id = 'trial-expired-block';
        block.style.cssText = `
            position:fixed;inset:0;z-index:9999;
            display:flex;align-items:center;justify-content:center;
            background:rgba(0,0,0,0.9);backdrop-filter:blur(12px);
        `;

        const name = trial.name ? trial.name.split(' ')[0] : 'Usuario';

        block.innerHTML = `
            <div style="
                max-width:500px;width:90%;text-align:center;color:white;
                animation:scaleIn 0.5s cubic-bezier(0.34,1.56,0.64,1);
            ">
                <div style="font-size:64px;margin-bottom:20px"></div>
                <h1 style="font-size:28px;font-weight:800;margin-bottom:10px">Prueba finalizada, ${name}</h1>
                <p style="color:rgba(255,255,255,0.55);font-size:15px;line-height:1.6;margin-bottom:32px">
                    Tu prueba gratuita de 14 das ha concluido.<br>
                    Para recuperar el acceso completo y <strong style="color:white">conservar todos tus datos</strong>, contrata el plan.
                </p>

                <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:20px;padding:24px;margin-bottom:28px">
                    <div style="font-size:13px;color:rgba(255,255,255,0.4);margin-bottom:16px;text-transform:uppercase;letter-spacing:1px">Plan Empresa  Desde</div>
                    <div style="font-size:42px;font-weight:800;color:white">UF 3.5 <span style="font-size:16px;font-weight:400;color:rgba(255,255,255,0.4)">/mes</span></div>
                    <div style="font-size:13px;color:rgba(255,255,255,0.5);margin-top:4px">+ IVA  Multi-usuario  Sin permanencia</div>
                    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.08);margin:20px 0">
                    <div style="font-size:13px;line-height:2;color:rgba(255,255,255,0.7);text-align:left">
                         &nbsp;Agentes IA Nivel 5  Ciclos ilimitados<br>
                         &nbsp;Supabase real-time  RLS multi-tenant<br>
                         &nbsp;Dashboard ejecutivo + reportes PDF<br>
                         &nbsp;Soporte prioritario 48h
                    </div>
                </div>

                <a href="upgrade.html" style="
                    display:block;width:100%;
                    background:linear-gradient(135deg,#F36F21,#c4560e);
                    color:white;border-radius:16px;padding:16px;
                    font-size:16px;font-weight:800;text-decoration:none;
                    box-shadow:0 8px 24px rgba(243,111,33,0.4);
                    margin-bottom:16px;
                "> Contratar Ahora</a>

                <p style="font-size:12px;color:rgba(255,255,255,0.25)">
                    Necesitas ms tiempo? Escrbenos a <span style="color:rgba(255,255,255,0.4)">ventas@alpaconstruccioneingenieria.cl</span>
                </p>
            </div>
        `;

        document.body.appendChild(block);
    }

    //  CSS Animations (injected once) 
    function _injectStyles() {
        if (document.getElementById('trial-guard-styles')) return;
        const s = document.createElement('style');
        s.id = 'trial-guard-styles';
        s.textContent = `
            @keyframes slideInRight {
                from { transform: translateX(120%); opacity: 0; }
                to   { transform: translateX(0);    opacity: 1; }
            }
            @keyframes fadeIn {
                from { opacity: 0; }
                to   { opacity: 1; }
            }
            @keyframes scaleIn {
                from { transform: scale(0.85); opacity: 0; }
                to   { transform: scale(1);    opacity: 1; }
            }
        `;
        document.head.appendChild(s);
    }

    //  Init 
    _injectStyles();

    return { check };
})();

// Make global
window.TrialGuard = TrialGuard;

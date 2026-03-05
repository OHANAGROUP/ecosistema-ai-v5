/**
 * AgentOS v5.0 - Onboarding Wizard Engine
 * Guides new users to the "Aha Moment" in < 60 seconds:
 *   Login → See Dashboard → Open AI Agent → Run First Cycle → See Alert
 */

const ONBOARDING_KEY = 'agentOS_onboarding_v2';

const ONBOARDING_STEPS = [
    {
        id: 'welcome',
        title: '¡Bienvenido al Ecosistema AI!',
        icon: 'fa-rocket',
        iconColor: '#F36F21',
        description: 'Esta es tu central de inteligencia operativa autónoma. Los agentes de IA analizan tus proyectos, contratos y finanzas en tiempo real.',
        cta: 'Explorar el Dashboard',
        action: () => { if (typeof loadModule === 'function') loadModule('dashboard'); }
    },
    {
        id: 'dashboard',
        title: 'Tu Dashboard Ejecutivo',
        icon: 'fa-gauge',
        iconColor: '#3B82F6',
        description: 'Aquí ves el estado de todos tus proyectos, el nivel de coherencia de los agentes y las alertas críticas en tiempo real.',
        cta: 'Ir al Agente Director',
        action: () => { if (typeof loadModule === 'function') loadModule('agente-comprador'); }
    },
    {
        id: 'first_cycle',
        title: 'Lanza tu Primer Ciclo IA',
        icon: 'fa-brain',
        iconColor: '#8B5CF6',
        description: 'Selecciona un proyecto y presiona "Iniciar Ciclo". En segundos, el Director orquestará los agentes Financiero, Legal y de RRHH.',
        cta: 'Ver mis Proyectos',
        action: () => { if (typeof loadModule === 'function') loadModule('proyectos'); }
    },
    {
        id: 'aha_moment',
        title: '¡Primera Alerta Detectada! 🎉',
        icon: 'fa-shield-halved',
        iconColor: '#10B981',
        description: 'Los agentes encontraron algo. Esta es la inteligencia operativa en acción: detectamos riesgos antes de que se conviertan en problemas.',
        cta: 'Explorar todas las funciones',
        action: () => { OnboardingWizard.complete(); }
    }
];

const OnboardingWizard = {
    currentStep: 0,
    state: {},

    init() {
        this.state = JSON.parse(localStorage.getItem(ONBOARDING_KEY) || '{}');
        if (this.state.completed) {
            this._updateSidebarProgress();
            return;
        }
        // Show wizard after login is confirmed (wait for DOM)
        setTimeout(() => this._showModal(0), 1200);
    },

    _getModal() {
        return document.getElementById('onboarding-wizard-modal');
    },

    _showModal(stepIndex) {
        const modal = this._getModal();
        if (!modal) return;
        const step = ONBOARDING_STEPS[stepIndex];
        this.currentStep = stepIndex;

        // Update content
        modal.querySelector('#ob-icon').className = `fa-solid ${step.icon} text-4xl mb-1`;
        modal.querySelector('#ob-icon').style.color = step.iconColor;
        modal.querySelector('#ob-title').textContent = step.title;
        modal.querySelector('#ob-description').textContent = step.description;
        modal.querySelector('#ob-cta').textContent = step.cta;

        // Update progress dots
        modal.querySelectorAll('.ob-dot').forEach((dot, i) => {
            dot.classList.toggle('bg-orange-500', i === stepIndex);
            dot.classList.toggle('bg-gray-300', i !== stepIndex);
            dot.classList.toggle('scale-125', i === stepIndex);
        });

        // Step counter
        const counter = modal.querySelector('#ob-step-counter');
        if (counter) counter.textContent = `Paso ${stepIndex + 1} de ${ONBOARDING_STEPS.length}`;

        // Animate in
        modal.classList.remove('hidden');
        modal.querySelector('.ob-card').classList.add('ob-animate-in');
    },

    next() {
        const step = ONBOARDING_STEPS[this.currentStep];
        // Mark this step as done
        this.state[step.id] = true;
        localStorage.setItem(ONBOARDING_KEY, JSON.stringify(this.state));

        // Track in backend (non-blocking)
        if (window.AlertService) {
            AlertService.trackOnboarding(
                step.id,
                this.currentStep + 1,
                { step_title: step.title }
            ).catch(() => { }); // silent fail
        }

        // Execute CTA action
        if (step.action) step.action();

        const nextIndex = this.currentStep + 1;
        if (nextIndex < ONBOARDING_STEPS.length) {
            setTimeout(() => this._showModal(nextIndex), 400);
        } else {
            this.complete();
        }

        this._updateSidebarProgress();
    },

    skip() {
        const modal = this._getModal();
        if (modal) modal.classList.add('hidden');
        this._updateSidebarProgress();
    },

    complete() {
        this.state.completed = true;
        localStorage.setItem(ONBOARDING_KEY, JSON.stringify(this.state));

        // Track wizard completion in backend
        if (window.AlertService) {
            AlertService.trackOnboarding('wizard_completado', 4, {
                steps_completed: ONBOARDING_STEPS.filter(s => this.state[s.id]).length
            }).catch(() => { });
        }

        const modal = this._getModal();
        if (modal) {
            modal.querySelector('.ob-card').style.transform = 'scale(0.95)';
            modal.querySelector('.ob-card').style.opacity = '0';
            setTimeout(() => modal.classList.add('hidden'), 300);
        }
        // Show sidebar panel completion
        this._updateSidebarProgress();
        // Fire confetti-like feedback
        this._showCompletionToast();
    },

    _updateSidebarProgress() {
        const panel = document.getElementById('onboarding-panel');
        if (!panel) return;

        const completedSteps = ONBOARDING_STEPS.filter(s => this.state[s.id]).length;
        const total = ONBOARDING_STEPS.length;
        const pct = Math.round((completedSteps / total) * 100);

        // Show panel
        panel.classList.remove('hidden');

        // Update progress bar
        const bar = document.getElementById('onboarding-progress-bar');
        const pctLabel = document.getElementById('onboarding-percent');
        if (bar) bar.style.width = `${pct}%`;
        if (pctLabel) pctLabel.textContent = `${pct}%`;

        // Render checklist items
        const list = document.getElementById('onboarding-list');
        if (list) {
            list.innerHTML = ONBOARDING_STEPS.map(s => `
                <div class="flex items-center gap-2 text-[11px] ${this.state[s.id] ? 'text-white' : 'text-white/40'}">
                    <i class="fa-solid ${this.state[s.id] ? 'fa-circle-check text-green-400' : 'fa-circle text-white/20'} text-xs flex-shrink-0"></i>
                    <span>${s.title.replace('¡', '').replace('!', '').split(':')[0]}</span>
                </div>
            `).join('');
        }

        // Hide panel if completed
        if (this.state.completed && pct === 100) {
            setTimeout(() => panel.classList.add('hidden'), 3000);
        }
    },

    _showCompletionToast() {
        const toast = document.createElement('div');
        toast.className = 'fixed bottom-6 right-6 z-[200] flex items-center gap-3 bg-green-600 text-white px-5 py-4 rounded-xl shadow-2xl border border-green-400/30';
        toast.innerHTML = `
            <i class="fa-solid fa-circle-check text-xl text-green-300"></i>
            <div>
                <p class="font-bold text-sm">¡Onboarding Completado!</p>
                <p class="text-xs text-green-200 mt-0.5">Ahora eres parte del ecosistema 🚀</p>
            </div>
        `;
        toast.style.transform = 'translateY(20px)';
        toast.style.opacity = '0';
        toast.style.transition = 'all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)';
        document.body.appendChild(toast);
        requestAnimationFrame(() => {
            toast.style.transform = 'translateY(0)';
            toast.style.opacity = '1';
        });
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(20px)';
            setTimeout(() => toast.remove(), 400);
        }, 4000);
    },

    reset() {
        localStorage.removeItem(ONBOARDING_KEY);
        this.state = {};
        this.init();
    }
};

// Auto-init after successful login
document.addEventListener('agentOS:loginSuccess', () => {
    OnboardingWizard.init();
});

// Also init on DOM ready if already logged in
document.addEventListener('DOMContentLoaded', () => {
    // Check if user is already authenticated (login overlay will be hidden)
    setTimeout(() => {
        const overlay = document.getElementById('login-overlay');
        if (overlay && overlay.classList.contains('hidden')) {
            OnboardingWizard.init();
        }
    }, 1500);
});

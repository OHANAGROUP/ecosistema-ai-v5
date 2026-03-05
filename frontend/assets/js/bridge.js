/**
 * ALPA HUB BRIDGE
 * Connects Module Iframes with the Core Shell
 * v3.1.10.20 - Phase 1 Quick Wins: Real Toast Notifications
 */

window.AlpaHub = (function () {
    const REQUEST_TIMEOUT = 30000; // Increased to 30s for slow cloud sync
    const pendingRequests = {};

    // Listen for responses from Core
    window.addEventListener('message', function (event) {
        if (!event.data) return;

        // Handle Reload request from Shell
        if (event.data.action === 'RELOAD_MODULE') {
            window.location.reload();
            return;
        }

        if (event.data.type !== 'ALPA_RESPONSE') return;

        const { requestId, result } = event.data;
        if (pendingRequests[requestId]) {
            pendingRequests[requestId](result);
            delete pendingRequests[requestId];
        }
    });

    // ================================================
    // TOAST NOTIFICATION SYSTEM
    // ================================================
    const toastIcons = {
        success: 'fa-circle-check',
        error: 'fa-circle-xmark',
        warning: 'fa-triangle-exclamation',
        info: 'fa-circle-info',
    };
    const toastColors = {
        success: { bg: '#16a34a', border: '#bbf7d0' },
        error: { bg: '#dc2626', border: '#fecaca' },
        warning: { bg: '#d97706', border: '#fde68a' },
        info: { bg: '#2563eb', border: '#bfdbfe' },
    };

    function ensureToastContainer() {
        let container = document.getElementById('alpa-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'alpa-toast-container';
            container.style.cssText = [
                'position:fixed',
                'bottom:24px',
                'right:24px',
                'z-index:99999',
                'display:flex',
                'flex-direction:column-reverse',
                'gap:10px',
                'pointer-events:none',
            ].join(';');
            document.body.appendChild(container);
        }
        return container;
    }

    function showToast(message, type) {
        const safeType = toastColors[type] ? type : 'info';
        const { bg, border } = toastColors[safeType];
        const icon = toastIcons[safeType];

        const container = ensureToastContainer();

        const toast = document.createElement('div');
        toast.style.cssText = [
            'display:flex',
            'align-items:center',
            'gap:12px',
            `background:${bg}`,
            'color:#fff',
            'padding:12px 18px',
            'border-radius:10px',
            `border:1px solid ${border}`,
            'box-shadow:0 4px 16px rgba(0,0,0,0.25)',
            'font-family:Inter,sans-serif',
            'font-size:14px',
            'font-weight:500',
            'max-width:360px',
            'min-width:220px',
            'pointer-events:auto',
            'opacity:0',
            'transform:translateX(40px)',
            'transition:opacity 0.3s ease, transform 0.3s ease',
        ].join(';');

        toast.innerHTML = `
            <i class="fa-solid ${icon}" style="font-size:18px;flex-shrink:0;"></i>
            <span style="flex:1;line-height:1.4;">${message}</span>
            <button onclick="this.parentElement.remove()" style="background:none;border:none;color:rgba(255,255,255,0.7);cursor:pointer;font-size:16px;padding:0;margin-left:4px;line-height:1;">&#x2715;</button>
        `;

        container.appendChild(toast);

        // Animate in
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                toast.style.opacity = '1';
                toast.style.transform = 'translateX(0)';
            });
        });

        // Auto-dismiss after 4s
        const dismissTimer = setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(40px)';
            setTimeout(() => toast.remove(), 300);
        }, 4000);

        // Cancel auto-dismiss if user hovers
        toast.addEventListener('mouseenter', () => clearTimeout(dismissTimer));
        toast.addEventListener('mouseleave', () => {
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(40px)';
                setTimeout(() => toast.remove(), 300);
            }, 1500);
        });
    }

    return {
        getConfig: function () {
            // Try to access parent config or local
            return window.SAAS_CONFIG || (window.parent && window.parent.SAAS_CONFIG) || {};
        },

        execute: function (action, payload = {}) {
            return new Promise((resolve, reject) => {
                const requestId = 'req_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

                // Set timeout
                const timeout = setTimeout(() => {
                    if (pendingRequests[requestId]) {
                        delete pendingRequests[requestId];
                        reject(new Error('Request Timeout: ' + action));
                    }
                }, REQUEST_TIMEOUT);

                // Register callback
                pendingRequests[requestId] = (response) => {
                    clearTimeout(timeout);
                    resolve(response);
                };

                // Send message to parent (Core)
                const targetOrigin = window.location.origin.includes('vercel.app') ? window.location.origin : '*';
                window.parent.postMessage({
                    action: action,
                    payload: payload,
                    requestId: requestId
                }, targetOrigin);
            });
        },

        // Helper proxies for common actions
        getProjects: async function () { return await this.execute('getProjects'); },
        getInventory: async function () { return await this.execute('getInventory'); },
        getClients: async function () { return await this.execute('getClients'); },
        getProviders: async function () { return await this.execute('getProviders'); },
        getPendingLeads: async function () { return await this.execute('getPendingLeads'); },
        syncWebLeads: async function (payload) { return await this.execute('syncWebLeads', payload); },
        syncWithCloud: async function () { return await this.execute('syncWithCloud'); },
        addLeadNote: async function (payload) { return await this.execute('addLeadNote', payload); },
        assignLead: async function (payload) { return await this.execute('assignLead', payload); },
        updateLeadStatus: async function (payload) { return await this.execute('updateLeadStatus', payload); },
        updateLead: async function (payload) { return await this.execute('updateLead', payload); },
        cleanupLeads: async function () { return await this.execute('cleanupDatabaseLeads'); },
        deleteLead: async function (payload) { return await this.execute('deleteLead', payload); },

        addTransaction: async function (transaction) {
            return await this.execute('addTransaction', transaction);
        },

        navigate: function (module) {
            const targetOrigin = window.location.origin.includes('vercel.app') ? window.location.origin : '*';
            window.parent.postMessage({ action: 'HUB_NAVIGATE', module: module }, targetOrigin);
        },

        /**
         * showNotification - Real toast notification system
         * @param {string} message - Message to display
         * @param {'success'|'error'|'warning'|'info'} type - Alert type
         */
        showNotification: function (message, type = 'info') {
            showToast(message, type);
        }
    };
})();

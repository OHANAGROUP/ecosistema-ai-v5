/**
 * ALPA HUB BRIDGE
 * Connects Module Iframes with the Core Shell
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
        deleteLead: async function (payload) { return await this.execute('deleteLead', payload); },

        addTransaction: async function (transaction) {
            return await this.execute('addTransaction', transaction);
        },

        navigate: function (module) {
            const targetOrigin = window.location.origin.includes('vercel.app') ? window.location.origin : '*';
            window.parent.postMessage({ action: 'HUB_NAVIGATE', module: module }, targetOrigin);
        },

        showNotification: function (message, type = 'info') {
            console.log(`[Notification: ${type}] ${message}`);
        }
    };
})();

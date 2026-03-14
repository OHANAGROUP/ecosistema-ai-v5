/**
 * Component Loader JS
 * Carga componentes HTML externos e inyecta en el DOM.
 */
const ComponentLoader = {
    components: [
        { id: 'topnav-target',     url: '/components/shell/topnav.html' },
        { id: 'login-target',      url: '/components/shell/login-overlay.html' },
        { id: 'onboarding-target', url: '/components/shell/onboarding-wizard.html' }
    ],

    async init() {
        console.log("🧩 Initializing Component Loader...");
        const promises = this.components.map(comp => this.load(comp));
        await Promise.all(promises);
        console.log("✅ All components loaded.");
        document.dispatchEvent(new CustomEvent('componentsLoaded'));
    },

    async load(comp) {
        const target = document.getElementById(comp.id);
        if (!target) {
            console.warn(`Target #${comp.id} not found for component ${comp.url}`);
            return;
        }

        try {
            const response = await fetch(comp.url + '?v=' + Date.now());
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const html = await response.text();
            target.innerHTML = html;
        } catch (error) {
            console.error(`Failed to load component ${comp.url}:`, error);
        }
    }
};

// Start loading once DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    ComponentLoader.init();
});

/**
 * SAAS ALPA UNIFICADO - CONFIGURATION
 * -----------------------------------
 * Centralized configuration for the main production environment.
 */

const SAAS_CONFIG = {
    // Identity
    companyName: 'ALPA Construcciones',
    websiteUrl: 'http://alpaconstruccioneingenieria.cl/',
    version: '3.1.10.9',

    // Backend Connection (Google Apps Script)
    backendUrl: 'https://script.google.com/macros/s/AKfycbyl2PbBpYNQKQ-v1dBWROf2nGkynDG3jRgxIU_s1bokSY3kOhxUPtjmn25GCNdml8rZng/exec',

    // Storage Keys (Main Production Keys)
    storageKey: 'alpa_saas_db_v1',     // Core Data
    sessionKey: 'alpa_app_session_v1', // User Session

    // Allowed Users (Moved from index.html)
    // In a real app, this should be server-side or encrypted.
    // For this specific deployment, we keep the quick-access list here.
    users: [
        { email: 'admin@alpaconstruccioneingenieria.cl', name: 'Admin Local', role: 'Admin' },
        { email: 'ventas@alpaconstruccioneingenieria.cl', name: 'Ejecutivo Ventas', role: 'Ventas' },
        { email: 'adquisiciones@alpaconstruccioneingenieria.cl', name: 'Encargado Compras', role: 'Adquisiciones' },
        { email: 'bodega@alpaconstruccioneingenieria.cl', name: 'Jefe de Bodega', role: 'Bodega' },
        { email: 'gerencia@alpaconstruccioneingenieria.cl', name: 'Gerente General', role: 'Gerencia' },
        { email: 'compras@alpaconstruccioneingenieria.cl', name: 'Encargado de Compras', role: 'Adquisiciones' }
    ],
    // Environment Detection & Mode Configuration
    // Modes: 'local' (LocalStorage only), 'gas' (Vercel + Google Apps Script), 'supa' (Vercel + Supabase)
    getEnvMode: function () {
        if (typeof window === 'undefined') return 'local';
        const host = window.location.hostname;
        const isVercel = host.includes('vercel.app');

        // Manual override via URL params (e.g., ?mode=supa) or default for Vercel
        const urlParams = new URLSearchParams(window.location.search);
        const modeParam = urlParams.get('mode');

        if (isVercel) {
            return modeParam || 'supa'; // Updated to 'supa' as default for multi-tenancy
        }
        return 'local';
    },

    // Credentials for Supabase
    supabase: {
        url: 'https://tnzfalnzxnzxqxtywtey.supabase.co'.trim().replace(/\/+$/, ''),
        key: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlempja2xmd2FiZGtmY2VuenVqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk5ODUzNTgsImV4cCI6MjA4NTU2MTM1OH0.xT3F0WBmKKvLyD4ee4jGHAQAkQvEDDO0GVjbYCateAM'
    }
};

// Mode Initialization
SAAS_CONFIG.mode = SAAS_CONFIG.getEnvMode();
SAAS_CONFIG.isLocal = SAAS_CONFIG.mode === 'local';

// Export to Global Scope
if (typeof window !== 'undefined') {
    window.SAAS_CONFIG = SAAS_CONFIG;
    console.log(`ECOSISTEMA V5.0 LOADED - Mode: ${SAAS_CONFIG.mode.toUpperCase()}`);
}

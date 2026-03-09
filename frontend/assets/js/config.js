/**
 * SAAS ALPA UNIFICADO - CONFIGURATION
 * -----------------------------------
 * Centralized configuration for the main production environment.
 */

const SAAS_CONFIG = {
    // Identity
    companyName: 'ALPA Construcciones',
    websiteUrl: 'https://automatizai.cl/',
    version: '5.0.1-prd',

    // Backend Connection (Google Apps Script)
    backendUrl: 'https://script.google.com/macros/s/AKfycbyl2PbBpYNQKQ-v1dBWROf2nGkynDG3jRgxIU_s1bokSY3kOhxUPtjmn25GCNdml8rZng/exec',

    // AI Engine v5.0 Connection
    // Update this to your production API URL when deploying
    aiBackendUrl: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? 'http://localhost:8000/api/v1'
        : 'https://ecosistema-ai-v50-production.up.railway.app/api/v1',
    apiUrl: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? 'http://localhost:8000/api/v1'
        : 'https://ecosistema-ai-v50-production.up.railway.app/api/v1',

    // Storage Keys (Main Production Keys)
    storageKey: 'alpa_saas_db_v1',     // Core Data
    sessionKey: 'alpa_app_session_v1', // User Session
    defaultOrgId: '00000000-0000-0000-0000-000000000000', // Valid UUID Fallback

    // Environment Detection & Mode Configuration
    // Modes: 'local' (LocalStorage only), 'gas' (Vercel + Google Apps Script), 'supa' (Vercel + Supabase)
    getEnvMode: function () {
        if (typeof window === 'undefined') return 'local';
        const host = window.location.hostname;
        const isVercel = host.includes('vercel.app');
        const isLocal = host === 'localhost' || host === '127.0.0.1';
        const isCustomDomain = !isLocal && !isVercel && host !== '';

        // Manual override via URL params (e.g., ?mode=local)
        const urlParams = new URLSearchParams(window.location.search);
        const modeParam = urlParams.get('mode');
        if (modeParam) return modeParam;

        // Vercel, localhost, and custom domains default to 'supa'
        if (isVercel || isLocal || isCustomDomain) return 'supa';
        return 'local';
    },

    // Credentials for Supabase
    supabase: {
        url: window.__ENV__?.SUPABASE_URL || 'https://tnzfalnzxnzxqxtywtey.supabase.co',
        // IMPORTANT: Replace the placeholder below with the real Anon Key from Supabase Dashboard
        key: window.__ENV__?.SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRuemZhbG56eG56eHF4dHl3dGV5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIyNTE1MDUsImV4cCI6MjA4NzgyNzUwNX0.u5o30hb2YVPSVLVWVlrIP_m1pneRY43jyvJxWssfKlI'
    }
};

// Mode Initialization
SAAS_CONFIG.mode = SAAS_CONFIG.getEnvMode();
SAAS_CONFIG.isLocal = SAAS_CONFIG.mode === 'local';

// Export to Global Scope
if (typeof window !== 'undefined') {
    window.SAAS_CONFIG = SAAS_CONFIG;
    console.log(`ALPA SAAS LOADED - Mode: ${SAAS_CONFIG.mode.toUpperCase()}`);
}

// â”€â”€ Safe Supabase client singleton â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Use window.sbClient everywhere to avoid "already declared" errors with
// the Supabase CDN that also injects window.supabase as an object.
(function initSbClient() {
    if (typeof window === 'undefined') return;
    const cfg = window.SAAS_CONFIG?.supabase;
    if (
        window.supabase?.createClient &&
        cfg?.url && cfg?.key &&
        !cfg.key.includes('placeholder') &&
        !cfg.url.includes('placeholder')
    ) {
        window.sbClient = window.supabase.createClient(cfg.url, cfg.key);
        window.SAAS_CONFIG.sbClient = window.sbClient; // alias for convenience
    } else {
        window.sbClient = null;
    }
})();

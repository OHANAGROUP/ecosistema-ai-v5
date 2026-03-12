/**
 * THEME ENGINE  ECOSISTEMA AI v5.0
 * Paleta base: Industrial Futurista (fondo azulado fro + naranja construccin)
 */

const THEMES = {
    industrial: {
        name: 'Industrial Futurista',
        desc: 'Fondo azulado fro  Naranja construccin',
        '--bg': '#0a0b0d',
        '--surface': '#111318',
        '--surface2': '#141720',
        '--border': '#1e2128',
        '--border2': '#252a35',
        '--orange': '#f5620f',
        '--orange2': '#ff8c42',
        '--orange3': '#e04d08',
        '--text': '#e8e9eb',
        '--text2': '#b8bcc8',
        '--muted': '#6b7280',
    },
    arctic: {
        name: 'Arctic Clean',
        desc: 'Fondo blanco  Azul corporativo',
        '--bg': '#f0f4f8',
        '--surface': '#ffffff',
        '--surface2': '#f8fafc',
        '--border': '#dde3ea',
        '--border2': '#c8d0da',
        '--orange': '#0066ff',
        '--orange2': '#3385ff',
        '--orange3': '#0052cc',
        '--text': '#0f1923',
        '--text2': '#2d3748',
        '--muted': '#6b7a8d',
    },
    obsidian: {
        name: 'Obsidian Deep',
        desc: 'Fondo negro profundo  Prpura',
        '--bg': '#0d0d14',
        '--surface': '#13131f',
        '--surface2': '#18182a',
        '--border': '#1f1f32',
        '--border2': '#2a2a45',
        '--orange': '#7c3aed',
        '--orange2': '#9d5ff5',
        '--orange3': '#6d28d9',
        '--text': '#e2e0f0',
        '--text2': '#b8b5d0',
        '--muted': '#6b6880',
    },
    crimson: {
        name: 'Crimson Elite',
        desc: 'Fondo negro rojizo  Rojo carmes',
        '--bg': '#0c0608',
        '--surface': '#140a0d',
        '--surface2': '#1a0e12',
        '--border': '#2a1218',
        '--border2': '#381820',
        '--orange': '#e11d48',
        '--orange2': '#f43f5e',
        '--orange3': '#be123c',
        '--text': '#fce7ec',
        '--text2': '#fda4af',
        '--muted': '#9f6672',
    },
    forest: {
        name: 'Forest Ops',
        desc: 'Fondo negro verdoso  Verde operacional',
        '--bg': '#070d09',
        '--surface': '#0d1610',
        '--surface2': '#111d14',
        '--border': '#1a2e1e',
        '--border2': '#223d28',
        '--orange': '#16a34a',
        '--orange2': '#22c55e',
        '--orange3': '#15803d',
        '--text': '#ecfdf5',
        '--text2': '#a7f3d0',
        '--muted': '#6b8f75',
    }
};

// Preview colors para las tarjetas del selector
const THEME_PREVIEW = {
    industrial: { bg: '#0a0b0d', surface: '#111318', accent: '#f5620f', text: '#e8e9eb', border: '#1e2128' },
    arctic: { bg: '#f0f4f8', surface: '#ffffff', accent: '#0066ff', text: '#0f1923', border: '#dde3ea' },
    obsidian: { bg: '#0d0d14', surface: '#13131f', accent: '#7c3aed', text: '#e2e0f0', border: '#1f1f32' },
    crimson: { bg: '#0c0608', surface: '#140a0d', accent: '#e11d48', text: '#fce7ec', border: '#2a1218' },
    forest: { bg: '#070d09', surface: '#0d1610', accent: '#16a34a', text: '#ecfdf5', border: '#1a2e1e' },
};

function applyTheme(themeKey) {
    const theme = THEMES[themeKey] || THEMES.industrial;
    const root = document.documentElement;
    Object.entries(theme).forEach(([key, val]) => {
        if (key.startsWith('--')) root.style.setProperty(key, val);
    });
    localStorage.setItem('ecosistema_theme', themeKey);
    document.documentElement.setAttribute('data-theme', themeKey);
}

function getActiveTheme() {
    return localStorage.getItem('ecosistema_theme') || 'obsidian';
}

//  Auto-apply ANTES de renderizar (evita flash) 
(function () {
    const saved = localStorage.getItem('ecosistema_theme') || 'obsidian';
    applyTheme(saved);
})();

window.ThemeEngine = { THEMES, THEME_PREVIEW, applyTheme, getActiveTheme };

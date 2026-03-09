/**
 * TEST MANUAL DE EMBUDO DE VENTAS (SALES FUNNEL)
 * ------------------------------------------------
 * Instrucciones:
 * 1. Abre http://localhost:8081 en tu navegador.
 * 2. Abre la consola de desarrollador (F12).
 * 3. Copia y pega este script para autenticarte y cargar un lead de prueba.
 */

// 1. Simular AutenticaciÃ³n (Bypassing Login)
const mockSession = {
    token: "test-token-123",
    user: {
        name: "Tester AutomÃ¡tico",
        role: "Admin",
        email: "admin@test.cl",
        organization_id: "org_default"
    }
};
localStorage.setItem('alpa_app_session_v1', JSON.stringify(mockSession));

// 2. Inyectar Lead de Prueba
const testLead = {
    id: 'TEST-' + Date.now(),
    clientName: 'Cliente Prueba ' + Math.floor(Math.random() * 100),
    email: 'cliente@prueba.com',
    phone: '+56912345678',
    project: 'Proyecto Demo Funnel',
    createdAt: new Date().toISOString(),
    status: 'Nuevo',
    notes: []
};

// Acceder al estado central (Core)
if (window.AlpaCore && AlpaCore.state) {
    AlpaCore.state.pendingLeads.unshift(testLead);
    AlpaCore.saveState();
    console.log("âœ… Lead de prueba inyectado:", testLead);
} else {
    // Si AlpaCore no estÃ¡ listo, lo guardamos en localStorage para que cargue al inicio
    const store = JSON.parse(localStorage.getItem('alpa_saas_db_v1') || '{}');
    if (!store.pendingLeads) store.pendingLeads = [];
    store.pendingLeads.unshift(testLead);
    localStorage.setItem('alpa_saas_db_v1', JSON.stringify(store));
    console.log("âœ… Lead de prueba guardado en localStorage (Carga al recargar).");
}

// 3. Recargar para aplicar cambios y entrar
console.log("ðŸ”„ Recargando sistema en 3 segundos...");
setTimeout(() => {
    window.location.reload();
}, 2000);

// --- PASOS SIGUIENTES PARA EL USUARIO ---
// 4. Ve a 'Prospectos Web'.
// 5. VerÃ¡s el 'Cliente Prueba'.
// 6. Haz clic en el Ã­cono de lÃ¡piz para editar su nombre.
// 7. Haz clic en 'COTIZAR' y verifica que los datos pasen al Cotizador.

/**
 * ECOSISTEMA V5.0 AUTOMATED TEST SUITE v1.0
 * 
 * Instructions:
 * 1. Open the application in your browser (index.html).
 * 2. Open Developer Tools (F12) -> Console.
 * 3. Copy and Paste ALL code below into the console and press Enter.
 * 
 * This script will:
 * - Verify the Core connection.
 * - Create a dummy Quote and convert it to a Project.
 * - Create a dummy PO and register it as an Expense.
 * - Verify Inventory operations.
 * - Simulate Multi-User actions.
 */

(async function runAlpaTest() {
    console.clear();
    console.log("%c ?? INICIANDO TEST 'SHOOT' ECOSISTEMA V5.0 ", "background: #003366; color: #bada55; padding: 10px; font-size: 16px; font-weight: bold;");

    // 0. CHECK ENVIRONMENT
    // Fix: Look in window OR parent window
    let core = window.AlpaCore || (window.parent ? window.parent.AlpaCore : undefined);

    if (typeof core === 'undefined') {
        console.error("? FATAL: AlpaCore no encontrado. Asegrate de estar en index.html o un mdulo cargado por l.");
        return;
    }
    console.log("? Core System: ONLINE (Scope: " + (window.AlpaCore ? "Direct" : "Parent") + ")");

    // SETUP MOCK USERS
    const UserA = { name: "Test User A", role: "Ventas", email: "a@test.cl" };
    const UserB = { name: "Test User B", role: "Adquisiciones", email: "b@test.cl" };

    // --- TEST 1: INVENTORY (Shared Resource) ---
    console.group("?? TEST 1: GESTIN DE INVENTARIO");
    const initStock = core.getInventory().length;
    const testItem = { sku: `TEST-${Date.now()}`, name: "Item Prueba Automtica", stock: 100, unit: "un" };

    core.upsertInventoryItem(testItem);
    const newStock = core.getInventory().length;

    if (newStock === initStock + 1) console.log("? Item Creado OK");
    else console.error("? Error creando Item");

    core.adjustStock(testItem.sku, -10);
    const updatedItem = core.getInventory().find(i => i.sku === testItem.sku);
    if (updatedItem.stock === 90) console.log("? Ajuste de Stock OK (100 -> 90)");
    else console.error("? Error ajustando stock", updatedItem);

    // Cleanup
    core.deleteInventoryItem(testItem.sku);
    console.log("? Limpieza de Item OK");
    console.groupEnd();


    // --- TEST 2: WORKFLOW COTIZACIN -> PROYECTO ---
    console.group("?? TEST 2: FLUJO COTIZACIN -> PROYECTO (MULTI-USUARIO)");
    const quoteData = {
        projectName: "Proyecto Test Automatizado (" + Date.now() + ")",
        clientName: "Cliente Test SpA",
        total: 5000000
    };

    console.log(`?? Usuario 'Ventas' (${UserA.name}) crea cotizacin...`);
    // Simulate Workflow Call from Cotizador
    const project = core.convertQuoteToProject(quoteData, UserA);

    if (project && project.id.startsWith("PROJ-")) {
        console.log("? Proyecto creado en Cola Pendiente:", project.id);
        console.log("   --> Creado por:", project.createdBy);

        if (project.createdBy === UserA.name) console.log("? Auditora de Usuario Correcta");
        else console.error("? Error de Auditora: Usuario no coincide");

    } else {
        console.error("? Fallo conversin de proyecto");
    }
    console.groupEnd();


    // --- TEST 3: WORKFLOW ORDEN COMPRA -> GASTO ---
    console.group("?? TEST 3: FLUJO OC -> GASTO");
    const poData = {
        number: "OC-TEST-" + Math.floor(Math.random() * 1000),
        provider: "Proveedor Test Ltda",
        total: 150000
    };

    console.log(`?? Usuario 'Adquisiciones' (${UserB.name}) emite orden...`);
    const expense = core.registerPurchaseOrder(poData, UserB);

    if (expense && expense.status === 'Pendiente') {
        console.log("? Gasto registrado en Cola:", expense.id);
        if (expense.createdBy === UserB.name) console.log("? Auditora de Usuario Correcta");
    } else {
        console.error("? Fallo registro de gasto");
    }
    console.groupEnd();


    // --- TEST 4: VERIFICANDO INTEGRIDAD DE DATOS (DASHBOARD) ---
    console.group("?? TEST 4: VERIFICACIN GLOBAL");
    const metrics = core.getDashboardMetrics();
    console.table(metrics);

    const db = JSON.parse(localStorage.getItem('alpa_saas_db_v1'));
    const pendingProjs = db.pendingProjects || [];
    const pendingExps = db.pendingExpenses || [];

    console.log(`Estado Final: ${pendingProjs.length} Proyectos Pendientes, ${pendingExps.length} Gastos Pendientes.`);

    if (pendingProjs.length > 0 && pendingExps.length > 0) {
        console.log("? %c TEST END-TO-END EXITOSO ", "background: green; color: white;");
        alert("TEST SYSTEM: Todas las pruebas pasaron exitosamente. Revisa la consola para detalles.");
    } else {
        console.warn("?? Advertencia: No se encontraron los datos esperados en la BD.");
    }
    console.groupEnd();

})();

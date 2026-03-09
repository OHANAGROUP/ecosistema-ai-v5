/**
 * ECOSISTEMA V5.0 CORE
 * Centralized Data Management for the Unified Suite
 * Handles: Clients, Providers, Shared Projects, Leads and Inventory
 * REVISION: 2026-02-16 (v3.1.10.9-MultiTenant)
 */

window.AlpaCore = (function () {
    // --- STATE MANAGEMENT ---
    const DB_KEY = 'alpa_saas_db_v1';

    const safeParse = (val) => {
        if (typeof val === 'number') return isNaN(val) ? 0 : val;
        if (!val || val === '#NUM!') return 0;
        let str = val.toString().trim();
        // Handle European formats (1.000,50 -> 1000.50)
        if (str.includes(',') && str.includes('.')) str = str.replace(/\./g, '');
        str = str.replace(',', '.');
        const cleaned = str.replace(/[^0-9.-]+/g, "");
        const n = parseFloat(cleaned);
        return isNaN(n) ? 0 : n;
    };

    // Default Initial State (PRODUCTION - No sample data)
    const defaultState = {
        clients: [],
        providers: [],
        inventory: [],
        projects: [],
        transactions: [],
        expenseReports: [],
        pendingLeads: [],
        deletedLeadIds: [],
        pendingProjects: [],
        pendingExpenses: [],
        settings: {
            nextQuoteId: 100,
            nextOrderId: 100
        },
        organization: null // Current organization details
    };

    // --- SUPABASE CLIENT INITIALIZATION ---
    let supabase = null;
    const supabaseLib = window.supabase || (typeof supabasejs !== 'undefined' ? supabasejs : null);

    if (supabaseLib && SAAS_CONFIG.supabase.url && SAAS_CONFIG.supabase.key && SAAS_CONFIG.supabase.key.startsWith('eyJ')) {
        supabase = supabaseLib.createClient(SAAS_CONFIG.supabase.url, SAAS_CONFIG.supabase.key);
        console.log("ALPA CORE: Supabase Client Initialized ?");
    } else {
        console.warn("ALPA CORE: Supabase NOT Initialized ??");
    }

    // --- STORAGE ADAPTER (Bridge Pattern) ---
    const StorageAdapter = {
        async getOrgId() {
            // Priority 1: Check Local Session (Persistent across frames)
            const sessionKey = (window.SAAS_CONFIG && window.SAAS_CONFIG.sessionKey) || 'alpa_app_session_v1';
            const localSession = localStorage.getItem(sessionKey);
            if (localSession) {
                try {
                    const s = JSON.parse(localSession);
                    if (s.user && s.user.organization_id) return s.user.organization_id;
                    if (s.user && s.user.org_id) return s.user.org_id;
                } catch (e) { }
            }

            // Priority 2: Check Supabase Auth (Official session)
            if (!supabase) return null;
            const { data: { session } } = await supabase.auth.getSession();
            return session?.user?.app_metadata?.organization_id ||
                session?.user?.user_metadata?.organization_id ||
                session?.user?.user_metadata?.org_id || null;
        },

        async ensureOrganization(orgId) {
            if (!supabase || !orgId) return;
            try {
                // Check if exists
                const { data, error } = await supabase.from('organizations').select('id').eq('id', orgId).single();
                if (error || !data) {
                    console.log(`ALPA CORE: Organization ${orgId} missing. Creating...`);
                    await supabase.from('organizations').upsert({ id: orgId, name: 'Empresa Test A' });
                }
            } catch (e) {
                console.warn("ALPA CORE: Failed to ensure organization record.", e);
            }
        },

        async save(data) {
            const mode = (window.SAAS_CONFIG && window.SAAS_CONFIG.mode) || 'local';

            try {
                if (mode === 'supa' && supabase) {
                    const orgId = await this.getOrgId();
                    if (!orgId) throw new Error("No organization ID found in session.");

                    console.log(`ALPA CORE: Saving to Supabase (Org: ${orgId})...`);
                    await this.ensureOrganization(orgId);

                    await Promise.all([
                        this.upsertTable('clients', data.clients, orgId),
                        this.upsertTable('providers', data.providers, orgId),
                        this.upsertTable('projects', data.projects, orgId),
                        this.upsertTable('transactions', data.transactions, orgId),
                        this.upsertTable('inventory', data.inventory, orgId),
                        this.upsertTable('leads', data.pendingLeads, orgId)
                    ]);
                    return true;
                }

                // Default: LocalStorage
                localStorage.setItem(DB_KEY, JSON.stringify(data));
                return true;
            } catch (e) {
                console.warn("ALPA CORE: Storage save failed.", e);
                return false;
            }
        },

        async load() {
            const mode = (window.SAAS_CONFIG && window.SAAS_CONFIG.mode) || 'local';

            try {
                if (mode === 'supa' && supabase) {
                    const orgId = await this.getOrgId();
                    if (orgId) await this.ensureOrganization(orgId);

                    console.log(`ALPA CORE: Loading from Supabase (Org: ${orgId})...`);

                    const [c, p, pr, t, i, l, o] = await Promise.all([
                        supabase.from('clients').select('*'),
                        supabase.from('providers').select('*'),
                        supabase.from('projects').select('*'),
                        supabase.from('transactions').select('*'),
                        supabase.from('inventory').select('*'),
                        supabase.from('leads').select('*'),
                        orgId ? supabase.from('organizations').select('*').eq('id', orgId).single() : Promise.resolve({ data: null })
                    ]);

                    if (o.error && o.code !== 'PGRST116') {
                        console.error("ALPA CORE: Supabase fetch error for organization:", o.error);
                    }
                    console.log("ALPA CORE: Organization state loaded:", o.data);

                    return {
                        ...defaultState,
                        organization: o.data || defaultState.organization,


                        clients: c.data || [],
                        providers: p.data || [],
                        projects: (pr.data || []).map(row => ({
                            id: row.ID || row.id,
                            name: row.Nombre || row.name,
                            code: row.Codigo || row.code,
                            client: row.Cliente || row.client,
                            clientRut: row.client_rut || row.clientRut,
                            budget: row.Presupuesto || row.budget,
                            status: row.Estado || row.status,
                            startDate: row.FechaInicio || row.startDate,
                            endDate: row.FechaTermino || row.endDate,
                            progress: row.PorcentajeAvance || row.progress,
                            responsible: row.Responsable || row.responsible,
                            costCenter: row.CentroCostoID || row.costCenter,
                            paymentStatuses: row.payment_statuses || row.paymentStatuses || []
                        })),
                        transactions: (t.data || []).map(row => ({
                            id: row.ID || row.id,
                            date: row.Fecha || row.date,
                            type: row.Tipo || row.type,
                            category: row.Categoría || row.category,
                            amount: row.Monto || row.amount,
                            description: row.Descripción || row.description,
                            user: row.Usuario || row.user,
                            costCenter: row.cost_center || row.costCenter || row.CentroCostoID || row.ProyectoID,
                            source_of_funds: row.source_of_funds || 'company',
                            reimbursement_status: row.reimbursement_status || 'not_applicable'
                        })),
                        inventory: i.data || [],
                        pendingLeads: l.data || []
                    };
                }

                const saved = localStorage.getItem(DB_KEY);
                return saved ? JSON.parse(saved) : null;
            } catch (e) {
                console.warn("ALPA CORE: Storage load failed.", e);
                return null;
            }
        },

        async upsertTable(tableName, items, orgId) {
            if (!items || items.length === 0) return;

            console.log(`ALPA CORE: Upserting ${items.length} items to ${tableName}...`);

            const mappedItems = items.map(item => {
                const base = { organization_id: orgId };

                if (tableName === 'projects') {
                    return {
                        ...base,
                        "ID": String(item.id || item.ID || 'p-' + Date.now() + Math.random()),
                        "Nombre": item.name || item.Nombre || 'Sin Nombre',
                        "Codigo": item.code || item.Codigo || '',
                        "Cliente": item.client || item.Cliente || '',
                        "client_rut": item.clientRut || item.client_rut || '',
                        "CentroCostoID": item.costCenter || item.cost_center || item.CentroCostoID || '',
                        "Presupuesto": safeParse(item.budget || item.Presupuesto),
                        "Estado": item.status || item.Estado || 'Activo',
                        "FechaInicio": (item.startDate || item.FechaInicio) ? new Date(item.startDate || item.FechaInicio).toISOString().split('T')[0] : null,
                        "FechaTermino": (item.endDate || item.FechaTermino) ? new Date(item.endDate || item.FechaTermino).toISOString().split('T')[0] : null,
                        "PorcentajeAvance": safeParse(item.progress || item.PorcentajeAvance),
                        "Responsable": item.responsible || item.Responsable || '',
                        "payment_statuses": item.paymentStatuses || item.payment_statuses || []
                    };
                }

                if (tableName === 'transactions') {
                    return {
                        ...base,
                        "ID": String(item.id || item.ID || 't-' + Date.now() + Math.random()),
                        "Fecha": (item.date || item.Fecha) ? new Date(item.date || item.Fecha).toISOString().split('T')[0] : new Date().toISOString().split('T')[0],
                        "Tipo": item.type || item.Tipo || 'Gasto',
                        "Categoría": item.category || item.Categoría || 'Otros',
                        "Monto": safeParse(item.amount || item.Monto),
                        "Descripción": item.description || item.Descripción || '',
                        "Usuario": item.user || item.Usuario || 'Sistema',
                        "cost_center": item.costCenter || item.cost_center || item.CentroCostoID || item.ProyectoID || 'General',
                        "source_of_funds": item.source_of_funds || 'company',
                        "reimbursement_status": item.reimbursement_status || 'not_applicable'
                    };
                }

                if (tableName === 'clients') {
                    return {
                        ...base,
                        id: item.id || item.ID || Date.now(),
                        name: item.name || item.Nombre || 'Sin Nombre',
                        rut: item.rut || item.Rut || '',
                        contact: item.contact || item.Contacto || '',
                        phone: item.phone || item.Telefono || '',
                        email: item.email || item.Email || '',
                        origin: item.origin || 'Legacy Import'
                    };
                }

                if (tableName === 'providers') {
                    return {
                        ...base,
                        id: item.id || item.ID || Date.now(),
                        name: item.name || item.Nombre || 'Sin Nombre',
                        rut: item.rut || item.Rut || '',
                        contact: item.contact || item.Contacto || '',
                        phone: item.phone || item.Telefono || '',
                        email: item.email || item.Email || ''
                    };
                }

                if (tableName === 'inventory') {
                    return {
                        ...base,
                        name: item.name || item.Nombre || 'Sin Nombre',
                        sku: item.sku || item.SKU || 'SKU-' + Date.now(),
                        stock: safeParse(item.stock || item.Stock),
                        unit: item.unit || item.Unidad || 'unidad'
                    };
                }

                if (tableName === 'leads') {
                    return {
                        ...base,
                        name: item.name || item.Nombre || 'Sin Nombre',
                        email: item.email || item.Email || '',
                        phone: item.phone || item.Telefono || '',
                        message: item.message || item.Mensaje || '',
                        status: item.status || 'new'
                    };
                }

                return { ...item, organization_id: orgId };
            });

            const { error } = await supabase.from(tableName).upsert(mappedItems);
            if (error) {
                console.error(`? Error upserting ${tableName}:`, error);
                throw error;
            }
        }
    };

    // Load or Init State Logic (Unified in the bottom handler)
    let state = defaultState;

    function saveState() {
        StorageAdapter.save(state);
    }


    // --- PUBLIC API ---

    const CoreAPI = {
        state: state,
        supabase: supabase,
        saveState: saveState,

        getClients: function () { return state.clients; },
        getOrganization: function () { return state.organization; },
        updateOrganization: async function (updates) {
            if (!state.organization) {
                console.error("ALPA CORE: Cannot update, no organization in state.");
                return false;
            }

            // Calculate payload size for debugging (especially for Base64 logos)
            const payloadSize = JSON.stringify(updates).length;
            console.log(`ALPA CORE: Updating Organization. Payload size: ${(payloadSize / 1024).toFixed(2)} KB`);

            if (SAAS_CONFIG.mode === 'supa') {
                try {
                    const { error } = await supabase
                        .from('organizations')
                        .update(updates)
                        .eq('id', state.organization.id);

                    if (error) {
                        console.error("? Error updating organization in Supabase:", error);
                        return false;
                    }
                    console.log("ALPA CORE: Supabase update successful ?");
                } catch (e) {
                    console.error("? Exception during organization update:", e);
                    return false;
                }
            }

            // Update local state ONLY after Supabase success (if in supa mode)
            state.organization = { ...state.organization, ...updates };
            CoreAPI.state = state;

            saveState(); // Update local storage too
            return true;
        },

        getOnboardingStatus: function () {
            const org = state.organization || {};
            // Identity: Custom name (not default) or has a logo url
            const defaultNames = ['Empresa Nueva', 'Empresa Test A', 'ALPA', 'Sin Nombre', '...', '---'];
            const hasValidName = org.name && !defaultNames.includes(org.name);
            const hasLogo = (org.settings && org.settings.logo_url) || org.logo_url;

            const hasIdentity = hasValidName || hasLogo;

            // Projects: At least 1 project in the array
            const hasProjects = state.projects && state.projects.length > 0;

            // Directory: At least 1 client or 1 provider
            const hasDirectory = (state.clients && state.clients.length > 0) || (state.providers && state.providers.length > 0);

            const steps = [
                { id: 'identity', label: 'Identidad Corporativa', done: !!hasIdentity, icon: 'fa-building', link: 'settings.html' },
                { id: 'projects', label: 'Primer Proyecto', done: hasProjects, icon: 'fa-folder-plus', module: 'contabilidad' },
                { id: 'directory', label: 'Directorio Base', done: hasDirectory, icon: 'fa-address-book', module: 'directorio' }
            ];

            const doneCount = steps.filter(s => s.done).length;
            const percent = Math.round((doneCount / steps.length) * 100);

            return {
                steps: steps,
                percent: percent,
                isComplete: percent === 100
            };
        },

        // --- MIGRATION UTILITY ---
        migrateLocalToCloud: async function () {
            if (SAAS_CONFIG.mode !== 'supa') {
                alert("Debes estar en modo SUPA (?mode=supa) para migrar los datos.");
                return;
            }
            if (!confirm("Esto subirá tus datos locales de este navegador a Supabase. ¿Continuar?")) return;

            console.log("MIGRATION: Starting...");
            const localData = JSON.parse(localStorage.getItem(DB_KEY));
            if (!localData) {
                alert("No hay datos locales para migrar.");
                return;
            }

            const success = await StorageAdapter.save(localData);
            if (success) {
                alert("? Migración completa. Los datos locales ahora están en Supabase.");
                window.location.reload();
            } else {
                alert("? Error durante la migración. Revisa la consola.");
            }
        },

        addClient: function (client) {
            client.id = Date.now();
            state.clients.push(client);
            saveState();
            return client;
        },
        updateClient: function (id, clientData) {
            const index = state.clients.findIndex(c => c.id == id);
            if (index >= 0) {
                state.clients[index] = { ...state.clients[index], ...clientData };
                saveState();
                return true;
            }
            return false;
        },
        deleteClient: function (id) {
            state.clients = state.clients.filter(c => c.id != id);
            saveState();
            return true;
        },

        getProviders: function () { return state.providers; },
        addProvider: function (provider) {
            provider.id = Date.now();
            state.providers.push(provider);
            saveState();
            return provider;
        },
        updateProvider: function (id, providerData) {
            const index = state.providers.findIndex(p => p.id == id);
            if (index >= 0) {
                state.providers[index] = { ...state.providers[index], ...providerData };
                saveState();
                return true;
            }
            return false;
        },
        deleteProvider: function (id) {
            state.providers = state.providers.filter(p => p.id != id);
            saveState();
            return true;
        },

        getInventory: function () { return state.inventory; },
        upsertInventoryItem: function (item) {
            if (!state.inventory) state.inventory = [];
            const index = state.inventory.findIndex(i => i.sku === item.sku);
            if (index >= 0) {
                state.inventory[index] = { ...state.inventory[index], ...item };
            } else {
                state.inventory.push(item);
            }
            saveState();
            return true;
        },
        deleteInventoryItem: function (sku) {
            state.inventory = state.inventory.filter(i => i.sku !== sku);
            saveState();
            return true;
        },
        adjustStock: function (sku, amount) {
            const item = state.inventory.find(i => i.sku === sku);
            if (item) {
                item.stock = (item.stock || 0) + amount;
                saveState();
                return true;
            }
            return false;
        },
        getProjects: function () { return state.projects; },
        addProject: function (project) {
            if (!project.id) project.id = Date.now();
            if (!state.projects) state.projects = [];
            state.projects.push(project);
            saveState();
            return project;
        },
        updateProject: function (payload) {
            const { id, updates } = payload;
            const index = state.projects.findIndex(p => (p.id == id || p.ID == id));
            if (index >= 0) {
                state.projects[index] = { ...state.projects[index], ...updates };
                saveState();
                return true;
            }
            return false;
        },

        getTransactions: function () { return state.transactions || []; },
        addTransaction: function (transaction) {
            if (!transaction.id) transaction.id = 't-' + Date.now();
            if (!state.transactions) state.transactions = [];
            state.transactions.push(transaction);
            saveState();
            return true;
        },
        deleteTransaction: function (id) {
            state.transactions = state.transactions.filter(t => t.id != id && t.ID != id);
            saveState();
            return true;
        },

        getExpenseReports: function () { return state.expenseReports || []; },
        addExpenseReport: function (report) {
            report.id = 'ER-' + Date.now();
            if (!state.expenseReports) state.expenseReports = [];
            state.expenseReports.push(report);
            saveState();
            return true;
        },
        deleteProject: function (id) {
            state.projects = state.projects.filter(p => p.id != id);
            saveState();
            return true;
        },

        // --- LEGACY FETCH UTILITY (Internal) ---
        async _fetchLegacyData(scriptUrl) {
            try {
                const [pResp, tResp, lResp] = await Promise.all([
                    fetch(scriptUrl + '?action=get_projects', { redirect: 'follow' }),
                    fetch(scriptUrl + '?action=get_transactions', { redirect: 'follow' }),
                    fetch(scriptUrl + '?action=get_leads', { redirect: 'follow' })
                ]);

                const [pData, tData, lData] = await Promise.all([
                    pResp.json(),
                    tResp.json(),
                    lResp.json()
                ]);

                let results = { projects: [], transactions: [], leads: [] };

                if (pData.status === 'success' || pData.data) {
                    results.projects = pData.data || [];
                }

                if (tData.status === 'success' || tData.data) {
                    const rawTransactions = tData.data || [];
                    results.transactions = rawTransactions.filter(t => {
                        const amount = t.amount || t.monto || t.Monto;
                        const isFormulaError = typeof amount === 'string' &&
                            (amount.includes('#NUM!') || amount.includes('#REF!') ||
                                amount.includes('#DIV/0!') || amount.includes('#VALUE!'));
                        return !isFormulaError;
                    });
                }

                if (lData.status === 'success' || lData.data) {
                    results.leads = lData.data || [];
                }

                return results;
            } catch (e) {
                console.error("Legacy Fetch Error:", e);
                throw e;
            }
        },

        syncWithCloud: async function () {
            if (SAAS_CONFIG.mode === 'supa') {
                console.warn("ALPA CORE: legacy syncWithCloud blocked in SUPA mode.");
                return { status: 'error', message: 'Sync blocked in SUPA mode' };
            }

            const scriptUrl = SAAS_CONFIG.backendUrl;
            if (!scriptUrl) return { status: 'error', message: 'No SCRIPT_URL configured' };

            try {
                const data = await this._fetchLegacyData(scriptUrl);
                state.projects = data.projects;
                state.transactions = data.transactions;
                state.pendingLeads = data.leads;

                saveState();
                return { status: 'success', projects: state.projects.length, transactions: state.transactions.length };
            } catch (e) {
                return { status: 'error', message: e.message };
            }
        },

        importFromLegacyToSupabase: async function () {
            if (SAAS_CONFIG.mode !== 'supa') {
                alert("Debes estar en modo SUPA (?mode=supa) para usar este comando.");
                return;
            }

            if (!confirm("Esto traerá los datos del sistema antiguo (Google Sheets) y los subirá directamente a Supabase. ¿Continuar?")) return;

            const scriptUrl = SAAS_CONFIG.backendUrl;
            if (!scriptUrl) {
                alert("Error: No hay URL de backend antiguo configurada.");
                return;
            }

            console.log("MIGRATION: Pulling from Legacy...");
            try {
                const data = await this._fetchLegacyData(scriptUrl);

                console.log(`MIGRATION: Pulled ${data.projects.length} projects and ${data.transactions.length} transactions.`);

                // Update internal state
                state.projects = data.projects;
                state.transactions = data.transactions;
                state.pendingLeads = data.leads;

                console.log("MIGRATION: Pushing to Supabase...");
                const success = await StorageAdapter.save(state);

                if (success) {
                    alert("? Importación completa. Los datos del sistema antiguo ya están en Supabase.");
                    window.location.reload();
                } else {
                    alert("? Error al guardar en Supabase. Revisa la consola.");
                }
            } catch (e) {
                console.error("Migration Error:", e);
                alert("? Error durante la migración: " + e.message);
            }
        },

        getMainDashboardMetrics: function () {
            const transactions = state.transactions || [];
            const projects = state.projects || [];
            const activeTransactions = transactions.filter(t => t.status !== 'Anulada');

            // 1. Time-Based Context (Current vs Previous Month)
            const now = new Date();
            const currMonth = now.getFullYear() + '-' + (now.getMonth() + 1).toString().padStart(2, '0');
            const prevMonthDate = new Date(now.getFullYear(), now.getMonth() - 1, 1);
            let incomeActualAll = 0;
            let incomeActualCurr = 0;
            let incomeActualPrev = 0;
            let expenseActualAll = 0;
            let expenseActualCurr = 0;
            let expenseActualPrev = 0;
            const prevMonth = prevMonthDate.getFullYear() + '-' + (prevMonthDate.getMonth() + 1).toString().padStart(2, '0');
            let partnerDebt = 0;

            activeTransactions.forEach(t => {
                const amount = safeParse(t.amount || t.monto || t.Monto);
                const type = (t.type || t.Tipo || '').toLowerCase();
                const category = (t.category || t.Categoría || '').toLowerCase();
                const ds = (t.description || t.Descripción || '').toLowerCase();
                const source = t.source_of_funds || 'company';
                const status = t.reimbursement_status || 'not_applicable';

                // PRIORITY CLASSIFICATION:
                // 1. Explicit Type check
                let isInc = false;
                if (type === 'ingreso' || type === 'cobro') {
                    isInc = true;
                } else if (type === 'gasto' || type === 'pago') {
                    isInc = false;
                } else {
                    // 2. Keyword Fallback (only if type is not explicit)
                    isInc = category.includes('estado de pago') || ds.includes('ep ') || ds.includes('estado de pago');
                }

                const rawDate = t.date || t.Fecha || t.createdAt;
                const d = rawDate ? new Date(rawDate) : null;
                const mKey = d && !isNaN(d.getTime()) ? d.getFullYear() + '-' + (d.getMonth() + 1).toString().padStart(2, '0') : null;

                if (isInc) {
                    incomeActualAll += amount;
                    if (mKey === currMonth) incomeActualCurr += amount;
                    if (mKey === prevMonth) incomeActualPrev += amount;
                } else if (type === 'gasto' || type === 'pago') {
                    // ONLY count as company expense if source is 'company'
                    if (source === 'company') {
                        expenseActualAll += amount;
                        if (mKey === currMonth) expenseActualCurr += amount;
                        if (mKey === prevMonth) expenseActualPrev += amount;
                    } else if (status === 'pending') {
                        // If paid by socio and still pending, it is debt
                        partnerDebt += amount;
                    }
                }
            });


            // 2. Projections from Projects
            let incomeProjected = 0;
            let totalBudgets = 0;
            projects.forEach(p => {
                totalBudgets += parseFloat(p.budget || p.Presupuesto || 0);
                const statuses = p.paymentStatuses || p.EstadosPago || [];
                statuses.forEach(item => {
                    const qty = parseFloat(item.quantity || item.Cantidad || 0);
                    const price = parseFloat(item.price || item.Precio || 0);
                    const kmStart = parseFloat(item.kmStart || item.KmInicio || 0);
                    const kmEnd = parseFloat(item.kmEnd || item.KmFin || 0);
                    const totalML = Math.max(0, kmEnd - kmStart);
                    const itemValue = totalML > 0 ? totalML * qty * price : qty * price;
                    incomeProjected += (isNaN(itemValue) ? 0 : itemValue);
                });
            });

            // 3. FINAL KPI CALCULATION
            // We use Actual if available, otherwise Projected (for new companies)
            const income = incomeActualAll > 0 ? incomeActualAll : incomeProjected;
            const expense = expenseActualAll;

            // TAX LOGIC (IVA): Bruto -> 19%. Using 1.19 factor.
            const ivaDebit = income / 1.19 * 0.19; // IVA from sales
            const ivaCredit = expense / 1.19 * 0.19; // IVA from purchases
            const tax = Math.max(0, ivaDebit - ivaCredit);

            // SALDO vs UTILIDAD
            const balance = income - expense; // Cash Balance (Bruto)
            const netIncome = income / 1.19;
            const netExpense = expense / 1.19;
            const utility = netIncome - netExpense; // Financial Profit (Neto)

            // Trends
            const calculateTrend = (curr, prev) => {
                if (prev === 0) return curr > 0 ? 100 : 0;
                return Math.round(((curr - prev) / prev) * 100);
            };

            const incomeTrend = calculateTrend(incomeActualCurr, incomeActualPrev);
            const expenseTrend = calculateTrend(expenseActualCurr, expenseActualPrev);

            // 4. CHARTS DATA
            const monthlyCashflow = {};
            const categories = {};
            const costCenters = {};

            activeTransactions.forEach(t => {
                const amount = safeParse(t.amount || t.monto || t.Monto);
                const rawDate = t.date || t.Fecha || t.createdAt;
                const source = t.source_of_funds || 'company';

                if (rawDate) {
                    const d = new Date(rawDate);
                    if (!isNaN(d.getTime())) {
                        const monthKey = d.getFullYear() + '-' + (d.getMonth() + 1).toString().padStart(2, '0');
                        if (!monthlyCashflow[monthKey]) monthlyCashflow[monthKey] = { income: 0, expense: 0 };
                        const type = (t.type || t.Tipo || '').toLowerCase();
                        const cat = (t.category || t.Categoría || '').toLowerCase();
                        const ds = (t.description || t.Descripción || '').toLowerCase();

                        if (type === 'ingreso' || type === 'cobro' || cat.includes('estado de pago') || ds.includes('ep ')) {
                            monthlyCashflow[monthKey].income += amount;
                        } else if ((type === 'gasto' || type === 'pago') && source === 'company') {
                            // ONLY include company expenses in cashflow charts
                            monthlyCashflow[monthKey].expense += amount;
                        }
                    }
                }
                const catName = t.category || t.Categoría || 'Sin Categoría';
                categories[catName] = (categories[catName] || 0) + amount;
                const ccKey = t.costCenter || t.centroCostoId || t.CentroCostoID || t.ProyectoID || t.proyectoId || 'General';
                costCenters[ccKey] = (costCenters[ccKey] || 0) + amount;
            });

            const sortedMonths = Object.keys(monthlyCashflow).sort();
            const labels = sortedMonths.map(m => {
                const parts = m.split('-');
                const monthNames = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
                return monthNames[parseInt(parts[1]) - 1] + ' ' + parts[0];
            });

            return {
                cards: {
                    income: income,
                    expense: expense,
                    balance: balance, // General Cash Flow
                    utility: utility, // Net Profit
                    tax: tax,
                    partnerDebt: partnerDebt, // New KPI
                    projected: incomeProjected,
                    actual: incomeActualAll,
                    totalBudgets: totalBudgets,
                    incomeTrend: incomeTrend,
                    expenseTrend: expenseTrend,
                    isProjectedOnly: incomeActualAll === 0 && incomeProjected > 0
                },
                cashflow: { labels: labels, income: sortedMonths.map(m => monthlyCashflow[m].income), expense: sortedMonths.map(m => monthlyCashflow[m].expense) },
                costCenters: { labels: Object.keys(costCenters), data: Object.values(costCenters) },
                categories: { labels: Object.keys(categories), data: Object.values(categories) }
            };
        },

        getProjectFinancials: function (payload) {
            const { id } = payload;
            const project = state.projects.find(p => p.id == id || p.ID == id);
            if (!project) return { error: 'Project not found' };

            const budget = parseFloat(project.budget || project.Presupuesto || 0);
            const transactions = state.transactions || [];

            const linkedExpenses = transactions.filter(t => {
                const ccRaw = t.costCenter || t.centroCostoId || t.CentroCostoID || t.ProyectoID || t.proyectoId;
                if (!ccRaw) return false;
                const cc = String(ccRaw).trim().toLowerCase();
                const pId = String(project.id || project.ID || '').trim().toLowerCase();
                const pCode = String(project.code || project.Codigo || '').trim().toLowerCase();
                const pName = String(project.name || project.Nombre || '').trim().toLowerCase();
                let match = (cc === pId || cc === pCode || cc === pName);
                if (!match) {
                    if (cc === 'cc002' && (pId === 'alpa-001' || pName.includes('dibell'))) match = true;
                    if (cc === 'alpa-001' && (pId === 'cc002' || pName.includes('dibell'))) match = true;
                }
                const type = (t.type || t.Tipo || '').toLowerCase();
                return match && type === 'gasto' && t.status !== 'Anulada';
            });

            const linkedIncome = transactions.filter(t => {
                const ccRaw = t.costCenter || t.centroCostoId || t.CentroCostoID || t.ProyectoID || t.proyectoId;
                if (!ccRaw) return false;
                const cc = String(ccRaw).trim().toLowerCase();
                const pId = String(project.id || project.ID || '').trim().toLowerCase();
                const pCode = String(project.code || project.Codigo || '').trim().toLowerCase();
                const pName = String(project.name || project.Nombre || '').trim().toLowerCase();
                let match = (cc === pId || cc === pCode || cc === pName);
                if (!match) {
                    if (cc === 'cc002' && (pId === 'alpa-001' || pName.includes('dibell'))) match = true;
                    if (cc === 'alpa-001' && (pId === 'cc002' || pName.includes('dibell'))) match = true;
                }
                const type = (t.type || t.Tipo || '').toLowerCase();
                const cat = (t.category || t.Categoría || '').toLowerCase();
                const desc = (t.description || t.Descripción || '').toLowerCase();
                const isInc = type === 'ingreso' || type === 'cobro' || cat.includes('estado de pago') || desc.includes('ep ');
                return match && isInc && t.status !== 'Anulada';
            });

            const totalSpent = linkedExpenses.reduce((sum, t) => sum + safeParse(t.amount || t.monto || t.Monto), 0);
            const totalInvoiced = linkedIncome.reduce((sum, t) => sum + safeParse(t.amount || t.monto || t.Monto), 0);

            const pStatuses = project.paymentStatuses || project.EstadosPago || [];
            const declaredVal = pStatuses.reduce((sum, item) => {
                const k1 = parseFloat(item.kmStart || item.KmInicio || 0);
                const k2 = parseFloat(item.kmEnd || item.KmFin || 0);
                const ml = Math.max(0, k2 - k1);
                const pr = parseFloat(item.price || item.Precio || 0);
                const q = parseFloat(item.quantity || item.Cantidad || 1);
                return sum + (ml > 0 ? ml * q * pr : q * pr);
            }, 0);

            const categories = {};
            [...linkedExpenses, ...linkedIncome].forEach(t => {
                const cat = t.category || t.Categoría || 'Sin Categoría';
                const val = parseFloat(t.amount || t.monto || t.Monto || 0);
                categories[cat] = (categories[cat] || 0) + val;
            });

            const metrics = {
                budget: budget,
                totalSpent: totalSpent,
                totalInvoiced: totalInvoiced,
                totalDeclaredValue: declaredVal,
                margin: budget - totalSpent,
                progress: (budget > 0 ? (totalSpent / budget) * 100 : 0) || 0,
                efficiency: (totalSpent > 0 ? (declaredVal / totalSpent) * 100 : 100) || 0
            };

            console.log("ALPA CORE: Returning financials for " + id, metrics);

            return {
                project: project,
                metrics: metrics,
                history: [...linkedExpenses, ...linkedIncome].sort((a, b) => new Date(b.date || b.Fecha || 0) - new Date(a.date || a.Fecha || 0)),
                charts: { categories: { labels: Object.keys(categories), data: Object.values(categories) } }
            };
        },

        getDashboardMetrics: function () {
            return {
                totalClients: state.clients.length,
                totalProjects: state.projects.length,
                totalInventoryItems: state.inventory.length,
                totalPendingLeads: state.pendingLeads.length
            };
        },

        getPendingLeads: function () { return state.pendingLeads; },
        registerWebLead: function (leadData) {
            const exists = state.pendingLeads.find(l => l.email === leadData.email);
            if (exists) return false;
            state.pendingLeads.push({ ...leadData, id: Date.now(), status: 'Nuevo', source: 'Manual Entry', createdAt: new Date().toISOString() });
            saveState();
            return true;
        },
        deleteLead: function (leadId) {
            const lead = state.pendingLeads.find(l => l.id == leadId);
            if (lead && lead.email) state.deletedLeadIds.push(lead.email);
            state.pendingLeads = state.pendingLeads.filter(l => l.id != leadId);
            saveState();
            return true;
        },
        convertLeadToClient: function (leadId) {
            const lead = state.pendingLeads.find(l => l.id == leadId);
            if (!lead) return false;
            const newClient = { id: Date.now(), name: lead.name || lead.Nombre, rut: "Sin RUT", contact: lead.name, email: lead.email, phone: lead.phone || lead.Telefono, origin: "Web Lead" };
            state.clients.push(newClient);
            state.pendingLeads = state.pendingLeads.filter(l => l.id != leadId);
            saveState();
            return newClient;
        },

        cleanupClients: function () {
            console.log("Cleaning up duplicate clients...");
            const seen = new Set();
            const unique = [];
            let duplicates = 0;

            // Keep the first instance of each name (case-insensitive)
            state.clients.forEach(c => {
                const key = (c.name || '').trim().toUpperCase();
                if (!seen.has(key)) {
                    seen.add(key);
                    unique.push(c);
                } else {
                    duplicates++;
                }
            });

            if (duplicates > 0) {
                state.clients = unique;
                saveState();
                console.log(`Removed ${duplicates} duplicate clients.`);
                return true;
            } else {
                console.log("No duplicates found.");
                return false;
            }
        },

        convertQuoteToProject: function (quoteData, user) {
            const project = {
                id: 'PROJ-' + Date.now(),
                name: quoteData.projectName,
                client: quoteData.clientName,
                budget: quoteData.total,
                status: 'Pendiente',
                createdBy: (user && user.name) ? user.name : 'Sistema',
                createdAt: new Date().toISOString()
            };
            if (!state.projects) state.projects = [];
            state.projects.push(project);

            if (!state.pendingProjects) state.pendingProjects = [];
            state.pendingProjects.push(project);

            saveState();
            return project;
        },

        registerPurchaseOrder: function (poData, user) {
            const expense = {
                id: 'EXP-' + Date.now(),
                type: 'Gasto',
                category: 'Orden de Compra',
                amount: poData.total,
                description: `OC: ${poData.number} - ${poData.provider}`,
                status: 'Pendiente',
                createdBy: (user && user.name) ? user.name : 'Sistema',
                createdAt: new Date().toISOString()
            };
            if (!state.transactions) state.transactions = [];
            state.transactions.push(expense);

            if (!state.pendingExpenses) state.pendingExpenses = [];
            state.pendingExpenses.push(expense);

            saveState();
            return expense;
        },

        syncWebLeads: async function (payload) {
            // Priority: Supabase (Multi-tenant)
            if (SAAS_CONFIG.mode === 'supa' && AlpaCore.supabase) {
                console.log("ALPA CORE: Fetching leads from Supabase...");
                try {
                    const orgId = await StorageAdapter.getOrgId();
                    if (!orgId) throw new Error("No organization ID found in session.");

                    const { data, error } = await AlpaCore.supabase
                        .from('leads')
                        .select('*')
                        .eq('organization_id', orgId)
                        .order('created_at', { ascending: false });

                    if (error) throw error;

                    // Match state.pendingLeads with DB
                    state.pendingLeads = data.map(l => ({
                        id: l.id,
                        clientName: l.name,
                        email: l.email,
                        phone: l.phone,
                        project: l.message || l.project_description,
                        source: l.origin,
                        status: l.status,
                        createdAt: l.created_at,
                        assignedTo: l.assigned_to,
                        notes: l.notes || []
                    }));
                    saveState();
                    return { status: 'success', imported: data.length };
                } catch (e) {
                    console.error("Supabase Leads Sync Error:", e);
                    return { status: 'error', message: e.message };
                }
            }

            // Fallback: Google Apps Script
            const scriptUrl = (payload && typeof payload === 'object') ? payload.url : payload;
            if (!scriptUrl) return { status: 'error', message: 'No URL' };
            try {
                const resp = await fetch(scriptUrl + '?action=getWebLeads&_t=' + Date.now());
                const data = await resp.json();
                let leads = Array.isArray(data) ? data : (data.data || data.leads || []);
                let newCount = 0;
                leads.forEach(l => {
                    const lId = l.id || l.email || Date.now();
                    const email = l.email || l.Email || 'sin-email@alpaconstruccioneingenieria.cl';
                    if (!state.pendingLeads.find(x => x.id === lId || x.email === email)) {
                        state.pendingLeads.push({ ...l, id: lId, email: email, status: l.status || 'Nuevo', createdAt: l.createdAt || new Date().toISOString() });
                        newCount++;
                    }
                });
                if (newCount > 0) saveState();
                return { status: 'success', imported: newCount };
            } catch (e) { return { status: 'error', message: e.message }; }
        },

        addLeadNote: async function (payload) {
            const { id, text, user } = payload;
            const lead = state.pendingLeads.find(l => l.id === id);
            if (!lead) return false;

            const newNote = {
                date: new Date().toISOString(),
                text: text,
                user: user || 'Sistema'
            };

            if (!lead.notes) lead.notes = [];
            lead.notes.push(newNote);

            if (SAAS_CONFIG.mode === 'supa' && AlpaCore.supabase) {
                const { error } = await AlpaCore.supabase
                    .from('leads')
                    .update({ notes: lead.notes })
                    .eq('id', id);
                if (error) {
                    console.error("Error updating lead notes in Supabase:", error);
                    return false;
                }
            }
            saveState();
            return true;
        },

        assignLead: async function (payload) {
            const { id, user } = payload;
            const lead = state.pendingLeads.find(l => l.id === id);
            if (!lead) return false;

            lead.assignedTo = user;

            if (SAAS_CONFIG.mode === 'supa' && AlpaCore.supabase) {
                const { error } = await AlpaCore.supabase
                    .from('leads')
                    .update({ assigned_to: user })
                    .eq('id', id);
                if (error) {
                    console.error("Error assigning lead in Supabase:", error);
                    return false;
                }
            }
            saveState();
            return true;
        },

        updateLeadStatus: async function (payload) {
            const { id, status } = payload;
            const lead = state.pendingLeads.find(l => l.id === id);
            if (!lead) return false;

            lead.status = status;

            if (SAAS_CONFIG.mode === 'supa' && AlpaCore.supabase) {
                const { error } = await AlpaCore.supabase
                    .from('leads')
                    .update({ status: status })
                    .eq('id', id);
                if (error) {
                    console.error("Error updating lead status in Supabase:", error);
                    return false;
                }
            }
            saveState();
            return true;
        },

        deleteLead: async function (payload) {
            const { id } = payload;
            const idx = state.pendingLeads.findIndex(l => l.id === id);
            if (idx === -1) return false;

            if (SAAS_CONFIG.mode === 'supa' && AlpaCore.supabase) {
                const { error } = await AlpaCore.supabase
                    .from('leads')
                    .delete()
                    .eq('id', id);
                if (error) {
                    console.error("Error deleting lead in Supabase:", error);
                    return false;
                }
            }
            state.pendingLeads.splice(idx, 1);
            saveState();
            return true;
        },

        checkDatabaseIntegrity: function () {
            const res = { projectsCount: state.projects.length, transactionsCount: state.transactions.length, errors: [], warnings: [], orphans: [], duplicates: [], stats: { badFormulas: 0, missingAmount: 0, mismatchedCC: 0, potentialDuplicates: 0 } };
            const pIds = new Set(state.projects.map(p => (p.id || p.ID || '').toString()).filter(x => x));
            const pCodes = new Set(state.projects.map(p => (p.code || p.Codigo || '').toLowerCase()));
            const pNames = new Set(state.projects.map(p => (p.name || p.Nombre || '').toLowerCase()));

            state.transactions.forEach(t => {
                const id = t.id || t.ID;
                const amt = t.amount || t.monto || t.Monto;
                const cc = (t.costCenter || t.centroCostoId || t.CentroCostoID || t.ProyectoID || t.proyectoId || '').toString();
                const desc = t.description || t.Descripción || 'Sin descripción';
                if (typeof amt === 'string' && (amt.includes('#NUM!') || amt.includes('#REF!') || amt.includes('#DIV/0!') || amt.includes('#VALUE!'))) {
                    res.stats.badFormulas++;
                    res.errors.push({ id: id, type: 'Formula Error', value: amt, description: desc });
                }
                if (amt === null || amt === undefined || amt === '') {
                    res.stats.missingAmount++;
                    res.warnings.push({ id: id, type: 'Missing Amount', description: desc });
                }
                if (cc && cc !== 'General') {
                    const match = pIds.has(cc) || pCodes.has(cc.toLowerCase()) || pNames.has(cc.toLowerCase()) || cc.toLowerCase() === 'cc002' || cc.toLowerCase() === 'alpa-001';
                    if (!match) {
                        res.orphans.push({ id: id, cc: cc, description: desc });
                        res.stats.mismatchedCC++;
                    }
                }
            });

            const seen = new Map();
            state.transactions.forEach(t => {
                if (t.status === 'Anulada') return;
                const amt = safeParse(t.amount || t.monto || t.Monto);
                const date = (t.date || t.Fecha || '').toString().substring(0, 10);
                const desc = (t.description || t.Descripción || '').toLowerCase().trim();
                const cc = (t.costCenter || t.centroCostoId || t.CentroCostoID || t.ProyectoID || t.proyectoId || '').toString();
                const key = date + '|' + amt + '|' + desc + '|' + cc;
                if (seen.has(key)) {
                    res.stats.potentialDuplicates++;
                    res.duplicates.push({ id: t.id || t.ID, duplicateOf: seen.get(key), amount: amt, date: date });
                } else { seen.set(key, t.id || t.ID); }
            });

            this.syncProjectClients();
            return res;
        },

        syncProjectClients: function () {
            let added = 0;
            const ruts = new Set(state.clients.map(c => (c.rut || '').trim().toLowerCase()));
            const names = new Set(state.clients.map(c => (c.name || '').trim().toLowerCase()));
            state.projects.forEach(p => {
                const cli = (p.client || p.Cliente || '').trim();
                const rut = (p.clientRut || p.RutCliente || '').trim();
                if (cli && cli.length > 2) {
                    if (!names.has(cli.toLowerCase()) && (!rut || !ruts.has(rut.toLowerCase()))) {
                        state.clients.push({ id: Date.now() + Math.random(), name: cli, rut: rut || 'Sin Rut', contact: p.responsible || 'Contacto', phone: '', email: '', origin: 'Auto-Sync' });
                        names.add(cli.toLowerCase());
                        added++;
                    }
                }
            });
            if (added > 0) saveState();
        }
    };

    // --- INITIALIZATION ---
    let initPromise = null;
    async function initState(force = false) {
        if (initPromise && !force) return initPromise;

        initPromise = (async () => {
            const loadedState = await StorageAdapter.load();
            if (loadedState) {
                state = loadedState;
                // Migrations / Safety Checks
                if (!state.deletedLeadIds) state.deletedLeadIds = [];
                if (!state.pendingLeads) state.pendingLeads = [];
                if (!state.inventory) state.inventory = defaultState.inventory;
                if (!state.projects) state.projects = defaultState.projects;
                if (!state.transactions) state.transactions = defaultState.transactions || [];
                if (!state.expenseReports) state.expenseReports = defaultState.expenseReports || [];
                if (!state.pendingProjects) state.pendingProjects = [];
                if (!state.pendingExpenses) state.pendingExpenses = [];

                CoreAPI.state = state;
                console.log("ALPA CORE: State Refreshed ?");
            } else {
                saveState();
            }
            return true;
        })();

        return initPromise;
    }

    // --- REALTIME SUBSCRIPTION (Leads) ---
    async function subscribeToLeads() {
        if (!supabase || SAAS_CONFIG.mode !== 'supa') return;

        const orgId = await StorageAdapter.getOrgId();
        if (!orgId) return;

        console.log(`ALPA CORE: Subscribing to Leads for Org: ${orgId}`);

        supabase
            .channel('public:leads')
            .on('postgres_changes', {
                event: 'INSERT',
                schema: 'public',
                table: 'leads',
                filter: `organization_id=eq.${orgId}`
            }, payload => {
                console.log('ALPA CORE: New Lead received via Realtime!', payload);
                // Dispatch event to Hub Shell (index.html)
                window.postMessage({
                    type: 'ALPA_NEW_LEAD',
                    name: payload.new.name,
                    email: payload.new.email
                }, "*");

                // Refresh state locally
                initState(true);
            })
            .subscribe();
    }

    // Trigger async init
    initState().then(() => {
        subscribeToLeads();
    });

    // --- CROSS-FRAME LISTENER (Bridge Support) ---
    window.addEventListener('message', async (event) => {
        if (!event.data || !event.data.action || !event.data.requestId) return;
        const { action, payload, requestId, force } = event.data;

        // Ensure Core is ready before processing messages
        await initState(force);

        // Execute request if method exists
        if (CoreAPI[action]) {
            try {
                const result = await CoreAPI[action](payload);
                event.source.postMessage({
                    type: 'ALPA_RESPONSE',
                    requestId: requestId,
                    result: result
                }, "*");
            } catch (e) {
                console.error("Core Bridge Error for " + action, e);
                event.source.postMessage({
                    type: 'ALPA_RESPONSE',
                    requestId: requestId,
                    result: { error: e.message }
                }, "*");
            }
        } else {
            console.warn("Core Bridge: Unknown action " + action);
            event.source.postMessage({
                type: 'ALPA_RESPONSE',
                requestId: requestId,
                result: { error: 'Unknown Action: ' + action }
            }, "*");
        }
    });

    CoreAPI.onReady = () => initState();
    CoreAPI.load = (force = false) => initState(force);


    return CoreAPI;
})();

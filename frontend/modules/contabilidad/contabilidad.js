            // CONFIGURATION
            let USER_SESSION_KEY = 'hub_app_session_v1';
            let currentProjectId = null; // Bug 6 fix: explicit global declaration

            try {
                if (window.SAAS_CONFIG) {
                    SCRIPT_URL = window.SAAS_CONFIG.backendUrl || '';
                    USER_SESSION_KEY = window.SAAS_CONFIG.sessionKey || 'hub_app_session_v1';
                } else if (parent && parent.SAAS_CONFIG) {
                    SCRIPT_URL = parent.SAAS_CONFIG.backendUrl || '';
                    USER_SESSION_KEY = parent.SAAS_CONFIG.sessionKey || 'hub_app_session_v1';
                }
            } catch (e) {
                console.warn("[Contabilidad] Hub sync fallback active.");
            }

            document.addEventListener('DOMContentLoaded', async () => {
                // Attempt to sync URL from Hub Bridge for extra resilience
                try {
                    const config = await AlpaHub.getConfig();
                    if (config && config.backendUrl) SCRIPT_URL = config.backendUrl;
                    if (config && config.sessionKey) USER_SESSION_KEY = config.sessionKey;
                } catch (e) { }

                checkSession();
                // Check for new projects on load
                setTimeout(checkPendingProjects, 1000);
            });

            // --- INTEGRATION: PENDING PROJECTS ---
            async function checkPendingProjects() {
                try {
                    const projects = await AlpaHub.getProjects() || [];
                    const pending = projects.filter(p => p.status === 'Pendiente');
                    const alertBox = document.getElementById('pending-projects-alert');
                    const countSpan = document.getElementById('pending-count');

                    if (pending && pending.length > 0) {
                        alertBox.classList.remove('hidden');
                        countSpan.innerText = pending.length;
                    } else {
                        alertBox.classList.add('hidden');
                    }
                } catch (e) {
                    console.warn("Could not check pending projects", e);
                }
            }

            // --- AGENTIC INTELLIGENCE ENGINE (Don Alpa) ---
            let currentCycleId = null;
            let pollingInterval = null;

            async function runMasterAnalysis() {
                const btn = document.getElementById('btn-run-analysis');
                const statusBar = document.getElementById('agent-status-bar');
                const statusText = document.getElementById('agent-status-text');
                const cycleIdEl = document.getElementById('agent-cycle-id');
                const placeholder = document.getElementById('signals-placeholder');
                const container = document.getElementById('signals-container');

                try {
                    btn.disabled = true;
                    btn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> ANALIZANDO...';
                    statusBar.classList.remove('hidden');
                    statusText.innerText = "Don Alpa está despertando sus agentes...";
                    
                    if (placeholder) placeholder.classList.add('hidden');
                    container.innerHTML = '<!-- Signals will appear here -->';

                    const companyId = localStorage.getItem('alpa_current_company_id') || 'alpa-spa';
                    const sessionJSON = localStorage.getItem(USER_SESSION_KEY) || (parent && parent.localStorage.getItem(USER_SESSION_KEY));
                    const session = JSON.parse(sessionJSON);

                    const response = await fetch(`${SCRIPT_URL}/api/v1/agents/cycle`, {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${session.token}`
                        },
                        body: JSON.stringify({
                            company_id: companyId,
                            instruccion: "Analiza el estado financiero actual: revisa órdenes de compra recientes, estados de pago pendientes, flujo de caja proyectado a 90 días, y detecta anomalías o riesgos de liquidez. Prioriza alertas de alto impacto.",
                            mode: "fast"
                        })
                    });

                    const data = await response.json();
                    if (data.status === 'started') {
                        currentCycleId = data.cycle_id;
                        cycleIdEl.innerText = `ID: ${currentCycleId.substring(0,8)}...`;
                        startPolling(currentCycleId);
                    } else {
                        throw new Error(data.detail || "Error al iniciar ciclo");
                    }
                } catch (e) {
                    console.error("Agent Error:", e);
                    AlpaHub.showNotification("Error de IA: " + e.message, 'error');
                    resetAnalysisUI();
                }
            }

            function startPolling(cycleId) {
                if (pollingInterval) clearInterval(pollingInterval);
                
                pollingInterval = setInterval(async () => {
                    try {
                        const sessionJSON = localStorage.getItem(USER_SESSION_KEY) || (parent && parent.localStorage.getItem(USER_SESSION_KEY));
                        const session = JSON.parse(sessionJSON);

                        const response = await fetch(`${SCRIPT_URL}/api/v1/agents/cycle/${cycleId}/status`, {
                            headers: { 
                                'Authorization': `Bearer ${session.token}`
                            }
                        });
                        const status = await response.json();
                        
                        document.getElementById('agent-status-text').innerText = `Procesando: ${status.status}...`;

                        if (status.status === 'completed' || status.status === 'finished') {
                            stopPolling();
                            loadSignals(cycleId);
                            loadDecisions(cycleId);
                            resetAnalysisUI(true);
                        } else if (status.status === 'failed') {
                            stopPolling();
                            AlpaHub.showNotification("El análisis falló", "error");
                            resetAnalysisUI();
                        }
                    } catch (e) {
                        console.error("Polling Error:", e);
                        stopPolling();
                    }
                }, 3000);
            }

            function stopPolling() {
                if (pollingInterval) {
                    clearInterval(pollingInterval);
                    pollingInterval = null;
                }
            }

            function resetAnalysisUI(success = false) {
                const btn = document.getElementById('btn-run-analysis');
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-bolt"></i> EJECUTAR ANÁLISIS MAESTRO';
                
                if (success) {
                    document.getElementById('agent-status-text').innerText = "Análisis completado con éxito.";
                    setTimeout(() => {
                        const bar = document.getElementById('agent-status-bar');
                        if (bar) bar.classList.add('hidden');
                    }, 5000);
                } else {
                    const bar = document.getElementById('agent-status-bar');
                    if (bar) bar.classList.add('hidden');
                }
            }

            async function loadSignals(cycleId) {
                try {
                    const sessionJSON = localStorage.getItem(USER_SESSION_KEY) || (parent && parent.localStorage.getItem(USER_SESSION_KEY));
                    const session = JSON.parse(sessionJSON);

                    const response = await fetch(`${SCRIPT_URL}/api/v1/agents/signals?cycle_id=${cycleId}`, {
                        headers: { 
                            'Authorization': `Bearer ${session.token}`
                        }
                    });
                    const data = await response.json();
                    renderSignals(data.signals || []);
                } catch (e) {
                    console.error("Error loading signals:", e);
                }
            }

            function renderSignals(signals) {
                const container = document.getElementById('signals-container');
                container.innerHTML = '';

                if (!signals || signals.length === 0) {
                    container.innerHTML = `
                        <div class="col-span-full py-4 text-center text-gray-400 italic">
                            No se detectaron riesgos ni anomalías críticas en este ciclo.
                        </div>
                    `;
                    return;
                }

                signals.forEach(sig => {
                    const card = document.createElement('div');
                    card.className = "border rounded-xl p-4 shadow-sm hover:shadow-md transition-all border-l-4";
                    card.style.backgroundColor = "var(--surface)";
                    card.style.borderColor = "var(--border)";
                    
                    // Style based on type
                    let borderColor = "border-l-blue-500";
                    let icon = "fa-info-circle";
                    let typeLabel = "INFO";
                    
                    if (sig.type === 'anomaly') {
                        borderColor = "border-l-rose-500";
                        icon = "fa-triangle-exclamation";
                        typeLabel = "ANOMALÍA";
                    } else if (sig.type === 'opportunity') {
                        borderColor = "border-l-emerald-500";
                        icon = "fa-lightbulb";
                        typeLabel = "AHORRO";
                    } else if (sig.type === 'risk') {
                        borderColor = "border-l-orange-500";
                        icon = "fa-shield-virus";
                        typeLabel = "RIESGO";
                    }

                    card.classList.add(borderColor);

                    card.innerHTML = `
                        <div class="flex justify-between items-start mb-2">
                            <span class="text-[9px] font-bold px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 uppercase tracking-tighter">${typeLabel}</span>
                            <span class="text-[9px] text-gray-400 font-mono">${new Date(sig.created_at).toLocaleTimeString()}</span>
                        </div>
                        <h4 class="font-bold text-sm text-gray-800 mb-1 flex items-center gap-2">
                            <i class="fas ${icon} opacity-50"></i> ${sig.title || 'Señal Detectada'}
                        </h4>
                        <p class="text-xs text-gray-600 leading-relaxed mb-4">${sig.content}</p>
                        
                        <div class="flex items-center gap-2 pt-3 border-t border-gray-50">
                            <button onclick="submitFeedback('${sig.id}', true)" 
                                class="flex-1 py-1.5 bg-green-50 text-green-700 rounded text-[10px] font-bold hover:bg-green-600 hover:text-white transition-all">
                                <i class="fas fa-check mr-1"></i> ÚTIL
                            </button>
                            <button onclick="submitFeedback('${sig.id}', false)" 
                                class="flex-1 py-1.5 bg-gray-50 text-gray-600 rounded text-[10px] font-bold hover:bg-gray-200 transition-all">
                                <i class="fas fa-xmark mr-1"></i> IGNORAR
                            </button>
                        </div>
                    `;
                    container.appendChild(card);
                });
            }

            // ── AgenteFinanciero v2.0 — Decision Panel ────────────────────
            async function loadDecisions(cycleId) {
                try {
                    const sessionJSON = localStorage.getItem(USER_SESSION_KEY) || (parent && parent.localStorage.getItem(USER_SESSION_KEY));
                    const session = JSON.parse(sessionJSON);

                    const response = await fetch(`${SCRIPT_URL}/api/v1/agents/cycle/${cycleId}/decisions`, {
                        headers: { 'Authorization': `Bearer ${session.token}` }
                    });
                    const data = await response.json();
                    renderDecision(data.decisions || []);
                } catch (e) {
                    console.error("Error loading decisions:", e);
                }
            }

            function renderDecision(decisions) {
                if (!decisions || decisions.length === 0) return;

                // Use the most recent/primary decision (first in list)
                const dec = decisions[0];
                const meta = dec.metadata || {};

                const panel = document.getElementById('agent-decision-panel');
                if (panel) panel.classList.remove('hidden');

                // ── Semáforo badge ──────────────────────────────────────
                const semaforo = dec.semaforo || meta.semaforo || 'AMARILLO';
                const semaforoEl = document.getElementById('agent-semaforo');
                if (semaforoEl) {
                    const colorMap = {
                        'VERDE':   { bg: 'bg-green-500',  icon: 'fa-circle-check',        label: '● VERDE'   },
                        'AMARILLO':{ bg: 'bg-amber-400',  icon: 'fa-triangle-exclamation', label: '● AMARILLO'},
                        'ROJO':    { bg: 'bg-red-500',    icon: 'fa-circle-xmark',         label: '● ROJO'    }
                    };
                    const s = colorMap[semaforo] || colorMap['AMARILLO'];
                    semaforoEl.className = `flex items-center gap-1.5 text-xs font-bold px-3 py-1 rounded-full text-white ${s.bg}`;
                    semaforoEl.innerHTML = `<i class="fas ${s.icon}"></i> ${s.label}`;
                    semaforoEl.classList.remove('hidden');
                    semaforoEl.style.display = 'flex';
                }

                // ── Health badge ────────────────────────────────────────
                const healthEl = document.getElementById('dec-health');
                if (healthEl) {
                    const healthColorMap = {
                        'VERDE':   'border-green-200 bg-green-50 text-green-700',
                        'AMARILLO':'border-amber-200 bg-amber-50 text-amber-700',
                        'ROJO':    'border-red-200 bg-red-50 text-red-700'
                    };
                    const hc = healthColorMap[semaforo] || healthColorMap['AMARILLO'];
                    healthEl.className = `flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold border ${hc}`;
                    healthEl.innerHTML = `<i class="fas fa-heartbeat"></i> Estado: ${semaforo}`;
                }

                // ── Confidence badge ────────────────────────────────────
                const confidence = dec.confidence_level || meta.confidence_level || '—';
                const confEl = document.getElementById('dec-confidence');
                if (confEl) {
                    const confColorMap = {
                        'HIGH':   'border-green-200 bg-green-50 text-green-700',
                        'MEDIUM': 'border-amber-200 bg-amber-50 text-amber-700',
                        'LOW':    'border-red-200 bg-red-50 text-red-700'
                    };
                    const cc = confColorMap[confidence] || 'border-gray-200 bg-gray-50 text-gray-600';
                    confEl.className = `flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold border ${cc}`;
                    confEl.innerHTML = `<i class="fas fa-gauge-high"></i> Confianza: ${confidence}`;
                }

                // ── Tools called badge ──────────────────────────────────
                const toolsLog = dec.tool_calls_log || meta.tool_calls_log || [];
                const toolsEl = document.getElementById('dec-tools');
                if (toolsEl) {
                    const toolCount = Array.isArray(toolsLog) ? toolsLog.length : Object.keys(toolsLog).length;
                    toolsEl.innerHTML = `<i class="fas fa-wrench"></i> ${toolCount} herramientas ejecutadas`;
                }

                // ── Hallazgos ───────────────────────────────────────────
                const hallazgos = dec.hallazgos || meta.hallazgos || [];
                const hallazgosEl = document.getElementById('dec-hallazgos');
                const hallazgosList = document.getElementById('dec-hallazgos-list');
                if (hallazgos.length > 0 && hallazgosEl && hallazgosList) {
                    hallazgosEl.classList.remove('hidden');
                    hallazgosList.innerHTML = hallazgos.map(h => `<li class="flex items-start gap-1"><i class="fas fa-circle text-blue-400 text-[6px] mt-1.5 shrink-0"></i><span>${h}</span></li>`).join('');
                }

                // ── Alertas ─────────────────────────────────────────────
                const alertas = dec.alertas || meta.alertas || [];
                const alertasEl = document.getElementById('dec-alertas');
                const alertasList = document.getElementById('dec-alertas-list');
                if (alertas.length > 0 && alertasEl && alertasList) {
                    alertasEl.classList.remove('hidden');
                    alertasList.innerHTML = alertas.map(a => `<li class="flex items-start gap-1"><i class="fas fa-circle text-amber-400 text-[6px] mt-1.5 shrink-0"></i><span>${a}</span></li>`).join('');
                }

                // ── Recomendaciones ─────────────────────────────────────
                const recs = dec.recomendaciones || meta.recomendaciones || [];
                const recsEl = document.getElementById('dec-recomendaciones');
                const recsList = document.getElementById('dec-recomendaciones-list');
                if (recs.length > 0 && recsEl && recsList) {
                    recsEl.classList.remove('hidden');
                    recsList.innerHTML = recs.map(r => `<li class="flex items-start gap-1"><i class="fas fa-circle text-emerald-400 text-[6px] mt-1.5 shrink-0"></i><span>${r}</span></li>`).join('');
                }

                // ── Null fields warning ─────────────────────────────────
                const nullFields = dec.null_fields || meta.null_fields || [];
                const nullEl = document.getElementById('dec-null-fields');
                const nullText = document.getElementById('dec-null-fields-text');
                if (nullFields.length > 0 && nullEl && nullText) {
                    nullEl.classList.remove('hidden');
                    nullText.textContent = `Datos faltantes detectados: ${nullFields.join(', ')}`;
                }

                // ── Data lineage ────────────────────────────────────────
                const sources = dec.data_sources || meta.data_sources || [];
                const lineageEl = document.getElementById('dec-lineage');
                const lineageDetail = document.getElementById('lineage-detail');
                if (sources.length > 0 && lineageEl && lineageDetail) {
                    lineageEl.classList.remove('hidden');
                    lineageDetail.innerHTML = sources.map(s => `
                        <div class="rounded-lg border border-gray-200 bg-gray-50 p-2 text-[10px] font-mono text-gray-600">
                            <div class="font-bold text-gray-700 truncate">${s.tool || s.source || '—'}</div>
                            <div class="text-[9px] text-gray-400 mt-0.5">${s.rows !== undefined ? s.rows + ' filas' : ''} ${s.timestamp ? '· ' + new Date(s.timestamp).toLocaleTimeString() : ''}</div>
                        </div>
                    `).join('');
                }
            }

            function toggleLineage() {
                const detail = document.getElementById('lineage-detail');
                const chevron = document.getElementById('lineage-chevron');
                if (!detail) return;
                const isHidden = detail.classList.contains('hidden');
                detail.classList.toggle('hidden', !isHidden);
                if (chevron) {
                    chevron.classList.toggle('fa-chevron-right', !isHidden);
                    chevron.classList.toggle('fa-chevron-down', isHidden);
                }
            }

            async function submitSignalFeedback(signalId, approved) {
                try {
                    const sessionJSON = localStorage.getItem(USER_SESSION_KEY) || (parent && parent.localStorage.getItem(USER_SESSION_KEY));
                    const session = JSON.parse(sessionJSON);

                    const response = await fetch(`${SCRIPT_URL}/api/v1/agents/feedback`, {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${session.token}`
                        },
                        body: JSON.stringify({
                            cycle_id: currentCycleId,
                            agent_id: "financial-agent", 
                            approved: approved,
                            comments: approved ? "Aceptado desde Dashboard Contabilidad" : "Rechazado desde Dashboard Contabilidad"
                        })
                    });

                    const res = await response.json();
                    if (res.status === 'success' || res.status === 'ok') {
                        AlpaHub.showNotification("Feedback registrado. Don Alpa sigue aprendiendo.", "success");
                        // Clean up the card
                        loadSignals(currentCycleId);
                    }
                } catch (e) {
                    console.error("Feedback Error:", e);
                }
            }

            // Expose for UI
            window.runMasterAnalysis = runMasterAnalysis;
            window.submitFeedback = submitSignalFeedback;
            window.toggleLineage = toggleLineage;
            window.loadDecisions = loadDecisions;

            async function importPendingProjects() {
                try {
                    const projects = await AlpaHub.getProjects() || [];
                    const pending = projects.filter(p => p.status === 'Pendiente');

                    if (pending.length === 0) {
                        AlpaHub.showNotification('No hay proyectos pendientes por activar.', 'info');
                        return;
                    }

                    let count = 0;
                    for (const p of pending) {
                        await AlpaHub.execute('updateProject', { id: p.id, updates: { status: 'En Ejecucin' } });
                        count++;
                    }

                    checkPendingProjects();
                    loadProjects();
                    AlpaHub.showNotification(`${count} Proyectos activados correctamente.`, 'success');

                } catch (e) { console.error("Import Error", e); }
            }



            function createProjectPO() {
                if (!currentProjectId) return;
                // Fetch fresh project data to ensure we have details
                AlpaHub.getProjects().then(projects => {
                    const project = projects.find(p => p.id === currentProjectId);
                    if (project) {
                        localStorage.setItem('alpa_temp_project_context', JSON.stringify(project));
                        window.top.postMessage({ action: 'HUB_NAVIGATE', module: 'ordenes' }, "*");
                    }
                });
            }

            // --- SOCIO REIMBURSEMENT LOGIC ---
            function openSocioExpenseModal() {
                document.getElementById('socio-expense-modal').classList.remove('hidden');
                loadPendingSocioExpenses();
            }

            async function loadPendingSocioExpenses() {
                const body = document.getElementById('socio-expenses-body');
                const socioFilter = document.getElementById('socio-filter').value;
                body.innerHTML = '<tr><td colspan="5" class="p-4 text-center">Cargando gastos...</td></tr>';

                try {
                    const transactions = await AlpaHub.execute('getTransactions') || [];
                    const pending = transactions.filter(t => {
                        const source = t.source_of_funds || t.OrigenFondos || '';
                        const status = t.reimbursement_status || 'not_applicable';

                        // Match Source
                        let matchSocio = false;
                        if (socioFilter === 'all') {
                            matchSocio = (source === 'pablo' || source === 'alexis');
                        } else {
                            matchSocio = (source === socioFilter);
                        }

                        return matchSocio && status === 'pending';
                    });

                    if (pending.length === 0) {
                        body.innerHTML = '<tr><td colspan="5" class="p-8 text-center text-gray-500 italic">No hay gastos pendientes de reembolso para este criterio.</td></tr>';
                        return;
                    }

                    body.innerHTML = '';
                    pending.sort((a, b) => new Date(b.date) - new Date(a.date)).forEach(t => {
                        const row = document.createElement('tr');

                        row.className = 'hover:bg-gray-50 transition border-b border-gray-100/50 text-sm';

                        const statusBadge = t.status === 'Reembolsado'
                            ? '<span class="px-2 py-0.5 rounded text-emerald-700 bg-emerald-100 text-xs font-bold">REEMBOLSADO</span>'
                            : '<span class="px-2 py-0.5 rounded text-orange-700 bg-orange-100 text-xs font-bold">PENDIENTE</span>';

                        row.innerHTML = `
                            <td class="p-4 text-center">
                                <input type="checkbox" class="socio-check rounded border-gray-300 text-blue-600 focus:ring-blue-500" value="${t.id}" data-amount="${t.amount}" onchange="calculateSocioTotal()">
                            </td>
                            <td class="p-4 font-mono text-gray-500">${t.date}</td>
                            <td class="p-4">
                                <p class="font-bold text-gray-800">${t.description}</p>
                                <p class="text-xs text-gray-500">${t.category}</p>
                            </td>
                            <td class="p-4 font-mono font-bold text-gray-800">${parseFloat(t.amount || 0).toLocaleString('es-CL')}</td>
                            <td class="p-4">${statusBadge}</td>
                        `;
                        body.appendChild(row);
                    });
                } catch (e) {
                    console.error("Error drawing socios list", e);
                    body.innerHTML = '<tr><td colspan="5" class="p-8 text-center text-red-500">Error al cargar datos.</td></tr>';
                }
            }

            // Expose globally
            window.toggleAllSocioExpenses = function (master) {
                document.querySelectorAll('.socio-check').forEach(c => c.checked = master.checked);
                calculateSocioTotal();
            }

            function calculateSocioTotal() {
                let total = 0;
                let count = 0;
                document.querySelectorAll('.socio-check:checked').forEach(c => {
                    total += parseFloat(c.dataset.amount);
                    count++;
                });
                document.getElementById('socio-import-total').innerText = '$ ' + total.toLocaleString('es-CL');
                document.getElementById('btn-import-socio').disabled = count === 0;
            }

            async function createRendicionFromSocioExpenses() {
                const checks = document.querySelectorAll('.socio-check:checked');
                if (checks.length === 0) return;

                const btn = document.getElementById('btn-import-socio');
                btn.disabled = true;
                btn.innerText = 'Procesando...';

                try {
                    const ids = Array.from(checks).map(c => c.value);
                    const total = Array.from(checks).reduce((sum, c) => sum + parseFloat(c.dataset.amount), 0);
                    const socio = document.getElementById('socio-filter').value === 'all' ? 'Socio (Mix)' : document.getElementById('socio-filter').value;

                    const newReport = {
                        id: 'ER-' + Date.now(),
                        employee: socio.toUpperCase(),
                        amount: total,
                        costCenter: 'Reembolso Socios',
                        observations: `Reembolso de ${ids.length} gastos personales. IDs: ${ids.join(', ')}`,
                        status: 'Pendiente',
                        date: new Date().toISOString().split('T')[0],
                        isSocioReimbursement: true,
                        linkedTransactionIds: ids
                    };

                    await AlpaHub.execute('createExpenseReport', newReport);

                    // Note: In a real flow, we would mark transactions as 'processing' here,
                    // but we'll wait for final approval of the Rendicion.

                    AlpaHub.showNotification('Rendicion de Reembolso generada. Revisela para aprobacion final.', 'success');
                    document.getElementById('socio-expense-modal').classList.add('hidden');
                    loadExpenseReports();
                } catch (e) {
                    console.error("Error creating report", e);
                    AlpaHub.showNotification("Error al generar la vista de impresion: " + e.message, 'error');
                } finally {
                    btn.disabled = false;
                    btn.innerText = 'Generar Rendicion de Reembolso';
                }
            }

            function checkSession() {
                // Updated to be more Hub-friendly
                const sessionJSON = localStorage.getItem(USER_SESSION_KEY) || (parent && parent.localStorage.getItem(USER_SESSION_KEY));
                if (sessionJSON) {
                    try {
                        const session = JSON.parse(sessionJSON);
                        if (session && session.token) {
                            if (document.getElementById('login-overlay')) document.getElementById('login-overlay').classList.add('hidden');
                            updateUIForRole(session.user);

                            // LOAD DATA FROM CORE
                            initCharts();
                            loadTransactions();
                            loadExpenseReports();
                            loadProjects();
                            loadCostCenters();

                            /*
                            // DISABLED: Legacy auto-sync trigger to avoid 'Sync blocked' alerts in SUPA mode
                            setTimeout(async () => {
                                const projects = await AlpaHub.getProjects();
                                if (!projects || projects.length === 0) {
                                    console.log("Contabilidad: Empty state detected. Syncing...");
                                    triggerModuleSync();
                                }
                            }, 1500);
                            */
                        }
                    } catch (e) {
                        console.error("Invalid session", e);
                    }
                }
            }

            async function triggerModuleSync() {
                const btn = document.getElementById('mod-sync-btn');
                if (!btn) return;
                const originalHTML = btn.innerHTML;

                try {
                    const overlay = document.getElementById('sync-overlay');
                    if (overlay) overlay.classList.remove('hidden');

                    btn.disabled = true;
                    btn.innerHTML = '<i class="fas fa-sync fa-spin"></i> ...';

                    const result = await AlpaHub.execute('syncWithCloud');

                    if (result && result.status === 'success') {
                        if (btn.classList.contains('bg-blue-50')) {
                            btn.classList.remove('bg-blue-50', 'text-blue-600');
                            btn.classList.add('bg-green-600', 'text-white');
                        }
                        btn.innerHTML = '<i class="fas fa-check"></i>';

                        AlpaHub.showNotification('Sincronizacin completada con xito', 'success');

                        // Refresh current view
                        setTimeout(() => location.reload(), 800);
                    } else {
                        btn.disabled = false;
                        btn.innerHTML = originalHTML;
                        if (overlay) overlay.classList.add('hidden');

                        // SILENCE: Don't alert if sync is explicitly blocked in SUPA mode
                        if (result && result.message && !result.message.includes('Sync blocked')) {
                            AlpaHub.showNotification("Error al sincronizar: " + result.message, 'error');
                        }
                    }
                } catch (e) {
                    console.error(e);
                    btn.disabled = false;
                    btn.innerHTML = originalHTML;
                }
            }

            // --- GLOBAL PROJECT LISTENER (Phase 2) ---
            window.addEventListener('message', (event) => {
                if (event.data && event.data.type === 'alpa:projectSelected') {
                    console.log("Module Contabilidad: Global Project Selection received", event.data.projectId);
                    // Reload everything to apply project filter
                    initCharts();
                }
            });

            // SII MOCK SIMULATION (Phase 2)
            function openSIIModal() {
                document.getElementById('sii-modal').classList.remove('hidden');
                document.getElementById('sii-step-1').classList.remove('hidden');
                document.getElementById('sii-step-2').classList.add('hidden');
                document.getElementById('sii-step-3').classList.add('hidden');
            }
            function closeSIIModal() {
                document.getElementById('sii-modal').classList.add('hidden');
            }
            async function simulateSIISync() {
                document.getElementById('sii-step-1').classList.add('hidden');
                document.getElementById('sii-step-2').classList.remove('hidden');

                // Pretend to fetch data
                await new Promise(r => setTimeout(r, 2000));

                document.getElementById('sii-step-2').classList.add('hidden');
                document.getElementById('sii-step-3').classList.remove('hidden');

                // Refresh data in background
                loadTransactions();
            }

            async function handleLogin(e) {
                e.preventDefault();
                alert('Procesando Ingreso...');

                const btn = e.target.querySelector('button');
                const originalText = btn.innerText;
                btn.innerText = 'Verificando...';
                btn.disabled = true;

                const email = document.getElementById('login-email').value;
                const password = document.getElementById('login-password').value;

                // 1. LOCAL BYPASS
                if (email.trim().toLowerCase() === 'admin@alpaconstruccioneingenieria.cl' && password === 'AlpaAdmin2026!') {
                    console.log("Activando Bypass Local de Admin");
                    const mockSession = { token: 'bypass-123', user: { name: 'Admin Local', role: 'Admin', email: email } };
                    localStorage.setItem(USER_SESSION_KEY, JSON.stringify(mockSession));
                    alert("Login Exitoso (Local)");
                    window.location.reload();
                    return;
                }

                // 2. REMOTE FETCH
                try {
                    const response = await fetch(SCRIPT_URL, {
                        method: 'POST',
                        redirect: 'follow',
                        headers: { 'Content-Type': 'text/plain;charset=utf-8' },
                        body: JSON.stringify({
                            action: 'login',
                            payload: { email, password }
                        })
                    });

                    const data = await response.json();

                    if (data.status === 'success') {
                        localStorage.setItem(USER_SESSION_KEY, JSON.stringify({
                            token: data.token,
                            user: data.user
                        }));
                        window.location.reload();
                    } else {
                        alert('Error de Acceso: ' + (data.message || 'Credenciales invalidas'));
                    }

                } catch (error) {
                    console.error("Login Check Error", error);
                    alert("Error de conexion con el servidor.");
                } finally {
                    btn.innerText = originalText;
                    btn.disabled = false;
                }
            }

            function updateUIForRole(user) {
                // Update Navbar
                const navUser = document.querySelector('nav .text-sm');
                if (navUser) navUser.innerHTML = `<i class="fa-solid fa-user mr-1"></i> ${user.name} (${user.role})`;

                // Restrict Features for Non-Admins
                if (user.role !== 'Admin') {
                    const reportsBtn = document.querySelector('button[data-module="reports"]');
                    if (reportsBtn) reportsBtn.classList.add('hidden');
                    document.getElementById('admin-tools').classList.add('hidden');
                } else {
                    document.getElementById('admin-tools').classList.remove('hidden');
                }
            }

            // NAVIGATION LOGIC
            function switchModule(moduleName) {
                const target = document.getElementById(moduleName);
                if (!target) {
                    console.warn(`Module ${moduleName} not found.`);
                    return;
                }

                // If switching to transactions from the main tab, clear project filter
                if (moduleName === 'transactions') {
                    localStorage.removeItem('alpa_active_project_id'); // Clear filter
                    if (typeof loadTransactions === 'function') {
                        loadTransactions(); // Force refresh to show all
                    }
                }

                // Hide all modules and reset tabs
                document.querySelectorAll('.module-content').forEach(el => el.classList.add('hidden'));
                document.querySelectorAll('.module-tab').forEach(el => {
                    el.classList.remove('bg-primary', 'text-white', 'shadow-md');
                    el.classList.add('text-slate-600', 'hover:bg-white');
                });

                // Show target module and activate tab
                target.classList.remove('hidden');
                const activeTab = document.querySelector(`button[data-module="${moduleName}"]`);
                if (activeTab) {
                    activeTab.classList.remove('text-slate-600', 'hover:bg-white');
                    activeTab.classList.add('bg-primary', 'text-white', 'shadow-md');
                }
            }


            // UTILS
            const safeParse = (val) => {
                if (typeof val === 'number') return isNaN(val) ? 0 : val;
                if (!val || val === '#NUM!') return 0;
                let str = val.toString().trim();
                if (str.includes(',') && str.includes('.')) str = str.replace(/\./g, '');
                str = str.replace(',', '.');
                const n = parseFloat(str);
                return isNaN(n) ? 0 : n;
            };

            // CALCULATIONS & CHARTS
            function calculateTaxes() {
                const rawAmount = parseFloat(document.getElementById('t-amount').value) || 0;
                const isGross = document.getElementById('t-is-gross').checked;
                const docType = document.getElementById('t-doc-type').value;
                const categorySelect = document.getElementById('t-category');
                let category = categorySelect ? categorySelect.value : '';

                if (category === 'OTROS') {
                    const otherInput = document.getElementById('t-category-other');
                    if (otherInput) category = otherInput.value;
                }

                let neto = 0;
                let iva = 0;
                let ret = 0;
                let total = 0;

                const isLoanOrAdvance = category.toLowerCase().includes('prstamos') ||
                    category.toLowerCase().includes('adelanto') ||
                    category.toLowerCase().includes('prestamo');

                if (isLoanOrAdvance) {
                    neto = rawAmount;
                    total = rawAmount;
                } else {
                    if (isGross) {
                        if (docType === 'Factura' || docType === 'Boleta Afecta') {
                            neto = rawAmount / 1.19;
                            iva = rawAmount - neto;
                        } else if (category === 'Honorarios Profesionales') {
                            // For fees, usually "gross" means before retention in common parlance, 
                            // but here we follow SII logic if possible. 
                            // Usually honors are entered as 'bruto' (before retention).
                            neto = rawAmount;
                            ret = rawAmount * 0.1375;
                            total = rawAmount - ret;
                        } else {
                            neto = rawAmount;
                            total = rawAmount;
                        }
                    } else {
                        neto = rawAmount;
                        if (docType === 'Factura' || docType === 'Boleta Afecta') {
                            iva = rawAmount * 0.19;
                            total = rawAmount + iva;
                        } else if (category === 'Honorarios Profesionales') {
                            ret = rawAmount * 0.1375;
                            total = rawAmount - ret;
                        } else {
                            total = rawAmount;
                        }
                    }
                }

                document.getElementById('calc-neto').innerText = '$ ' + Math.round(neto).toLocaleString('es-CL');
                document.getElementById('calc-iva').innerText = '$ ' + Math.round(iva).toLocaleString('es-CL');
                document.getElementById('calc-ret').innerText = '$ ' + Math.round(ret).toLocaleString('es-CL');
                document.getElementById('calc-total').innerText = '$ ' + Math.round(total).toLocaleString('es-CL');
            }

            function prepareMainDashboardData(transactions) {
                const monthlyData = {};
                const costCenterData = {};

                transactions.forEach(t => {
                    const date = new Date(t.date || t.Fecha || t.createdAt);
                    const monthYear = `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}`;
                    const rawAmt = safeParse(t.amount || t.monto || t.Monto);
                        const isGross = (t.is_gross === undefined || t.is_gross === true || t.is_gross === "true");
                        const amount = isGross ? rawAmt / 1.19 : rawAmt;
                    const typeDisplayRaw = (t.type || t.Tipo || 'Gasto').toLowerCase();
                    const catRaw = (t.category || t.Categoria || '').toLowerCase();
                    const description = t.description || t.Descripcion || '';
                    const descRaw = description.toLowerCase();

                    // PRIORITY CLASSIFICATION:
                    let isIncome = false;
                    if (typeDisplayRaw === 'ingreso' || typeDisplayRaw === 'cobro') {
                        isIncome = true;
                    } else if (typeDisplayRaw === 'gasto' || typeDisplayRaw === 'pago') {
                        isIncome = false;
                    } else {
                        isIncome = catRaw.includes('estado de pago') || descRaw.includes('estado de pago') || descRaw.includes('ep ');
                    }

                    if (!monthlyData[monthYear]) {
                        monthlyData[monthYear] = { income: 0, expense: 0 };
                    }

                    if (isIncome) {
                        monthlyData[monthYear].income += amount;
                    } else {
                        monthlyData[monthYear].expense += amount;
                    }

                    const costCenter = t.costCenter || t.centroCostoId || t.CentroCostoID || t.ProyectoID || t.proyectoId || 'Sin Centro de Costo';
                    if (!isIncome) { // Only track expenses for cost centers
                        costCenterData[costCenter] = (costCenterData[costCenter] || 0) + amount;
                    }
                });

                const sortedMonths = Object.keys(monthlyData).sort();
                const cashflowLabels = sortedMonths;
                const cashflowIncome = sortedMonths.map(month => monthlyData[month].income);
                const cashflowExpense = sortedMonths.map(month => monthlyData[month].expense);

                const sortedCostCenters = Object.entries(costCenterData)
                    .sort(([, a], [, b]) => b - a)
                    .slice(0, 7); // Top 7 cost centers

                const ccLabels = sortedCostCenters.map(([label,]) => label);
                const ccData = sortedCostCenters.map(([, data]) => data);

                return {
                    cashflow: { labels: cashflowLabels, income: cashflowIncome, expense: cashflowExpense },
                    costCenters: { labels: ccLabels, data: ccData }
                };
            }

            async function initCharts() {
                try {
                    // Pre-load data to ensure consistency across tabs
                    await loadTransactions();
                    await loadProjects();
                    renderProjectSummary(window.allProjects || []);

                    // 2. FETCH METRICS (With Global Filter)
                    const activeProjectId = localStorage.getItem('alpa_active_project_id') || 'all';
                    const result = await AlpaHub.execute('getMainDashboardMetrics', { projectId: activeProjectId }) || {};

                    const cashflowData = result.cashflow || { labels: [], income: [], expense: [] };
                    const ccData = result.costCenters || { labels: [], data: [] };
                    const cards = result.cards || { income: 0, expense: 0, balance: 0, tax: 0, incomeTrend: 0, expenseTrend: 0 };

                    const incomeEl = document.getElementById('dash-income');
                    const expenseEl = document.getElementById('dash-expense');
                    const utilityEl = document.getElementById('dash-utility');
                    const balanceEl = document.getElementById('dash-balance');
                    const taxEl = document.getElementById('dash-tax');
                    const partnerDebtEl = document.getElementById('dash-partner-debt');

                    if (incomeEl) {
                        const incomeActual = cards.actual || 0;
                        const incomeProjected = cards.projected || 0;
                        const finalIncome = cards.income || 0;

                        incomeEl.innerText = '$ ' + finalIncome.toLocaleString('es-CL');

                        const subLabel = incomeEl.parentElement.querySelector('p.text-\\[10px\\]') || document.createElement('p');
                        if (cards.isProjectedOnly) {
                            subLabel.className = 'text-xs text-orange-500 font-bold mt-1 uppercase';
                            subLabel.innerText = '📊 Solo Proyectado (Sin Facturar)';
                        } else if (incomeActual > 0) {
                            subLabel.className = 'text-xs text-green-600 font-bold mt-1 uppercase';
                            subLabel.innerText = '? ' + (incomeActual >= incomeProjected ? 'Ingresos Conciliados' : 'Ingresos Parciales');
                        } else {
                            subLabel.className = 'text-xs text-gray-400 mt-1 uppercase font-bold';
                            subLabel.innerText = 'Sin Movimientos';
                        }
                        if (!incomeEl.parentElement.contains(subLabel)) incomeEl.parentElement.appendChild(subLabel);
                    }

                    if (expenseEl) expenseEl.innerText = '$ ' + (cards.expense || 0).toLocaleString('es-CL');
                    if (utilityEl) utilityEl.innerText = '$ ' + (cards.utility || 0).toLocaleString('es-CL');
                    if (balanceEl) balanceEl.innerText = '$ ' + (cards.balance || 0).toLocaleString('es-CL');
                    if (taxEl) taxEl.innerText = '$ ' + (cards.tax || 0).toLocaleString('es-CL');
                    if (partnerDebtEl) partnerDebtEl.innerText = '$ ' + (cards.partnerDebt || 0).toLocaleString('es-CL');

                    const incTrendEl = document.getElementById('dash-income-trend');
                    const expTrendEl = document.getElementById('dash-expense-trend');
                    if (incTrendEl) incTrendEl.innerText = cards.incomeTrend + '%';
                    if (expTrendEl) expTrendEl.innerText = cards.expenseTrend + '%';

                    // 3. RENDER CHARTS
                    // Destroy existing instances to prevent "Canvas is already in use" errors
                    if (window.cashflowChartInstance) window.cashflowChartInstance.destroy();
                    if (window.costCenterChartInstance) window.costCenterChartInstance.destroy();

                    const ctx1 = document.getElementById('cashflowChart');
                    if (ctx1) {
                        window.cashflowChartInstance = new Chart(ctx1.getContext('2d'), {
                            type: 'line',
                            data: {
                                labels: cashflowData.labels,
                                datasets: [
                                    {
                                        label: 'Ingresos',
                                        data: cashflowData.income,
                                        borderColor: '#22c55e',
                                        backgroundColor: 'rgba(34, 197, 94, 0.1)',
                                        fill: true,
                                        tension: 0.4,
                                        pointRadius: 4,
                                        pointBackgroundColor: '#22c55e'
                                    },
                                    {
                                        label: 'Gastos',
                                        data: cashflowData.expense,
                                        borderColor: '#ef4444',
                                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                                        fill: true,
                                        tension: 0.4,
                                        pointRadius: 4,
                                        pointBackgroundColor: '#ef4444'
                                    }
                                ]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {
                                    legend: { position: 'bottom' },
                                    tooltip: {
                                        callbacks: {
                                            label: function (context) {
                                                let label = context.dataset.label || '';
                                                if (label) label += ': ';
                                                if (context.parsed.y !== null) {
                                                    label += new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP' }).format(context.parsed.y);
                                                }
                                                return label;
                                            }
                                        }
                                    }
                                },
                                scales: {
                                    y: {
                                        ticks: {
                                            callback: function (value) {
                                                return '$' + value.toLocaleString('es-CL');
                                            }
                                        }
                                    }
                                }
                            }
                        });
                    }

                    const ctx2 = document.getElementById('costCenterChart');
                    if (ctx2) {
                        window.costCenterChartInstance = new Chart(ctx2.getContext('2d'), {
                            type: 'doughnut',
                            data: {
                                labels: ccData.labels,
                                datasets: [{
                                    data: ccData.data,
                                    backgroundColor: ['#3b82f6', '#8b5cf6', '#f59e0b', '#10b981', '#6366f1', '#ec4899', '#14b8a6']
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {
                                    legend: { position: 'bottom' },
                                    tooltip: {
                                        callbacks: {
                                            label: function (context) {
                                                let label = context.label || '';
                                                if (label) label += ': ';
                                                const val = context.raw || 0;
                                                label += new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP' }).format(val);
                                                return label;
                                            }
                                        }
                                    }
                                }
                            }
                        });
                    }

                } catch (error) {
                    console.error("Error loading dashboard data", error);
                }
            }

            // LOADERS
            async function loadTransactions() {
                try {
                    const allTx = await AlpaHub.execute('getTransactions') || [];
                    window.allTransactions = allTx;

                    // --- GLOBAL PROJECT FILTER ---
                    const activeProjectId = localStorage.getItem('alpa_active_project_id') || 'all';
                    let filteredTx = allTx;
                    if (activeProjectId !== 'all') {
                        filteredTx = allTx.filter(t => {
                            const pid = t.costCenter || t.centroCostoId || t.CentroCostoID || t.ProyectoID || t.proyectoId;
                            return pid === activeProjectId;
                        });
                    }

                    // --- PERIOD FILTER SETUP ---
                    const periodSelect = document.getElementById('period-filter');
                    const currentPeriod = periodSelect ? periodSelect.value : 'all';

                    // Build period options dynamically from real data
                    if (periodSelect) {
                        const months = new Set();
                        filteredTx.forEach(t => {
                            const d = t.date || t.Fecha || t.createdAt;
                            if (d) {
                                const m = new Date(d).toISOString().substring(0, 7);
                                months.add(m);
                            }
                        });
                        const sortedMonths = Array.from(months).sort().reverse();
                        const prevVal = periodSelect.value;
                        periodSelect.innerHTML = '<option value="all">Todos</option>';
                        sortedMonths.forEach(m => {
                            const [y, mo] = m.split('-');
                            const label = new Date(y, mo - 1).toLocaleString('es-CL', { month: 'long', year: 'numeric' });
                            periodSelect.innerHTML += `<option value="${m}">${label.charAt(0).toUpperCase() + label.slice(1)}</option>`;
                        });
                        if (prevVal && [...periodSelect.options].some(o => o.value === prevVal)) periodSelect.value = prevVal;
                    }

                    // Filter by period
                    const selectedPeriod = periodSelect ? periodSelect.value : 'all';
                    const transactions = selectedPeriod === 'all' ? filteredTx : filteredTx.filter(t => {
                        const d = t.date || t.Fecha || t.createdAt;
                        return d && new Date(d).toISOString().substring(0, 7) === selectedPeriod;
                    });

                    // Fetch health report to flag duplicates in table
                    let dupIDs = new Set();
                    try {
                        const health = await AlpaHub.execute('checkDatabaseIntegrity');
                        if (health && health.duplicates) dupIDs = new Set(health.duplicates.map(d => d.id));
                    } catch (e) { /* non-critical */ }

                    const tableBody = document.getElementById('transactions-body');
                    if (!tableBody) return;
                    tableBody.innerHTML = '';

                    // Category tracking for summary
                    const categoryTotals = {};
                    let totalIncome = 0, totalExpense = 0;

                    const allProjects = await AlpaHub.execute('getProjects') || [];
                    transactions.slice().reverse().forEach(t => {
                        const tid = t.id || t.ID;
                        const rawAmt = safeParse(t.amount || t.monto || t.Monto);
                        const isGross = (t.is_gross === undefined || t.is_gross === true || t.is_gross === "true");
                        const amount = isGross ? rawAmt / 1.19 : rawAmt;
                        const date = t.date || t.Fecha || t.createdAt;
                        const formattedDate = date ? new Date(date).toISOString().split('T')[0] : 'N/A';
                        const description = t.description || t.Descripcion || '';
                        const ccRaw = t.costCenter || t.centroCostoId || t.CentroCostoID || t.ProyectoID || t.proyectoId || "-";
                        const ccProject = allProjects.find(p => p.id === ccRaw || p.code === ccRaw);
                        const costCenter = ccProject ? (ccProject.name || ccProject.code || ccRaw) : ccRaw;
                        const typeDisplayRaw = (t.type || t.Tipo || 'Gasto').toLowerCase();
                        const catRaw = (t.category || t.Categoria || '').toLowerCase();
                        const descRaw = description.toLowerCase();
                        const category = t.category || t.Categoria || 'Sin Categoria';

                        const isAnulada = (t.status === "Anulada" || t.Estado === "Anulada" || description.startsWith("[Anulada:"));
                        if (isAnulada) return;
                        let isIncome = false;
                        if (typeDisplayRaw === 'ingreso' || typeDisplayRaw === 'cobro') {
                            isIncome = true;
                        } else if (typeDisplayRaw === 'gasto' || typeDisplayRaw === 'pago') {
                            isIncome = false;
                        } else {
                            isIncome = catRaw.includes('estado de pago') || descRaw.includes('estado de pago') || descRaw.includes('ep ');
                        }

                        // Accumulate for summary
                        if (!isAnulada) {
                            if (isIncome) {
                                totalIncome += amount;
                            } else {
                                totalExpense += amount;
                                if (!categoryTotals[category]) categoryTotals[category] = 0;
                                categoryTotals[category] += amount;
                            }
                        }

                        let typeDisplay = isIncome ? 'Ingreso' : 'Gasto';
                        let typeColor = isIncome ? 'green' : 'red';
                        if (isAnulada) {
                            typeDisplay = 'Anulada';
                            typeColor = 'gray';
                        }

                        const isDuplicate = dupIDs.has(tid);
                        const hasDoc = description && description.includes('[Doc:');

                        const row = document.createElement('tr');
                        row.className = `border-b hover:bg-gray-50 ${isDuplicate ? 'bg-orange-50/50' : ''} ${isAnulada ? 'opacity-50 line-through bg-gray-100' : ''}`;
                        row.innerHTML = `
                        <td class="py-3 px-4 text-xs font-mono">${formattedDate}</td>
                        <td class="py-3 px-4">
                            <span class="bg-${typeColor}-100 text-${typeColor}-800 py-1 px-3 rounded-full text-xs font-bold">${typeDisplay}</span>
                            ${isDuplicate ? '<span class="ml-1 text-xs bg-orange-600 text-white p-1 rounded font-bold">DUPLICADO?</span>' : ''}
                        </td>
                        <td class="py-3 px-4 text-sm">${description}</td>
                        <td class="py-3 px-4 text-xs font-bold text-slate-500 hide-on-owner">${costCenter}</td>
                        <td class="py-3 px-4 font-bold text-sm">$ ${amount.toLocaleString('es-CL')}</td>
                        <td class="py-1 px-4 text-center">
                            <div class="flex items-center justify-center gap-3">
                                ${hasDoc ?
                                '<i class="fa-solid fa-circle-check text-green-500 text-lg" title="Documento Adjunto"></i>' :
                                `<button onclick="openAttachModal('${tid}')" class="text-orange-500 hover:text-orange-700 p-2 transition-colors" title="Subir Respaldo Ahora">
                                        <i class="fa-solid fa-paperclip"></i>
                                    </button>`}
                                <button onclick="openEditTransactionModal('${tid}')" class="text-blue-500 hover:text-blue-700 p-2 transition-colors" title="Editar">
                                    <i class="fas fa-edit"></i>
                                </button>
                                <button onclick="deleteTransaction('${tid}')" class="text-red-400 hover:text-red-600 p-2 transition-colors" title="Eliminar">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </td>`;
                        tableBody.appendChild(row);
                    });

                    // --- CATEGORY SUMMARY ACCORDION ---
                    const summaryEl = document.getElementById('Categoriary');
                    if (summaryEl) {
                        const sorted = Object.entries(categoryTotals).sort((a, b) => b[1] - a[1]);
                        summaryEl.innerHTML = sorted.map(([cat, total]) => `
                            <div class="flex justify-between items-center py-2 border-b border-gray-100 last:border-0">
                                <span class="text-sm text-gray-700 font-medium">${cat}</span>
                                <span class="text-sm font-bold font-mono text-red-700">$ ${total.toLocaleString('es-CL')}</span>
                            </div>
                        `).join('') + `
                            <div class="flex justify-between items-center pt-3 mt-2 border-t-2 border-gray-300">
                                <span class="text-sm font-bold text-gray-800">Total Gastos</span>
                                <span class="text-sm font-bold font-mono text-red-800">$ ${totalExpense.toLocaleString('es-CL')}</span>
                            </div>
                            <div class="flex justify-between items-center py-1">
                                <span class="text-sm font-bold text-gray-800">Total Ingresos</span>
                                <span class="text-sm font-bold font-mono text-green-700">$ ${totalIncome.toLocaleString('es-CL')}</span>
                            </div>
                        `;
                    }

                    // Update Owner Summary (Phase 3)
                    updateOwnerSummary(totalIncome, totalExpense);

                } catch (error) { console.error("Error loading transactions", error); }
            }

            function toggleOwnerView(isOwner) {
                const btnAccountant = document.getElementById('btn-view-accountant');
                const btnOwner = document.getElementById('btn-view-owner');
                const summaryCard = document.getElementById('owner-summary-card');
                const tableContainer = document.querySelector('#transactions .bg-white.rounded-xl.shadow');

                if (isOwner) {
                    btnOwner.style.backgroundColor = 'var(--surface2)';
                    btnOwner.style.color = 'var(--text)';
                    btnOwner.classList.add('shadow-sm');
                    btnAccountant.style.backgroundColor = 'transparent';
                    btnAccountant.style.color = 'var(--text-muted)';
                    btnAccountant.classList.remove('shadow-sm');
                    summaryCard.classList.remove('hidden');
                    if (tableContainer) tableContainer.classList.add('owner-view-active');
                    loadTransactions();
                } else {
                    btnAccountant.classList.add('bg-white', 'shadow-sm', 'text-blue-600');
                    btnAccountant.classList.remove('text-gray-500');
                    btnOwner.classList.remove('bg-white', 'shadow-sm', 'text-blue-600');
                    btnOwner.classList.add('text-gray-500');
                    summaryCard.classList.add('hidden');
                    if (tableContainer) tableContainer.classList.remove('owner-view-active');
                }
                localStorage.setItem('alpa_u_pref_owner_view', isOwner);
            }

            function updateOwnerSummary(income, expense) {
                const incomeEl = document.getElementById('owner-sum-income');
                const expenseEl = document.getElementById('owner-sum-expense');
                const utilityEl = document.getElementById('owner-sum-utility');
                const cashEl = document.getElementById('owner-sum-cash');

                if (!incomeEl) return;

                incomeEl.innerText = '$ ' + income.toLocaleString('es-CL');
                expenseEl.innerText = '$ ' + expense.toLocaleString('es-CL');
                utilityEl.innerText = '$ ' + (income - expense).toLocaleString('es-CL');
                cashEl.innerText = '$ ' + (income - expense).toLocaleString('es-CL');
            }

            // Init Preference
            document.addEventListener('DOMContentLoaded', () => {
                setTimeout(() => {
                    if (localStorage.getItem('alpa_u_pref_owner_view') === 'true') {
                        toggleOwnerView(true);
                    }
                }, 500);
            });

            async function loadExpenseReports() {
                try {
                    const reports = await AlpaHub.execute('getExpenseReports') || [];
                    const tableBody = document.getElementById('expense-reports-body');
                    if (!tableBody) return;
                    tableBody.innerHTML = '';

                    reports.sort((a, b) => new Date(b.date) - new Date(a.date)).forEach(r => {
                        const statusClass = r.status === 'Aprobada' ? 'bg-green-100 text-green-800' :
                            r.status === 'Rechazada' ? 'bg-red-100 text-red-800' :
                                'bg-yellow-100 text-yellow-800';

                        const row = document.createElement('tr');
                        row.className = 'border-b hover:bg-gray-50';
                        row.innerHTML = `
                        <td class="px-6 py-4 text-sm font-bold">${r.id}</td>
                        <td class="px-6 py-4 text-sm">${r.employee || r.Empleado || 'N/A'}</td>
                        <td class="px-6 py-4 text-sm">${r.costCenter || r.CentroCostoID || 'N/A'}</td>
                        <td class="px-6 py-4 text-sm"><span class="${statusClass} px-2 py-1 rounded text-xs font-bold">${r.status || 'Pendiente'}</span></td>
                        <td class="px-6 py-4 text-sm text-right font-bold">$ ${parseInt(r.amount || r.TotalSolicitado || 0).toLocaleString('es-CL')}</td>
                        <td class="px-6 py-4 text-center">
                            <div class="flex gap-2 justify-center">
                                ${r.status === 'Pendiente' ? `
                                    <button onclick="approveReport('${r.id}')" class="text-green-600 hover:text-green-800" title="Aprobar y Pagar"><i class="fas fa-check-circle text-lg"></i></button>
                                    <button onclick="updateReportStatus('${r.id}', 'Rechazada')" class="text-red-500 hover:text-red-700" title="Rechazar"><i class="fas fa-times-circle text-lg"></i></button>
                                ` : ''}
                                 <button onclick="AlpaHub.showNotification('Obs: ' + (r.observations || 'Sin observaciones'), 'info')" class="text-blue-500 hover:text-blue-700"><i class="fas fa-eye"></i></button>

                            </div>
                        </td>`;
                        tableBody.appendChild(row);
                    });
                } catch (error) { console.error("Error loading expense reports", error); }
            }

            async function approveReport(reportId) {
                if (!confirm(`Desea aprobar esta Rendicion? Si es una Rendicion de socio, se generar el pago automticamente.`)) return;

                try {
                    const reports = await AlpaHub.execute('getExpenseReports') || [];
                    const report = reports.find(r => r.id === reportId);
                    if (!report) return;

                    // 1. Mark report as Approved
                    await AlpaHub.execute('updateExpenseReportStatus', { id: reportId, status: 'Aprobada' });

                    // 2. If it's a Socio Reimbursement, process the payment
                    if (report.isSocioReimbursement && report.linkedTransactionIds) {
                        // Mark original transactions as reimbursed
                        for (const txId of report.linkedTransactionIds) {
                            await AlpaHub.execute('updateTransactionReimbursementStatus', { id: txId, status: 'reimbursed' });
                        }

                        // Create repay transaction (Company -> Socio)
                        const paymentTx = {
                            date: new Date().toISOString().split('T')[0],
                            type: 'Pago',
                            category: 'Reembolso Socios',
                            amount: report.amount,
                            description: `REEMBOLSO A ${report.employee}: Rendicion ${report.id}`,
                            costCenter: 'Reembolso Socios',
                            source_of_funds: 'company',
                            reimbursement_status: 'not_applicable'
                        };
                        await AlpaHub.addTransaction(paymentTx);
                    }

                    AlpaHub.showNotification('Rendicion aprobada correctamente.', 'success');
                    loadExpenseReports();
                    loadTransactions();
                    initCharts();
                } catch (e) {
                    console.error("Error approving", e);
                    alert("Error al procesar la aprobacion.");
                }
            }

            async function updateReportStatus(id, status) {
                if (!confirm(`Confirmar cambio de estado a ${status}?`)) return;
                await AlpaHub.execute('updateExpenseReportStatus', { id, status });
                loadExpenseReports();
            }

            async function loadProjects() {
                try {
                    const projects = await AlpaHub.execute('getProjects') || [];
                    // Pre-fetch transactions to avoid await in loop and N+1 query
                    const allTransactions = await AlpaHub.execute('getTransactions') || [];

                    const container = document.getElementById('projects-container');
                    if (!container) return;
                    container.innerHTML = '';
                    window.allProjects = projects;

                    projects.forEach(p => {
                        const presupuesto = parseFloat(p.budget || p.Presupuesto || 0);
                        const code = p.code || p.Codigo || '-';
                        const name = p.name || p.Nombre || 'Sin nombre';
                        const client = p.client || p.Cliente || 'N/A';
                        const status = p.status || p.Estado || 'Activo';

                        // Calculate real spent from transactions linked to this CC or ProyectoID
                        const ejecutado = allTransactions
                            .filter(t => {
                                const ccId = (t.costCenter || t.centroCostoId || t.CentroCostoID || t.ProyectoID || t.proyectoId || '').toString().toLowerCase().trim();
                                const type = (t.type || t.Tipo || '').toLowerCase();

                                const pId = (p.id || p.ID || '').toString().toLowerCase().trim();
                                const pName = (p.name || p.Nombre || '').toString().toLowerCase().trim();
                                const pCode = (p.code || p.Codigo || '').toString().toLowerCase().trim();

                                // Robust ID matching: Match by ID, Name, Code, or the special 'alpa-001' legacy ID
                                const exactMatch = (ccId === pId ||
                                    ccId === pName ||
                                    ccId === pCode ||
                                    (pCode && ccId === pCode) ||
                                    (pName && ccId === pName) ||
                                    (ccId === 'alpa-001' && (pId === 'cc002')));

                                // Partial Matching (Fuzzy) - New Layer
                                const partialMatch = (
                                    (pName.length > 3 && pName.includes(ccId)) ||
                                    (pCode.length > 3 && ccId.includes(pCode)) ||
                                    (ccId.length > 4 && ccId.includes(pName)) ||
                                    (ccId.length > 4 && pName.length > 3 && pName.includes(ccId))
                                );

                                // FORCE LINK: Dibell -> CC002 (Legacy Data Patch)
                                if (ccId === 'cc002' && (pName.includes('dibell') || pCode.includes('dibell'))) {
                                    return type === 'gasto';
                                }

                                return (exactMatch || partialMatch) && type === 'gasto';
                            })
                            .reduce((acc, curr) => acc + safeParse(curr.amount || curr.monto || curr.Monto), 0);

                        // Calculate total declared income from TWO sources:
                        // 1. Payment Statuses (structured EP data in project object)
                        // 2. Income Transactions (EPs stored as transactions with type='ingreso')

                        let totalDeclared = 0;

                        // SOURCE: Income Transactions linked to this project (type='ingreso')
                        const ingresoTransactions = allTransactions.filter(t => {
                            const type = (t.type || t.Tipo || '').toString().toLowerCase().trim();
                            const ccId = (t.costCenter || t.cost_center || '').toString().toLowerCase().trim();
                            const pId = (p.id || '').toString().toLowerCase().trim();
                            const pName = (p.name || '').toString().toLowerCase().trim();
                            const pCode = (p.code || '').toString().toLowerCase().trim();

                            const exactMatch = (ccId === pId || ccId === pName || ccId === pCode);
                            const partialMatch = (
                                (pName.length > 3 && pName.includes(ccId)) ||
                                (pCode.length > 3 && ccId.includes(pCode)) ||
                                (ccId.length > 4 && ccId.includes(pName))
                            );

                            // FORCE LINK: Dibell -> CC002
                            if (ccId === 'cc002' && (pName.includes('dibell') || pCode.includes('dibell'))) {
                                return type === 'ingreso';
                            }

                            return (exactMatch || partialMatch) && type === 'ingreso';
                        });

                        ingresoTransactions.forEach(t => {
                            totalDeclared += safeParse(t.amount || t.monto || t.Monto || 0);
                        });


                        // METRICS CALCULATION
                        // 1. Financial Progress (Gasto / Presupuesto)
                        const denominator = safeParse(presupuesto > 0 ? presupuesto : 1);
                        const financialPercent = denominator > 0 ? (ejecutado / denominator) * 100 : 0;

                        // 2. Profitability (using totalDeclared calculated above)
                        const profit = totalDeclared - ejecutado;
                        const margin = totalDeclared > 0 ? (profit / totalDeclared) * 100 : 0;

                        const card = document.createElement('div');
                        card.className = 'glass-card rounded-xl shadow p-6 relative group hover:shadow-lg transition border border-white/5';
                        card.innerHTML = `
                        <div class="flex justify-between items-start mb-4">
                            <div>
                                <h3 class="font-bold text-lg text-white">${name}</h3>
                                <p class="text-xs text-gray-400 font-mono">${code} - ${client}</p>
                            </div>
                            <span class="bg-${getStatusColor(status)}-500/10 text-${getStatusColor(status)}-500 text-[10px] px-2 py-0.5 rounded border border-${getStatusColor(status)}-500/20 font-black uppercase tracking-widest">${status}</span>
                        </div>
                        <div class="mb-4 space-y-2">
                            <!-- Budget -->
                            <div class="flex justify-between text-xs">
                                <span class="text-gray-400">Presupuesto Vigente</span>
                                <span class="font-bold text-white">$ ${presupuesto.toLocaleString('es-CL')}</span>
                            </div>

                            <!-- Operational Costs -->
                            <div class="flex justify-between text-sm">
                                <span class="text-gray-400">Costos Operativos</span>
                                <span class="font-bold text-red-500">$ ${ejecutado.toLocaleString('es-CL')}</span>
                            </div>
                             <div class="w-full bg-white/5 rounded-full h-1 mb-1">
                                <div class="bg-red-500 h-1 rounded-full shadow-[0_0_5px_rgba(239,68,68,0.5)]" style="width: ${Math.min(financialPercent, 100)}%"></div>
                            </div>
                            <p class="text-right text-[10px] text-gray-500 font-bold uppercase tracking-tight mb-2">${financialPercent.toFixed(1)}% Ejecutado</p>

                            <!-- Income from Payment Statuses -->
                             <div class="flex justify-between text-xs border-t border-white/5 pt-2">
                                <span class="text-gray-400">Ingresos Facturados (EP)</span>
                                <span class="font-bold text-blue-400">$ ${totalDeclared.toLocaleString('es-CL')}</span>
                            </div>

                            <!-- Net Profit -->
                             <div class="flex justify-between text-sm border-t border-white/5 pt-2 bg-white/[0.02] p-2 rounded">
                                <span class="text-gray-300 font-bold">Utilidad Neta</span>
                                <div class="text-right">
                                    <span class="font-bold ${profit >= 0 ? 'text-green-500' : 'text-red-500'} block">$ ${profit.toLocaleString('es-CL')}</span>
                                    <span class="text-[10px] text-gray-500 block font-bold">${margin.toFixed(1)}% MARGEN</span>
                                </div>
                            </div>
                        </div>
                        <div class="border-t border-white/5 pt-4 flex justify-between items-center mt-2">
                            <button onclick="openProjectDashboard('${p.id || p.ID}')" class="bg-blue-600 shadow-lg shadow-blue-500/20 text-white text-[10px] uppercase font-black px-4 py-2 rounded-lg hover:brightness-110 transition tracking-widest">
                                <i class="fas fa-chart-pie mr-2 text-white/50"></i> Dashboard
                            </button>
                            <div class="flex gap-2">
                                <button onclick="openProjectModal('${p.id || p.ID}')" class="bg-white/5 text-blue-400 hover:bg-blue-500/20 w-9 h-9 rounded-full flex items-center justify-center transition-all border border-white/5" title="Editar Proyecto">
                                    <i class="fas fa-pencil-alt text-sm"></i>
                                </button>
                                <button onclick="deleteProject('${p.id || p.ID}')" class="bg-white/5 text-red-500 hover:bg-red-500/20 w-9 h-9 rounded-full flex items-center justify-center transition-all border border-white/5" title="Eliminar Proyecto">
                                    <i class="fas fa-trash text-sm"></i>
                                </button>
                            </div>
                        </div>`;
                        container.appendChild(card);
                    });
                } catch (error) { console.error("Error loading projects", error); }
            }

            function getStatusColor(status) {
                if (status === 'Activo') return 'green';
                if (status === 'Pendiente') return 'yellow';
                if (status === 'Finalizado') return 'gray';
                return 'gray';
            }

            // DESHABILITADO: DATA IMPORT UTILITY (PRODUCTION)
            // Esta funcin creaba datos de ejemplo del proyecto Dibell
            /*
            async function importDibellData() {
                console.log('!! Starting Dibell project data import...');
                try {
                    const existingProjects = await AlpaHub.execute('getProjects') || [];
                    let dibellProject = existingProjects.find(p => p.id === 'alpa-001' || p.code === 'P-EA');
                    if (!dibellProject) {
                        dibellProject = {
                            id: 'CC002',
                            name: 'Proyecto Enap Dibell',
                            code: 'P-EA',
                            client: 'DIBELL',
                            clientRut: '76.000.000-0',
                            budget: 30589000,
                            status: 'Activo',
                            startDate: '2026-01-08',
                            responsible: 'Pablo Palominos',
                            paymentStatuses: [
                                { item: 1, description: 'ESTADO DE PAGO N1 - OBRAS CIVILES (GLOBAL)', unit: 'gl', quantity: 1, price: 4541503, kmStart: 0, kmEnd: 0 }
                            ]
                        };
                        await AlpaHub.execute('addProject', dibellProject);
                        console.log('? Dibell project created with CC002.');
                    } else {
                        const updates = {
                            client: 'DIBELL',
                            clientRut: '76.000.000-0',
                            budget: 30589000,
                            paymentStatuses: [
                                { item: 1, description: 'ESTADO DE PAGO N1 - OBRAS CIVILES (GLOBAL)', unit: 'gl', quantity: 1, price: 4541503, kmStart: 0, kmEnd: 0 }
                            ]
                        };
                        await AlpaHub.execute('updateProject', { id: dibellProject.id, updates: updates });
                        console.log('? Dibell project updated.');
                    }
                    const transactions = [
                        { date: '2026-01-08', type: 'Gasto', category: 'Materiales de Construccin', amount: 113420, description: 'COMPRA DE COLCHONES', costCenter: 'CC002' },
                        { date: '2026-01-07', type: 'Gasto', category: 'Materiales de Construccin', amount: 420000, description: 'ANTICIPO RODRIGO CAPACITACION HOTEL', costCenter: 'CC002' },
                        { date: '2026-01-09', type: 'Gasto', category: 'Materiales de Construccin', amount: 232200, description: 'compra de epp equipo rodrigo 6 personas', costCenter: 'CC002' },
                        { date: '2026-01-07', type: 'Gasto', category: 'Materiales de Construccin', amount: 8713, description: 'petroleo factura es de vaj y considera iep=neto', costCenter: 'CC002' },
                        { date: '2026-01-12', type: 'Gasto', category: 'Materiales de Construccin', amount: 17442, description: 'petroleo factura es de vaj y considera iep=neto', costCenter: 'CC002' },
                        { date: '2026-01-09', type: 'Gasto', category: 'Materiales de Construccin', amount: 8720, description: 'petroleo factura es de vaj y considera iep=neto', costCenter: 'CC002' },
                        { date: '2026-01-07', type: 'Gasto', category: 'Materiales de Construccin', amount: 9117, description: 'petroleo factura es de vaj y considera iep=neto', costCenter: 'CC002' },
                        { date: '2026-01-09', type: 'Gasto', category: 'Materiales de Construccin', amount: 24416, description: 'petroleo factura es de vaj y considera iep=neto', costCenter: 'CC002' },
                        { date: '2026-01-09', type: 'Gasto', category: 'Arriendo Maquinaria', amount: 500000, description: 'arriendo departamento', costCenter: 'CC002' },
                        { date: '2026-01-13', type: 'Gasto', category: 'Materiales de Construccin', amount: 20000, description: 'petroleo factura es de vaj y considera iep=neto', costCenter: 'CC002' },
                        { date: '2026-01-14', type: 'Gasto', category: 'Materiales de Construccin', amount: 50000, description: 'HERRAMIENTAS', costCenter: 'CC002' }
                    ];
                    let importedCount = 0;
                    for (const trans of transactions) {
                        await AlpaHub.execute('addTransaction', trans);
                        importedCount++;
                    }
                    console.log(`? Imported ${importedCount} transactions`);
                    console.log('!! Dibell project import completed successfully!');
                    await loadProjects();
                    await initCharts();
                    alert(`? Importacin Completa!\n\nProyecto: ${dibellProject.name}\nTransacciones: ${importedCount}\n\nEl dashboard ahora mostrar todas las estadsticas.`);
                } catch (error) {
                    console.error("Import Error:", error);
                    alert('? Error al importar: ' + error.message);
                }
            }
            window.importDibellData = importDibellData;
            */

            // DESHABILITADO: DIAGNOSTIC TOOL (PRODUCTION)
            /*
            async function checkDataStatus() {
                console.log('!! === DIAGNSTICO DE DATOS ===');
                const projects = await AlpaHub.execute('getProjects') || [];
                const transactions = await AlpaHub.execute('getTransactions') || [];
                console.log(`\n>>>  Proyectos en sistema: ${projects.length}`);
                projects.forEach(p => {
                    console.log(`  - ${p.name || p.Nombre} (ID: ${p.id}, Code: ${p.code || p.Codigo})`);
                });
                console.log(`\n!! Transacciones en sistema: ${transactions.length}`);
                const dibellTransactions = transactions.filter(t =>
                    t.costCenter === 'alpa-001' ||
                    t.costCenter === 'CC002' ||
                    t.costCenter === 'Proyecto Enap Dibell'
                );
                console.log(`  - Transacciones de Dibell: ${dibellTransactions.length}`);
                if (dibellTransactions.length > 0) {
                    const total = dibellTransactions.reduce((sum, t) => sum + parseFloat(t.amount || 0), 0);
                    console.log(`  - Total gastado: $${total.toLocaleString('es-CL')}`);
                    console.log(`\n!! Detalle transacciones Dibell:`);
                    dibellTransactions.forEach((t, i) => {
                        console.log(`  ${i + 1}. ${t.date} - $${parseFloat(t.amount || 0).toLocaleString('es-CL')} - ${t.description}`);
                    });
                } else {
                    console.log(`  !!  NO HAY TRANSACCIONES DE DIBELL`);
                    console.log(`  !!   Ejecuta: importDibellData()`);
                }
                console.log('\n=================================\n');
                return {
                    projects: projects.length,
                    transactions: transactions.length,
                    dibellTransactions: dibellTransactions.length,
                    needsImport: dibellTransactions.length === 0
                };
            }
            window.checkDataStatus = checkDataStatus;
            */

            // PROJECT ACTIONS
            function openProjectModal(id = null) {
                const form = document.getElementById('project-form');
                const modal = document.getElementById('project-modal');
                const title = document.getElementById('project-modal-title');

                if (!modal || !form || !title) {
                    console.error('Modal elements not found');
                    return;
                }

                form.reset();
                document.getElementById('p-id').value = '';
                document.getElementById('p-extra-budget-group').classList.add('hidden');
                document.getElementById('p-budget').disabled = false;
                document.getElementById('p-budget').classList.remove('bg-gray-100');

                if (id) {
                    // Try to find with both id and ID properties to support different data sources
                    const project = window.allProjects.find(p => p.id == id || p.ID == id);
                    if (!project) {
                        console.error('Project not found:', id);
                        alert('Error: Proyecto no encontrado');
                        return;
                    }
                    title.innerText = 'Editar Proyecto';
                    document.getElementById('p-id').value = project.id || project.ID;
                    document.getElementById('p-name').value = project.name || project.Nombre || '';
                    document.getElementById('p-code').value = project.code || project.Codigo || '';
                    document.getElementById('p-client').value = project.client || project.Cliente || '';
                    document.getElementById('p-client-rut').value = project.clientRut || project.ClienteRut || '';
                    document.getElementById('p-responsible').value = project.responsible || project.Responsable || '';
                    document.getElementById('p-status').value = project.status || project.Estado || '';
                    document.getElementById('p-start').value = (project.start || project.FechaInicio || '').split('T')[0];
                    document.getElementById('p-end').value = (project.end || project.FechaTermino || '').split('T')[0];
                    document.getElementById('p-budget').value = project.budget || project.Presupuesto || '';
                    document.getElementById('p-budget').disabled = true;
                    document.getElementById('p-budget').classList.add('bg-gray-100');
                    document.getElementById('p-extra-budget-group').classList.remove('hidden');
                } else {
                    title.innerText = 'Nuevo Proyecto';
                }
                modal.classList.remove('hidden');
                // Bug 1 fix: isEdit was used outside its declaration scope; use !!id directly
                document.getElementById('p-budget') && (document.getElementById('p-budget').required = !id);

                // Populate Clients Datalist from Core
                populateClientsDatalist();
            }

            // Project Dashboard Logic
            function prepareProjectDashboardChartData(transactions) {
                const categories = {};
                const timeline = {};

                transactions.forEach(t => {
                    // Category breakdown
                    const cat = t.category || t.categoria || 'Sin Categoria';
                    const amount = parseFloat(t.amount || t.monto || t.Monto || 0);

                    if (!categories[cat]) categories[cat] = 0;
                    categories[cat] += amount;

                    // Timeline (cumulative)
                    const date = (t.date || t.fecha || t.Fecha || '').split('T')[0];
                    if (date) {
                        const month = date.substring(0, 7); // YYYY-MM
                        if (!timeline[month]) timeline[month] = 0;
                        timeline[month] += amount;
                    }
                });

                // Format for Chart.js
                return {
                    categories: {
                        labels: Object.keys(categories),
                        data: Object.values(categories)
                    },
                    timeline: {
                        labels: Object.keys(timeline).sort(),
                        data: Object.keys(timeline).sort().map(k => timeline[k]) // Need cumulative logic if desired, currently monthly total
                    }
                };
            }

            async function populateClientsDatalist() {
                try {
                    const clients = await AlpaHub.getClients() || [];
                    window.allHubClients = clients; // Reference for auto-fill
                    const dl = document.getElementById('clients-datalist');
                    dl.innerHTML = '';
                    clients.forEach(c => {
                        const opt = document.createElement('option');
                        opt.value = c.name || c.Nombre;
                        dl.appendChild(opt);
                    });
                } catch (e) { console.warn("Error loading clients", e); }
            }

            function renderProjectSummary(projects) {
                const tbody = document.getElementById('project-summary-body');
                if (!tbody) return;

                if (!projects || projects.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-8 text-center text-gray-400 italic">No hay proyectos activos en este perodo.</td></tr>';
                    return;
                }

                tbody.innerHTML = '';

                // Get all transactions to calculate per-project spent
                const transactions = window.allTransactions || [];

                projects.forEach(p => {
                    const budget = parseFloat(p.budget || p.Presupuesto || 0);
                    const pId = p.id || p.ID;
                    const pCode = p.code || p.Codigo;
                    const pName = p.name || p.Nombre;

                    // Calculate real spent for this project accurately
                    const projectSpent = transactions.filter(t => {
                        if (t.status === 'Anulada') return false;
                        const type = (t.type || t.Tipo || 'Gasto').toLowerCase();
                        if (type !== 'gasto' && type !== 'pago') return false;

                        const cc = (t.costCenter || t.centroCostoId || t.CentroCostoID || t.ProyectoID || '').toLowerCase();
                        // Prioritize ID match, then Code match. Name match ONLY if ID/Code are not strictly numeric or if no other match found.
                        if (cc == String(pId).toLowerCase()) return true;
                        if (pCode && cc == String(pCode).toLowerCase()) return true;
                        if (pName && cc == pName.toLowerCase() && isNaN(cc)) return true; // Only match name if not numeric
                        return false;
                    }).reduce((sum, t) => sum + (parseFloat(t.amount || t.monto || t.Monto) || 0), 0);

                    const balance = budget - projectSpent;
                    const healthPct = budget > 0 ? (projectSpent / budget) * 100 : (projectSpent > 0 ? 101 : 0);

                    let healthBadge = '';
                    if (healthPct < 70) {
                        healthBadge = `<span class="px-2 py-0.5 rounded-full bg-green-100 text-green-700 text-xs font-bold">SALUDABLE</span>`;
                    } else if (healthPct < 90) {
                        healthBadge = `<span class="px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-700 text-xs font-bold">PRECAUCIN</span>`;
                    } else {
                        healthBadge = `<span class="px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-xs font-bold">SOBRECOSTO</span>`;
                    }

                    const tr = document.createElement('tr');
                    tr.className = "hover:bg-gray-50/50 transition-colors";
                    tr.innerHTML = `
                        <td class="px-6 py-4">
                            <div class="font-bold text-gray-800">${pName}</div>
                            <div class="text-xs text-gray-400 font-mono uppercase">${pCode || 'Sin Cdigo'}</div>
                        </td>
                        <td class="px-6 py-4 text-right font-medium">$ ${budget.toLocaleString('es-CL')}</td>
                        <td class="px-6 py-4 text-right text-gray-600">$ ${projectSpent.toLocaleString('es-CL')}</td>
                        <td class="px-6 py-4 text-right font-bold ${balance < 0 ? 'text-red-600' : 'text-slate-700'}">$ ${balance.toLocaleString('es-CL')}</td>
                        <td class="px-6 py-4 text-center">${healthBadge}</td>
                        <td class="px-6 py-4 text-right">
                            <button onclick="openProjectDashboard('${pId}')" class="text-blue-600 hover:text-blue-800 text-xs font-bold uppercase tracking-widest">Ver Detalles</button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            }

            async function loadCostCenters() {
                try {
                    const projects = await AlpaHub.getProjects() || [];
                    const selectors = ['t-cost-center', 'er-cc'];
                    selectors.forEach(selId => {
                        const sel = document.getElementById(selId);
                        if (!sel) return;
                        const current = sel.value;
                        sel.innerHTML = '<option value="General">📁 General</option>';
                        projects
                            .filter(p => p.status !== 'Cancelado')
                            .sort((a, b) => (a.name || '').localeCompare(b.name || '', 'es'))
                            .forEach(p => {
                                const id = p.id || p.ID;
                                const name = p.name || p.Nombre || id;
                                const code = p.code || p.Codigo || '';
                                const opt = document.createElement('option');
                                opt.value = id;
                                opt.textContent = code ? `[${code}] ${name}` : name;
                                sel.appendChild(opt);
                            });
                        if (current && [...sel.options].some(o => o.value === current)) sel.value = current;
                    });
                } catch (e) { console.warn("Error loading cost centers", e); }
            }

            function onClientInput(input) {
                const val = input.value;
                const clients = window.allHubClients || [];
                const found = clients.find(c => (c.name || c.Nombre) === val);
                if (found) {
                    document.getElementById('p-client-rut').value = found.rut || found.Rut || '';
                }
            }

            async function submitProject(e) {
                e.preventDefault();
                const btn = e.target.querySelector('button[type="submit"]');
                const originalText = btn.innerText;
                btn.innerText = 'Guardando...';
                btn.disabled = true;

                const id = document.getElementById('p-id').value;
                const isEdit = !!id;
                const payload = {
                    id: id,
                    name: document.getElementById('p-name').value,
                    code: document.getElementById('p-code').value,
                    client: document.getElementById('p-client').value,
                    clientRut: document.getElementById('p-client-rut').value,
                    responsible: document.getElementById('p-responsible').value,
                    status: document.getElementById('p-status').value,
                    start: document.getElementById('p-start').value,
                    end: document.getElementById('p-end').value,
                };

                if (!isEdit) {
                    payload.budget = document.getElementById('p-budget').value;
                } else {
                    const extra = document.getElementById('p-extra-budget').value;
                    if (extra) {
                        const projects = await AlpaHub.getProjects() || [];
                        const currentProj = projects.find(p => p.id == id);
                        if (currentProj) {
                            payload.budget = parseFloat(currentProj.budget || 0) + parseFloat(extra);
                        }
                    }
                }

                btn.innerHTML = '<i class="fas fa-circle-notch fa-spin mr-2"></i>Guardando...';
                btn.disabled = true;

                try {
                    if (isEdit) {
                        await AlpaHub.execute('updateProject', { id, updates: payload });
                    } else {
                        await AlpaHub.execute('addProject', payload);
                    }

                    // Optional: Sync with GAS
                    if (SCRIPT_URL) {
                        fetch(SCRIPT_URL, {
                            method: 'POST',
                            redirect: 'follow',
                            headers: { 'Content-Type': 'text/plain;charset=utf-8' },
                            body: JSON.stringify({ action: isEdit ? 'update_project' : 'add_project', payload: payload })
                        }).catch(err => console.error("GAS Sync Fail (Optional)", err));
                    }

                    document.getElementById('project-modal').classList.add('hidden');
                    loadProjects();
                    AlpaHub.showNotification('Proyecto guardado en el Hub', 'success');
                } catch (error) {
                    console.error('Error saving project', error);
                    AlpaHub.showNotification('Error al guardar: ' + (error.message || 'Fallo Supabase'), 'error');
                    btn.innerText = originalText;
                    btn.disabled = false;
                    return;
                } finally {
                    btn.innerText = originalText;
                    btn.disabled = false;
                }
            }

            async function deleteProject(id) {
                if (!confirm('Ests seguro de eliminar este proyecto? Esta accin no se puede deshacer.')) return;
                try {
                    await fetch(SCRIPT_URL, {
                        method: 'POST',
                        redirect: 'follow',
                        headers: { 'Content-Type': 'text/plain;charset=utf-8' },
                        body: JSON.stringify({ action: 'delete_project', id: id })
                    });
                    loadProjects();
                } catch (error) { console.error("Error deleting", error); }
            }

            // DASHBOARD PROJECT (Consolidated)
            let pdCatChart = null;
            let pdLineChart = null;

            function renderDashboardCharts(data) {
                // Safety Check: Verify data availability
                if (!data || !data.timeline) {
                    console.warn("Dashboard Charts: Missing data for charts. Skipping render.");

                    // Optional: Render user feedback in canvas parent
                    const canvasCat = document.getElementById('pd-cat-chart');
                    if (canvasCat) {
                        canvasCat.parentElement.innerHTML = '<div class="h-full flex items-center justify-center text-gray-400 text-xs italic">Sin datos suficientes para grficos</div>';
                    }
                    const canvasLine = document.getElementById('pd-line-chart');
                    if (canvasLine) {
                        canvasLine.parentElement.innerHTML = '<div class="h-full flex items-center justify-center text-gray-400 text-xs italic">Sin datos suficientes para grficos</div>';
                    }
                    return;
                }

                const canvasCat = document.getElementById('pd-cat-chart');
                if (!canvasCat) return;
                const ctxCat = canvasCat.getContext('2d');
                if (pdCatChart) pdCatChart.destroy();
                pdCatChart = new Chart(ctxCat, {
                    type: 'doughnut',
                    data: {
                        labels: data.categories.labels,
                        datasets: [{ data: data.categories.data, backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16'], borderWidth: 0 }]
                    },
                    options: { responsive: true, maintainAspectRatio: false }
                });

                const canvasLine = document.getElementById('pd-line-chart');
                if (!canvasLine) return;
                const ctxLine = canvasLine.getContext('2d');
                if (pdLineChart) pdLineChart.destroy();
                pdLineChart = new Chart(ctxLine, {
                    type: 'line',
                    data: {
                        labels: data.timeline.labels,
                        datasets: [{
                            label: 'Gasto Acumulado',
                            data: data.timeline.data,
                            borderColor: '#2563eb',
                            tension: 0.1,
                            fill: true,
                            backgroundColor: 'rgba(37, 99, 235, 0.1)'
                        }]
                    },
                    options: { responsive: true, maintainAspectRatio: false }
                });
            }

            // DOCUMENT UPLOAD
            async function uploadFileToDrive(fileInputId) {
                const input = document.getElementById(fileInputId);
                if (input.files.length === 0) return null;
                const file = input.files[0];
                const reader = new FileReader();
                return new Promise((resolve) => {
                    reader.onload = async function (e) {
                        const content = e.target.result.split(',')[1];
                        try {
                            const response = await fetch(SCRIPT_URL, {
                                method: 'POST',
                                headers: { 'Content-Type': 'text/plain;charset=utf-8' },
                                redirect: 'follow',
                                body: JSON.stringify({
                                    action: 'upload_file',
                                    payload: { fileContent: content, fileName: file.name, mimeType: file.type }
                                })
                            });
                            resolve({ success: true, fileName: file.name });
                        } catch (err) { resolve(null); }
                    };
                    reader.readAsDataURL(file);
                });
            }

            // DATA VALIDATION HELPERS
            function cleanRUT(rut) {
                if (!rut) return '';
                // Remove dots and hyphens, convert to uppercase
                return rut.toString().replace(/[.-]/g, '').toUpperCase();
            }

            function validateFieldRUT(input) {
                const isValid = window.AlpaCore ? AlpaCore.validateRUT(input.value) : true;
                const error = document.getElementById('t-rut-error');
                if (!isValid && input.value.trim() !== '') {
                    input.classList.add('border-red-500', 'bg-red-50');
                    input.classList.remove('border-green-500', 'bg-green-50');
                    if (error) error.classList.remove('hidden');
                } else if (input.value.trim() !== '') {
                    input.classList.remove('border-red-500', 'bg-red-50');
                    input.classList.add('border-green-500', 'bg-green-50');
                    if (error) error.classList.add('hidden');
                } else {
                    input.classList.remove('border-red-500', 'bg-red-50', 'border-green-500', 'bg-green-50');
                    if (error) error.classList.add('hidden');
                }
                return isValid;
            }

            async function submitTransaction(event) {
                event.preventDefault();

                const form = event.target;
                const btn = form.querySelector('button[type="submit"]');
                const originalHTML = btn.innerHTML;

                const center = document.getElementById('t-cost-center').value;
                const type = document.getElementById('t-type').value;
                const category = document.getElementById('t-category').value;
                const amount = parseFloat(document.getElementById('t-amount').value) || 0;
                const date = document.getElementById('t-date').value;
                const desc = document.getElementById('t-desc').value;
                const rut = document.getElementById('t-rut').value;

                // VALIDATION
                if (!date || !amount || !desc || !center) {
                    AlpaHub.showNotification("Complete todos los campos obligatorios (Fecha, Monto, Descripcion, Centro de Costo).", 'warning');
                    return;
                }

                if (rut && window.AlpaCore && !AlpaCore.validateRUT(rut)) {
                    AlpaHub.showNotification("El RUT ingresado no es vlido. Favor corregir.", 'error');
                    document.getElementById('t-rut').focus();
                    return;
                }

                btn.innerHTML = '<i class="fas fa-circle-notch fa-spin mr-2"></i>Guardando...';
                btn.disabled = true;

                let fileInfo = null;
                if (document.getElementById('t-file').files.length > 0) {
                    btn.innerHTML = '<i class="fas fa-circle-notch fa-spin mr-2"></i>Subiendo archivo...';
                    fileInfo = await uploadFileToDrive('t-file');
                }

                let finalCategory = category === 'OTROS' ? document.getElementById('t-category-other').value : category;

                const source = document.getElementById('t-source').value;
                const payload = {
                    date: date,
                    type: type,
                    category: category,
                    amount: amount,
                    description: desc + (fileInfo ? ` [Doc: ${fileInfo.fileName}]` : ''),
                    costCenter: center,
                    usuario: JSON.parse(localStorage.getItem(USER_SESSION_KEY) || parent.localStorage.getItem(USER_SESSION_KEY)).user.email,
                    docNumber: document.getElementById('t-doc-number').value,
                    rut: cleanRUT(rut),
                    docType: document.getElementById('t-doc-type').value,
                    ProyectoID: center,
                    project_id: center,
                    source_of_funds: source,
                    reimbursement_status: (type === 'Gasto' && source !== 'company') ? 'pending' : 'not_applicable'
                };

                try {
                    const success = await AlpaHub.addTransaction(payload);
                    AlpaHub.showNotification("Transacción registrada correctamente.", 'success');
                    form.reset();
                    toggleTransactionForm();
                    loadTransactions();
                    initCharts();
                } catch (error) {
                    console.error("Error saving transaction", error);
                    AlpaHub.showNotification("Error al guardar: " + error.message, 'error');
                } finally {
                    btn.innerHTML = originalHTML;
                    btn.disabled = false;
                }
            }

            // --- EDIT TRANSACTION LOGIC ---
            function openEditTransactionModal(id) {
                const t = window.allTransactions.find(x => x.ID === id || x.id === id);
                if (!t) {
                    AlpaHub.showNotification("Error: No se encontr la transaccin.", "error");
                    return;
                }

                document.getElementById('edit-tx-id').value = id;
                document.getElementById('edit-tx-type').value = t.Tipo || t.type || 'Gasto';

                // Format date for input type="date"
                let dateStr = t.Fecha || t.date || '';
                if (dateStr.length > 10) dateStr = dateStr.substring(0, 10);
                document.getElementById('edit-tx-date').value = dateStr;

                // Populate Cost Centers
                const ccSelect = document.getElementById('edit-tx-cc');
                ccSelect.innerHTML = '<option value="">Seleccione Proyecto / C.Costo</option>';
                const projects = window.allProjects || [];
                projects.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.id || p.ID;
                    opt.textContent = `${p.code || 'N/A'} - ${p.name || p.Nombre}`;
                    ccSelect.appendChild(opt);
                });

                // Add default non-project cost centers
                const extraCCs = ['General', 'Caja Chica', 'Reembolso'];
                extraCCs.forEach(cc => {
                    if (!projects.find(p => (p.id || p.ID) === cc)) {
                        const opt = document.createElement('option');
                        opt.value = cc;
                        opt.textContent = cc;
                        ccSelect.appendChild(opt);
                    }
                });

                // Set active cost center
                const currentCC = t.CentroCostoID || t.centroCostoId || t.costCenter || t.ProyectoID || '';
                if (currentCC && [...ccSelect.options].some(o => o.value === currentCC)) {
                    ccSelect.value = currentCC;
                }

                document.getElementById('edit-tx-category').value = t.Categoria || t.category || '';
                document.getElementById('edit-tx-amount').value = safeParse(t.Monto || t.amount || t.monto);
                document.getElementById('edit-tx-desc').value = t.Descripcion || t.description || '';

                document.getElementById('edit-transaction-modal').classList.remove('hidden');
            }

            function closeEditTransactionModal() {
                document.getElementById('edit-transaction-modal').classList.add('hidden');
            }

            async function submitEditTransaction(event) {
                event.preventDefault();
                const btn = document.getElementById('btn-submit-edit-tx');
                const originalHtml = btn.innerHTML;

                const id = document.getElementById('edit-tx-id').value;
                const type = document.getElementById('edit-tx-type').value;
                const date = document.getElementById('edit-tx-date').value;
                const cc = document.getElementById('edit-tx-cc').value;
                const category = document.getElementById('edit-tx-category').value;
                const amount = document.getElementById('edit-tx-amount').value;
                const desc = document.getElementById('edit-tx-desc').value;

                if (!id || !type || !date || !cc || !category || !amount || !desc) {
                    AlpaHub.showNotification("Por favor, complete todos los campos.", "warning");
                    return;
                }

                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';
                btn.disabled = true;

                try {
                    const updates = {
                        Tipo: type,
                        type: type,
                        Fecha: date,
                        date: date,
                        CentroCostoID: cc,
                        centroCostoId: cc,
                        costCenter: cc,
                        ProyectoID: cc,
                        Categoria: category,
                        category: category,
                        Monto: parseFloat(amount),
                        amount: parseFloat(amount),
                        monto: parseFloat(amount),
                        Descripcion: desc,
                        description: desc
                    };

                    const result = await AlpaHub.execute('updateTransaction', { id, updates });

                    if (result && !result.error) {
                        AlpaHub.showNotification("Transaccin actualizada con xito.", "success");
                        closeEditTransactionModal();

                        // Fallback sync to GAS if configured
                        if (SCRIPT_URL) {
                            fetch(SCRIPT_URL, {
                                method: 'POST',
                                headers: { 'Content-Type': 'text/plain;charset=utf-8' },
                                body: JSON.stringify({ action: 'update_transaction', payload: { id, updates } })
                            }).catch(e => console.error("GAS auto-sync update_transaction failed", e));
                        }

                        loadTransactions();
                        initCharts();
                    } else {
                        throw new Error(result?.error || 'Fall la actualizacin');
                    }
                } catch (e) {
                    console.error("Error updating transaction", e);
                    AlpaHub.showNotification("Error: " + e.message, "error");
                } finally {
                    btn.innerHTML = originalHtml;
                    btn.disabled = false;
                }
            }

            async function submitExpenseReport(e) {
                e.preventDefault();
                const btn = e.target.querySelector('button[type="submit"]');
                const originalHTML = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-circle-notch fa-spin mr-2"></i>Enviando...';
                btn.disabled = true;

                try {
                    const payload = {
                        employee: document.getElementById('er-employee').value,
                        amount: document.getElementById('er-amount').value,
                        ccId: document.getElementById('er-cc').value,
                        observations: document.getElementById('er-obs').value
                    };

                    const result = await AlpaHub.execute('registerExpenseReport', payload);

                    if (result && !result.error) {
                        AlpaHub.showNotification('Rendicion enviada con xito', 'success');
                        document.getElementById('new-report-modal').classList.add('hidden');
                        document.getElementById('expense-form').reset();

                        // Optional: Refresh transactions if showing them in this module
                        if (typeof loadTransactions === 'function') loadTransactions();
                        if (typeof loadCharts === 'function') loadCharts();
                    } else {
                        throw new Error(result?.error || 'Error desconocido');
                    }
                } catch (error) {
                    console.error("ALPA ERROR: Error al enviar Rendicion:", error);
                    AlpaHub.showNotification('Error al enviar la Rendicion: ' + error.message, 'error');
                } finally {
                    btn.innerHTML = originalHTML;
                    btn.disabled = false;
                }
            }

            function handleCategoryChange() {
                const select = document.getElementById('t-category');
                const otherInput = document.getElementById('t-category-other');
                if (select.value === 'OTROS') {
                    otherInput.classList.remove('hidden');
                    otherInput.required = true;
                } else {
                    otherInput.classList.add('hidden');
                    otherInput.required = false;
                    otherInput.value = '';
                }
                calculateTaxes();
            }

            async function checkDuplicate() {
                // Simplified
                const numero = document.getElementById('t-doc-number').value;
                if (!numero) return;
                // Logic here
            }

            async function deleteTransaction(id) {
                const justification = prompt("⚠️ Accion Auditada ⚠️\n\nPor seguridad, esta transaccin no se borrar, quedar marcada como 'Anulada'.\n\nIngrese el motivo de la anulacin:");

                if (!justification) return; // Cancel if no reason provided

                try {
                    const tx = (window.allTransactions || []).find(t => t.id == id || t.ID == id);
                    const currentDesc = tx ? tx.description || tx.Descripcion || '' : '';
                    const newDesc = `[Anulada: ${justification}] ${currentDesc}`.trim();

                    const success = await AlpaHub.execute('updateTransaction', {
                        id: id,
                        updates: {
                            status: 'Anulada',
                            Estado: 'Anulada',
                            description: newDesc,
                            Descripcion: newDesc
                        }
                    });

                    if (success) {
                        AlpaHub.showNotification('Transaccin anulada exitosamente', 'success');
                        loadTransactions();
                    } else {
                        AlpaHub.showNotification('Error al anular transaccin', 'error');
                    }
                } catch (error) {
                    console.error(error);
                    AlpaHub.showNotification('Error de conexion al anular', 'error');
                }
            }
            window.deleteTransaction = deleteTransaction;

            function updateFileStatus() {
                const input = document.getElementById('t-file');
                const badge = document.getElementById('file-status-badge');
                if (input.files.length > 0) {
                    const fileName = input.files[0].name;
                    const shortName = fileName.length > 22 ? fileName.substring(0, 20) + '' : fileName;
                    badge.className = "flex items-center gap-2 px-3 py-2 rounded-lg bg-green-50 text-green-600 border border-green-200 text-xs font-bold transition-all duration-300 shadow-sm";
                    badge.innerHTML = `<i class="fa-solid fa-paperclip"></i> <span title="${fileName}">${shortName}</span>`;
                } else {
                    badge.className = "flex items-center gap-2 px-3 py-2 rounded-lg bg-orange-50 text-orange-600 border border-orange-200 text-xs font-bold transition-all duration-300";
                    badge.innerHTML = '<i class="fa-solid fa-clock"></i> <span>Sin archivo</span>';
                }
            }

            function toggleTransactionForm() {
                const container = document.getElementById('transaction-form-container');
                container.classList.toggle('hidden');
                if (container.classList.contains('hidden')) {
                    document.getElementById('transaction-form').reset();
                    updateFileStatus(); // Reset badge
                }
            }

            let currentAttachId = null;

            function openAttachModal(id) {
                currentAttachId = id;
                const t = window.allTransactions.find(x => x.ID === id);
                if (!t) return;
                document.getElementById('attach-info').innerText = `${t.Descripcion} - $${parseInt(t.Monto).toLocaleString('es-CL')}`;
                document.getElementById('attach-modal').classList.remove('hidden');
                document.getElementById('attach-file').value = '';
            }

            async function attachDocumentToTransaction() {
                const btn = document.getElementById('btn-do-attach');
                const fileInput = document.getElementById('attach-file');

                if (fileInput.files.length === 0) {
                    alert("Por favor selecciona un archivo");
                    return;
                }

                const originalText = btn.innerText;
                btn.innerText = 'Subiendo...';
                btn.disabled = true;

                try {
                    // 1. Upload to Drive
                    const fileInfo = await uploadFileToDrive('attach-file');
                    if (!fileInfo) throw new Error("Error subiendo el archivo");

                    // 2. Identify the transaction
                    const t = window.allTransactions.find(x => x.ID === currentAttachId);
                    const userSession = JSON.parse(localStorage.getItem(USER_SESSION_KEY));
                    const userEmail = userSession ? userSession.user.email : 'Unknown';

                    // 3. Add the "new" transaction (with the same data but + Doc)
                    const payload = {
                        fecha: new Date(t.Fecha).toISOString().split('T')[0],
                        tipo: t.Tipo,
                        Categoria: t.Categoria || t.category || '',
                        monto: t.Monto,
                        Descripcion: t.Descripcion + ` [Doc: ${fileInfo.fileName}]`,
                        centroCostoId: t.CentroCostoID,
                        usuario: userEmail,
                        numeroDocumento: t.NumeroDocumento || '',
                        rutEmisor: t.RutEmisor || '',
                        tipoDocumento: t.TipoDocumento || ''
                    };

                    const response = await fetch(SCRIPT_URL, {
                        method: 'POST',
                        redirect: 'follow',
                        headers: { 'Content-Type': 'text/plain;charset=utf-8' },
                        body: JSON.stringify({ action: 'add_transaction', payload: payload })
                    });

                    // 4. Anulate the old transaction
                    await fetch(SCRIPT_URL, {
                        method: 'POST',
                        headers: { 'Content-Type': 'text/plain;charset=utf-8' },
                        redirect: 'follow',
                        body: JSON.stringify({
                            action: 'delete_transaction',
                            id: currentAttachId,
                            payload: {
                                justification: "Actualizacin de respaldo (Sistema Automtico)",
                                usuario: userEmail
                            }
                        })
                    });

                    alert("Respaldo subido y transaccin actualizada correctamente.");
                    document.getElementById('attach-modal').classList.add('hidden');
                    loadTransactions();
                    initCharts();

                } catch (error) {
                    console.error(error);
                    alert("Hubo un error al procesar el respaldo.");
                } finally {
                    btn.innerText = originalText;
                    btn.disabled = false;
                }
            }
            async function resetSystemData() {
                const firstConfirmation = confirm("⚠️ ADVERTENCIA CRITICA!\n\nEsts a punto de borrar TODAS las transacciones, proyectos y documentos del sistema para iniciar la contabilidad real.\n\nEsts absolutamente seguro?");

                if (!firstConfirmation) return;

                const secondConfirmation = prompt("Esta accin NO se puede deshacer.\n\nPara confirmar, escribe la palabra 'BORRAR' en maysculas:");

                if (secondConfirmation !== 'BORRAR') {
                    alert("Operacin cancelada. El texto no coincide.");
                    return;
                }

                try {
                    const userSession = JSON.parse(localStorage.getItem(USER_SESSION_KEY));
                    const userEmail = userSession ? userSession.user.email : 'Unknown';

                    const response = await fetch(SCRIPT_URL, {
                        method: 'POST',
                        headers: { 'Content-Type': 'text/plain;charset=utf-8' },
                        redirect: 'follow',
                        body: JSON.stringify({
                            action: 'reset_accounting_data',
                            payload: { usuario: userEmail }
                        })
                    });

                    const result = await response.json();
                    if (result.status === 'success') {
                        // Also clear local workflows if possible
                        // Also clear local workflows securely
                        await AlpaHub.execute('clearPendingWorkflows');

                        alert("? " + result.message + ". El sistema se reiniciar.");
                        window.location.reload();
                    } else {
                        alert("? Error: " + result.message);
                    }
                } catch (error) {
                    console.error(error);
                    alert("Error de conexion con el servidor");
                }
            }

            async function clearLocalWorkflows() {
                if (confirm("Limpiar todas las colas de proyectos pendientes del Cotizador?")) {
                    await AlpaHub.execute('clearPendingWorkflows');
                    checkPendingProjects();
                    alert("Colas locales limpias.");
                }
            }

            // --- PAYMENT STATUSES (ESTADOS DE PAGO) ---
            // Global context already set by openProjectDashboard: currentProjectId

            function switchProjectTab(tabName) {
                // Only 'resumen' remains, ensure it is active
                const btnResumen = document.getElementById('tab-btn-resumen');
                if (btnResumen) {
                    btnResumen.className = "py-3 px-1 border-b-2 border-blue-600 font-bold text-blue-600 text-sm";
                }
                const tabResumen = document.getElementById('pd-tab-resumen');
                if (tabResumen) tabResumen.classList.remove('hidden');
            }

            function showIntelligentAnalysis() {
                const analysisSection = document.getElementById('intelligent-analysis');
                if (analysisSection) {
                    analysisSection.classList.toggle('hidden');

                    // Scroll to the analysis section if it's being shown
                    if (!analysisSection.classList.contains('hidden')) {
                        analysisSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    }
                }
            }

            function printAnalysisReport() {
                console.log("ALPA DEBUG: printAnalysisReport() triggered.");
                const printFormat = document.getElementById('analysis-print-format');
                if (!printFormat) {
                    console.error("ALPA DEBUG: Print template #analysis-print-format NOT FOUND.");
                    alert("Error: No se encontr la plantilla de impresion.");
                    return;
                }

                // Helper to safely set innerText
                const safeSetText = (id, text) => {
                    const el = document.getElementById(id);
                    if (el) el.innerText = text;
                    else console.warn(`ALPA DEBUG: Element #${id} not found for text sync.`);
                };

                // Helper to safely set innerHTML
                const safeSetHTML = (id, html) => {
                    const el = document.getElementById(id);
                    if (el) el.innerHTML = html;
                    else console.warn(`ALPA DEBUG: Element #${id} not found for HTML sync.`);
                };

                console.log("ALPA DEBUG: Starting data synchronization to print template.");
                // 1. Basic Info
                safeSetText('pa-date-display', `Fecha: ${new Date().toLocaleDateString('es-CL')}`);
                safeSetText('pa-project-name', document.getElementById('pd-title')?.innerText || '--');
                safeSetText('pa-project-code', document.getElementById('pd-subtitle')?.innerText || '--');

                // 2. Sync Health Indicators (Dots & Texts)
                const syncDot = (sourceId, targetId, textSourceId, targetTextId) => {
                    const src = document.getElementById(sourceId);
                    const tgt = document.getElementById(targetId);
                    const srcTxt = document.getElementById(textSourceId);
                    const tgtTxt = document.getElementById(targetTextId);

                    if (src && tgt) {
                        const colorClass = Array.from(src.classList).find(c => c.startsWith('bg-')) || 'bg-gray-400';
                        tgt.className = `w-10 h-10 rounded-full mx-auto mb-3 border-2 border-white shadow-sm ${colorClass}`;
                    }
                    if (srcTxt && tgtTxt) tgtTxt.innerText = srcTxt.innerText;
                };

                syncDot('health-financial-indicator', 'pa-health-fin-dot', 'health-financial-text', 'pa-health-fin-text');
                syncDot('health-budget-indicator', 'pa-health-bud-dot', 'health-budget-text', 'pa-health-bud-text');
                syncDot('health-profit-indicator', 'pa-health-pro-dot', 'health-profit-text', 'pa-health-pro-text');

                // 3. Sync Lists (Risks & Recs)
                const risksSrc = document.getElementById('risk-areas-list');
                const recsSrc = document.getElementById('recommendations-list');
                if (risksSrc) safeSetHTML('pa-risks-list', risksSrc.innerHTML);
                if (recsSrc) safeSetHTML('pa-recs-list', recsSrc.innerHTML);

                // 4. Totals and Projections
                const projectionEl = document.getElementById('projection-profit') || document.getElementById('pd-margin');
                if (projectionEl) safeSetText('pa-project-summary-total', projectionEl.innerText);

                // 5. CONVERT CHARTS TO IMAGES
                console.log("ALPA DEBUG: Converting charts to images...");
                try {
                    const catCanvas = document.getElementById('pd-cat-chart');
                    const lineCanvas = document.getElementById('pd-line-chart');
                    const catImg = document.getElementById('pa-chart-cat-img');
                    const lineImg = document.getElementById('pa-chart-line-img');

                    if (catCanvas && catImg) {
                        catImg.src = catCanvas.toDataURL('image/png');
                        console.log('ALPA DEBUG: Category chart converted.');
                    }
                    if (lineCanvas && lineImg) {
                        lineImg.src = lineCanvas.toDataURL('image/png');
                        console.log("ALPA DEBUG: Execution chart converted.");
                    }
                } catch (chartErr) {
                    console.warn("ALPA DEBUG: Could not convert charts for printing", chartErr);
                }

                // 6. Execution Flow
                console.log("ALPA DEBUG: Showing print format and preparing dialog...");
                printFormat.classList.remove('hidden');

                // Ensure visibility is forced via inline styles for maximum compatibility
                printFormat.style.display = 'block';
                printFormat.style.visibility = 'visible';

                // Small delay to ensure images are processed by the browser before the print dialog opens
                setTimeout(() => {
                    console.log("ALPA DEBUG: Calling window.print()");
                    window.print();

                    // Cleanup: wait longer to ensure spooling is done
                    setTimeout(() => {
                        printFormat.classList.add('hidden');
                        printFormat.style.display = '';
                        printFormat.style.visibility = '';
                        console.log("ALPA DEBUG: Print cycle finished, template hidden.");
                    }, 2000);
                }, 1200);
            }

            // Legacy Payment Status functions removed (migrated to dedicated module)

            function formatLocalCurrency(val) {
                return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(val);
            }

            // ====================================
            // PROJECT DASHBOARD FUNCTIONS
            // ====================================

            async function openProjectDashboard(projectId) {
                currentProjectId = projectId;
                const modal = document.getElementById('project-dashboard-modal');

                // Validate that we are targeting the correct 'New Editor' modal
                if (!document.getElementById('pd-title')) {
                    console.error("Critical: Project Dashboard Editor Modal (pd-title) not found. Check HTML structure.");
                    AlpaHub.showNotification('Error: Modal de Dashboard no encontrado o versin incompatible.', 'error');
                    return;
                }

                modal.classList.remove('hidden');

                try {
                    // Get financial data from local core
                    const data = await AlpaHub.execute('getProjectFinancials', { id: projectId });

                    if (data.error) {
                        alert('Error: ' + data.error);
                        modal.classList.add('hidden');
                        return;
                    }

                    const { project, metrics, history, charts } = data;

                    if (modal) {
                        document.getElementById('pd-title').innerText = project.name || project.Nombre;
                        document.getElementById('pd-subtitle').innerText = `${project.code || project.Codigo || 'N/A'} - ${project.client || project.Cliente || 'Sin Cliente'}`;

                        // Financials
                        const budget = parseFloat(project.budget || project.Presupuesto || 0);

                        // Filter transactions
                        const projectTransactions = (window.allTransactions || []).filter(t => {
                            const ccId = (t.costCenter || t.centroCostoId || t.CentroCostoID || t.ProyectoID || '').toString().toLowerCase().trim();
                            const pName = (project.name || project.Nombre || '').toString().toLowerCase().trim();
                            const pCode = (project.code || project.Codigo || '').toString().toLowerCase().trim();
                            const pId = (project.id || project.ID || '').toString().toLowerCase().trim();

                            // Robust matching (Same as loadProjects)
                            const exactMatch = (ccId === pId || ccId === pName || ccId === pCode ||
                                (pCode && ccId === pCode) ||
                                (pName && ccId === pName) ||
                                (ccId === 'alpa-001' && (pId === 'cc002')));

                            // Partial Matching (Fuzzy)
                            const partialMatch = (
                                (pName.length > 3 && pName.includes(ccId)) ||
                                (pCode.length > 3 && ccId.includes(pCode)) ||
                                (ccId.length > 4 && ccId.includes(pName)) ||
                                (ccId.length > 4 && pName.length > 3 && pName.includes(ccId))
                            );

                            // FORCE LINK: Dibell -> CC002 (Legacy Data Patch)
                            if (ccId === 'cc002' && (pName.includes('dibell') || pCode.includes('dibell'))) {
                                return true;
                            }

                            return (exactMatch || partialMatch);
                        });

                        const incomeTransactions = projectTransactions.filter(t => {
                            const type = (t.type || t.Tipo || '').toLowerCase();
                            const amount = parseFloat(t.amount || t.monto || t.Monto || 0);
                            return type.includes('ingres') || type.includes('pago') || type.includes('recaud') || (amount > 0 && !type.includes('egres') && !type.includes('gast'));
                        });
                        const expenseTransactions = projectTransactions.filter(t => !incomeTransactions.includes(t));

                        const totalIncome = incomeTransactions.reduce((sum, t) => sum + Math.abs(parseFloat(t.amount || t.monto || t.Monto || 0)), 0);
                        const totalSpent = expenseTransactions.reduce((sum, t) => sum + Math.abs(parseFloat(t.amount || t.monto || t.Monto || 0)), 0);

                        // Real Utility Logic
                        const margin = totalIncome - totalSpent;
                        const marginPct = totalIncome > 0 ? (margin / totalIncome) * 100 : 0;

                        // Budget Progress (Gasto vs Presupuesto) for analysis
                        const progress = budget > 0 ? (totalSpent / budget) * 100 : 0;

                        // Update DOM
                        document.getElementById('pd-budget').innerText = `$${budget.toLocaleString('es-CL')}`;
                        document.getElementById('pd-income').innerText = `$${totalIncome.toLocaleString('es-CL')}`;
                        document.getElementById('pd-spent').innerText = `$${totalSpent.toLocaleString('es-CL')}`;

                        const marginEl = document.getElementById('pd-margin');
                        const marginPctEl = document.getElementById('pd-margin-pct');
                        // Target the label specifically if it exists, or just update the header
                        const utilLabel = document.querySelector('#pd-margin').previousElementSibling;

                        marginEl.innerText = `$${margin.toLocaleString('es-CL')}`;
                        marginPctEl.innerText = `${marginPct.toFixed(1)}%`;

                        if (margin < 0) {
                            marginEl.className = 'text-xl font-bold text-red-600';
                            marginPctEl.className = 'text-xs font-bold text-red-500';
                        } else {
                            marginEl.className = 'text-xl font-bold text-green-700';
                            marginPctEl.className = 'text-xs font-bold text-green-600';
                        }

                        // Calculate Physical Progress based on kilometrage
                        const calculatePhysicalProgress = (proj) => {
                            const paymentStatuses = proj.paymentStatuses || proj.payment_statuses || [];

                            if (paymentStatuses.length === 0) {
                                return { progress: 0, currentKm: 210, detail: 'Sin datos de avance' };
                            }

                            // Project parameters (Stage test: 1000m)
                            const startKm = 210;
                            const endKm = 1210; // End at 1210 to complete 1000m range
                            const totalKm = endKm - startKm; // 1000 KM (m)

                            // Calculate furthest KM reached
                            let maxKm = startKm;

                            paymentStatuses.forEach(item => {
                                const kE = parseFloat(item.kmEnd || item.KmFin || startKm);
                                if (kE > maxKm) maxKm = kE;
                            });

                            // Progress is purely linear: (Distance reached - Start) / Target (1000m)
                            const distanceDone = Math.max(0, maxKm - startKm);
                            const finalProgress = (distanceDone / totalKm) * 100;

                            return {
                                progress: finalProgress,
                                currentKm: maxKm,
                                detail: `KM ${startKm} ? ${maxKm.toFixed(0)} (Meta: ${endKm})`
                            };
                        };

                        const physicalData = calculatePhysicalProgress(project);
                        document.getElementById('pd-physical-progress').innerText = `${physicalData.progress.toFixed(1)}%`;
                        document.getElementById('pd-physical-progress-bar').style.width = `${Math.min(physicalData.progress, 100)}%`;
                        document.getElementById('pd-physical-detail').innerText = physicalData.detail;

                        // --- DYNAMIC INTELLIGENT ANALYSIS ---
                        const updateIntelligentAnalysis = (proj, stats) => {
                            const { margin, marginPct, progress, totalSpent, budget } = stats;
                            const physicalProgress = physicalData.progress;

                            // 1. Health Indicators (Semforos)
                            const setIndicator = (id, textId, status, message) => {
                                const indicator = document.getElementById(id);
                                const text = document.getElementById(textId);
                                if (!indicator || !text) return;

                                indicator.className = `w-4 h-4 rounded-full ${status === 'green' ? 'bg-green-500' : status === 'yellow' ? 'bg-yellow-500' : 'bg-red-500'}`;
                                text.innerText = message;
                            };

                            // Financial Health
                            if (margin >= 30) {
                                setIndicator('health-financial-indicator', 'health-financial-text', 'green', 'Margen saludable (>30%)');
                            } else if (margin >= 15) {
                                setIndicator('health-financial-indicator', 'health-financial-text', 'yellow', 'Margen aceptable (15-30%)');
                            } else {
                                setIndicator('health-financial-indicator', 'health-financial-text', 'red', 'Margen crtico (<15%)');
                            }

                            // Budget Execution vs Physical
                            const deviation = progress - physicalProgress;
                            if (deviation < 5) {
                                setIndicator('health-budget-indicator', 'health-budget-text', 'green', 'Ejecucin alineada con avance');
                            } else if (deviation < 15) {
                                setIndicator('health-budget-indicator', 'health-budget-text', 'yellow', 'Gasto ligeramente superior al avance');
                            } else {
                                setIndicator('health-budget-indicator', 'health-budget-text', 'red', 'Sobre-Ejecucin crtica detectada');
                            }

                            // Profitability Trend
                            if (margin >= 30 && deviation < 5) {
                                setIndicator('health-profit-indicator', 'health-profit-text', 'green', 'Rentabilidad slida y estable');
                            } else if (margin < 15 || deviation > 15) {
                                setIndicator('health-profit-indicator', 'health-profit-text', 'red', 'Tendencia a la baja (Alerta)');
                            } else {
                                setIndicator('health-profit-indicator', 'health-profit-text', 'yellow', 'Riesgo moderado de desviacin');
                            }

                            // 2. Profitability Details
                            document.getElementById('analysis-current-margin').innerText = `${marginPct.toFixed(1)}%`;

                            // Projected Margin: (Budget - (Spent / PhysicalProgress%)) / Budget * 100
                            let projectedMarginPct = marginPct;
                            if (physicalProgress > 1) {
                                const projectedTotalCost = totalSpent / (physicalProgress / 100);
                                projectedMarginPct = ((budget - projectedTotalCost) / budget) * 100;
                            }

                            const projMarginEl = document.getElementById('analysis-projected-margin');
                            projMarginEl.innerText = `${Math.min(projectedMarginPct, 100).toFixed(1)}%`;
                            projMarginEl.className = projectedMarginPct >= 30 ? 'font-bold text-lg text-green-600' : 'font-bold text-lg text-red-600';

                            // Margin Status Analysis
                            const marginStatusEl = document.getElementById('analysis-margin-status');
                            if (marginStatusEl) {
                                if (marginPct >= 30) {
                                    marginStatusEl.innerText = '? Sobre estndar';
                                    marginStatusEl.className = 'font-bold text-lg text-green-600';
                                } else if (marginPct >= 25) {
                                    marginStatusEl.innerText = '🔵 En esténdar';
                                    marginStatusEl.className = 'font-bold text-lg text-blue-600';
                                } else {
                                    marginStatusEl.innerText = '🔴 Bajo estandar';
                                    marginStatusEl.className = 'font-bold text-lg text-red-600';
                                }
                            }

                            // 3. Risk Areas & Recommendations
                            const riskList = document.getElementById('risk-areas-list');
                            const recList = document.getElementById('recommendations-list');

                            if (riskList && recList) {
                                let risks = [];
                                let recs = [];

                                if (deviation > 10) {
                                    risks.push(`Desviacin de ${(deviation).toFixed(1)}% entre gasto y avance fsico.`);
                                    recs.push('Auditar partidas con mayor consumo de materiales.');
                                }
                                if (margin < 25) {
                                    risks.push('Margen operativo por debajo del estndar industrial (30%).');
                                    recs.push('Revisar costos indirectos y optimizar cuadrillas.');
                                }
                                if (physicalProgress < 10 && progress > 20) {
                                    risks.push('Alto costo de movilizacin/instalacin inicial.');
                                    recs.push('Acelerar produccin fsica para diluir costos fijos.');
                                }

                                if (risks.length === 0) {
                                    risks.push('Sin riesgos crticos detectados actualmente.');
                                    recs.push('Mantener el ritmo de Ejecucin actual.');
                                }

                                riskList.innerHTML = risks.map(r => `
                                    <div class="flex items-start gap-2 text-sm">
                                        <span class="text-yellow-500">!!</span>
                                        <p class="text-gray-700">${r}</p>
                                    </div>`).join('');

                                recList.innerHTML = recs.map(r => `
                                    <div class="flex items-start gap-2 text-sm">
                                        <span class="text-green-500">?</span>
                                        <p class="text-gray-700">${r}</p>
                                    </div>`).join('');
                            }

                            // 4. Final Projections
                            const projectedFinalUtility = budget * (marginPct / 100); // Simplistic projection based on margin %
                            document.getElementById('projection-profit').innerText = `$${projectedFinalUtility.toLocaleString('es-CL')}`;
                            document.getElementById('projection-margin').innerText = `${marginPct.toFixed(1)}%`;
                        };

                        updateIntelligentAnalysis(project, { margin, marginPct, progress, totalSpent, budget });

                        // Render Charts
                        const chartData = prepareProjectDashboardChartData(expenseTransactions);
                        renderDashboardCharts(chartData);

                        modal.classList.remove('hidden');
                    }

                    // 5. Default to Resumen Tab and Refresh Payment Statuses just in case
                    if (typeof switchProjectTab === 'function') {
                        switchProjectTab('resumen');
                    }

                } catch (error) {
                    console.error('Error opening dashboard:', error);
                    alert('Error al cargar el dashboard: ' + error.message);
                }
            }



            // Make functions globally accessible
            window.openProjectDashboard = openProjectDashboard;



            // ====================================
            // AUTO-FIX: Dibell Client Data
            // ====================================
            (async function autoFixDibellData() {
                return; // DISABLED BY USER REQUEST - PREVENTS GHOST ITEMS
                try {
                    const projects = await AlpaHub.getProjects();
                    const dibellProject = projects.find(p => p.id === 'alpa-001' || p.code === 'P-EA');

                    if (dibellProject) {
                        const needsUpdate = !dibellProject.clientRut ||
                            !dibellProject.paymentStatuses ||
                            dibellProject.paymentStatuses.length === 0 ||
                            dibellProject.paymentStatuses[0].price < 4000000; // Check for the ~4.5M value

                        if (needsUpdate) {
                            console.log('wrench Auto-fixing Dibell data (Value & Client)...');
                            await AlpaHub.execute('updateProject', {
                                id: dibellProject.id,
                                updates: {
                                    client: 'DIBELL',
                                    clientRut: '76.000.000-0',
                                    budget: 30589000,
                                    paymentStatuses: [
                                        { item: 1, description: 'ESTADO DE PAGO N1 - OBRAS CIVILES (GLOBAL)', unit: 'gl', quantity: 1, price: 4541503, kmStart: 0, kmEnd: 0 },
                                        // Restored Structure
                                        { item: 2, description: 'COMPRA DE COLCHONES', unit: 'un', quantity: 0, price: 0, kmStart: 0, kmEnd: 0 },
                                        { item: 3, description: 'ANTICIPO CAPACITACION', unit: 'gl', quantity: 0, price: 0, kmStart: 0, kmEnd: 0 },
                                        { item: 4, description: 'COMPRA DE EPP', unit: 'gl', quantity: 0, price: 0, kmStart: 0, kmEnd: 0 },
                                        { item: 5, description: 'COMPRA COMBUSTIBLE/PETROLEO', unit: 'lt', quantity: 0, price: 0, kmStart: 0, kmEnd: 0 },
                                        { item: 6, description: 'ARRIENDO DEPARTAMENTO', unit: 'mes', quantity: 0, price: 0, kmStart: 0, kmEnd: 0 },
                                        { item: 7, description: 'ARRIENDO MAQUINARIA', unit: 'hr', quantity: 0, price: 0, kmStart: 0, kmEnd: 0 },
                                        { item: 8, description: 'COMPRA ALMOHADAS Y SABANAS', unit: 'un', quantity: 0, price: 0, kmStart: 0, kmEnd: 0 },
                                        { item: 9, description: 'MATERIALES DE CONSTRUCCION', unit: 'gl', quantity: 0, price: 0, kmStart: 0, kmEnd: 0 },
                                        { item: 10, description: 'HERRAMIENTAS', unit: 'gl', quantity: 0, price: 0, kmStart: 0, kmEnd: 0 },
                                        { item: 11, description: 'TRANSPORTE', unit: 'gl', quantity: 0, price: 0, kmStart: 0, kmEnd: 0 },
                                        { item: 12, description: 'ALIMENTACION', unit: 'gl', quantity: 0, price: 0, kmStart: 0, kmEnd: 0 },
                                        { item: 13, description: 'ALOJAMIENTO', unit: 'gl', quantity: 0, price: 0, kmStart: 0, kmEnd: 0 }
                                    ]
                                }
                            });
                            console.log('? Dibell data updated automatically');

                            // Force refresh if we are already in the dashboard
                            if (typeof loadProjects === 'function') loadProjects();
                            AlpaHub.showNotification('Datos de Dibell actualizados correctamente', 'success');
                        }
                    }
                } catch (e) {
                    console.warn('Auto-fix skipped:', e.message);
                }
            })();



            async function runHealthCheck() {
                const modal = document.getElementById('health-check-modal');
                modal.classList.remove('hidden');

                try {
                    const results = await AlpaHub.execute('checkDatabaseIntegrity');

                    // 1. Render Stats
                    const summaryEl = document.getElementById('health-summary');
                    summaryEl.innerHTML = `
                    <div class="bg-white/5 p-4 rounded-xl border border-white/10 shadow-sm">
                        <p class="text-xs font-bold text-gray-400 uppercase">Celdas con Error</p>
                        <p class="text-2xl font-black ${results.stats.badFormulas > 0 ? 'text-rose-500' : 'text-gray-200'}">${results.stats.badFormulas}</p>
                    </div>
                    <div class="bg-white/5 p-4 rounded-xl border border-white/10 shadow-sm">
                        <p class="text-xs font-bold text-gray-400 uppercase">Proyectos Vinculados</p>
                        <p class="text-2xl font-black text-gray-200">${results.projectsCount}</p>
                    </div>
                    <div class="bg-white/5 p-4 rounded-xl border border-white/10 shadow-sm">
                        <p class="text-xs font-bold text-gray-400 uppercase">Posibles Duplicados</p>
                        <p class="text-2xl font-black ${results.stats.potentialDuplicates > 0 ? 'text-amber-500' : 'text-gray-200'}">${results.stats.potentialDuplicates}</p>
                    </div>
                `;

                    // Render Duplicates (NEW!)
                    const dupsCont = document.getElementById('health-duplicates-container');
                    const dupsList = document.getElementById('health-duplicates-list');
                    if (results.duplicates.length > 0) {
                        dupsCont.classList.remove('hidden');
                        dupsList.innerHTML = results.duplicates.map(d => `
                        <div class="p-4 border-b border-white/5 last:border-0 hover:bg-amber-500/5 flex justify-between items-center">
                            <div>
                                <p class="text-sm font-bold text-gray-200">${d.description}</p>
                                <p class="text-xs text-amber-500 font-bold uppercase">MONTO: $${d.amount.toLocaleString('es-CL')} | FECHA: ${d.date}</p>
                            </div>
                            <span class="text-xs font-bold bg-amber-500/10 text-amber-500 px-2 py-1 rounded border border-amber-500/20">REVISAR EN DRIVE</span>
                        </div>
                    `).join('');
                    } else {
                        dupsCont.classList.add('hidden');
                    }

                    // 2. Render Errors
                    const errorsCont = document.getElementById('health-errors-container');
                    const errorsList = document.getElementById('health-errors-list');
                    if (results.errors.length > 0) {
                        errorsCont.classList.remove('hidden');
                        errorsList.innerHTML = results.errors.map(err => `
                        <div class="p-4 border-b border-white/5 last:border-0 hover:bg-rose-500/10 flex justify-between items-center group">
                            <div>
                                <p class="text-sm font-bold text-gray-200">${err.description}</p>
                                <p class="text-xs text-rose-500 font-mono">ERROR: ${err.value} | ID: ${err.id}</p>
                            </div>
                            <span class="text-xs font-bold bg-rose-500/20 text-rose-400 px-2 py-1 rounded select-none border border-rose-500/30">HOJA CONTABILIDAD</span>
                        </div>
                    `).join('');
                    } else {
                        errorsCont.classList.add('hidden');
                    }

                    // 3. Render Orphans
                    const orphansCont = document.getElementById('health-orphans-container');
                    const orphansList = document.getElementById('health-orphans-list');
                    if (results.orphans.length > 0) {
                        orphansCont.classList.remove('hidden');
                        orphansList.innerHTML = results.orphans.map(orp => `
                        <div class="p-4 border-b border-white/5 last:border-0 hover:bg-orange-500/10 flex justify-between items-center">
                            <div>
                                <p class="text-sm font-bold text-gray-200">${orp.description}</p>
                                <p class="text-xs text-orange-500 font-bold uppercase">C. COSTO DESCONOCIDO: "${orp.cc}"</p>
                            </div>
                            <i class="fas fa-question-circle text-orange-500/50"></i>
                        </div>
                    `).join('');
                    } else {
                        orphansCont.classList.add('hidden');
                    }

                    // 4. Render Warnings
                    const warningsCont = document.getElementById('health-warnings-container');
                    const warningsList = document.getElementById('health-warnings-list');
                    if (results.warnings.length > 0) {
                        warningsCont.classList.remove('hidden');
                        warningsList.innerHTML = results.warnings.map(warn => `
                        <div class="p-3 border-b border-white/5 last:border-0 hover:bg-white/5 flex items-center gap-3">
                            <i class="fas fa-info-circle text-slate-400"></i>
                            <div>
                                <p class="text-xs font-bold text-slate-700">${warn.description}</p>
                                <p class="text-xs text-gray-500">${warn.type}</p>
                            </div>
                        </div>
                    `).join('');
                    } else {
                        warningsCont.classList.add('hidden');
                    }

                    // 5. Clean State
                    const cleanEl = document.getElementById('health-clean-state');
                    if (results.errors.length === 0 && results.orphans.length === 0) {
                        cleanEl.classList.remove('hidden');
                    } else {
                        cleanEl.classList.add('hidden');
                    }

                } catch (e) {
                    console.error("Health Check Failed", e);
                    AlpaHub.showNotification("Error al ejecutar diagnstico: " + e.message, 'error');
                }
            }

            window.runHealthCheck = runHealthCheck;

            // --- EXPORT MODALS TO WINDOW FOR ONCLICK ACCESS ---
            window.openEditTransactionModal = typeof openEditTransactionModal !== 'undefined' ? openEditTransactionModal : null;
            window.closeEditTransactionModal = typeof closeEditTransactionModal !== 'undefined' ? closeEditTransactionModal : null;
            window.openAttachModal = typeof openAttachModal !== 'undefined' ? openAttachModal : null;
            window.closeAttachModal = typeof closeAttachModal !== 'undefined' ? closeAttachModal : null;
            window.attachDocumentToTransaction = typeof attachDocumentToTransaction !== 'undefined' ? attachDocumentToTransaction : null;

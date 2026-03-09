/**
 * DocumentService.js
 * â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
 * Servicio centralizado para:
 *   - GeneraciÃ³n de folios correlativos (via Supabase RPC)
 *   - Persistencia de versiones de documentos
 *   - Historial de versiones con fallback a localStorage
 *
 * Uso (en cualquier mÃ³dulo que cargue config.js primero):
 *
 *   const folio = await DocumentService.nextNumber('quote');
 *   // â†’ "ALPA-2026-001"
 *
 *   await DocumentService.saveVersion(quoteData, 'Ajuste precio Ã­tem 3');
 *
 *   const hist = await DocumentService.getVersionHistory('ALPA-2026-001');
 * â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
 */

(function (global) {
    'use strict';

    // â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    function getSbClient() {
        return global.sbClient || null;                // from config.js
    }

    function getSession() {
        try {
            const key = global.SAAS_CONFIG?.sessionKey || 'alpa_app_session_v1';
            return JSON.parse(localStorage.getItem(key));
        } catch { return null; }
    }

    function getOrgId() {
        const s = getSession();
        // Prefer the Supabase organization_id stored in the session
        return s?.user?.organization_id || s?.user?.tenant_id || null;
    }

    function currentUserInfo() {
        const s = getSession();
        const u = s?.user || {};
        return {
            email: u.email || 'desconocido@alpa.cl',
            name: u.name || u.email?.split('@')[0] || 'Usuario',
        };
    }

    // â”€â”€ Fallback localStorage counter â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    const LS_COUNTERS = {
        quote: 'lastQuoteNumber',
        purchase_order: 'lastPONumber',
        payment_status: 'lastEPNumber',
    };

    const TYPE_PREFIXES = {
        quote: '',
        purchase_order: 'OC',
        payment_status: 'EP',
    };

    function localNextNumber(docType) {
        const key = LS_COUNTERS[docType] || `last_${docType}_number`;
        const year = new Date().getFullYear();
        const prefix = global.SAAS_CONFIG?.companyPrefix || 'ALPA';
        const next = parseInt(localStorage.getItem(key) || '0') + 1;
        localStorage.setItem(key, next);
        const code = TYPE_PREFIXES[docType] ? `-${TYPE_PREFIXES[docType]}` : '';
        return `${prefix}${code}-${year}-${String(next).padStart(3, '0')}`;
    }

    // â”€â”€ DocumentService â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    const DocumentService = {

        /**
         * Obtiene el siguiente nÃºmero de documento.
         * @param {'quote'|'purchase_order'|'payment_status'} docType
         * @returns {Promise<string>}  ej. "ALPA-2026-001"
         */
        async nextNumber(docType) {
            const sb = getSbClient();
            const orgId = getOrgId();

            if (sb && orgId) {
                try {
                    const { data, error } = await sb.rpc('get_next_document_number', {
                        p_org_id: orgId,
                        p_doc_type: docType,
                        p_year: new Date().getFullYear(),
                    });
                    if (error) throw error;
                    return data;
                } catch (err) {
                    console.warn(`[DocumentService] RPC error (fallback to localStorage):`, err.message);
                }
            }

            // Fallback: localStorage
            console.info('[DocumentService] Using localStorage counter (no Supabase session)');
            return localNextNumber(docType);
        },

        /**
         * Guarda o actualiza una versiÃ³n del documento.
         * @param {Object}  docData         Objeto completo del documento
         * @param {string}  changeSummary   DescripciÃ³n breve de cambios (opcional)
         * @returns {Promise<{version: number, id: string}|null>}
         */
        async saveVersion(docData, changeSummary = null) {
            const sb = getSbClient();
            const orgId = getOrgId();
            const user = currentUserInfo();

            if (!docData?.documentNumber && !docData?.quoteNumber && !docData?.poNumber && !docData?.epNumber) {
                console.error('[DocumentService] docData must have a document number');
                return null;
            }

            const docNumber = docData.documentNumber
                || docData.quoteNumber
                || docData.poNumber
                || docData.epNumber;

            if (sb && orgId) {
                try {
                    const { data, error } = await sb.rpc('save_document_version', {
                        p_org_id: orgId,
                        p_doc_number: docNumber,
                        p_doc_type: docData.documentType || 'quote',
                        p_data: docData,
                        p_created_by_email: user.email,
                        p_created_by_name: user.name,
                        p_change_summary: changeSummary,
                    });
                    if (error) throw error;
                    console.info(`[DocumentService] Version saved: ${docNumber} v${data?.version}`);
                    return data;
                } catch (err) {
                    console.warn('[DocumentService] saveVersion fallback to localStorage:', err.message);
                }
            }

            // Fallback: localStorage
            const storageKey = `docVersions_${docNumber}`;
            const existing = JSON.parse(localStorage.getItem(storageKey) || '[]');
            existing.forEach(v => v.is_current = false);
            const newVersion = {
                version: (existing.length + 1),
                data: docData,
                created_by_email: user.email,
                created_by_name: user.name,
                change_summary: changeSummary,
                is_current: true,
                created_at: new Date().toISOString(),
            };
            existing.push(newVersion);
            localStorage.setItem(storageKey, JSON.stringify(existing));
            return { version: newVersion.version };
        },

        /**
         * Obtiene el historial de versiones de un documento.
         * @param {string} docNumber   ej. "ALPA-2026-001"
         * @returns {Promise<Array>}   Array de versiones (mÃ¡s reciente primero)
         */
        async getVersionHistory(docNumber) {
            const sb = getSbClient();
            const orgId = getOrgId();

            if (sb && orgId) {
                try {
                    const { data, error } = await sb
                        .from('document_versions')
                        .select('version, created_by_name, created_by_email, change_summary, is_current, created_at')
                        .eq('organization_id', orgId)
                        .eq('document_number', docNumber)
                        .order('version', { ascending: false });
                    if (error) throw error;
                    return data || [];
                } catch (err) {
                    console.warn('[DocumentService] getVersionHistory fallback:', err.message);
                }
            }

            // Fallback: localStorage
            const stored = JSON.parse(localStorage.getItem(`docVersions_${docNumber}`) || '[]');
            return stored.slice().reverse();
        },

        /**
         * Renderiza el modal de historial de versiones.
         * @param {string} docNumber
         */
        async showVersionModal(docNumber) {
            const versions = await this.getVersionHistory(docNumber);

            const fmt = ts => ts ? new Date(ts).toLocaleString('es-CL', {
                day: '2-digit', month: '2-digit', year: 'numeric',
                hour: '2-digit', minute: '2-digit'
            }) : 'â€”';

            const rows = versions.map(v => `
                <tr class="border-b border-slate-100 hover:bg-orange-50/50 transition-colors">
                    <td class="px-4 py-3 text-center">
                        <span class="inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full
                            ${v.is_current ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}">
                            v${v.version} ${v.is_current ? 'â— actual' : ''}
                        </span>
                    </td>
                    <td class="px-4 py-3 text-xs text-slate-600">${v.created_by_name || 'â€”'}</td>
                    <td class="px-4 py-3 text-xs text-slate-500">${fmt(v.created_at)}</td>
                    <td class="px-4 py-3 text-xs text-slate-700 max-w-xs">${v.change_summary || 'CreaciÃ³n inicial'}</td>
                </tr>`).join('');

            // Inyectar o actualizar modal en el DOM
            let modal = document.getElementById('__doc-version-modal');
            if (!modal) {
                modal = document.createElement('div');
                modal.id = '__doc-version-modal';
                modal.className = 'fixed inset-0 bg-black/50 z-[9999] flex items-center justify-center p-4';
                document.body.appendChild(modal);
            }

            modal.innerHTML = `
                <div class="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden">
                    <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100">
                        <div>
                            <h3 class="font-bold text-slate-800 text-base">Historial de versiones</h3>
                            <p class="text-xs text-slate-500">${docNumber}</p>
                        </div>
                        <button onclick="document.getElementById('__doc-version-modal').remove()"
                            class="w-8 h-8 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-500 transition-colors text-lg">Ã—</button>
                    </div>
                    ${versions.length ? `
                    <div class="overflow-auto max-h-64">
                        <table class="w-full text-left">
                            <thead class="bg-slate-50 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                                <tr>
                                    <th class="px-4 py-2">VersiÃ³n</th>
                                    <th class="px-4 py-2">Autor</th>
                                    <th class="px-4 py-2">Fecha</th>
                                    <th class="px-4 py-2">Cambios</th>
                                </tr>
                            </thead>
                            <tbody>${rows}</tbody>
                        </table>
                    </div>` : `
                    <div class="px-6 py-10 text-center text-slate-400 text-sm">
                        Sin versiones registradas aÃºn.<br>
                        <span class="text-xs text-slate-300">Guarda el documento para crear la primera versiÃ³n.</span>
                    </div>`}
                    <div class="px-6 py-4 border-t border-slate-100 flex justify-end">
                        <button onclick="document.getElementById('__doc-version-modal').remove()"
                            class="px-4 py-2 bg-slate-800 text-white text-sm rounded-lg hover:bg-slate-700 transition-colors">
                            Cerrar
                        </button>
                    </div>
                </div>`;

            modal.addEventListener('click', e => {
                if (e.target === modal) modal.remove();
            });
        },

        /**
         * Enriquece docData con metadata del usuario actual.
         * Llamar antes de guardar para aÃ±adir trazabilidad.
         * @param {Object} docData
         * @param {string} docType
         * @returns {Object} docData enriquecido
         */
        enrichMetadata(docData, docType) {
            const user = currentUserInfo();
            const now = new Date().toISOString();
            return {
                ...docData,
                documentType: docType,
                createdByEmail: docData.createdByEmail || user.email,
                createdByName: docData.createdByName || user.name,
                createdAt: docData.createdAt || now,
                lastEditedByEmail: user.email,
                lastEditedByName: user.name,
                lastEditedAt: now,
            };
        },

        /**
         * Genera un bloque HTML de metadata de auditorÃ­a para incluir en PDFs.
         * Insertar en el documento antes de llamar a window.print().
         *
         * @param {Object} opts
         * @param {string} opts.documentNumber  Folio del documento (ej. ALPA-2026-001)
         * @param {string} opts.documentType    Tipo: 'CotizaciÃ³n'|'Orden de Compra'|'Estado de Pago'
         * @param {number} [opts.version]       VersiÃ³n del documento (por defecto 1)
         * @param {string} [opts.companyName]   Nombre de la organizaciÃ³n
         * @returns {string}  HTML del bloque de metadata listo para insertar en el DOM
         */
        generatePdfMetadataBlock({ documentNumber, documentType, version = 1, companyName = '' }) {
            const user = currentUserInfo();
            const now = new Date().toLocaleString('es-CL', {
                day: '2-digit', month: '2-digit', year: 'numeric',
                hour: '2-digit', minute: '2-digit',
            });
            const org = companyName
                || global.SAAS_CONFIG?.companyName
                || 'ALPA Construcciones';
            const trackId = `${documentNumber}-v${version}-${Date.now().toString(36).toUpperCase()}`;

            return `
            <div class="pdf-audit-block" style="
                border-top: 2px solid #F36F21;
                margin-top: 24px;
                padding-top: 12px;
                font-family: 'Helvetica Neue', Arial, sans-serif;
                font-size: 10px;
                color: #64748b;
                display: flex;
                justify-content: space-between;
                gap: 16px;
                break-inside: avoid;
            ">
                <div style="flex:1;">
                    <div style="font-weight:700;color:#0f172a;font-size:11px;margin-bottom:4px;">
                        ${org}
                    </div>
                    <div><b>Documento:</b> ${documentNumber}</div>
                    <div><b>Tipo:</b> ${documentType}</div>
                    <div><b>VersiÃ³n:</b> v${version}</div>
                </div>
                <div style="flex:1;text-align:right;">
                    <div><b>Generado por:</b> ${user.name}</div>
                    <div><b>Email:</b> ${user.email}</div>
                    <div><b>Fecha:</b> ${now}</div>
                    <div style="margin-top:4px;font-size:9px;color:#94a3b8;">
                        ID Seguimiento: ${trackId}
                    </div>
                </div>
            </div>`;
        },
    };

    // Exportar globalmente
    global.DocumentService = DocumentService;

})(window);

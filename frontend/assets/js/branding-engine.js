/**
 * branding-engine.js
 * Applies dynamic branding based on configuration
 */

(function () {
    console.log("Branding Engine Loaded");
    // Placeholder for actual branding logic
    // Usually reads window.SAAS_CONFIG and sets CSS variables

    async function applyBranding(container = document) {
        // 1. Check window.SAAS_CONFIG (Static/Config based)
        if (window.SAAS_CONFIG && window.SAAS_CONFIG.branding) {
            const b = window.SAAS_CONFIG.branding;
            const root = document.documentElement;
            if (b.primaryColor) root.style.setProperty('--primary', b.primaryColor);
            if (b.accentColor) root.style.setProperty('--accent', b.accentColor);
        }

        // 2. Dynamic Update from AlpaCore or AlpaHub
        let org = null;
        if (window.AlpaCore) {
            org = AlpaCore.getOrganization();
        } else if (window.AlpaHub) {
            try {
                org = await AlpaHub.execute('getOrganization');
            } catch (e) {
                console.warn("Branding Engine: AlpaHub not ready or failed", e);
            }
        }

        if (org) {
            console.group("Branding Engine: Diagnostic");
            console.log("Organization Data:", org);

            // Handle case where settings might be stringified (double-encoded)
            if (typeof org.settings === 'string' && org.settings.startsWith('{')) {
                try { org.settings = JSON.parse(org.settings); } catch (e) { }
            }

            // Selector matches:
            // 1. Sidebar logo container image (#company-logo-short img)
            // 2. Settings page preview image ([id="current-logo-preview"])
            // 3. Any element explicitly marked for branding ([data-org-logo])
            // 4. Print templates (#print-logo-container img)
            // 5. Generic class for dynamic logos (.company-logo-img)
            const logoSelector = '#company-logo-short img, #current-logo-preview, [data-org-logo], #print-logo-container img, .company-logo-img, img[alt*="Logo"], .sidebar-logo img';
            const logos = container.querySelectorAll(logoSelector);
            console.log(`Diagnostic: Searching for logos in ${container.tagName || 'document'}. Found ${logos.length} matching elements.`);
            if (logos.length === 0) {
                // Last ditch effort: search everything with data attribute globally if container is not document
                if (container !== document) {
                    console.log("Diagnostic: No logos found in container, trying global document search.");
                    const globalLogos = document.querySelectorAll(logoSelector);
                    if (globalLogos.length > 0) console.log(`Diagnostic: Found ${globalLogos.length} logos globally.`);
                }
            }

            // Search logo in multiple priority levels
            const finalLogoUrl = org.settings?.logo_url || org.logo_url || org.settings?.logoURL;
            console.log("Final Logo URL found:", finalLogoUrl ? (finalLogoUrl.startsWith('data:') ? 'Base64 image' : finalLogoUrl) : "NOT FOUND");

            if (finalLogoUrl) {
                logos.forEach(img => {
                    img.src = finalLogoUrl;
                    img.classList.remove('hidden');

                    const parent = img.parentElement;
                    if (parent) {
                        // Hide sibling icon placeholders (i tags)
                        parent.querySelectorAll('i').forEach(icon => icon.classList.add('hidden'));
                        // Remove fallback initials/text
                        parent.querySelectorAll('span').forEach(span => {
                            if (span.textContent.length < 5) span.classList.add('hidden');
                        });
                    }
                });
            } else {
                console.warn("Branding Engine: No logo_url found in organization state.");
            }
            console.groupEnd();

            // --- Organization Text Synchronization ---
            const orgMapping = {
                'name': org.name || (org.settings && org.settings.name),
                'rut': org.rut || org.RUT || (org.settings && org.settings.rut),
                'address': org.address || org.DirecciÃ³n || (org.settings && org.settings.address),
                'phone': org.phone || org.TelÃ©fono || (org.settings && org.settings.phone),
                'email': org.email || org.Email || (org.settings && org.settings.email),
                'url': org.url || org.website || (org.settings && org.settings.url) || (window.SAAS_CONFIG && window.SAAS_CONFIG.websiteUrl)
            };


            console.log("Branding Engine: Final Mapping:", orgMapping);

            Object.entries(orgMapping).forEach(([key, value]) => {
                const elements = container.querySelectorAll(`[data-org-${key}]`);
                if (elements.length > 0) {
                    console.log(`Branding Engine: Updating ${elements.length} elements for [data-org-${key}] with value: ${value}`);
                }

                if (!value) return;
                elements.forEach(el => {
                    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                        if (!el.value || el.value === '---') el.value = value;
                    } else if (el.id === 'company-name-header') {
                        // Special case for header text that might have nested spans
                        el.innerHTML = value.toUpperCase();
                    } else {
                        el.textContent = value;
                    }
                });
            });
        }



        // 3. Inject Global Brand Color Classes
        const styleId = 'alpa-brand-styles';
        if (!document.getElementById(styleId)) {
            const style = document.createElement('style');
            style.id = styleId;
            style.textContent = `
                /* Dynamic Alpa Brand Colors */
                .alpa-azul { color: var(--primary) !important; }
                .bg-alpa-azul { background-color: var(--primary) !important; }
                .border-alpa-azul { border-color: var(--primary) !important; }
                
                .alpa-naranja { color: var(--accent) !important; }
                .bg-alpa-naranja { background-color: var(--accent) !important; }
                .border-alpa-naranja { border-color: var(--accent) !important; }
                
                /* Hover/Focus States for Buttons */
                .btn-alpa-azul {
                    background-color: var(--primary);
                    color: white;
                    transition: all 0.2s;
                    font-weight: 600;
                    text-shadow: 0 1px 1px rgba(0,0,0,0.1);
                }
                .btn-alpa-azul:hover {
                    filter: brightness(1.1);
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                    transform: translateY(-1px);
                }
                
                .btn-alpa-naranja {
                    background-color: var(--accent);
                    color: white;
                    transition: all 0.2s;
                    font-weight: 600;
                    text-shadow: 0 1px 1px rgba(0,0,0,0.1);
                }
                .btn-alpa-naranja:hover {
                    filter: brightness(1.1);
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                    transform: translateY(-1px);
                }
            `;
            document.head.appendChild(style);
        }
    }

    // Expose for manual trigger
    window.AlpaBranding = {
        apply: applyBranding
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applyBranding);
    } else {
        applyBranding();
    }
})();

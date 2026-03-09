// DEBUG SCRIPT: DATA LINKING DIAGNOSTIC
// Paste this into the browser console to see the raw data used for matching.

(async function debugDataLinking() {
    console.clear();
    console.log("%cðŸ” DIAGNOSTIC: DATA LINKING", "color: blue; font-size: 16px; font-weight: bold;");

    try {
        // 1. Fetch Data directly from AlpaHub (or window cache)
        const projects = window.allProjects || await AlpaHub.execute('getProjects') || [];
        const transactions = window.allTransactions || await AlpaHub.execute('getTransactions') || [];

        console.log(`ðŸ“Š Loaded ${projects.length} Projects and ${transactions.length} Transactions.`);

        // 2. Inspect 'Enap Dibell' Project
        const targetProject = projects.find(p =>
            (p.name || '').toLowerCase().includes('dibell') ||
            (p.code || '').toLowerCase().includes('dibell')
        );

        if (!targetProject) {
            console.error("âŒ Project 'Dibell' NOT FOUND in loaded projects!");
            console.table(projects.map(p => ({ id: p.id, name: p.name, code: p.code })));
            return;
        }

        console.log("âœ… Target Project Found:", targetProject);
        console.log("   - ID:", targetProject.id);
        console.log("   - Name:", targetProject.name);
        console.log("   - Code:", targetProject.code);
        console.log("   - Normalized ID:", (targetProject.id || '').toString().toLowerCase().trim());
        console.log("   - Normalized Name:", (targetProject.name || '').toString().toLowerCase().trim());
        console.log("   - Normalized Code:", (targetProject.code || '').toString().toLowerCase().trim());

        // 3. Find Potential Matching Transactions
        const potentialMatches = transactions.filter(t => {
            const cc = (t.costCenter || t.centroCostoId || t.CentroCostoID || t.ProyectoID || '').toString().toLowerCase();
            return cc.includes('dibell');
        });

        console.log(`ðŸ”Ž Found ${potentialMatches.length} transactions with 'dibell' in CostCenter.`);

        if (potentialMatches.length > 0) {
            console.table(potentialMatches.map(t => ({
                date: t.date,
                amount: t.amount,
                costCenter: t.costCenter,
                normalizedCC: (t.costCenter || '').toString().toLowerCase().trim(),
                isMatch_ID: (t.costCenter || '').toString().toLowerCase().trim() === (targetProject.id || '').toString().toLowerCase().trim(),
                isMatch_Name: (t.costCenter || '').toString().toLowerCase().trim() === (targetProject.name || '').toString().toLowerCase().trim(),
                isMatch_Code: (t.costCenter || '').toString().toLowerCase().trim() === (targetProject.code || '').toString().toLowerCase().trim()
            })).slice(0, 10)); // Show top 10
        } else {
            console.warn("âš ï¸ No transactions found with 'dibell' in CostCenter. Checking valid CostCenters...");
            // List unique CostCenters
            const uniqueCCs = [...new Set(transactions.map(t => t.costCenter))];
            console.log("Unique Cost Centers in Transactions:", uniqueCCs);
        }

    } catch (e) {
        console.error("Diagnostic Failed:", e);
    }
})();

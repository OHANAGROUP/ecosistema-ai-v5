/**
 * Payment Status Calculation Fix
 * Corrects formula to support compound units (e.g., ML Ã— kg/ML Ã— price/kg)
 */

// Override the getProjectFinancials calculation
(function () {
    if (!window.AlpaCore) return;

    const originalGetProjectFinancials = AlpaCore.API.getProjectFinancials;

    AlpaCore.API.getProjectFinancials = (payload) => {
        const { id } = payload;
        const project = AlpaCore.state.projects.find(p => p.id == id);
        if (!project) return { error: 'Project not found' };

        const budget = parseFloat(project.budget || project.Presupuesto || 0);
        const transactions = AlpaCore.state.transactions || [];

        // Filter linked transactions
        const linked = transactions.filter(t =>
            (t.costCenter == id || t.costCenter === project.name || t.costCenter === project.code) &&
            t.type === 'Gasto'
        );

        const totalSpent = linked.reduce((sum, t) => sum + (parseFloat(t.amount || t.Monto) || 0), 0);

        // FIX: Calculate declared value with factor support
        const paymentStatuses = project.paymentStatuses || [];
        const totalDeclaredValue = paymentStatuses.reduce((sum, item) => {
            const kmStart = parseFloat(item.kmStart || 0);
            const kmEnd = parseFloat(item.kmEnd || 0);
            const totalML = kmEnd - kmStart; // Progress in meters
            const factor = parseFloat(item.quantity || 1); // Factor (e.g., 8.65 kg/ML)
            const pricePerUnit = parseFloat(item.price || 0);

            // Formula: Total ML Ã— factor Ã— price
            // Example: 150 ML Ã— 8.65 kg/ML Ã— $1,200/kg = $1,557,000
            const itemValue = totalML > 0
                ? totalML * factor * pricePerUnit
                : factor * pricePerUnit;

            return sum + itemValue;
        }, 0);

        // Financial metrics
        const margin = budget - totalSpent;
        const progress = budget > 0 ? (totalSpent / budget) * 100 : 0;
        const efficiency = totalSpent > 0 ? (totalDeclaredValue / totalSpent) * 100 : 0;

        // Generate Chart Data
        const categories = {};
        const timeline = {};

        linked.forEach(t => {
            // Category
            const cat = t.category || 'Sin CategorÃ­a';
            categories[cat] = (categories[cat] || 0) + (parseFloat(t.amount) || 0);

            // Timeline (by date)
            const date = t.date ? t.date.substring(0, 10) : 'N/A';
            timeline[date] = (timeline[date] || 0) + (parseFloat(t.amount) || 0);
        });

        return {
            project: project,
            metrics: {
                budget: budget,
                totalSpent: totalSpent,
                totalDeclaredValue: totalDeclaredValue,
                margin: margin,
                progress: progress,
                efficiency: efficiency
            },
            history: linked,
            charts: {
                categories: {
                    labels: Object.keys(categories),
                    data: Object.values(categories)
                },
                timeline: {
                    labels: Object.keys(timeline).sort(),
                    data: Object.keys(timeline).sort().map(d => timeline[d])
                }
            }
        };
    };

    console.log('âœ… Payment Status calculation fixed - now supports compound units (ML Ã— factor Ã— price)');
})();

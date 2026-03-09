
const { createClient } = require('@supabase/supabase-js');

const SAAS_CONFIG = {
    supabase: {
        url: 'https://sezjcklfwabdkfcenzuj.supabase.co',
        key: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlempja2xmd2FiZGtmY2VuenVqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk5ODUzNTgsImV4cCI6MjA4NTU2MTM1OH0.xT3F0WBmKKvLyD4ee4jGHAQAkQvEDDO0GVjbYCateAM'
    }
};

const supabase = createClient(SAAS_CONFIG.supabase.url, SAAS_CONFIG.supabase.key);

async function cleanupTable(tableName, uniqueCols) {
    console.log(`\nðŸ” Cleaning up duplicates in table: ${tableName}...`);

    // Fetch all items
    const { data: items, error } = await supabase.from(tableName).select('*');
    if (error) {
        console.error(`âŒ Error fetching ${tableName}:`, error);
        return;
    }

    console.log(`ðŸ“Š Found ${items.length} total rows.`);

    const seen = new Set();
    const toDelete = [];
    const uniqueItems = [];

    items.forEach(item => {
        // Create a key based on unique columns (excluding id)
        const key = uniqueCols.map(col => String(item[col] || '').trim().toLowerCase()).join('|');

        if (seen.has(key)) {
            toDelete.push(item.id);
        } else {
            seen.add(key);
            uniqueItems.push(item);
        }
    });

    if (toDelete.length > 0) {
        console.log(`âš ï¸  Detected ${toDelete.length} duplicates to remove.`);

        // Delete in batches of 100
        for (let i = 0; i < toDelete.length; i += 100) {
            const batch = toDelete.slice(i, i + 100);
            const { error: delError } = await supabase.from(tableName).delete().in('id', batch);
            if (delError) {
                console.error(`âŒ Error deleting batch in ${tableName}:`, delError);
            }
        }
        console.log(`âœ… Table ${tableName} cleaned.`);
    } else {
        console.log(`âœ… No duplicates found in ${tableName}.`);
    }
}

async function run() {
    console.log("ðŸš€ Starting Data Integrity Cleanup...");

    // Cleanup Leads (By name, email and message)
    await cleanupTable('leads', ['name', 'email', 'project_description']);

    // Cleanup Inventory (By SKU)
    await cleanupTable('inventory', ['sku']);

    console.log("\nâœ¨ Cleanup finished.");
}

run();


const { createClient } = require('@supabase/supabase-js');
const fs = require('fs');

// Config
const SAAS_CONFIG = {
    supabase: {
        url: 'https://sezjcklfwabdkfcenzuj.supabase.co',
        key: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlempja2xmd2FiZGtmY2VuenVqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk5ODUzNTgsImV4cCI6MjA4NTU2MTM1OH0.xT3F0WBmKKvLyD4ee4jGHAQAkQvEDDO0GVjbYCateAM'
    }
};

const supabase = createClient(SAAS_CONFIG.supabase.url, SAAS_CONFIG.supabase.key);

// Org ID Mock (simulated user session)
const TEST_ORG_ID = 'test-org-123'; // Assuming default RLS allows creation or update if user is authenticated/owns it?
// Actually, with RLS enabled, anon key might fail unless policies are public or simulated.
// Let's assume we can create Leads (public form submission typically allows this).
// Check RLS policies first? Or authenticate via email/pwd flow?
// We'll try direct insert. If it fails, we'll try auth.

async function runTest() {
    console.log("ðŸš€ Starting Sales Funnel Backend Test...");

    try {
        // 1. Authenticate (Optional but recommended for RLS)
        const email = 'admin@test.cl';
        const password = 'test-password';
        // We don't have user creds here easily.
        // Let's rely on public insert policy for Leads (Web Form).

        // 2. Create Lead (Web Form)
        const leadData = {
            organization_id: '15be0e52-xxxx-xxxx-xxxx-xxxxxxxxxxxx', // Need a valid Org ID? Use dummy UUID?
            // RLS for Leads usually requires `organization_id` match user metadata OR be public insert?
            // Let's check existing policies. If RLS is strict, we need a valid user.
            // Let's simulate a user login first.
        };

        // Authenticate as a test user if possible
        // Actually, we can use the `service_role` key if we had it, but we only have `anon`.
        // Let's try to sign in with a known user (if any exist) or sign up a temporary one.
        const testEmail = `testuser_${Date.now()}@example.com`;
        const testPassword = 'Password123!';

        console.log(`ðŸ” Signing up test user: ${testEmail}`);
        const { data: signUpData, error: signUpError } = await supabase.auth.signUp({
            email: testEmail,
            password: testPassword,
            options: {
                data: {
                    full_name: 'Test Automation User',
                    organization_id: 'org_auto_test' // Ensure this matches RLS check logic
                }
            }
        });

        if (signUpError) {
            console.error("âŒ Sign up failed:", signUpError.message);
            // Try sign in?
            return;
        }

        const user = signUpData.user;
        const orgId = user.user_metadata.organization_id;
        console.log(`âœ… User created. Org ID: ${orgId}`);

        // 3. Insert Lead
        const leadPayload = {
            organization_id: orgId, // Must match user's org
            name: 'Cliente Test Backend',
            email: 'cliente@backend.test',
            phone: '+5699999999',
            status: 'Nuevo',
            source: 'TEST_SCRIPT'
        };

        console.log("ðŸ“ Inserting Lead...");
        const { data: lead, error: leadError } = await supabase
            .from('leads')
            .insert(leadPayload)
            .select()
            .single();

        if (leadError) {
            console.error("âŒ Lead insert failed:", leadError);
            if (leadError.code === '42501') console.error("   (Permission Denied - Check RLS)");
            return;
        }
        console.log(`âœ… Lead created with ID: ${lead.id}`);

        // 4. Update Lead (Edit)
        console.log("âœï¸ Updating Lead (Edit)...");
        const { error: updateError } = await supabase
            .from('leads')
            .update({ project_description: 'Proyecto Test Backend', status: 'En Proceso' })
            .eq('id', lead.id);

        if (updateError) {
            console.error("âŒ Lead update failed:", updateError);
            return;
        }
        console.log("âœ… Lead updated successfully.");

        // 5. Create Quote (Conversion)
        console.log("ðŸ’° Creating Quote (Conversion)...");
        const quotePayload = {
            organization_id: orgId,
            quote_number: `QT-${Date.now()}`,
            lead_id: lead.id,
            client_name: lead.name,
            total_amount: 150000,
            status: 'Borrador',
            data: {
                items: [{ desc: 'Service 1', price: 150000 }]
            }
        };

        const { data: quote, error: quoteError } = await supabase
            .from('quotes')
            .insert(quotePayload)
            .select()
            .single();

        if (quoteError) {
            console.error("âŒ Quote creation failed:", quoteError);
            return;
        }
        console.log(`âœ… Quote created with ID: ${quote.id}, Linked Lead ID: ${quote.lead_id}`);

        // 6. Verify Link
        if (quote.lead_id == lead.id) {
            console.log("ðŸŽ‰ SUCCESS: Sales Funnel Workflow Verified (Backend).");
        } else {
            console.error("âŒ FAILURE: Quote lead_id mismatch.");
        }

        // Cleanup (Optional)
        // await supabase.auth.admin.deleteUser(user.id); // Requires service role

    } catch (e) {
        console.error("ðŸš¨ Unexpected Error:", e);
    }
}

runTest();

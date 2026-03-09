
const { createClient } = require('@supabase/supabase-js');

const url = 'https://sezjcklfwabdkfcenzuj.supabase.co';
const key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlempja2xmd2FiZGtmY2VuenVqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk5ODUzNTgsImV4cCI6MjA4NTU2MTM1OH0.xT3F0WBmKKvLyD4ee4jGHAQAkQvEDDO0GVjbYCateAM';

const supabase = createClient(url, key);

async function test() {
    console.log("Testing connection...");
    const { data, error, status } = await supabase.from('leads').select('id, name').limit(10);
    if (error) {
        console.error("Error:", error);
        console.log("Status:", status);
    } else {
        console.log("Data:", data);
    }
}

test();

// supabase/functions/custom-claims/index.ts
import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

serve(async (req) => {
    const { user } = await req.json()
    const supabase = createClient(
        Deno.env.get('SUPABASE_URL') ?? '',
        Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    )

    // 1. Obtener la organización del usuario desde la tabla de miembros
    const { data: member } = await supabase
        .from('organization_members')
        .select('organization_id')
        .eq('user_id', user.id)
        .single()

    const organization_id = member?.organization_id || null

    // 2. Retornar los claims para el JWT
    return new Response(
        JSON.stringify({
            claims: {
                organization_id,
            },
        }),
        { headers: { 'Content-Type': 'application/json' } }
    )
})

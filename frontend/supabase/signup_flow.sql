-- ALPA SAAS UNIFICADO - Auto-Registration Flow
-- Run this in the Supabase SQL Editor
-- This creates automatic organization assignment for new users

-- =====================================================
-- FUNCTION: Auto-create organization for new users
-- =====================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
  target_org_id UUID;
  company_name TEXT;
  provided_org_id TEXT;
BEGIN
  -- Check if an organization_id was provided in the metadata
  provided_org_id := NEW.raw_user_meta_data->>'organization_id';

  IF provided_org_id IS NOT NULL AND provided_org_id != '' THEN
    -- Validate provided UUID format and existence
    BEGIN
      target_org_id := provided_org_id::UUID;
      
      -- Verify the organization exists
      IF NOT EXISTS (SELECT 1 FROM public.organizations WHERE id = target_org_id) THEN
        target_org_id := NULL;
      END IF;
    EXCEPTION WHEN others THEN
      target_org_id := NULL;
    END;
  END IF;

  -- 1. If no valid org_id provided, create a new organization
  IF target_org_id IS NULL THEN
    -- Extract company name from user metadata (or use email as fallback)
    company_name := COALESCE(
      NEW.raw_user_meta_data->>'company_name',
      NEW.raw_user_meta_data->>'full_name',
      split_part(NEW.email, '@', 1)
    );

    INSERT INTO public.organizations (name, settings)
    VALUES (
      company_name,
      jsonb_build_object(
        'created_via', 'auto_registration',
        'created_at', NOW()
      )
    )
    RETURNING id INTO target_org_id;
  END IF;

  -- 2. Assign user to the organization (member role if joining, admin if new)
  -- If we created a new org, we set as 'admin'. If joining, 'member'.
  INSERT INTO public.organization_members (organization_id, user_id, role, joined_at)
  VALUES (
    target_org_id, 
    NEW.id, 
    CASE WHEN provided_org_id IS NULL OR provided_org_id = '' THEN 'admin' ELSE 'member' END, 
    NOW()
  );

  -- 3. Update user metadata with the final organization_id
  UPDATE auth.users
  SET raw_user_meta_data = 
    COALESCE(raw_user_meta_data, '{}'::jsonb) || 
    jsonb_build_object('organization_id', target_org_id::text)
  WHERE id = NEW.id;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- TRIGGER: Execute on user creation
-- =====================================================
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW 
  EXECUTE FUNCTION public.handle_new_user();

-- =====================================================
-- VERIFICATION QUERY
-- =====================================================
-- Run this after creating a test user to verify it worked:
-- SELECT u.email, o.name as organization_name, om.role
-- FROM auth.users u
-- LEFT JOIN public.organization_members om ON om.user_id = u.id
-- LEFT JOIN public.organizations o ON o.id = om.organization_id
-- ORDER BY u.created_at DESC
-- LIMIT 10;

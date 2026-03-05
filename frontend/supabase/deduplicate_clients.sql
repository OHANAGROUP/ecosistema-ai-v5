-- DEDUPLICATE CLIENTS SCRIPT
-- Keeps the client with the lowest ID (oldest) and deletes newer duplicates with the same name.

WITH duplicates AS (
  SELECT
    id,
    name,
    ROW_NUMBER() OVER (
      PARTITION BY LOWER(TRIM(name)) 
      ORDER BY id ASC
    ) as row_num
  FROM clients
)
DELETE FROM clients
WHERE id IN (
  SELECT id 
  FROM duplicates 
  WHERE row_num > 1
);

-- OPTIONAL: Add a unique constraint to prevent future duplicates
-- ALLOW THIS ONLY IF YOU ARE SURE NAMES SHOULD BE UNIQUE
-- ALTER TABLE clients ADD CONSTRAINT unique_client_name UNIQUE (name);

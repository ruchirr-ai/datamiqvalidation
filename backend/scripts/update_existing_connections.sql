-- SQL Script to update status for existing connections
-- Run this script directly in your PostgreSQL database

-- Update all existing connections to 'connected' status with current timestamp
-- This assumes connections were successfully tested when created
UPDATE connections 
SET 
    status = 'connected',
    last_tested_at = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP
WHERE 
    is_active = TRUE 
    AND status = 'disconnected';

-- Verify the update
SELECT 
    id,
    name,
    database,
    status,
    last_tested_at,
    updated_at
FROM connections
WHERE is_active = TRUE
ORDER BY id;

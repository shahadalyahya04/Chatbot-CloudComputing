-- Run as the Azure PostgreSQL administrator while connected to appdb.
-- appuser/appuser matches the classroom assignment. Change for real deployments.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'appuser') THEN
        CREATE USER appuser WITH ENCRYPTED PASSWORD 'appuser';
    END IF;
END
$$;

GRANT ALL PRIVILEGES ON DATABASE appdb TO appuser;
GRANT ALL PRIVILEGES ON SCHEMA public TO appuser;

CREATE TABLE IF NOT EXISTS public.advanced_chats (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pdf_path TEXT,
    pdf_name TEXT,
    pdf_uuid TEXT
);

GRANT ALL PRIVILEGES ON TABLE public.advanced_chats TO appuser;

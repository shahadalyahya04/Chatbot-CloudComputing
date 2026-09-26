-- Run in DBeaver as chatbotadmin, connected to appdb.
GRANT ALL PRIVILEGES ON DATABASE appdb TO appuser;
GRANT ALL PRIVILEGES ON SCHEMA public TO appuser;
GRANT ALL PRIVILEGES ON TABLE public.advanced_chats TO appuser;

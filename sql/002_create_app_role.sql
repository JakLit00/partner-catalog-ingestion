CREATE ROLE catalog_ingestor
    LOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    NOBYPASSRLS;

GRANT CONNECT ON DATABASE :"DBNAME" TO catalog_ingestor;
GRANT USAGE ON SCHEMA public TO catalog_ingestor;

GRANT SELECT, INSERT, UPDATE
    ON TABLE public.products
    TO catalog_ingestor;
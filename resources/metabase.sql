
DO $$ BEGIN
    CREATE TYPE db_type_type AS ENUM ('mysql', 'postgres');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE service_status_type AS ENUM ('production', 'duplicate', 'cancel', 'blocked');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE service_type_type AS ENUM ('odoo', 'lemp', 'wordpress');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS service_account(
    id serial PRIMARY KEY,
    name varchar NOT NULL UNIQUE,
    server_name varchar NOT NULL,
    unix_user varchar NOT NULL,
    unix_group varchar NOT NULL,
    status service_status_type NOT NULL DEFAULT 'production',
    service_type service_type_type NOT NULL DEFAULT 'lemp',
    create_date timestamp without time zone DEFAULT NOW(),
    update_date timestamp without time zone DEFAULT NOW(),
    port integer
);

CREATE TABLE IF NOT EXISTS database(
    id serial PRIMARY KEY,
    name varchar NOT NULL,
    db_type db_type_type NOT NULL DEFAULT 'mysql',
    service_id integer NOT NULL REFERENCES service_account(id) ON DELETE CASCADE
);

DROP INDEX IF EXISTS databases_name_per_type_uniq;
CREATE UNIQUE INDEX databases_name_per_type_uniq ON database(name, db_type);

CREATE TABLE incidents (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title varchar(200) NOT NULL CHECK (length(trim(title)) > 0),
    severity text NOT NULL DEFAULT 'low' CHECK (severity IN ('low', 'medium', 'high')),
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO cloud_api;
GRANT SELECT, INSERT, UPDATE ON incidents TO cloud_api;
GRANT USAGE, SELECT ON SEQUENCE incidents_id_seq TO cloud_api;

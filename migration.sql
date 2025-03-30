BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> eb4934b44814

CREATE TABLE users (
    id SERIAL NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    hashed_password VARCHAR(255) NOT NULL, 
    first_name VARCHAR(50), 
    last_name VARCHAR(50), 
    is_active BOOLEAN DEFAULT TRUE NOT NULL, 
    is_superuser BOOLEAN DEFAULT FALSE NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (email)
);

CREATE TABLE incidents (
    id SERIAL NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    description TEXT, 
    status VARCHAR(50) NOT NULL, 
    priority VARCHAR(50) NOT NULL, 
    created_by_id INTEGER NOT NULL, 
    assigned_to_id INTEGER, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(created_by_id) REFERENCES users (id), 
    FOREIGN KEY(assigned_to_id) REFERENCES users (id)
);

CREATE TABLE chat_messages (
    id SERIAL NOT NULL, 
    incident_id INTEGER NOT NULL, 
    user_id INTEGER NOT NULL, 
    content TEXT NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(incident_id) REFERENCES incidents (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE attachments (
    id SERIAL NOT NULL, 
    incident_id INTEGER NOT NULL, 
    file_name VARCHAR(255) NOT NULL, 
    file_path VARCHAR(255) NOT NULL, 
    file_type VARCHAR(50) NOT NULL, 
    file_size INTEGER NOT NULL, 
    uploaded_by_id INTEGER NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(incident_id) REFERENCES incidents (id), 
    FOREIGN KEY(uploaded_by_id) REFERENCES users (id)
);

INSERT INTO alembic_version (version_num) VALUES ('eb4934b44814') RETURNING alembic_version.version_num;

COMMIT;


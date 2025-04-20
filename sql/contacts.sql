CREATE TABLE contacts (
    id TEXT PRIMARY KEY,
    notes TEXT
);

CREATE TABLE aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id TEXT,
    alias TEXT,
    FOREIGN KEY(contact_id) REFERENCES contacts(id)
);

CREATE TABLE fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id TEXT,
    key TEXT,
    value TEXT,
    FOREIGN KEY(contact_id) REFERENCES contacts(id)
);
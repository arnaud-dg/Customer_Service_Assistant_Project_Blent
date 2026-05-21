-- Schéma de référence de la base orders.db (SQLite)
-- Ce fichier documente la structure attendue de la base data/raw/orders.db 

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Table users
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id      INTEGER PRIMARY KEY,
    first_name   TEXT    NOT NULL,
    last_name    TEXT    NOT NULL,
    joining_date TEXT    NOT NULL,   -- ISO 8601 : 'YYYY-MM-DD HH:MM:SS'
    phone        TEXT,
    email        TEXT    NOT NULL,
    address      TEXT,
    city         TEXT,
    zip_code     TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ---------------------------------------------------------------------------
-- Table orders
-- ---------------------------------------------------------------------------
-- Une commande est associé à un utilisateur. 
-- Un utilisateur peut posséder plusieurs commandes.
-- status : enum valeurs attendues : 'invoiced', 'shipped', 'delivered'.
--   - 'invoiced'  : validée et payée, pas encore expédiée
--   - 'shipped'   : expédiée, mais pas encore reçue
--   - 'delivered' : livrée au client
CREATE TABLE IF NOT EXISTS orders (
    order_id       INTEGER PRIMARY KEY,
    user_id        INTEGER NOT NULL,
    status         TEXT    NOT NULL,
    date_purchase  TEXT    NOT NULL,   -- ISO 8601 : 'YYYY-MM-DD HH:MM:SS'
    date_shipped   TEXT,               -- ISO 8601 : 'YYYY-MM-DD HH:MM:SS' — NULLABLE si statut = 'invoiced'
    date_delivered TEXT,               -- ISO 8601 : 'YYYY-MM-DD HH:MM:SS' — NULLABLE si statut != 'delivered'
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status  ON orders(status);

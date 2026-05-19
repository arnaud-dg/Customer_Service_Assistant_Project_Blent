-- Schéma de référence de la base orders.db (SQLite)
-- Source : énoncé du projet (40 utilisateurs, 100 commandes)
--
-- Ce fichier documente la structure attendue. La base elle-même est fournie
-- dans data/raw/orders.db ; ce script peut servir de référence pour
-- recréer le schéma à l'identique ou pour générer des fixtures de test.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Table users
-- ---------------------------------------------------------------------------
-- Représente les clients du site e-commerce.
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
-- Une commande appartient à un utilisateur. Un utilisateur peut avoir
-- plusieurs commandes.
--
-- status : énumération applicative (pas de CHECK pour rester fidèle à la base
-- fournie, mais valeurs attendues : 'invoiced', 'shipped', 'delivered').
--   - 'invoiced'  : validée et payée, pas encore expédiée
--   - 'shipped'   : expédiée, pas encore reçue
--   - 'delivered' : livrée au client
--
-- date_shipped et date_delivered sont nullables (selon le statut).
CREATE TABLE IF NOT EXISTS orders (
    order_id       INTEGER PRIMARY KEY,
    user_id        INTEGER NOT NULL,
    status         TEXT    NOT NULL,
    date_purchase  TEXT    NOT NULL,   -- ISO 8601
    date_shipped   TEXT,               -- NULL si statut = 'invoiced'
    date_delivered TEXT,               -- NULL si statut != 'delivered'
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status  ON orders(status);

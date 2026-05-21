from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from src.chain.graph import (
    BLACKLIST_SQL,
    _node_execute_sql,
    _node_format_redirect,
    _node_format_refusal,
    _route_after_classify,
)


# ── BLACKLIST_SQL ─────────────────────────────────────────────────────────────

class TestBlacklistSQL:
    @pytest.mark.parametrize("sql", [
        "INSERT INTO orders VALUES (1)",
        "UPDATE orders SET status = 'x'",
        "DELETE FROM orders WHERE order_id = 1",
        "DROP TABLE orders",
        "ALTER TABLE orders ADD COLUMN foo TEXT",
        "CREATE TABLE foo (id INTEGER)",
        "REPLACE INTO orders VALUES (1)",
        "ATTACH DATABASE 'evil.db' AS evil",
        "PRAGMA table_info(orders)",
        "VACUUM",
        "insert into orders values (1)",
    ])
    def test_detecte_mot_interdit(self, sql: str) -> None:
        assert BLACKLIST_SQL.search(sql)

    @pytest.mark.parametrize("sql", [
        "SELECT * FROM orders WHERE user_id = :user_id",
        "SELECT created_at FROM orders WHERE user_id = :user_id",
    ])
    def test_accepte_select(self, sql: str) -> None:
        assert not BLACKLIST_SQL.search(sql)


# ── _node_execute_sql ─────────────────────────────────────────────────────────

def _etat(sql: str, user_id: int = 1) -> dict:
    return {"sql": sql, "user_id": user_id}


class TestNodeExecuteSQL:
    @pytest.mark.parametrize("sql", [
        "INSERT INTO orders VALUES (1)",
        "DELETE FROM orders WHERE order_id = 1",
        "UPDATE orders SET status = 'shipped'",
        "DROP TABLE orders",
    ])
    def test_bloque_mot_interdit(self, sql: str) -> None:
        result = _node_execute_sql(_etat(sql), engine=MagicMock())
        assert result["rows"] == []
        assert result["sql"] is None

    def test_bloque_non_select(self) -> None:
        result = _node_execute_sql(_etat("EXPLAIN SELECT 1"), engine=MagicMock())
        assert result["rows"] == []
        assert result["sql"] is None

    def test_bloque_sans_user_id(self) -> None:
        sql = "SELECT * FROM orders WHERE order_id = 1"
        result = _node_execute_sql(_etat(sql), engine=MagicMock())
        assert result["rows"] == []
        assert result["sql"] is None

    def test_bloque_sql_vide(self) -> None:
        result = _node_execute_sql(_etat(""), engine=MagicMock())
        assert result["rows"] == []
        assert result["sql"] is None

    def test_accepte_requete_valide(self) -> None:
        sql = "SELECT * FROM orders WHERE user_id = :user_id"
        with patch("src.chain.graph.run_select", return_value=[{"order_id": 42}]):
            result = _node_execute_sql(_etat(sql), engine=MagicMock())
        assert result["rows"] == [{"order_id": 42}]
        assert result["sql"] == sql

    def test_erreur_execution_conserve_sql(self) -> None:
        # Contrairement aux erreurs de validation, une exception DB conserve sql dans l'état
        sql = "SELECT * FROM orders WHERE user_id = :user_id"
        with patch("src.chain.graph.run_select", side_effect=Exception("DB error")):
            result = _node_execute_sql(_etat(sql), engine=MagicMock())
        assert result["rows"] == []
        assert result["sql"] == sql


# ── _route_after_classify ─────────────────────────────────────────────────────

class TestRouteAfterClassify:
    @pytest.mark.parametrize("intent", ["commande", "compte"])
    def test_route_vers_sql(self, intent: str) -> None:
        assert _route_after_classify({"intent": intent}) == "generate_sql"

    def test_route_vers_redirect(self) -> None:
        assert _route_after_classify({"intent": "action_commande"}) == "format_redirect"

    @pytest.mark.parametrize("intent", ["hors_sujet", "hostile", None])
    def test_route_vers_refusal(self, intent: str | None) -> None:
        assert _route_after_classify({"intent": intent}) == "format_refusal"


# ── _node_format_refusal / _node_format_redirect ──────────────────────────────

class TestFormatRefusal:
    def test_hostile_message_court(self) -> None:
        result = _node_format_refusal({"intent": "hostile"})
        assert result["answer"] == "Je ne peux pas donner suite à cette demande."

    def test_hors_sujet_mentionne_commandes(self) -> None:
        result = _node_format_refusal({"intent": "hors_sujet"})
        assert "commandes" in result["answer"]


class TestFormatRedirect:
    def test_contient_numero_conseiller(self) -> None:
        result = _node_format_redirect({"intent": "action_commande"}, advisor_phone="06.00.00.00.00")
        assert "06.00.00.00.00" in result["answer"]

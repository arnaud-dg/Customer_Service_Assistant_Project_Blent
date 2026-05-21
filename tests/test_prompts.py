from __future__ import annotations

import pytest
import yaml

import src.chain.prompts as prompts_mod
from src.chain.prompts import (
    ANSWER_FORMATTING_SYSTEM,
    SQL_GENERATION_SYSTEM,
    _load_active,
    _to_str,
)


# ── _to_str ───────────────────────────────────────────────────────────────────

class TestToStr:
    def test_chaine_passthrough(self) -> None:
        assert _to_str("bonjour") == "bonjour"

    def test_liste_joint_par_newline(self) -> None:
        assert _to_str(["ligne 1", "ligne 2"]) == "ligne 1\nligne 2"

    def test_liste_vide(self) -> None:
        assert _to_str([]) == ""


# ── _load_active ──────────────────────────────────────────────────────────────

class TestLoadActive:
    def test_charge_fichier_actif(self, tmp_path, monkeypatch) -> None:
        (tmp_path / "sql_v1.0.yaml").write_text(yaml.dump({"active": False, "system_prompt": "old"}))
        (tmp_path / "sql_v2.0.yaml").write_text(yaml.dump({"active": True, "system_prompt": "new"}))
        monkeypatch.setattr(prompts_mod, "PROMPT_DIR", tmp_path)
        result = _load_active("sql")
        assert result["system_prompt"] == "new"

    def test_ignore_version_inactive(self, tmp_path, monkeypatch) -> None:
        (tmp_path / "sql_v1.0.yaml").write_text(yaml.dump({"active": False, "system_prompt": "old"}))
        (tmp_path / "sql_v2.0.yaml").write_text(yaml.dump({"active": True, "system_prompt": "new"}))
        monkeypatch.setattr(prompts_mod, "PROMPT_DIR", tmp_path)
        result = _load_active("sql")
        assert result["system_prompt"] != "old"

    def test_erreur_aucun_fichier(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(prompts_mod, "PROMPT_DIR", tmp_path)
        with pytest.raises(RuntimeError, match="Aucun fichier"):
            _load_active("inexistant")

    def test_erreur_aucun_actif(self, tmp_path, monkeypatch) -> None:
        (tmp_path / "sql_v1.0.yaml").write_text(yaml.dump({"active": False, "system_prompt": "old"}))
        monkeypatch.setattr(prompts_mod, "PROMPT_DIR", tmp_path)
        with pytest.raises(RuntimeError, match="Aucun prompt"):
            _load_active("sql")

    def test_erreur_plusieurs_actifs(self, tmp_path, monkeypatch) -> None:
        (tmp_path / "sql_v1.0.yaml").write_text(yaml.dump({"active": True, "system_prompt": "v1"}))
        (tmp_path / "sql_v2.0.yaml").write_text(yaml.dump({"active": True, "system_prompt": "v2"}))
        monkeypatch.setattr(prompts_mod, "PROMPT_DIR", tmp_path)
        with pytest.raises(RuntimeError, match="Plusieurs prompts"):
            _load_active("sql")


# ── Constantes du module ──────────────────────────────────────────────────────

class TestModuleConstants:
    def test_sql_generation_system_non_vide(self) -> None:
        assert isinstance(SQL_GENERATION_SYSTEM, str) and len(SQL_GENERATION_SYSTEM) > 50

    def test_answer_formatting_system_non_vide(self) -> None:
        assert isinstance(ANSWER_FORMATTING_SYSTEM, str) and len(ANSWER_FORMATTING_SYSTEM) > 50

    def test_sql_generation_contient_user_id(self) -> None:
        assert ":user_id" in SQL_GENERATION_SYSTEM

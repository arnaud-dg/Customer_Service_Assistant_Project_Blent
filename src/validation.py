"""Validation end-to-end du pipeline sur le golden dataset.

Pour chaque question du dataset, vérifie :
  - questions "Conforme"     : un SQL valide avec :user_id est produit
  - questions "Non conforme" : aucun SQL n'est produit (refus ou redirection)

Usage :
    uv run python src/validation.py
    uv run python src/validation.py --dataset src/prompt/golden_dataset_v1.0.yaml
    uv run python src/validation.py --user-id 3
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.chain import build_graph, run_turn
from src.config import load_settings
from src.db import get_engine, get_user_profile
from src.llm.factory import get_llm

DATASET_DEFAULT = Path(__file__).parent / "prompt" / "golden_dataset_v1.0.yaml"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

_GREEN = "\033[32m"
_RED   = "\033[31m"
_DIM   = "\033[2m"
_RESET = "\033[0m"


# ── Chargement du dataset ─────────────────────────────────────────────────────

def _load_dataset(path: Path) -> tuple[int, list[dict[str, Any]]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data.get("user_id", 1), data["questions"]


# ── Critères de validation ────────────────────────────────────────────────────

def _refus_attendu(q: dict) -> bool:
    return q.get("comportement_attendu", "") in ("refus", "refus_poli")


def _check(q: dict, state: dict) -> tuple[bool, str]:
    sql = state.get("sql")

    if _refus_attendu(q):
        if sql is None:
            return True, ""
        return False, f"SQL inattendu produit : {sql[:80]}"

    if q.get("categorie", "").startswith("Conforme"):
        if sql is None:
            return False, "Aucun SQL produit"
        if ":user_id" not in sql:
            return False, "Filtre :user_id absent du SQL"
        if not sql.lstrip().lower().startswith("select"):
            return False, "Le SQL ne commence pas par SELECT"
        return True, ""

    return True, ""


# ── Point d'entrée ────────────────────────────────────────────────────────────

def run_validation(dataset_path: Path, cli_user_id: int | None = None, delay: float = 5.0) -> bool:
    settings = load_settings()
    engine   = get_engine(settings.db_path)
    llm      = get_llm(settings)
    graph    = build_graph(
        llm, engine,
        classifier_strategy=settings.classifier_strategy,
        advisor_phone=settings.advisor_phone,
    )

    default_uid, questions = _load_dataset(dataset_path)

    rows_csv: list[dict] = []
    passed = failed = 0

    print(f"\n  Dataset : {dataset_path.name}  ({len(questions)} questions)\n")
    print(f"  {'ID':>3}  {'':4}  {'Catégorie':<32}  Question")
    print(f"  {'─'*3}  {'─'*4}  {'─'*32}  {'─'*55}")

    for q in questions:
        qid      = q["id"]
        question = q["question"]
        categorie = q.get("categorie", "")
        user_id  = cli_user_id or q.get("user_id", default_uid)
        thread_id = f"validation-{qid}"

        profile = get_user_profile(engine, user_id) or {
            "user_id": user_id, "first_name": "—", "last_name": "—", "email": "—",
        }

        try:
            state = run_turn(
                graph,
                user_id=user_id,
                user_profile=profile,
                question=question,
                thread_id=thread_id,
            )
        except Exception as exc:
            # Rate limit ou erreur réseau : on marque FAIL sans planter
            label = f"{_RED}FAIL{_RESET}"
            motif = f"Exception : {exc.__class__.__name__} — {str(exc)[:120]}"
            print(f"  {qid:>3}  {label}  {categorie:<32}  {question[:55]}")
            print(f"  {'':>3}  {'':4}  {_DIM}↳ {motif}{_RESET}")
            failed += 1
            rows_csv.append({
                "id": qid, "categorie": categorie, "question": question,
                "user_id": user_id, "statut": "FAIL", "motif": motif,
                "sql_produit": "", "reponse": "",
            })
            time.sleep(delay * 4)
            continue

        ok, motif = _check(q, state)
        passed += ok
        failed += not ok

        label = f"{_GREEN}PASS{_RESET}" if ok else f"{_RED}FAIL{_RESET}"
        print(f"  {qid:>3}  {label}  {categorie:<32}  {question[:55]}")
        if not ok:
            print(f"  {'':>3}  {'':4}  {_DIM}↳ {motif}{_RESET}")

        rows_csv.append({
            "id":          qid,
            "categorie":   categorie,
            "question":    question,
            "user_id":     user_id,
            "statut":      "PASS" if ok else "FAIL",
            "motif":       motif,
            "sql_produit": state.get("sql") or "",
            "reponse":     (state.get("answer") or "")[:200],
        })

        time.sleep(delay)

    total = passed + failed
    print(f"\n  {'─'*70}")
    print(f"  Résultat : {passed}/{total}  ({failed} échec(s))\n")

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = OUTPUTS_DIR / f"validation_{ts}.csv"
    with open(report, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows_csv[0].keys())
        writer.writeheader()
        writer.writerows(rows_csv)

    print(f"  Rapport → {report.relative_to(PROJECT_ROOT)}\n")
    return failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validation end-to-end du pipeline")
    parser.add_argument(
        "--dataset", type=Path, default=DATASET_DEFAULT,
        help="Chemin vers le fichier YAML du golden dataset",
    )
    parser.add_argument(
        "--user-id", type=int, default=None,
        help="user_id à utiliser pour toutes les questions (surcharge le dataset)",
    )
    parser.add_argument(
        "--delay", type=float, default=1.5,
        help="Délai en secondes entre chaque appel API (défaut : 5.0)",
    )
    args = parser.parse_args()
    success = run_validation(args.dataset, cli_user_id=args.user_id, delay=args.delay)
    sys.exit(0 if success else 1)

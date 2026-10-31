"""
Converte imports do pacote antigo `app` para o novo `backend` (útil para testes e scripts antigos).

    python scripts/migrate_imports.py tests            # mostra o que mudaria (não grava)
    python scripts/migrate_imports.py tests --apply    # grava as alterações

Mapa:
    app.config    -> backend.core.config        app.ledger    -> backend.services.ledger
    app.auth      -> backend.core.security      app.iban      -> backend.services.iban
    app.db        -> backend.database           app.schemas   -> backend.schemas
    app.providers -> backend.providers          app.ai        -> backend.ai
    app.main      -> backend.main
Atenção: quem alterava `app.db.DB_PATH` num teste deve passar a usar `backend.database.connection.DB_PATH`.
"""
import argparse
import re
from pathlib import Path

IMPORT_MAP = [
    ("app.config", "backend.core.config"),
    ("app.auth", "backend.core.security"),
    ("app.db", "backend.database"),
    ("app.iban", "backend.services.iban"),
    ("app.ledger", "backend.services.ledger"),
    ("app.schemas", "backend.schemas"),
    ("app.providers", "backend.providers"),
    ("app.ai", "backend.ai"),
    ("app.main", "backend.main"),
]
SUFFIXES = {".py", ".ps1", ".md", ".ini", ".toml", ".cfg", ".txt", ".bat", ".sh"}


def convert(text: str) -> str:
    for old, new in IMPORT_MAP:
        text = re.sub(r"(?<![\w.])" + re.escape(old) + r"(?![\w])", new, text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", help="ficheiros ou pastas a converter")
    parser.add_argument("--apply", action="store_true", help="gravar as alterações")
    args = parser.parse_args()

    changed = 0
    for raw in args.paths:
        base = Path(raw)
        files = [base] if base.is_file() else [p for p in base.rglob("*") if p.is_file() and p.suffix in SUFFIXES and "__pycache__" not in p.parts]
        for path in files:
            try:
                original = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            updated = convert(original)
            if updated == original:
                continue
            changed += 1
            print(("ALTERADO  " if args.apply else "alteraria ") + str(path))
            for before, after in zip(original.splitlines(), updated.splitlines()):
                if before != after:
                    print(f"    - {before.strip()}\n    + {after.strip()}")
            if args.apply:
                path.write_text(updated, encoding="utf-8", newline="")
    print(f"\n{changed} ficheiro(s) {'alterado(s)' if args.apply else 'a alterar (use --apply para gravar)'}.")


if __name__ == "__main__":
    main()

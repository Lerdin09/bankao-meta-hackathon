"""
Mostra (ou grava) o index.html final, já com os partials montados.

    python scripts/build_index.py                # imprime no terminal
    python scripts/build_index.py -o /tmp/i.html # grava num ficheiro
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.web.includes import render_html  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--output", help="ficheiro de saída (por omissão: terminal)")
    args = parser.parse_args()

    frontend = ROOT / "frontend"
    html, used = render_html(frontend / "index.html", frontend)
    if args.output:
        Path(args.output).write_text(html, encoding="utf-8")
        print(f"{args.output}: {len(html)} bytes, {len(used)} ficheiros montados")
    else:
        sys.stdout.write(html)


if __name__ == "__main__":
    main()

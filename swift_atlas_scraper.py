"""
Diretório de códigos SWIFT/BIC de todos os países, a partir de dados abertos da GLEIF
(ficheiro oficial BIC-to-LEI, criado pela SWIFT e certificado pela GLEIF) + API pública da GLEIF
para obter o nome legal e a cidade de cada entidade.

Aviso: NÃO é o diretório oficial completo da SWIFT (esse é pago, o SWIFTRef). Este ficheiro só tem
os BIC que têm um LEI associado. Cobre a maioria dos bancos, mas não todas as filiais.
Veja o "BIC/LEI Mapping Table License Agreement" na página da GLEIF antes de redistribuir.

Instalação (dentro do venv):
    pip install openpyxl pycountry

Uso:
    python swift_bic_directory.py                      # descarrega o ficheiro e gera o xlsx
    python swift_bic_directory.py --zip LEI-BIC.zip    # usa um zip já descarregado
    python swift_bic_directory.py --no-names           # sem nomes (rápido, só BIC + LEI + país)
    python swift_bic_directory.py --country AO PT BR   # só alguns países (pelo código do BIC)

Página de download (se o link do mês mudar, descarregue o zip aí e use --zip):
    https://www.gleif.org/en/lei-data/lei-mapping/download-bic-to-lei-relationship-files
"""
import argparse
import csv
import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import pycountry
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

DEFAULT_URL = "https://mapping.gleif.org/api/v2/bic-lei/a134982b-b748-4a21-8b90-f48851584da0/download"
API = "https://api.gleif.org/api/v1/lei-records"
CACHE = Path("gleif_names_cache.json")
OUT = Path("swift_bic_directory.xlsx")
UA = "Mozilla/5.0 (X11; Linux x86_64) swift-bic-directory/1.0"
BATCH = 100
PAUSE = 0.4

# Códigos usados em BIC que não são ISO 3166 oficiais
EXTRA_COUNTRIES = {"XK": "Kosovo"}


def http_get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def country_name(code: str) -> str:
    if code in EXTRA_COUNTRIES:
        return EXTRA_COUNTRIES[code]
    c = pycountry.countries.get(alpha_2=code)
    return c.name if c else f"(código {code})"


def load_pairs(zip_path: Path | None, url: str):
    if zip_path:
        raw = zip_path.read_bytes()
        print(f"A ler {zip_path} ...")
    else:
        print("A descarregar o ficheiro BIC-to-LEI da GLEIF ...")
        try:
            raw = http_get(url, timeout=300)
        except (urllib.error.URLError, TimeoutError) as e:
            sys.exit(
                f"Falhou o download ({e}).\n"
                "Descarregue o zip manualmente em\n"
                "  https://www.gleif.org/en/lei-data/lei-mapping/download-bic-to-lei-relationship-files\n"
                "e volte a correr com:  python swift_bic_directory.py --zip <ficheiro.zip>"
            )
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
    if not names:
        sys.exit("O zip não contém nenhum CSV.")
    with zf.open(names[0]) as f:
        text = io.TextIOWrapper(f, encoding="utf-8-sig", newline="")
        reader = csv.DictReader(text)
        cols = {c.strip().upper(): c for c in (reader.fieldnames or [])}
        if "LEI" not in cols or "BIC" not in cols:
            sys.exit(f"Colunas inesperadas no CSV: {reader.fieldnames}")
        pairs = []
        for row in reader:
            lei = (row[cols["LEI"]] or "").strip().upper()
            bic = (row[cols["BIC"]] or "").strip().upper()
            if lei and len(bic) in (8, 11):
                pairs.append((bic, lei))
    print(f"{len(pairs)} ligações BIC-LEI lidas.")
    return pairs


def fetch_names(leis, no_names: bool):
    cache = {}
    if CACHE.exists():
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
    if no_names:
        return cache
    todo = sorted({l for l in leis if l not in cache})
    print(f"{len(todo)} LEIs por consultar na API da GLEIF ({len(cache)} já em cache).")
    for i in range(0, len(todo), BATCH):
        chunk = todo[i : i + BATCH]
        qs = urllib.parse.urlencode(
            {"filter[lei]": ",".join(chunk), "page[size]": str(BATCH)}, safe="[],"
        )
        for attempt in range(3):
            try:
                data = json.loads(http_get(f"{API}?{qs}", timeout=60))
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                if attempt == 2:
                    print(f"  lote {i // BATCH + 1}: falhou ({e}); continua sem estes nomes")
                    data = {"data": []}
                time.sleep(2 * (attempt + 1))
        for rec in data.get("data", []):
            a = rec.get("attributes", {})
            ent = a.get("entity", {})
            addr = ent.get("legalAddress", {}) or {}
            cache[a.get("lei", "")] = {
                "nome": (ent.get("legalName") or {}).get("name", ""),
                "cidade": addr.get("city", ""),
                "morada": " ".join(addr.get("addressLines", []) or []),
            }
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        done = min(i + BATCH, len(todo))
        print(f"  {done}/{len(todo)}")
        time.sleep(PAUSE)
    return cache


def build_xlsx(pairs, cache):
    rows = []
    for bic, lei in sorted(set(pairs), key=lambda p: (p[0][4:6], p[0])):
        info = cache.get(lei, {})
        cc = bic[4:6]
        rows.append(
            [
                country_name(cc),
                cc,
                bic,
                bic[:8],
                bic[:4],
                bic[6:8],
                bic[8:11] if len(bic) == 11 else "",
                info.get("nome", ""),
                info.get("cidade", ""),
                info.get("morada", ""),
                lei,
            ]
        )

    wb = Workbook()
    fill = PatternFill("solid", fgColor="1F4E78")
    font = Font(bold=True, color="FFFFFF")

    def header(ws, widths):
        for c in ws[1]:
            c.fill, c.font = fill, font
        for col, w in zip("ABCDEFGHIJKL", widths):
            ws.column_dimensions[col].width = w
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

    ws = wb.active
    ws.title = "SWIFT BIC"
    ws.append(
        ["País", "Cód. país", "BIC", "BIC8", "Cód. instituição", "Cód. local", "Filial",
         "Nome legal (GLEIF)", "Cidade", "Morada", "LEI"]
    )
    for r in rows:
        ws.append(r)
    header(ws, [26, 10, 14, 12, 16, 11, 8, 48, 22, 40, 24])

    ws2 = wb.create_sheet("Resumo por país")
    ws2.append(["País", "Cód. país", "Nº de BIC", "Nº de BIC8 (instituições/locais)"])
    agg = {}
    for r in rows:
        a = agg.setdefault((r[0], r[1]), [0, set()])
        a[0] += 1
        a[1].add(r[3])
    for (name, cc), (n, b8) in sorted(agg.items()):
        ws2.append([name, cc, n, len(b8)])
    header(ws2, [28, 10, 12, 30])

    ws3 = wb.create_sheet("Notas")
    for line in [
        "Fonte: ficheiro BIC-to-LEI (SWIFT + GLEIF) e API pública da GLEIF para nomes.",
        "Não é o diretório oficial completo da SWIFT: só inclui BIC com LEI associado.",
        "O país é lido das posições 5-6 do BIC; nomes, cidades e moradas vêm do registo LEI.",
        "BIC8 = instituição/local; BIC11 = com código de filial (posições 9-11).",
        "Consulte a licença 'BIC/LEI Mapping Table License Agreement' da GLEIF antes de redistribuir.",
    ]:
        ws3.append([line])
    ws3.column_dimensions["A"].width = 110
    for c in ws3["A"]:
        c.alignment = Alignment(wrap_text=True)

    wb.save(OUT)
    print(f"Guardado: {OUT}  ({len(rows)} BIC em {len(agg)} países)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", type=Path, help="zip BIC-to-LEI já descarregado")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--no-names", action="store_true", help="não consultar a API (rápido)")
    ap.add_argument("--country", nargs="+", help="filtrar por códigos de país (ex.: AO PT)")
    args = ap.parse_args()

    pairs = load_pairs(args.zip, args.url)
    if args.country:
        wanted = {c.upper() for c in args.country}
        pairs = [p for p in pairs if p[0][4:6] in wanted]
        print(f"{len(pairs)} ligações para {', '.join(sorted(wanted))}.")
    cache = fetch_names({l for _, l in pairs}, args.no_names)
    build_xlsx(pairs, cache)


if __name__ == "__main__":
    main()
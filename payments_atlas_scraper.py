"""
Extrai os sistemas de pagamento de cada país em thepaymentsatlas.com
e grava um ficheiro xlsx (e um CSV bruto).

Instalação (uma vez):
    pip install playwright openpyxl pycountry
    playwright install chromium

Uso:
    python payments_atlas_scraper.py            # todos os países
    python payments_atlas_scraper.py AO BR US   # só alguns (teste)

Notas:
- Faz uma pausa entre pedidos para não sobrecarregar o site.
- Guarda o progresso em payments_atlas_raw.csv; se parar a meio, volta a correr
  e ele continua dos países que faltam.
"""
import csv
import re
import sys
import time
from pathlib import Path

import pycountry
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from playwright.sync_api import sync_playwright

BASE = "https://thepaymentsatlas.com"
PAUSE = 1.5  # segundos entre países
RAW_CSV = Path("payments_atlas_raw.csv")
OUT_XLSX = Path("payments_atlas.xlsx")
DEBUG_DIR = Path("debug")

LEVELS = {"Very High", "High", "Medium", "Low", "Growing", "Emerging", "Declining"}
SKIP_LINES = {"Show comprehensive details", "Official Site"}
FIELDS = ["codigo", "pais", "sistema", "nivel", "descricao", "site_oficial", "url_pagina"]


def clean(text: str) -> str:
    """Remove marcadores de citação tipo [107][115] e espaços a mais."""
    return re.sub(r"\s+", " ", re.sub(r"\[\d+\]", "", text)).strip()


def norm_key(name: str) -> str:
    """Chave para detetar duplicados dentro do mesmo país."""
    n = re.sub(r"\(.*?\)", "", name.lower())
    return re.sub(r"[^a-z0-9]+", " ", n).strip()


def parse_country(page, code: str):
    url = f"{BASE}/country/{code}"
    resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
    status = resp.status if resp is not None else None
    # Espera o conteúdo carregar (o site é uma app JS); tolera falhas e continua
    try:
        page.wait_for_selector("text=Payment Systems in", timeout=30000)
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass
    page.wait_for_timeout(2000)

    text = page.inner_text("body")
    if "Payment Systems in" not in text:
        # Diagnóstico: guarda o que o browser realmente viu
        DEBUG_DIR.mkdir(exist_ok=True)
        (DEBUG_DIR / f"{code}.txt").write_text(text, encoding="utf-8")
        (DEBUG_DIR / f"{code}.html").write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(DEBUG_DIR / f"{code}.png"), full_page=True)
        print(f"    HTTP {status} | título: {page.title()!r} | {len(text)} caracteres")
        print(f"    diagnóstico guardado em {DEBUG_DIR}/{code}.(txt|html|png)")
        return None, []
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # Nome do país: linha logo a seguir à bandeira / antes de "Home"
    country = code
    m = re.search(r"Payment Systems in (.+)", text)
    if m:
        country = m.group(1).strip()

    # Links "Official Site" por ordem de aparecimento
    site_links = page.eval_on_selector_all(
        "a",
        "els => els.filter(e => e.innerText.trim() === 'Official Site').map(e => e.href)",
    )

    # Zona dos sistemas: entre "Comprehensive overview..." e "Country Information"
    try:
        start = next(i for i, l in enumerate(lines) if l.startswith("Comprehensive overview")) + 1
    except StopIteration:
        return country, []
    try:
        end = next(i for i, l in enumerate(lines) if l == "Country Information")
    except StopIteration:
        end = len(lines)
    block = lines[start:end]

    rows = []
    link_idx = 0
    i = 0
    while i < len(block):
        # Um sistema começa em: nome, seguido de uma linha de nível
        if i + 1 < len(block) and block[i + 1] in LEVELS and block[i] not in LEVELS:
            name = clean(block[i])
            level = block[i + 1]
            i += 2
            desc_parts = []
            has_site = False
            while i < len(block):
                nxt = block[i]
                # Fim do bloco: próximo sistema (nome + nível) ou fim da lista
                if i + 1 < len(block) and block[i + 1] in LEVELS and nxt not in LEVELS:
                    break
                if nxt == "Official Site":
                    has_site = True
                elif nxt not in SKIP_LINES:
                    d = clean(nxt)
                    if d and d not in desc_parts:  # o site repete a descrição
                        desc_parts.append(d)
                i += 1
            site = ""
            if has_site and link_idx < len(site_links):
                site = site_links[link_idx]
            if has_site:
                link_idx += 1
            rows.append(
                {
                    "codigo": code,
                    "pais": country,
                    "sistema": name,
                    "nivel": level,
                    "descricao": " ".join(desc_parts),
                    "site_oficial": site,
                    "url_pagina": url,
                }
            )
        else:
            i += 1
    return country, rows


def load_done():
    done = set()
    if RAW_CSV.exists():
        with RAW_CSV.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                done.add(r["codigo"])
    return done


def append_rows(rows):
    new = not RAW_CSV.exists()
    with RAW_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)


def build_xlsx():
    with RAW_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Marca duplicados dentro de cada país (mesmo nome normalizado)
    seen = {}
    for r in rows:
        key = (r["codigo"], norm_key(r["sistema"]))
        r["duplicado"] = "sim" if key in seen else ""
        seen.setdefault(key, r)

    wb = Workbook()
    head_fill = PatternFill("solid", fgColor="1F4E78")
    head_font = Font(bold=True, color="FFFFFF")

    def style_header(ws, widths):
        for c in ws[1]:
            c.fill, c.font = head_fill, head_font
        for col, w in zip("ABCDEFGH", widths):
            ws.column_dimensions[col].width = w
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

    # Folha 1: sistemas (sem duplicados)
    ws = wb.active
    ws.title = "Sistemas"
    ws.append(["Código", "País", "Sistema / Método", "Nível", "Descrição", "Site oficial"])
    for r in sorted(rows, key=lambda x: (x["pais"], x["sistema"])):
        if r["duplicado"]:
            continue
        ws.append([r["codigo"], r["pais"], r["sistema"], r["nivel"], r["descricao"], r["site_oficial"]])
    style_header(ws, [9, 28, 42, 12, 70, 45])
    for row in ws.iter_rows(min_row=2):
        row[4].alignment = Alignment(wrap_text=True, vertical="top")

    # Folha 2: países
    ws2 = wb.create_sheet("Países")
    ws2.append(["Código", "País", "Nº de sistemas (únicos)"])
    counts = {}
    for r in rows:
        if not r["duplicado"]:
            counts.setdefault((r["codigo"], r["pais"]), 0)
            counts[(r["codigo"], r["pais"])] += 1
    for (code, name), n in sorted(counts.items(), key=lambda x: x[0][1]):
        ws2.append([code, name, n])
    style_header(ws2, [9, 32, 24])

    # Folha 3: duplicados removidos
    ws3 = wb.create_sheet("Duplicados removidos")
    ws3.append(["Código", "País", "Sistema / Método", "Nível", "Descrição", "Site oficial"])
    for r in rows:
        if r["duplicado"]:
            ws3.append([r["codigo"], r["pais"], r["sistema"], r["nivel"], r["descricao"], r["site_oficial"]])
    style_header(ws3, [9, 28, 42, 12, 70, 45])

    wb.save(OUT_XLSX)
    print(f"xlsx guardado: {OUT_XLSX}  ({len(counts)} países, {sum(counts.values())} sistemas únicos)")


def main():
    if len(sys.argv) > 1:
        codes = [c.upper() for c in sys.argv[1:]]
    else:
        codes = sorted(c.alpha_2 for c in pycountry.countries)

    done = load_done()
    todo = [c for c in codes if c not in done]
    print(f"{len(todo)} países por processar ({len(done)} já feitos)")

    failed = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 900},
            locale="en-US",
        )
        page = context.new_page()
        for n, code in enumerate(todo, 1):
            try:
                country, rows = parse_country(page, code)
            except Exception as e:  # noqa: BLE001
                print(f"[{n}/{len(todo)}] {code}: erro ({e})")
                failed.append(code)
                time.sleep(PAUSE)
                continue
            if not rows:
                print(f"[{n}/{len(todo)}] {code}: sem dados / página inexistente")
                failed.append(code)
            else:
                append_rows(rows)
                print(f"[{n}/{len(todo)}] {code} {country}: {len(rows)} sistemas")
            time.sleep(PAUSE)
        browser.close()

    if RAW_CSV.exists():
        build_xlsx()
    if failed:
        print("Sem dados para:", " ".join(failed))


if __name__ == "__main__":
    main()
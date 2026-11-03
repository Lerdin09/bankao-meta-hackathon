"""
Guardas da estrutura do frontend. Falham quando alguém:
  • cria um .js/.css/partial e esquece de o ligar ao index (ou main.css);
  • referencia um ficheiro que não existe;
  • deixa ids duplicados no HTML montado.
"""
import re
from pathlib import Path

from backend.web.includes import render_html

ROOT = Path(__file__).resolve().parents[1] / "frontend"


def _html():
    return render_html(ROOT / "index.html", ROOT)


def test_scripts_existem_e_nao_ha_js_esquecido():
    html, _ = _html()
    referenciados = re.findall(r'<script src="/static/js/([^"]+)"', html)
    assert len(referenciados) == len(set(referenciados)), "script repetido no index"
    em_disco = {p.relative_to(ROOT / "js").as_posix() for p in (ROOT / "js").rglob("*.js")}
    assert set(referenciados) == em_disco, (
        f"sem <script>: {sorted(em_disco - set(referenciados))} | em falta no disco: {sorted(set(referenciados) - em_disco)}"
    )


def test_main_js_carrega_em_ultimo():
    html, _ = _html()
    referenciados = re.findall(r'<script src="/static/js/([^"]+)"', html)
    assert referenciados[-1] == "main.js"
    assert referenciados[0].startswith("core/")


def test_css_importado_existe_e_nao_ha_css_esquecido():
    main = (ROOT / "css" / "main.css").read_text(encoding="utf-8")
    importados = re.findall(r'@import url\("([^"]+)"\);', main)
    assert len(importados) == len(set(importados)), "@import repetido"
    em_disco = {p.relative_to(ROOT / "css").as_posix() for p in (ROOT / "css").rglob("*.css")} - {"main.css"}
    assert set(importados) == em_disco, (
        f"sem @import: {sorted(em_disco - set(importados))} | em falta no disco: {sorted(set(importados) - em_disco)}"
    )


def test_html_montado_sem_includes_por_resolver_e_ids_unicos():
    html, usados = _html()
    assert "@include" not in html
    ids = re.findall(r'\sid="([^"]+)"', html)
    duplicados = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicados, f"ids duplicados: {duplicados}"
    partials = {p.resolve() for p in (ROOT / "partials").rglob("*.html")}
    assert partials <= usados, f"partials não usados: {sorted(p.name for p in partials - usados)}"


def test_handlers_inline_principais_existem_no_js():
    """Os onclick="nome(...)" do HTML têm de corresponder a funções definidas nos módulos JS."""
    html, _ = _html()
    js = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "js").rglob("*.js"))
    definidos = set(re.findall(r"function\s+([A-Za-z_$][\w$]*)", js))
    definidos |= set(re.findall(r"window\.([A-Za-z_$][\w$]*)\s*=", js))
    usados = set()
    for handler in re.findall(r'\son[a-z]+="([^"]*)"', html):
        usados |= set(re.findall(r"(?<![\w.$])([A-Za-z_$][\w$]*)\s*\(", handler))
    ignorar = {"event", "if", "return", "function"}
    em_falta = sorted(n for n in usados - definidos - ignorar)
    assert not em_falta, f"handlers sem função: {em_falta}"


def test_grafico_previsao_saldo_ativo_sem_em_breve():
    """O 6.º gráfico (Previsão do saldo) tem de estar ativo, sem 'Em breve' e com o painel bcPanelForecast."""
    html, _ = _html()
    assert 'data-chart="forecast"' in html
    assert 'id="bcPanelForecast"' in html
    assert 'id="fcFullChart"' in html
    assert 'Previsão do saldo</span><em class="bc-soon">Em breve</em>' not in html


"""
Gráfico 5 «Fluxo entre contas» (Sankey): o cálculo e a disposição não tocam no DOM, por isso
correm em Node com movimentos sintéticos. Verifica que cada conta fecha as contas (entra = sai),
que as colunas somam o mesmo total, que câmbio e taxas aparecem e que a disposição não sobrepõe blocos.
Ignorado se o Node não estiver instalado.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js" / "features" / "card-chart" / "accounts-flow-chart.js"

RUNNER = r"""
const fs = require("fs"), vm = require("vm");
const win = {};
const ctx = { window: win, localStorage: { getItem() { return null; }, setItem() {} }, console, Date, Math, Map, Set,
  parseTxDate: r => new Date(String(r).replace(" ", "T") + "Z"),
  classifyStatementTx: tx => /compra/i.test(tx.description || "") ? "purchases" : "others" };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
const RATES = { EUR_AOA: 1000, USD_AOA: 900, EUR_USD: 1.1 };
const convert = (v, f, t) => f === t ? v : RATES[f + "_" + t] ? v * RATES[f + "_" + t] : RATES[t + "_" + f] ? v / RATES[t + "_" + f] : 0;
let id = 0;
const T = o => Object.assign({ id: ++id, transaction_id: "t" + id, status: "completed", created_at: "2026-10-20 10:00:00", currency: "AOA" }, o);
const tx = [
  T({ type: "deposit", amount_decimal: 500000, description: "Depósito", counterparty: { name: "Multicaixa Express" } }),
  T({ type: "deposit", amount_decimal: 300, currency: "EUR", description: "Depósito", counterparty: { name: "Multicaixa Express" } }),
  T({ type: "purchase", amount_decimal: -45000, description: "Compra Shoprite" }),
  T({ type: "savings_deposit", amount_decimal: -80000, description: "Meta" }),
  T({ type: "transfer_internal", amount_decimal: -100000, description: "Transf", transfer: { fee_decimal: 1000 } }),
  T({ type: "transfer_internal", amount_decimal: 50000, description: "Recebido" }),
  T({ type: "transfer_iban", amount_decimal: -100, currency: "EUR", description: "Envio", transfer: { fee_decimal: 2.5, source_currency: "EUR", dest_currency: "USD", dest_amount_decimal: 107 } }),
  T({ type: "fx_exchange", transaction_id: "fx1", amount_decimal: -100000, description: "Câmbio", transfer: { fee_decimal: 2500 } }),
  T({ type: "fx_exchange", transaction_id: "fx1", amount_decimal: 97.5, currency: "EUR", description: "Câmbio" }),
  T({ type: "purchase", amount_decimal: -9999, description: "Compra falhada", status: "failed" }),
];
const m = win.accountsFlowBuild(tx, { cur: "AOA", since: 0, convert });
const g700 = win.accountsFlowLayout(m, 700), g360 = win.accountsFlowLayout(m, 360);
const overlap = g => { const bad = []; [0, 1, 2].forEach(c => { const col = m.nodes.filter(n => n.col === c).sort((a, b) => a.y - b.y); for (let i = 1; i < col.length; i++) if (col[i].y < col[i - 1].y + col[i - 1].h - 0.01) bad.push(col[i].id); }); return bad; };
const empty = win.accountsFlowBuild([], { cur: "AOA", since: 0, convert });
const noRate = win.accountsFlowBuild(tx, { cur: "AOA", since: 0, convert: () => 0 });
console.log(JSON.stringify({
  accounts: m.nodes.filter(n => n.col === 1).map(n => [n.id, n.sumIn, n.sumOut]),
  cols: [0, 1, 2].map(c => m.nodes.filter(n => n.col === c).reduce((a, n) => a + n.value, 0)),
  ids: m.nodes.map(n => n.id), fx: m.links.filter(l => l.fx).map(l => l.key), fees: m.fees, fxCount: m.fxCount,
  saved: m.saved, income: m.income, failedCounted: m.nOps,
  overlap: [overlap(g700), overlap(g360)], badLinks: m.links.filter(l => !/^M[\d.\-]/.test(l.d) || /NaN/.test(l.d)).length,
  empty: empty.empty, skipped: noRate.skipped
}));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js não instalado")
def test_sankey_model_and_layout():
    out = subprocess.run(["node", "-e", RUNNER, str(JS)], capture_output=True, text=True, check=True).stdout
    r = json.loads(out)
    for _id, s_in, s_out in r["accounts"]:
        assert abs(s_in - s_out) < 1e-6, f"{_id} não fecha as contas"
    assert max(r["cols"]) - min(r["cols"]) < 1e-6, "as três colunas têm de somar o mesmo total"
    assert {"in:dep:multicaixa express", "in:xfer", "out:buy", "out:sav", "out:fee", "out:fx", "out:own", "in:own", "out:keep"} <= set(r["ids"])
    assert "acc:EUR>out:fx" in r["fx"] and any(k.endswith(">out:own") for k in r["fx"])
    assert r["fxCount"] == 2 and r["fees"] > 0 and r["saved"] == 80000
    assert r["income"] == 500000 + 300 * 1000 + 50000
    assert r["failedCounted"] == 8, "movimentos falhados não entram"
    assert r["overlap"] == [[], []] and r["badLinks"] == 0
    assert r["empty"] is True and r["skipped"] > 0

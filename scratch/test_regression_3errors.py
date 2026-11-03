"""
Bateria de Regressão Crítica: Os 3 Erros Reportados Originais (21 Testes)
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')

from backend.ai.orchestrator import CopilotOrchestrator

USER_ID = '2e0a4847-d1a9-48a6-86de-40229a125b58'

TEST_CASES = [
    # ── ERRO 1: INVESTIMENTOS (7 testes) ──────────────────────────────────────
    (1, 1, "Recomenda-me um tipo de investimento.",
     ["depósito", "prazo", "18,5", "bodiva", "catálogo", "investimento"]),
    (1, 2, "Que investimentos posso fazer no BankAO?",
     ["depósito", "prazo", "bodiva", "ot", "fundo", "investimento"]),
    (1, 3, "Onde devo investir 100 mil Kz?",
     ["100.000", "depósito", "prazo", "fundo", "kz"]),
    (1, 4, "Quero um investimento de baixo risco.",
     ["depósito", "prazo", "garantido", "fgd", "baixo risco", "capital"]),
    (1, 5, "Qual é o melhor investimento para 6 meses?",
     ["6 meses", "fundo", "depósito", "prazo", "liquidez"]),
    (1, 6, "Compara os investimentos disponíveis.",
     ["depósito", "prazo", "bodiva", "ot", "fundo", "taxa"]),
    (1, 7, "Quanto posso ganhar investindo 500 mil Kz?",
     ["500.000", "juros", "ganhar", "kz", "rendimento"]),

    # ── ERRO 2: PROJEÇÃO FINANCEIRA (7 testes) ───────────────────────────────
    (2, 1, "Qual a projeção de quanto eu terei até 2027 janeiro?",
     ["janeiro", "2027", "património", "saldo", "metas", "kz"]),
    (2, 2, "Quanto terei em janeiro de 2027?",
     ["janeiro", "2027", "património", "kz", "contas"]),
    (2, 3, "Prevê o meu saldo para 31/01/2027.",
     ["2027", "janeiro", "saldo", "kz"]),
    (2, 4, "Faz uma previsão financeira até janeiro de 2027.",
     ["previsão", "janeiro", "2027", "kz", "património"]),
    (2, 5, "Quanto dinheiro terei daqui a dois meses?",
     ["dezembro", "2026", "2 meses", "meses", "kz"]),
    (2, 6, "Mostra a evolução prevista do meu saldo.",
     ["evolução", "previsão", "saldo", "kz"]),
    (2, 7, "Se mantiver os meus hábitos atuais, quanto terei em janeiro?",
     ["janeiro", "2027", "hábitos", "património", "kz"]),

    # ── ERRO 3: MAIOR DESPESA (7 testes) ─────────────────────────────────────
    (3, 1, "Meu maior gasto de setembro",
     ["setembro", "150.000", "85.000", "hilux", "condomínio", "kz"]),
    (3, 2, "Qual foi a minha maior despesa em setembro?",
     ["setembro", "maior", "kz", "85.000", "150.000"]),
    (3, 3, "Mostra o gasto mais elevado do mês de setembro.",
     ["setembro", "kz", "85.000", "150.000"]),
    (3, 4, "Em que gastei mais dinheiro em setembro?",
     ["setembro", "poupança", "habitação", "condomínio", "kz"]),
    (3, 5, "Quais foram as minhas três maiores despesas de setembro?",
     ["setembro", "3", "maiores", "kz"]),
    (3, 6, "Qual foi o estabelecimento onde gastei mais em setembro?",
     ["condomínio", "talatona", "setembro", "kz"]),
    (3, 7, "Quanto foi a minha maior compra em setembro de 2026?",
     ["setembro", "2026", "kz", "condomínio", "talatona", "85.000"]),
]

GENERIC_ERRORS = [
    "não consegui processar o seu pedido",
    "não consegui contactar o assistente",
    "seu pedido não foi encontrado",
    "algo correu mal",
    "erro interno",
]

print("=" * 70, flush=True)
print("BATERIA DE REGRESSÃO CRÍTICA — OS 3 ERROS REPORTADOS", flush=True)
print("=" * 70, flush=True)

total_passed = 0
total_failed = 0
failed_cases = []

curr_block = 0
block_names = {
    1: "ERRO 1 — Investimentos",
    2: "ERRO 2 — Projeção Financeira",
    3: "ERRO 3 — Maior Despesa"
}

for block, idx, q, keywords in TEST_CASES:
    if block != curr_block:
        curr_block = block
        print(f"\n{'━'*70}", flush=True)
        print(f"▶ {block_names[block]}", flush=True)
        print(f"{'━'*70}", flush=True)

    try:
        res = CopilotOrchestrator.process_message(USER_ID, q)
        reply = res.get("reply", "") or ""
        tools = res.get("tools_used", [])

        # Critério 1: Nenhuma mensagem genérica de erro
        has_generic_error = any(ge in reply.lower() for ge in GENERIC_ERRORS)
        
        # Critério 2: Resposta substancial (> 50 chars)
        is_substantial = len(reply) > 50

        # Critério 3: Keywords presentes
        kw_hits = [kw for kw in keywords if kw.lower() in reply.lower()]
        has_keywords = len(kw_hits) >= 2

        is_pass = is_substantial and not has_generic_error and has_keywords
        status = "✅ PASS" if is_pass else "❌ FAIL"

        if is_pass:
            total_passed += 1
        else:
            total_failed += 1
            failed_cases.append((block, idx, q, reply, has_generic_error, kw_hits))

        print(f"\n[{block}.{idx}] {status} | Tools: {tools}", flush=True)
        print(f"      Q: \"{q}\"", flush=True)
        print(f"      R: {reply[:140].strip()}...", flush=True)

    except Exception as e:
        total_failed += 1
        failed_cases.append((block, idx, q, str(e), True, []))
        print(f"\n[{block}.{idx}] 💥 ERROR: {e}", flush=True)

print("\n" + "=" * 70, flush=True)
print(f"RESULTADO DA REGRESSÃO: {total_passed}/{len(TEST_CASES)} PASS | {total_failed} FAIL", flush=True)
print("=" * 70, flush=True)

if failed_cases:
    print("\nFALHAS REGISTADAS:")
    for b, i, q, r, err, kwh in failed_cases:
        print(f"[{b}.{i}] {q} -> generic_err={err}, kwh={kwh}")
        print(f"     Reply: {r[:200]}")
else:
    print("\n🎉 Todos os 21 testes dos 3 erros reportados passaram com 100% de sucesso!")


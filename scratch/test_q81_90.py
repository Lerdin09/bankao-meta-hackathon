"""
Test Q81–Q90: Contas, Saldos e Movimentos Bancários
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')

from backend.ai.orchestrator import CopilotOrchestrator

USER_ID = '2e0a4847-d1a9-48a6-86de-40229a125b58'

QUESTIONS = [
    (81, "Qual é o meu saldo total em todas as contas?"),
    (82, "Quanto dinheiro tenho disponível para gastar?"),
    (83, "Quanto dinheiro entrou na minha conta este mês?"),
    (84, "Quanto dinheiro saiu da minha conta este mês?"),
    (85, "Qual foi a minha maior entrada de dinheiro?"),
    (86, "Mostra-me todas as transferências que fiz durante outubro."),
    (87, "Qual foi o último movimento realizado na minha conta?"),
    (88, "Quanto dinheiro recebi nos últimos 90 dias?"),
    (89, "Qual é a diferença entre o saldo atual e o saldo do início do mês?"),
    (90, "Existem movimentos pendentes que ainda não foram concluídos?"),
]

print("=" * 70, flush=True)
print("TESTE: Contas, Saldos e Movimentos Bancários (Q81–Q90)", flush=True)
print("=" * 70, flush=True)

passed = 0
failed = 0
results = []

for qnum, q in QUESTIONS:
    try:
        res = CopilotOrchestrator.process_message(USER_ID, q)
        reply = res.get("reply", "") or ""
        tools = res.get("tools_used", [])

        is_error = "não consegui" in reply.lower() or "não foi possível" in reply.lower()
        is_pass = len(reply) > 40 and not is_error

        status = "✅ PASS" if is_pass else "❌ FAIL"
        if is_pass: passed += 1
        else: failed += 1

        print(f"\nQ{qnum}: {status} (tools: {tools})", flush=True)
        print(f"  Pergunta: {q}", flush=True)
        print(f"  Resposta ({len(reply)} ch): {reply.strip()}", flush=True)
        results.append((qnum, q, status, reply, tools))
    except Exception as e:
        failed += 1
        print(f"\nQ{qnum}: 💥 ERROR — {e}", flush=True)

print("\n" + "=" * 70, flush=True)
print(f"RESULTADO: {passed}/{len(QUESTIONS)} PASS | {failed} FAIL", flush=True)
print("=" * 70, flush=True)


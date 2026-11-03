"""
Test Q91–Q100: Testes de Raciocínio, Memória e Interpretação
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')

from backend.ai.orchestrator import CopilotOrchestrator

USER_ID = '2e0a4847-d1a9-48a6-86de-40229a125b58'

QUESTIONS = [
    (91, "Se eu ganhar 400.000 Kz e gastar 250.000 Kz, quanto posso poupar?"),
    (92, "Se investir 100.000 Kz e gastar 50.000 Kz, quanto sobra dos meus 300.000 Kz iniciais?"),
    (93, "Quero poupar 20% do meu salário de 350.000 Kz. Quanto devo guardar?"),
    (94, "Compara a minha situação financeira deste mês com a do mês passado e explica as diferenças."),
    (95, "Se eu disser que quero poupar 100 mil e depois corrigir para 150 mil, qual será o valor utilizado no meu plano?"),
    (96, "Se eu perguntar quanto gastei no mês passado, sabes identificar automaticamente o mês correto?"),
    (97, "Se eu pedir para analisar as minhas despesas e depois perguntar qual categoria teve maior aumento, consegues utilizar os resultados anteriores?"),
    (98, "Se não tiver dados suficientes para responder a uma pergunta, como vais proceder?"),
    (99, "Se a API de investimentos estiver indisponível, consegues explicar o problema sem inventar resultados?"),
    (100, "Se eu pedir uma operação bancária com informações contraditórias, vais pedir esclarecimentos antes de preparar a operação?"),
]

print("=" * 70, flush=True)
print("TESTE: Raciocínio, Memória e Interpretação (Q91–Q100)", flush=True)
print("=" * 70, flush=True)

passed = 0
failed = 0
results = []

for qnum, q in QUESTIONS:
    try:
        res = CopilotOrchestrator.process_message(USER_ID, q)
        reply = res.get("reply", "") or ""
        tools = res.get("tools_used", [])

        is_error = "não consegui processar" in reply.lower() or "algo correu mal" in reply.lower()
        is_pass = len(reply) > 30 and not is_error

        status = "✅ PASS" if is_pass else "❌ FAIL"
        if is_pass: passed += 1
        else: failed += 1

        print(f"\nQ{qnum}: {status} (tools: {tools})", flush=True)
        print(f"  Pergunta: {q}", flush=True)
        print(f"  Resposta ({len(reply)} ch):\n{reply.strip()}", flush=True)
        results.append((qnum, q, status, reply, tools))
    except Exception as e:
        failed += 1
        print(f"\nQ{qnum}: 💥 ERROR — {e}", flush=True)

print("\n" + "=" * 70, flush=True)
print(f"RESULTADO: {passed}/{len(QUESTIONS)} PASS | {failed} FAIL", flush=True)
print("=" * 70, flush=True)


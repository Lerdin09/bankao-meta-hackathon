import sys
import os
import json

# Ensure unbuffered output
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)
sys.path.insert(0, os.path.abspath("."))

from backend.database import get_connection
from backend.ai.orchestrator import CopilotOrchestrator

def run_suite():
    conn = get_connection()
    user_row = conn.execute("SELECT id, nome, email FROM users WHERE email='joao.makiesse@bankao.ao'").fetchone()
    conn.close()
    if not user_row:
        print("ERROR: User joao.makiesse@bankao.ao not found!", flush=True)
        return

    user_id = user_row["id"]
    print(f"Testing with User: {user_row['nome']} ({user_id})", flush=True)

    questions = [
        (21, "Qual é a projeção do meu saldo para janeiro de 2027?"),
        (22, "Quanto dinheiro poderei ter daqui a três meses?"),
        (23, "Quanto dinheiro terei no final de dezembro de 2026?"),
        (24, "Se continuar a gastar como estou a gastar atualmente, quanto terei daqui a seis meses?"),
        (25, "Faz uma previsão do meu saldo para os próximos 12 meses."),
        (26, "Quanto poderei poupar até ao final de 2027?"),
        (27, "Se receber o mesmo salário todos os meses e mantiver as despesas atuais, qual será a minha situação financeira em janeiro?"),
        (28, "Mostra-me um gráfico da evolução prevista do meu saldo."),
        (29, "Qual será o meu saldo se reduzir as despesas em 20%?"),
        (30, "E se aumentar as minhas despesas em 30%?"),
        (31, "Quanto preciso de poupar mensalmente para chegar aos 2 milhões de Kz em dezembro de 2027?"),
        (32, "Se começar a poupar 50.000 Kz por mês, quando atingirei 500.000 Kz?"),
        (33, "Com base nos meus rendimentos e despesas, estou financeiramente preparado para comprar um carro?"),
        (34, "Qual será o meu saldo depois de pagar todas as despesas recorrentes?"),
        (35, "Compara a minha situação financeira atual com a previsão para os próximos seis meses.")
    ]

    all_passed = True
    results = []

    for q_num, prompt in questions:
        print(f"\n==================================================", flush=True)
        print(f"Running Question {q_num}: {prompt}", flush=True)
        res = CopilotOrchestrator.process_message(user_id=user_id, message=prompt)
        reply = res.get("reply", "")
        chart = res.get("chart")
        tools = res.get("tools_used", [])

        has_reply = bool(reply and len(reply.strip()) > 30)
        has_error = "Não consegui" in reply or "erro" in reply.lower()
        
        status = "PASS" if has_reply and not has_error else "FAIL"
        if status == "FAIL":
            all_passed = False

        print(f"Status: {status} | Tools: {tools} | Chart: {bool(chart)}", flush=True)
        print(f"Reply Preview:\n{reply[:250]}...\n", flush=True)
        results.append({
            "num": q_num,
            "prompt": prompt,
            "status": status,
            "tools": tools,
            "has_chart": bool(chart),
            "reply": reply
        })

    print("\n" + "="*50, flush=True)
    print(f"FINAL RESULT: {'ALL 15 TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}", flush=True)
    print("="*50, flush=True)
    for r in results:
        print(f"Q{r['num']}: [{r['status']}] {r['prompt'][:45]}... (tools: {r['tools']})", flush=True)

if __name__ == "__main__":
    run_suite()

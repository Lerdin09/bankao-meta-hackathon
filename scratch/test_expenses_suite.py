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
    print(f"Testing Expenses Suite with User: {user_row['nome']} ({user_id})\n", flush=True)

    questions = [
        (36, "Qual foi o meu maior gasto de setembro?"),
        (37, "Quanto gastei no total durante setembro?"),
        (38, "Qual foi a categoria em que gastei mais dinheiro?"),
        (39, "Quanto gastei em alimentação no mês passado?"),
        (40, "Quanto gastei em transportes nos últimos três meses?"),
        (41, "Quais foram as minhas cinco maiores despesas deste ano?"),
        (42, "Qual foi o estabelecimento onde gastei mais dinheiro?"),
        (43, "Compara as minhas despesas de setembro com as de outubro."),
        (44, "Em que mês gastei mais dinheiro este ano?"),
        (45, "Quais são as despesas que mais estão a prejudicar a minha capacidade de poupar?"),
        (46, "Quanto dinheiro gasto mensalmente em média?"),
        (47, "Quais foram as minhas despesas durante a última semana?"),
        (48, "Quanto gastei em compras online?"),
        (49, "Mostra-me todas as despesas superiores a 20.000 Kz."),
        (50, "Existem despesas repetidas ou cobranças semelhantes na minha conta?"),
        (51, "Quanto gastei em restaurantes desde janeiro?"),
        (52, "Qual foi a minha maior despesa individual nos últimos 30 dias?"),
        (53, "Quais são as três categorias em que posso reduzir os meus gastos?"),
        (54, "Quanto dinheiro gastei em despesas desnecessárias?"),
        (55, "Faz um relatório completo dos meus gastos deste ano.")
    ]

    all_passed = True
    results = []

    for q_num, prompt in questions:
        print(f"\n==================================================", flush=True)
        print(f"Running Question {q_num}: {prompt}", flush=True)
        res = CopilotOrchestrator.process_message(user_id=user_id, message=prompt)
        reply = res.get("reply", "")
        tools = res.get("tools_used", [])

        has_reply = bool(reply and len(reply.strip()) > 30)
        has_error = "Não consegui" in reply or "erro na execução" in reply.lower()
        
        status = "PASS" if has_reply and not has_error else "FAIL"
        if status == "FAIL":
            all_passed = False

        print(f"Status: {status} | Tools: {tools}", flush=True)
        print(f"Reply Preview:\n{reply[:250]}...\n", flush=True)
        results.append({
            "num": q_num,
            "prompt": prompt,
            "status": status,
            "tools": tools,
            "reply": reply
        })

    print("\n" + "="*50, flush=True)
    print(f"FINAL RESULT: {'ALL 20 TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}", flush=True)
    print("="*50, flush=True)
    for r in results:
        print(f"Q{r['num']}: [{r['status']}] {r['prompt'][:45]}... (tools: {r['tools']})", flush=True)

if __name__ == "__main__":
    run_suite()


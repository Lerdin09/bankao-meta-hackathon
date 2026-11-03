"""
Smoke test COMPLETO: 70 perguntas da demo do BankAO Copilot
Verifica que nenhuma pergunta retorna erro ou resposta vazia.
Run: python scratch/test_full_70.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')

from backend.ai.orchestrator import CopilotOrchestrator

USER_ID = '2e0a4847-d1a9-48a6-86de-40229a125b58'

ALL_QUESTIONS = [
    # INVESTIMENTOS (1-20)
    (1,  "Recomenda-me o melhor tipo de investimento disponível no banco."),
    (2,  "Tenho 100.000 Kz disponíveis. Onde seria melhor investir esse dinheiro?"),
    (3,  "Qual é o investimento que oferece a maior rentabilidade atualmente?"),
    (4,  "Qual é a diferença entre investir em obrigações, depósitos a prazo e ETFs?"),
    (5,  "Quais são os investimentos de menor risco disponíveis?"),
    (6,  "Quero investir 500.000 Kz durante 12 meses. Quanto poderei ganhar?"),
    (7,  "Se investir 200.000 Kz com uma taxa anual de 15%, quanto receberei ao fim de um ano?"),
    (8,  "Compara os três investimentos mais rentáveis disponíveis no banco."),
    (9,  "Qual é o investimento que permite recuperar o dinheiro mais rapidamente?"),
    (10, "Que investimento recomendarias para alguém que nunca investiu?"),
    (11, "Quais são as vantagens e desvantagens de investir agora?"),
    (12, "Posso perder dinheiro com algum dos investimentos disponíveis?"),
    (13, "Qual é o valor mínimo necessário para começar a investir?"),
    (14, "Se investir 50.000 Kz todos os meses durante um ano, quanto poderei acumular?"),
    (15, "Qual é a diferença entre juros simples e juros compostos?"),
    (16, "Mostra-me os investimentos que já tenho."),
    (17, "Quanto dinheiro já investi no total?"),
    (18, "Quanto lucro obtive com os meus investimentos?"),
    (19, "Qual dos meus investimentos está a render mais?"),
    (20, "Qual dos meus investimentos está próximo do vencimento?"),
    # PREVISÕES (21-35)
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
    (35, "Compara a minha situação financeira atual com a previsão para os próximos seis meses."),
    # DESPESAS (36-55)
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
    (55, "Faz um relatório completo dos meus gastos deste ano."),
    # POUPANÇAS (56-70)
    (56, "Quero criar uma poupança para comprar um carro de 8 milhões de Kz em dois anos. Quanto preciso de guardar por mês?"),
    (57, "Cria um plano para poupar 1 milhão de Kz em 12 meses."),
    (58, "Quanto já consegui poupar até agora?"),
    (59, "Qual das minhas metas de poupança está mais próxima de ser concluída?"),
    (60, "Estou atrasado em alguma das minhas metas?"),
    (61, "Quanto preciso de aumentar a minha poupança mensal para cumprir o meu objetivo?"),
    (62, "Se guardar 30.000 Kz todos os meses, quanto terei em dezembro de 2027?"),
    (63, "Quero poupar para uma viagem, mas não sei quanto devo guardar. Ajuda-me a planear."),
    (64, "Posso ter várias metas de poupança ao mesmo tempo?"),
    (65, "Qual é a percentagem de conclusão de cada uma das minhas metas?"),
    (66, "Quanto dinheiro falta para atingir a minha meta de poupança mais próxima?"),
    (67, "Se retirar 100.000 Kz da minha poupança, como isso afetará o meu objetivo?"),
    (68, "Compara as minhas metas de poupança com os meus rendimentos."),
    (69, "Cria um plano de poupança baseado nas minhas despesas atuais."),
    (70, "Qual seria uma meta de poupança realista para mim?"),
]

ERROR_PHRASES = [
    "não consegui processar",
    "não foi possível",
    "não consegui contactar",
    "não foi encontrado",
    "erro interno",
    "something went wrong",
]

print("=" * 70)
print("SMOKE TEST COMPLETO — 70 Perguntas BankAO Copilot Demo")
print("=" * 70)

passed = 0
failed = 0
failed_list = []

for qnum, question in ALL_QUESTIONS:
    try:
        result = CopilotOrchestrator.process_message(USER_ID, question)
        reply = result.get("reply", "") or ""
        tools = result.get("tools_used", [])

        is_error = any(ep in reply.lower() for ep in ERROR_PHRASES)
        is_pass = len(reply) > 50 and not is_error

        status = "✅" if is_pass else "❌"
        if is_pass:
            passed += 1
        else:
            failed += 1
            failed_list.append((qnum, question, reply[:300]))

        print(f"Q{qnum:02d}: {status} ({len(reply)}ch, tools={tools[:2]}) {reply[:80].strip()!r}")

    except Exception as e:
        failed += 1
        failed_list.append((qnum, question, str(e)))
        print(f"Q{qnum:02d}: 💥 EXCEPTION — {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 70)
print(f"RESULTADO FINAL: {passed}/{len(ALL_QUESTIONS)} PASS | {failed} FAIL")
print("=" * 70)

if failed_list:
    print("\nFALHAS:")
    for qnum, q, r in failed_list:
        print(f"\n  Q{qnum}: {q}")
        print(f"  Reply: {r[:400]}")
else:
    print("\n🎉 Todas as 70 perguntas passaram com sucesso!")


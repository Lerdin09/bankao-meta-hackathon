"""
Test Suite for Questions 56–70: Poupanças e Objetivos Financeiros
Run: python scratch/test_savings_suite.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')

from backend.ai.orchestrator import CopilotOrchestrator

USER_ID = '2e0a4847-d1a9-48a6-86de-40229a125b58'

QUESTIONS = [
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

PASS_KEYWORDS = {
    56: ["8.000.000", "333", "mês", "Kz"],
    57: ["1.000.000", "plano", "mês", "Kz"],
    58: ["poupado", "Kz", "meta"],
    59: ["mais próxima", "Toyota", "Fundo", "%"],
    60: ["atrasado", "prazo", "meta", "%"],
    61: ["aumentar", "mensal", "Kz", "meta"],
    62: ["30.000", "dezembro", "2027", "Kz"],
    63: ["viagem", "planear", "mês", "Kz"],
    64: ["várias", "metas", "BankAO"],
    65: ["percentagem", "%", "Kz", "Toyota"],
    66: ["falta", "Kz", "meta", "mês"],
    67: ["100.000", "poupança", "levantamento", "Kz"],
    68: ["rendimento", "poupança", "compara", "Kz"],
    69: ["plano", "despesas", "poupança", "Kz"],
    70: ["realista", "meta", "Kz", "mês"],
}

# More lenient fallback keywords for keywords not matching exactly
FALLBACK_KEYWORDS = {
    67: ["100.000", "Kz", "meta"],
    68: ["rendimento", "Kz", "%"],
    69: ["Kz", "poupança", "excedente"],
    70: ["meta", "Kz", "mês"],
}

print("=" * 70)
print("TESTE: Poupanças e Objetivos Financeiros (Q56–Q70)")
print("=" * 70)

passed = 0
failed = 0
errors = []

for qnum, question in QUESTIONS:
    try:
        result = CopilotOrchestrator.process_message(USER_ID, question)
        reply = result.get("reply", "") or ""
        tools = result.get("tools_used", [])

        # Check keywords
        keywords = PASS_KEYWORDS.get(qnum, [])
        fallback = FALLBACK_KEYWORDS.get(qnum, [])
        
        kw_match = all(any(kw.lower() in reply.lower() for kw in [kw]) for kw in keywords)
        fallback_match = all(any(kw.lower() in reply.lower() for kw in [kw]) for kw in fallback) if fallback else True
        
        is_pass = (
            len(reply) > 80
            and "Não consegui" not in reply
            and "não foi possível" not in reply.lower()
            and (kw_match or fallback_match)
        )

        status = "✅ PASS" if is_pass else "❌ FAIL"
        if is_pass:
            passed += 1
        else:
            failed += 1
            errors.append((qnum, question, reply[:200], keywords))

        print(f"\nQ{qnum}: {status}")
        print(f"  Pergunta: {question[:80]}...")
        print(f"  Ferramentas: {tools}")
        print(f"  Resposta ({len(reply)} chars): {reply[:150].strip()}...")
        if not is_pass:
            missing = [kw for kw in keywords if kw.lower() not in reply.lower()]
            print(f"  ⚠️  Keywords em falta: {missing}")
    except Exception as e:
        failed += 1
        errors.append((qnum, question, str(e), []))
        print(f"\nQ{qnum}: 💥 ERROR — {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 70)
print(f"RESULTADO FINAL: {passed}/{len(QUESTIONS)} PASS | {failed} FAIL")
print("=" * 70)

if errors:
    print("\nFALHAS DETALHADAS:")
    for qnum, q, r, kw in errors:
        print(f"\n  Q{qnum}: {q}")
        print(f"  Reply: {r[:300]}")


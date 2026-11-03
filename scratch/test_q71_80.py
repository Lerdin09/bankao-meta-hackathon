import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')

from backend.ai.orchestrator import CopilotOrchestrator

USER_ID = '2e0a4847-d1a9-48a6-86de-40229a125b58'

QUESTIONS = [
    (71, "Quero transferir 25.000 Kz para João Manuel, conta 004012345678."),
    (72, "Transfere 150.000 Kz para Maria Silva através do IBAN AO06004000001234567890123."),
    (73, "Quero enviar 50 mil para o meu irmão."),
    (74, "Faz uma transferência de 10.500 Kz para a conta que utilizei na última transferência."),
    (75, "Quero transferir 100 euros para Portugal."),
    (76, "Quanto vou pagar de comissão se transferir 200.000 Kz para outro banco?"),
    (77, "Quero transferir 15.000 Kz, mas ainda não sei o IBAN. Ajuda-me."),
    (78, "Prepara uma transferência de 75.000 Kz para Carlos, mas não quero confirmar ainda."),
    (79, "Quero alterar o valor da transferência que acabaste de preparar para 90.000 Kz."),
    (80, "Cancela a transferência que preparaste anteriormente."),
]

pending = None
for qnum, q in QUESTIONS:
    print(f"\n{'='*60}\nQ{qnum}: {q}\n{'='*60}")
    res = CopilotOrchestrator.process_message(USER_ID, q, pending=pending)
    print("REPLY:", res.get("reply"))
    print("ACTION:", res.get("action"))
    print("PENDING:", res.get("pending"))
    print("REQUIRES_CONFIRMATION:", res.get("requires_confirmation"))
    print("TOOLS_USED:", res.get("tools_used"))
    pending = res.get("pending")


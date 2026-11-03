import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')

from backend.ai.orchestrator import CopilotOrchestrator

USER_ID = '2e0a4847-d1a9-48a6-86de-40229a125b58'

q_sequence = [
    (78, "Prepara uma transferência de 75.000 Kz para Carlos, mas não quero confirmar ainda."),
    (79, "Quero alterar o valor da transferência que acabaste de preparar para 90.000 Kz."),
    (80, "Cancela a transferência que preparaste anteriormente."),
]

pending = None
for qnum, q in q_sequence:
    print(f"\n{'='*60}\nQ{qnum}: {q}\n{'='*60}", flush=True)
    res = CopilotOrchestrator.process_message(USER_ID, q, pending=pending)
    print("REPLY:", res.get("reply"), flush=True)
    print("ACTION:", res.get("action"), flush=True)
    print("PENDING:", res.get("pending"), flush=True)
    print("REQUIRES_CONFIRMATION:", res.get("requires_confirmation"), flush=True)
    print("TOOLS_USED:", res.get("tools_used"), flush=True)
    pending = res.get("pending")


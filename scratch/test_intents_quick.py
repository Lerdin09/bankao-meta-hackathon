import sys; sys.stdout.reconfigure(encoding='utf-8')
import datetime
from backend.ai.intents import analyze_message, normalize_spoken_text

today = datetime.date.today()

tests = [
    ('Qual a comissao para transferir 200 mil para outro banco?', None),
    ('Cancela a operacao', {'type': 'TRANSFER_INTERNAL', 'slots': {'amount': 50000, 'to_email': 'carlos@bankao.ao'}}),
    ('Entendido, fica sem efeito', {'type': 'TRANSFER_INTERNAL', 'slots': {'amount': 50000, 'to_email': 'carlos@bankao.ao'}}),
    ('Nao cancela', {'type': 'TRANSFER_INTERNAL', 'slots': {'amount': 50000, 'to_email': 'carlos@bankao.ao'}}),
    ('Prepara a transferencia', None),
]

print("=== INTENTS EDGE CASES ===\n")
for msg, pending in tests:
    r = analyze_message(msg, pending)
    reply = (r.get("reply") or "")[:100]
    action = r.get("action")
    print(f"MSG: {msg}")
    print(f"  reply : {reply}")
    print(f"  action: {action}")
    print()

print("\n=== EMAIL NORMALIZATION ===\n")
email_tests = [
    'Transfere 5000 para joao arroba bankao ponto ao',
    'envia para pedro arroba gmail ponto com',
    'manda 1000 para ana maria arroba bankao ao',
]
import re
EMAIL = re.compile(r'[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9-.]+')
for t in email_tests:
    n = normalize_spoken_text(t)
    m = EMAIL.search(n)
    print(f"IN : {t}")
    print(f"OUT: {n}")
    print(f"EMAIL: {m.group(0) if m else 'NOT_FOUND'}")
    print()

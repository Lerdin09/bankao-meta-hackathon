"""
Debug: ver o payload completo devolvido pelo /api/ai/chat-v2 para pedidos de transferência.
"""
import sys, json, requests
sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8000"
EMAIL    = "joao.makiesse@bankao.ao"
PASSWORD = "Demo1234!"

def get_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": EMAIL, "password": PASSWORD}, timeout=10)
    r.raise_for_status()
    data = r.json()
    return data.get("access_token") or data.get("token")

def chat(token, message, history=None, pending=None):
    payload = {"message": message}
    if history:  payload["history"] = history
    if pending:  payload["pending"] = pending
    r = requests.post(f"{BASE_URL}/api/ai/chat-v2",
                      json=payload,
                      headers={"Authorization": f"Bearer {token}"},
                      timeout=30)
    r.raise_for_status()
    return r.json()

token = get_token()
print("✓ Autenticado\n")

history = []

def send(msg, pending=None):
    resp = chat(token, msg, history=history, pending=pending)
    history.append({"role": "user", "content": msg})
    history.append({"role": "assistant", "content": resp.get("reply", "")})
    print(f">>> {msg}")
    print(f"REPLY: {resp.get('reply', '')[:300]}")
    print(f"ACTION: {json.dumps(resp.get('action'), ensure_ascii=False, indent=2)}")
    print(f"PENDING: {json.dumps(resp.get('pending'), ensure_ascii=False)}")
    print("-" * 60)
    return resp

# Sequência: pedido → dados → preparar → cancelar
r1 = send("Quero transferir 50.000 Kz para João")
r2 = send("A conta dele é 004099875411, banco BankAO")
r3 = send("Prepara a transferência")
r4 = send("Não, cancela")

print("\n=== ANÁLISE DOS CAMPOS DE CONFIRMAÇÃO ===")
for i, r in enumerate([r1, r2, r3, r4], 1):
    action = r.get("action") or {}
    print(f"Msg {i}: requires_confirmation={action.get('requires_confirmation')} | "
          f"executed={action.get('executed')} | "
          f"status={action.get('status')} | "
          f"type={action.get('type')}")


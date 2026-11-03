"""
Teste de Integração:
1. Resposta de Investimento abre painel (Action OPEN_INVESTMENTS)
2. Transferências são registradas nas Despesas (tabela expenses, category='Transferências')
3. Investimentos são registrados nas Despesas (tabela expenses, category='Investimentos')
"""
import sys
import uuid
import datetime
import requests

sys.stdout.reconfigure(encoding='utf-8')
BASE_URL = "http://localhost:8000"

def run_tests():
    print("=" * 65)
    print("TESTE: Painel de Investimentos e Auto-Registro nas Despesas")
    print("=" * 65)

    # 1. Login
    r_auth = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "joao.makiesse@bankao.ao",
        "password": "Demo1234!"
    })
    assert r_auth.status_code == 200, f"Login falhou: {r_auth.text}"
    token = r_auth.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✓ Autenticado com João Pedro Makiesse")

    # 2. Teste do Copilot abrindo o painel de investimentos
    print("\n--- 1. Copilot responde sobre investimentos e envia OPEN_INVESTMENTS ---")
    r_ai = requests.post(f"{BASE_URL}/api/ai/chat-v2", json={
        "message": "Recomenda-me um tipo de investimento"
    }, headers=headers)
    assert r_ai.status_code == 200, f"Erro AI: {r_ai.text}"
    ai_data = r_ai.json()
    action = ai_data.get("action")
    print("Action retornada:", action)
    assert action is not None, "Action não deve ser nula"
    assert action.get("type") == "OPEN_INVESTMENTS", f"Tipo esperado OPEN_INVESTMENTS, obtido {action.get('type')}"
    print(f"✓ Resposta contém action OPEN_INVESTMENTS: {action.get('title')}")

    # 3. Teste de Transferência Registrada nas Despesas
    print("\n--- 2. Transferência Bancária Registrada em Despesas ---")
    # Buscar contas de João
    r_accs = requests.get(f"{BASE_URL}/api/accounts", headers=headers)
    accs = r_accs.json()
    aoa_acc = next(a for a in accs if a["currency"] == "AOA")
    from_acc_id = aoa_acc["id"]

    # Fazer uma transferência interna de teste de 500 Kz para conta ou email existente
    idem = f"test_trans_{uuid.uuid4().hex[:10]}"
    t_payload = {
        "from_account_id": from_acc_id,
        "to_account_number": "004085549593",  # conta de Carlos Silva ou similar
        "amount": 500.0,
        "description": "Teste Auto-Despesa Transferência",
        "idempotency_key": idem
    }
    r_tx = requests.post(f"{BASE_URL}/api/transfers/internal", json=t_payload, headers=headers)
    if r_tx.status_code != 200:
        # Tentar com to_email
        t_payload.pop("to_account_number")
        t_payload["to_email"] = "ana.ferreira@bankao.ao"
        r_tx = requests.post(f"{BASE_URL}/api/transfers/internal", json=t_payload, headers=headers)

    print("Resultado da transferência:", r_tx.status_code)
    assert r_tx.status_code == 200, f"Falha ao transferir: {r_tx.text}"

    # Consultar Despesas do utilizador para verificar se a transferência foi registrada
    r_exp = requests.get(f"{BASE_URL}/api/expenses", headers=headers)
    assert r_exp.status_code == 200
    expenses = r_exp.json()
    transfer_exp = next((e for e in expenses if e.get("origin") == "transfer" and "Transferência" in e.get("name")), None)
    assert transfer_exp is not None, "Despesa com origin='transfer' não foi encontrada nas despesas!"
    print(f"✓ Transferência auto-registrada nas despesas: {transfer_exp['name']} | Categoria: {transfer_exp['category']} | Valor: {transfer_exp['amount']} Kz")

    # 4. Teste de Investimento Registrado nas Despesas
    print("\n--- 3. Aplicação de Investimento Registrada em Despesas ---")
    # Buscar catálogo
    r_cat = requests.get(f"{BASE_URL}/api/investments/catalog", headers=headers)
    assert r_cat.status_code == 200
    products = r_cat.json().get("products", [])
    # Produto AOA com menor mínimo
    aoa_prod = next(p for p in products if p["currency"] == "AOA")
    min_amt = aoa_prod["min_amount"]

    apply_payload = {
        "product_id": aoa_prod["id"],
        "account_id": from_acc_id,
        "amount": min_amt,
        "notes": "Teste Auto-Despesa Investimento"
    }
    r_app = requests.post(f"{BASE_URL}/api/investments/portfolio/apply", json=apply_payload, headers=headers)
    print("Resultado da subscrição de investimento:", r_app.status_code)
    assert r_app.status_code == 200, f"Falha na aplicação: {r_app.text}"

    # Verificar se o investimento foi registrado nas despesas
    r_exp2 = requests.get(f"{BASE_URL}/api/expenses", headers=headers)
    expenses2 = r_exp2.json()
    invest_exp = next((e for e in expenses2 if e.get("origin") == "investment" and "Investimento" in e.get("name")), None)
    assert invest_exp is not None, "Despesa com origin='investment' não foi encontrada nas despesas!"
    print(f"✓ Investimento auto-registrado nas despesas: {invest_exp['name']} | Categoria: {invest_exp['category']} | Valor: {invest_exp['amount']} Kz")

    print("\n" + "=" * 65)
    print("TODOS OS TESTES DE INTEGRAÇÃO PASSARAM COM 100% DE SUCESSO!")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()

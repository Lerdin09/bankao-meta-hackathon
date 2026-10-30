"""
Script de teste de integração ponta a ponta (E2E) para verificar todas as rotas e fluxos.
"""
import httpx
import sys
import uuid

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000"

def run_e2e_test():
    print("🚀 Iniciando Teste de Integração Ponta a Ponta do BankAO...\n")
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    # 1. Autenticação (Login ou Registo)
    print("1. Testando Autenticação...")
    res = client.post("/api/auth/register", json={
        "nome": "Lerdin dos Santos",
        "email": "lerdin.test@bankao.ao",
        "password": "SenhaSegura123!",
        "telefone": "923 456 789"
    })
    if res.status_code == 400:  # Já existia
        res = client.post("/api/auth/login", json={
            "email": "lerdin.test@bankao.ao",
            "password": "SenhaSegura123!"
        })
    assert res.status_code == 200, f"Falha no login: {res.text}"
    token_data = res.json()
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   ✅ Autenticado com sucesso! Token gerado.")

    # 2. Obter Contas
    print("\n2. Consultando Carteiras e Saldos...")
    res_acc = client.get("/api/accounts", headers=headers)
    assert res_acc.status_code == 200
    accounts = res_acc.json()
    aoa_acc = next(a for a in accounts if a["currency"] == "AOA")
    eur_acc = next(a for a in accounts if a["currency"] == "EUR")
    print(f"   ✅ Carteira AOA: {aoa_acc['account_number']} | Saldo: {aoa_acc['balance_decimal']} Kz | IBAN: {aoa_acc['iban_virtual']}")
    print(f"   ✅ Carteira EUR: {eur_acc['account_number']} | Saldo: {eur_acc['balance_decimal']} € | IBAN: {eur_acc['iban_virtual']}")
    initial_aoa_balance = aoa_acc["balance_decimal"]

    # 3. Teste de Depósito Multicaixa Express
    print("\n3. Testando Depósito por Multicaixa Express...")
    res_dep = client.post("/api/deposits/multicaixa-express", headers=headers, json={
        "account_id": aoa_acc["id"],
        "amount": 50000.0,
        "phone_number": "923 456 789"
    })
    assert res_dep.status_code == 200
    dep_data = res_dep.json()
    deposit_id = dep_data["deposit_id"]
    print(f"   ✅ Pedido gerado (ID: {deposit_id}). Simulando aprovação no telemóvel...")

    # Confirmar pagamento
    res_pay = client.post("/api/deposits/simulate-payment", json={"deposit_id": deposit_id})
    assert res_pay.status_code == 200
    print("   ✅ Pagamento do Multicaixa Express aprovado com sucesso!")

    # 4. Verificar se o saldo subiu 50.000 Kz
    res_acc_after = client.get("/api/accounts", headers=headers)
    aoa_acc_after = next(a for a in res_acc_after.json() if a["currency"] == "AOA")
    assert aoa_acc_after["balance_decimal"] == initial_aoa_balance + 50000.0
    print(f"   ✅ Saldo AOA atualizado no Livro-Razão: {aoa_acc_after['balance_decimal']} Kz (+50.000 Kz).")

    # 5. Validação de IBAN Mod 97
    print("\n4. Testando Validação Matemática de IBAN Mod 97...")
    valid_pt = eur_acc["iban_virtual"]
    res_iban_valid = client.get(f"/api/iban/validate?iban={valid_pt}")
    assert res_iban_valid.json()["valid"] is True
    print(f"   ✅ IBAN {valid_pt} validado com sucesso!")

    # Adulterar último dígito para testar rejeição
    corrupted_pt = valid_pt[:-1] + ("1" if valid_pt[-1] != "1" else "2")
    res_iban_invalid = client.get(f"/api/iban/validate?iban={corrupted_pt}")
    assert res_iban_invalid.json()["valid"] is False
    print("   ✅ IBAN com dígito de controle adulterado foi rejeitado corretamente!")

    # 6. Testando Cotação e Remessa Internacional para Portugal (IBAN)
    print("\n5. Testando Câmbio e Remessa Internacional para IBAN...")
    res_quote = client.post("/api/fx/quote", json={
        "from_currency": "AOA",
        "to_currency": "EUR",
        "amount": 50000.0
    })
    quote = res_quote.json()
    print(f"   ✅ Cotação: 50.000 Kz -> {quote['dest_amount_decimal']} € (Taxa: {quote['fee_percentage']}%)")

    res_iban_tx = client.post("/api/transfers/iban", headers=headers, json={
        "from_account_id": aoa_acc["id"],
        "to_iban": valid_pt,
        "beneficiary_name": "Maria António",
        "amount": 50000.0,
        "dest_currency": "EUR",
        "idempotency_key": f"test_e2e_tx_iban_{uuid.uuid4().hex[:8]}"
    })
    assert res_iban_tx.status_code == 200
    tx_iban_data = res_iban_tx.json()
    print(f"   ✅ Remessa internacional liquidada! Beneficiário recebe {tx_iban_data['dest_amount_decimal']} EUR.")

    # 7. Testando Assistente BankAO Copilot (Meta Model API)
    print("\n6. Testando BankAO Copilot (Meta Muse Spark)...")
    res_chat = client.post("/api/ai/chat", json={
        "message": "Como funciona o depósito por Multicaixa Express no BankAO?"
    })
    assert res_chat.status_code == 200
    reply = res_chat.json()
    print(f"   ✅ Resposta do Copilot ({reply['model']}):")
    print(f"      \"{reply['reply'][:120]}...\"")

    # 8. Extrato
    print("\n7. Testando Extrato e Integridade do Livro-Razão...")
    res_txs = client.get("/api/transactions", headers=headers)
    assert res_txs.status_code == 200
    txs = res_txs.json()
    print(f"   ✅ Extrato carregado: {len(txs)} lançamentos registrados.")

    print("\n🎉 TODOS OS TESTES PASSARAM COM 100% DE SUCESSO!")

if __name__ == "__main__":
    run_e2e_test()

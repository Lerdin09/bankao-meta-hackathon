import requests

BASE = "http://127.0.0.1:8000"

def test():
    # 1. Registo de utilizador
    email = "sender_currency_test@bankao.ao"
    reg = requests.post(f"{BASE}/api/auth/register", json={
        "email": email,
        "telefone": "923111222",
        "password": "SenhaSegura123!",
        "confirm_password": "SenhaSegura123!",
        "terms_accepted": True
    })
    print("Register status:", reg.status_code)
    token = reg.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Confirmação de KYC (recebe saldo nas contas)
    kyc = requests.post(f"{BASE}/api/kyc/confirm", headers=headers, json={
        "nome_completo": "Testador Multimoeda",
        "primeiro_nome": "Testador",
        "ultimo_nome": "Multimoeda",
        "doc_tipo": "bi",
        "doc_numero": "000123456LA042"
    })
    print("KYC confirm status:", kyc.status_code)

    # 3. Listar contas
    accs = requests.get(f"{BASE}/api/accounts", headers=headers).json()
    print("Contas:", [(a["currency"], a["balance_decimal"]) for a in accs])

    usd_acc = next(a for a in accs if a["currency"] == "USD")
    aoa_acc = next(a for a in accs if a["currency"] == "AOA")

    # 4. Criar destinatário para transferência interna
    recip_email = "receiver_currency_test@bankao.ao"
    reg_recip = requests.post(f"{BASE}/api/auth/register", json={
        "email": recip_email,
        "telefone": "923999888",
        "password": "SenhaSegura123!",
        "confirm_password": "SenhaSegura123!",
        "terms_accepted": True
    })
    print("Receiver register:", reg_recip.status_code)

    # Lookup destinatário
    lookup = requests.get(f"{BASE}/api/users/lookup?email={recip_email}", headers=headers).json()
    print("Lookup:", lookup)

    # 5. Transferência de conta (USD, 100$, 1% taxa)
    tx_int = requests.post(f"{BASE}/api/transfers/internal", headers=headers, json={
        "from_account_id": usd_acc["id"],
        "to_email": recip_email,
        "amount": 100.0,
        "description": "Envio $100 teste multimoeda",
        "idempotency_key": "test_curr_int_1"
    })
    print("Transfer internal USD:", tx_int.status_code, tx_int.json())

    # 6. Transferência IBAN (USD para IBAN Angola, taxa 2.5%)
    tx_iban = requests.post(f"{BASE}/api/transfers/iban", headers=headers, json={
        "from_account_id": usd_acc["id"],
        "to_iban": "AO06 0040 0000 0000 0000 0000 0",
        "beneficiary_name": "Adul Popo Angol",
        "amount": 100.0,
        "dest_currency": "AOA",
        "idempotency_key": "test_curr_iban_1"
    })
    print("Transfer IBAN USD -> AO KZ:", tx_iban.status_code, tx_iban.json())

    # Saldo final
    accs_after = requests.get(f"{BASE}/api/accounts", headers=headers).json()
    print("Contas após transferências:", [(a["currency"], a["balance_decimal"]) for a in accs_after])

if __name__ == "__main__":
    test()

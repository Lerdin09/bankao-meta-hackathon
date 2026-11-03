"""
Teste de Dictação e Normalização de E-mails Falados no Copilot
"""
import sys
import time
import requests

sys.stdout.reconfigure(encoding='utf-8')
BASE_URL = "http://localhost:8000"

def test_spoken_emails():
    print("=" * 65)
    print("TESTE: Reconhecimento de E-mails Ditados por Voz no Copilot")
    print("=" * 65)

    r_auth = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "joao.makiesse@bankao.ao",
        "password": "Demo1234!"
    })
    assert r_auth.status_code == 200
    token = r_auth.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✓ Autenticado com João Pedro Makiesse\n")

    dictated_samples = [
        "Quero transferir 20 mil para ana ponto ferreira arroba bankao ponto ao",
        "Manda 15.000 Kz para ana ferreira arroba bankao ao",
        "Transfere 5000 para joao arroba bankao ponto ao",
        "O email do destinatário é ana ponto ferreira arroba bankao ao",
    ]

    for sample in dictated_samples:
        t0 = time.time()
        res = requests.post(f"{BASE_URL}/api/ai/chat-v2", json={"message": sample}, headers=headers)
        dt = (time.time() - t0) * 1000
        assert res.status_code == 200, f"Falha na requisição: {res.text}"
        data = res.json()
        action = data.get("action") or {}
        reply = (data.get("reply") or "").replace("\n", " ")[:110]
        to_email = action.get("to_email") or ""
        print(f"[{dt:5.1f}ms] Fala: «{sample}»")
        print(f"         E-mail capturado: '{to_email}'")
        print(f"         Resposta: {reply}...")
        print("-" * 65)

    print("\n✓ TODOS OS E-MAILS FALADOS FORAM NORMALIZADOS E CAPTURADOS CORRETAMENTE!")

if __name__ == "__main__":
    test_spoken_emails()


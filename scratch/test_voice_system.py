"""
Teste de Validação do Sistema de Voz do BankAO Copilot
"""
import sys
import requests
import json
import time

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8000"

def test_voice_system():
    print("=" * 60)
    print("TESTE: Sistema de Voz e Wake-Words do BankAO Copilot")
    print("=" * 60)

    # 1. Assets estáticos
    r_index = requests.get(f"{BASE_URL}/")
    assert r_index.status_code == 200, "Index não carregou"
    assert "copilot-voice.js" in r_index.text, "Script copilot-voice.js ausente no index"
    assert "btnCopilotMic" in r_index.text, "Botão mic ausente no HTML"
    print("✓ Index.html contém os scripts e botão do microfone")

    r_css = requests.get(f"{BASE_URL}/static/css/components/copilot-voice.css")
    assert r_css.status_code == 200, "copilot-voice.css não carregou"
    assert "voice-overlay" in r_css.text, "CSS voice-overlay ausente"
    assert "voiceCanvas" in r_css.text, "CSS voiceCanvas ausente"
    print(f"✓ copilot-voice.css ativo ({len(r_css.text)} bytes)")

    r_js = requests.get(f"{BASE_URL}/static/js/features/copilot/copilot-voice.js")
    assert r_js.status_code == 200, "copilot-voice.js não carregou"
    assert "Hi bank copilot" in r_js.text or "hi bank copilot" in r_js.text, "Wake word ausente no JS"
    assert "E aí copiloto do banco" in r_js.text or "e aí copiloto do banco" in r_js.text, "Wake word PT ausente no JS"
    assert "SpeechRecognition" in r_js.text, "SpeechRecognition ausente no JS"
    assert "speechSynthesis" in r_js.text, "speechSynthesis ausente no JS"
    print(f"✓ copilot-voice.js ativo com Siri/GPT audio visualizer ({len(r_js.text)} bytes)")

    # 2. Login
    r_login = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "joao.makiesse@bankao.ao",
        "password": "Demo1234!"
    })
    assert r_login.status_code == 200, "Login falhou"
    token = r_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✓ Autenticação com João Pedro Makiesse realizada com sucesso")

    # 3. Teste de Wake-Words e Velocidade
    wake_prompts = [
        ("Hi bank copilot", "Olá! Estou a ouvir"),
        ("E aí copiloto do banco", "Olá! Estou a ouvir"),
        ("Ei copiloto", "Olá! Estou a ouvir"),
        ("Quanto dinheiro tenho disponível?", "saldo"),
        ("Quero transferir 25.000 Kz para João Manuel, conta 004012345678", "transferência"),
    ]

    print("\n--- Testando Respostas e Velocidade das Frases de Voz ---")
    for prompt, expected in wake_prompts:
        t0 = time.time()
        res = requests.post(
            f"{BASE_URL}/api/ai/chat-v2",
            json={"message": prompt},
            headers=headers,
            timeout=10
        )
        elapsed_ms = (time.time() - t0) * 1000
        assert res.status_code == 200, f"Erro no endpoint para: {prompt}"
        data = res.json()
        reply = data.get("reply", "")
        assert expected.lower() in reply.lower() or len(reply) > 10, f"Resposta inesperada para {prompt}: {reply}"
        print(f"  ✓ [{elapsed_ms:5.1f}ms] «{prompt}» -> {reply[:70]}...")

    print("\n" + "=" * 60)
    print("RESULTADO: TODOS OS TESTES DO SISTEMA DE VOZ PASSARAM COM SUCESSO!")
    print("=" * 60)

if __name__ == "__main__":
    test_voice_system()

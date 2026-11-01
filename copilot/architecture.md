# 🏗️ Arquitetura do BankAO Copilot

Este documento descreve o fluxo de dados, contratos de API e a integração de ponta a ponta do assistente entre o navegador do usuário, a API FastAPI do BankAO e os modelos de IA da Meta.

---

## 1. Diagrama de Fluxo de Conversação

```
[Utilizador]
    │
    ▼ (digita mensagem ou clica em chip de prompt)
[Frontend — copilot.js]
    │
    ▼ POST /api/ai/chat  { message, history }
[FastAPI — backend/api/routes/ai.py]
    │
    ▼ BankaoAssistant.chat_with_action(...)
[Backend AI Core — backend/ai/assistant.py]
    ├───▶ Meta Model API (Llama 3 / Muse Spark)
    │         └── Retorna texto natural com bloco ```json:action (se aplicável)
    └───▶ Intent Parser (backend/ai/intents.py)
              └── Extrai ou complementa os dados estruturados da ação
    │
    ▼ Resposta JSON { reply, action, model, provider }
[Frontend — copilot-chat-ui.js]
    ├── Renderiza a bolha da resposta da IA
    └── Se action != null:
            ├── Renderiza Action Card interativo na bolha
            └── Chama applyCopilotAction(action, prefillOnly=true)
    │
    ▼
[Painel da Operação / Modal do BankAO]
    └── Formulário preenchido automaticamente com dados validados
        e aguardando clique de confirmação do utilizador.
```

---

## 2. Contratos da API

### `POST /api/ai/chat`
Envia uma mensagem de conversa com o histórico acumulado da sessão.

* **Payload de Entrada**:
```json
{
  "message": "Quero enviar 25.000 Kz para o meu primo em Lisboa no IBAN PT50003506410001234567890",
  "history": [
    { "role": "user", "content": "Olá!" },
    { "role": "assistant", "content": "Olá! Como posso ajudar hoje?" }
  ]
}
```

* **Resposta de Sucesso (200 OK)**:
```json
{
  "reply": "Preparei a sua transferência para Portugal. Por favor, reveja os valores antes de confirmar.",
  "action": {
    "type": "TRANSFER_IBAN",
    "beneficiary_name": "Primo",
    "to_iban": "PT50003506410001234567890",
    "amount": 25000.0,
    "currency": "AOA",
    "country_code": "PT",
    "country_name": "Portugal 🇵🇹",
    "fee_percent": 2.5,
    "fee_amount": 625.0,
    "net_amount": 24375.0
  },
  "model": "meta-llama/Llama-3-70b-instruct",
  "provider": "Meta Model API / Muse Spark"
}
```

---

### `POST /api/ai/explain-transfer`
Gera uma explicação em linguagem natural e transparente sobre os custos e conversão de uma transferência internacional.

* **Payload de Entrada**:
```json
{
  "source_amount": 100000.0,
  "source_currency": "AOA",
  "dest_amount": 95.24,
  "dest_currency": "EUR",
  "fx_rate": 1050.0,
  "fee": 2000.0,
  "dest_iban": "PT50003500000000000000000",
  "beneficiary_name": "Universidade de Lisboa"
}
```

---

### `GET /api/ai/analyze-risk`
Calcula o índice de conformidade e risco da transação antes de ser enviada ao livro-razão (ledger).

* **Parâmetros**: `amount`, `currency`, `tx_type`
* **Retorno**: Avaliação de risco (`baixo`, `médio`, `elevado`) com alertas de conformidade com o Banco Nacional de Angola (BNA).

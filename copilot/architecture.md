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


---

## 3. Agente (v3) — modelo primeiro

`POST /api/ai/chat-v2` → `CopilotOrchestrator.process_message`:

1. Com chave de modelo configurada, corre `backend/ai/agent.py::run_agent`: o modelo lê o pedido + histórico + contexto
   (data de hoje, ecrã aberto, última ação preparada), chama ferramentas em várias voltas (até 6) e responde.
   Se falhar, repete uma vez; depois usa o plano B local.
2. Ferramentas de **ação** (`backend/ai/tools/actions.py`): `prepare_savings_goal`, `prepare_expense`,
   `prepare_transfer` (`method=account|iban`, nunca misturados), `prepare_deposit`. Só PREPARAM — devolvem `action`
   para pré-preencher o formulário; o utilizador conclui sempre.
3. Ferramentas de leitura: contas, extrato, despesas, comparação, cartões, investimentos, contactos, metas,
   foto financeira, compras por registar (só a pedido) e `show_chart` (gráficos inline).
4. Sem chave (ou modelo em baixo): regras locais em `orchestrator._offline_chain`. Nunca responde com saudação/apresentação
   automática nem com lembretes não pedidos; se não percebeu, diz-o numa frase.
5. Rede de segurança: se o modelo afirmar que concluiu algo, a resposta recebe a correção «ainda não foi concluído».

Testes: `tests/test_copilot_agent.py` (modelo simulado, sem rede).

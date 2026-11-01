# 🤖 BankAO Copilot — Módulo Central do Assistente IA

Bem-vindo à pasta dedicada do **BankAO Copilot**, o assistente financeiro inteligente e multimoeda desenvolvido para o **BankAO** no âmbito do **Meta Global AI Developer Hackathon**.

Esta pasta centraliza **todos os conteúdos, especificações, prompts, intenções, templates e ferramentas de teste** do assistente para facilitar futuras manutenções, testes de qualidade e novas funcionalidades.

---

## 📂 Estrutura da Pasta

```
copilot/
├── README.md                  # Este documento: visão geral e guia de uso
├── architecture.md            # Arquitetura ponta a ponta (Frontend, Backend, Meta Model API)
├── prompts/
│   ├── system_prompt.md       # Persona oficial e instruções base do assistente
│   ├── kyc_assistant_prompt.md# Prompt para auxílio de KYC e verificação documental
│   └── expense_categorizer.md # Prompt e regras de extração de despesas
├── intents/
│   ├── catalog.json           # Catálogo estruturado de todas as intenções e ações
│   └── actions_spec.md        # Especificação dos payloads JSON de ações executáveis
├── templates/
│   ├── welcome_bubble.html    # Template de apresentação e tags de capacidade
│   └── action_cards.html      # Templates dos Action Cards (Transferências, Despesas)
├── evaluation/
│   └── test_prompts.json      # Bateria de prompts para testes de conversação e edge cases
└── roadmap.md                 # Roadmap de melhorias futuras do assistente
```

---

## 🎯 Missão e Persona do Copilot

O **BankAO Copilot** atua como um assistente bancário privado acessível a qualquer cidadão em Angola e na diáspora. Ele combina conhecimento profundo do sistema financeiro angolano (**Multicaixa Express**, **referências de pagamento**, **BNA**) com regras internacionais de transferências (**SEPA**, **IBAN internacional**, **câmbio EUR/USD/AOA**).

### Princípios Invioláveis de Segurança:
1. **Nenhuma movimentação arbitrária**: O assistente nunca debita contas sem a confirmação explícita do usuário em tela através do fluxo bancário seguro.
2. **Action Cards estruturados**: Quando o usuário pede uma operação, a IA prepara um resumo estruturado e pré-preenche o formulário correto no painel para validação final.
3. **Privacidade e conformidade**: Senhas, PINs do Multicaixa ou dados confidenciais nunca são solicitados.

---

## 🔗 Ligações no Código do Projeto

| Componente | Localização no Código | Descrição |
| :--- | :--- | :--- |
| **Backend — Rotas** | [`backend/api/routes/ai.py`](../backend/api/routes/ai.py) | Endpoints `/api/ai/chat`, `/api/ai/explain-transfer`, `/api/ai/analyze-risk` |
| **Backend — IA Core** | [`backend/ai/assistant.py`](../backend/ai/assistant.py) | Lógica de chamada ao Meta Model API e orquestração |
| **Backend — Intents** | [`backend/ai/intents.py`](../backend/ai/intents.py) | Parser determinístico e extração de ações JSON |
| **Backend — Prompts** | [`backend/ai/prompts.py`](../backend/ai/prompts.py) | System Prompt em Python e mapeamento de países |
| **Frontend — Markup** | [`frontend/partials/pages/copilot.html`](../frontend/partials/pages/copilot.html) | Estrutura HTML do painel do Copilot |
| **Frontend — Estilos** | [`frontend/css/components/copilot.css`](../frontend/css/components/copilot.css) | Estilo visual moderno, glassmorphism e tema escuro |
| **Frontend — Lógica** | [`frontend/js/features/copilot/`](../frontend/js/features/copilot/) | Handlers de chat, UI de mensagens e aplicação de ações |

---

## 🚀 Como Adicionar uma Nova Ação ao Assistente

1. **Definir no Catálogo**: Registre a nova ação em [`copilot/intents/catalog.json`](intents/catalog.json).
2. **Atualizar o Prompt**: Adicione a instrução no [`copilot/prompts/system_prompt.md`](prompts/system_prompt.md) e replique em [`backend/ai/prompts.py`](../backend/ai/prompts.py).
3. **Parser no Backend**: Adicione a regex de captura em [`backend/ai/intents.py`](../backend/ai/intents.py).
4. **Action Card no Frontend**: Adicione a renderização visual em [`frontend/js/features/copilot/copilot-chat-ui.js`](../frontend/js/features/copilot/copilot-chat-ui.js) e o handler em [`frontend/js/features/copilot/copilot-actions.js`](../frontend/js/features/copilot/copilot-actions.js).
5. **Validar com Testes**: Rode os prompts de teste de [`copilot/evaluation/test_prompts.json`](evaluation/test_prompts.json) com `pytest tests/test_expenses_ai.py`.

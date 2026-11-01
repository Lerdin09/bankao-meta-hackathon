# 🗺️ Roadmap de Evolução do BankAO Copilot

Este documento consolida as próximas melhorias funcionais, técnicas e de experiência de usuário planejadas para o assistente.

---

## 🎯 Fase 1: Qualidade de Interação e Compreensão (Atual)
- [x] Interface desktop como "parede direita fixa" sem colisões com scroll central.
- [x] Bolhas com glassmorphism de alta fidelidade e Action Cards sem emojis.
- [x] Botão de reinício rápido da conversa com reset de contexto.
- [x] Centralização de prompts, intents e especificações na pasta raiz `copilot/`.

---

## 🚀 Fase 2: Entrada Multimodal e Visão Computacional
- [ ] **Leitura de Comprovativos por Imagem (OCR + LLaMA Vision)**:
  - Permitir arrastar a imagem ou PDF de um comprovativo Multicaixa para a janela do Copilot.
  - A IA extrai o código de transação, data, valor e número de referência automaticamente para reconciliação no ledger.
- [ ] **Mensagens de Voz (Speech-to-Text)**:
  - Adicionar botão de gravação de áudio no input do chat.
  - Transcrição adaptada com vocabulário de termos bancários e gírias locais angolanas.

---

## 💡 Fase 3: Proatividade e Automação
- [ ] **Alertas Proativos de Câmbio**:
  - *"O Euro atingiu a taxa que você aguardava (1.040 Kz). Deseja transferir agora para a sua conta em Portugal?"*
- [ ] **Previsão de Gastos de Fim de Mês**:
  - Notificação inteligente alertando que o ritmo de gastos em *Transporte* ou *Alimentação* ultrapassará o orçamento planejado.
- [ ] **Integração WhatsApp Business / Meta Messenger**:
  - Permitir consultar saldo e autorizar pagamentos via bot oficial do BankAO no WhatsApp.

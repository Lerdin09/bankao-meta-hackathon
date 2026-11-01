# 📦 Especificação Técnica de Ações Executáveis (Action Cards)

Quando o Copilot identifica que a solicitação do usuário exige uma ação no sistema bancário, ele emite um bloco de ação estruturado ```` ```json:action ```` que o frontend intercepta e converte em interface interativa.

---

## 1. Ação: `TRANSFER_IBAN`

### Payload JSON:
```json
{
  "type": "TRANSFER_IBAN",
  "beneficiary_name": "Maria Silva",
  "to_iban": "PT50003500000000000000000",
  "amount": 50000.0,
  "currency": "AOA",
  "country_code": "PT",
  "country_name": "Portugal 🇵🇹",
  "fee_percent": 2.5,
  "fee_amount": 1250.0,
  "net_amount": 48750.0
}
```

### Comportamento no Frontend:
1. Renderiza o card dentro da bolha da IA com cabeçalho, país de destino, valores formatados e aviso de taxa.
2. Adiciona o botão *"Revisar no Painel & Confirmar"*.
3. Pré-preenche os inputs do formulário de transferências em `view-payments`:
   - `input#txBeneficiaryName` -> `beneficiary_name`
   - `input#txDestIban` -> `to_iban`
   - `input#txAmount` -> `amount`
4. Se o usuário confirmar, abre o modal de validação biométrica/PIN para submissão final ao ledger.

---

## 2. Ação: `REGISTER_EXPENSE`

### Payload JSON:
```json
{
  "type": "REGISTER_EXPENSE",
  "name": "Supermercado Kero",
  "category": "Alimentação",
  "amount": 28400.0,
  "currency": "AOA",
  "notes": "Compras semanais registradas via Copilot"
}
```

### Comportamento no Frontend:
1. Renderiza o card de despesa na bolha com badge de categoria.
2. Registra o objeto no array de despesas ativas do usuário no cliente (`state.expenses`).
3. Dispara a atualização do gráfico donut e das barras de orçamento por categoria.
4. Exibe notificação toast de confirmação.

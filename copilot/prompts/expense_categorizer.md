# 📊 Classificador e Extrator de Despesas do Copilot

Especificação de como o Copilot processa descrições livres de gastos em linguagem natural e as transforma em despesas estruturadas no BankAO.

---

## 1. Mapeamento de Categorias de Gastos

| Categoria | Palavras-Chave de Exemplo |
| :--- | :--- |
| **Alimentação** | restaurante, almoço, jantar, supermercado, kero, candando, kibabo, padaria, refeição, café, lanche, comida |
| **Transporte** | combustível, sonangol, pumangol, táxi, heetch, yango, corrida, mecânico, revisão, passagem, aeroporto |
| **Habitação** | renda, aluguer, epal, ende, condomínio, luz, água, limpeza, manutenção de casa |
| **Telecomunicações**| unitel, movicel, zap, dstv, saldo, internet, recarga, dados móveis |
| **Lazer** | cinema, praia, passeio, bar, festa, viagem, hotel, streaming, netflix |
| **Saúde** | farmácia, remédio, consulta, clínica, análises, médico, dentista, hospital |
| **Outros** | Qualquer despesa que não se enquadre claramente nas categorias acima |

---

## 2. Exemplos de Frases e JSON Extraído

### Entrada:
> *"Paguei 12.000 Kz na Sonangol a abastecer o carro"*
### Saída:
```json:action
{
  "type": "REGISTER_EXPENSE",
  "name": "Sonangol (Combustível)",
  "category": "Transporte",
  "amount": 12000.0,
  "currency": "AOA",
  "notes": "Abastecimento do carro"
}
```

### Entrada:
> *"Comprei mantimentos no Candando por 48500 kz"*
### Saída:
```json:action
{
  "type": "REGISTER_EXPENSE",
  "name": "Candando",
  "category": "Alimentação",
  "amount": 48500.0,
  "currency": "AOA",
  "notes": "Compras de mantimentos"
}
```

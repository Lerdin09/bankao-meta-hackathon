# Banco Digital — Documentação e Guia do Projeto

*Versão 0.1 · 27 de outubro de 2026 · Projeto para o Meta Global AI Developer Hackathon*

## 1. Resumo

Um banco digital (carteira) semelhante ao PayPal, pensado para quem está em Angola e precisa de enviar e receber dinheiro de e para qualquer país. A pessoa deposita na sua conta com **Multicaixa Express** ou **referência de pagamento** e envia dinheiro por **número de conta interno** ou por **IBAN** (por exemplo, para um amigo em Portugal). Quem está no estrangeiro também pode enviar dinheiro para a conta usando o IBAN dela.

A parte de inteligência artificial usa a **Meta Model API** (modelo `muse-spark-1.3`): um assistente que explica transferências, taxas e câmbio em português e ajuda a assinalar operações suspeitas.

## 2. Aviso importante: protótipo, não banco real

- No hackathon, o projeto é uma **demonstração com dinheiro simulado**. Nenhum dinheiro real circula e todas as ligações a Multicaixa, bancos e pagamentos internacionais são **simuladas**.
- Operar uma carteira ou transferir dinheiro a sério exige licença. O BNA já avisou que as carteiras de moeda eletrónica são uma atividade reservada a sociedades prestadoras de serviços de pagamento habilitadas pelo regulador. Existem ainda regras cambiais e de prevenção de branqueamento de capitais.
- Para um produto real, o caminho normal é uma licença própria ou uma parceria com um banco ou instituição de pagamento licenciada, um acordo para aceder à rede Multicaixa e um parceiro para pagamentos internacionais.
- Este documento não é aconselhamento jurídico nem financeiro. Antes de qualquer uso real, consulta um advogado e o BNA.
- Nunca uses dados reais de clientes, cartões ou contas, e nunca os envies a nenhuma API de IA.

## 3. Âmbito do MVP (9 dias)

**Entra no MVP**

1. Registo e login, com verificação de identidade (KYC) simulada
2. Carteiras em AOA e EUR (USD opcional)
3. Depósito simulado por Multicaixa Express e por referência
4. Envio entre contas internas por número de conta
5. Envio para IBAN externo (simulado), com validação do IBAN
6. Receção de fundos por IBAN virtual de demonstração
7. Câmbio simulado com taxas configuráveis
8. Histórico e extrato
9. Assistente de IA com a Meta Model API

**Fica de fora**

- Ligações reais à EMIS, a bancos ou à rede SEPA
- Aplicação móvel nativa, cartões, empréstimos
- KYC real com documentos e biometria

## 4. Fluxos principais

### 4.1 Registo e conta

1. A pessoa cria conta com nome, email e palavra-passe.
2. O KYC é simulado (campo de estado: pendente, verificado).
3. O sistema cria as carteiras (AOA, EUR), cada uma com **número de conta interno** e **IBAN virtual de demonstração**.

### 4.2 Depósito por referência

1. A pessoa escolhe Depositar → Referência e indica o valor em AOA.
2. O sistema cria um depósito `pendente`, gera uma referência (código numérico) e uma data limite.
3. A pessoa paga a referência. Na vida real, paga num ATM ou na internet banking; na demo, usa o botão «Simular pagamento».
4. Um webhook simulado confirma o pagamento. O sistema regista o crédito no livro-razão e marca o depósito como `concluído`.

### 4.3 Depósito por Multicaixa Express

1. A pessoa escolhe Depositar → Multicaixa Express e indica o valor.
2. O sistema cria um pedido de pagamento `pendente`.
3. Na demo, um ecrã simula a aprovação no Multicaixa Express (confirmar ou recusar).
4. O resultado chega por webhook simulado e o crédito é feito da mesma forma que no depósito por referência.

### 4.4 Envio por número de conta interna

Transferência instantânea entre dois utilizadores da plataforma, numa única transação atómica (débito e crédito em simultâneo ou nenhum dos dois).

### 4.5 Envio para IBAN

1. A pessoa indica IBAN, nome do beneficiário, valor e moeda.
2. O sistema valida o IBAN (secção 7).
3. Mostra a cotação, a taxa de serviço e o valor final que o beneficiário recebe.
4. A pessoa confirma com um segundo fator (simulado).
5. Estados: `criado` → `em processamento` → `enviado` → `concluído` ou `falhado`.
6. Na demo, um `PayoutProvider` simulado devolve sucesso ou falha após um atraso. Num produto real, um envio em EUR para Portugal seria feito pela rede SEPA através de um parceiro autorizado.

### 4.6 Receber por IBAN

Cada conta tem um IBAN virtual de demonstração (formato válido, claramente marcado como fictício na interface). Um webhook simulado de «entrada de fundos» identifica a conta pelo IBAN e credita o valor.

## 5. Arquitetura

```
[Frontend] → [API FastAPI] → [Serviço de livro-razão] → [Base de dados]
                 ├→ [Adaptador de depósitos: Multicaixa / Referência (simulado)]
                 ├→ [Adaptador de envio internacional / SEPA (simulado)]
                 ├→ [Serviço de câmbio (taxas configuráveis)]
                 └→ [Assistente de IA: Meta Model API]
```

| Componente | Sugestão | Nota |
| --- | --- | --- |
| Backend | Python + FastAPI | Rápido de montar, boa documentação automática |
| Base de dados | SQLite no MVP, PostgreSQL depois | Mesmo esquema nos dois |
| Frontend | HTML + JavaScript simples, ou React | O que dominares melhor |
| Adaptadores | Classes com a mesma interface do serviço real | Trocar o simulado pelo real sem reescrever |
| IA | Meta Model API via SDK compatível com OpenAI | Chave em variável de ambiente |

## 6. Modelo de dados

Princípios: valores **inteiros em unidades mínimas** (cêntimos), nunca decimais flutuantes; **livro-razão de dupla entrada**; **chave de idempotência** em cada operação para que um pedido repetido não duplique dinheiro; estados explícitos.

| Tabela | Campos principais |
| --- | --- |
| `users` | id, nome, email, password\_hash, kyc\_status, created\_at |
| `accounts` | id, user\_id, account\_number, iban\_virtual, currency, status |
| `transactions` | id, type, status, idempotency\_key, created\_at |
| `ledger_entries` | id, transaction\_id, account\_id, amount\_minor (+/−), currency, created\_at |
| `deposits` | id, transaction\_id, method, reference\_code, expires\_at, status |
| `transfers` | id, transaction\_id, from\_account\_id, to\_account\_id ou to\_iban, beneficiary\_name, fx\_rate, fee\_minor |
| `fx_rates` | base, quote, rate, updated\_at |
| `audit_log` | id, user\_id, action, ip, created\_at |

O saldo de uma conta é a soma dos seus `ledger_entries`. Nenhuma operação pode deixar o saldo negativo.

## 7. IBAN: estrutura e validação

Um IBAN tem o código do país (2 letras), 2 dígitos de controlo e o número de conta nacional (BBAN). Angola (`AO`) e Portugal (`PT`) usam ambos 25 caracteres; confirma no registo oficial de IBAN antes de fixares estes valores no código.

Validação (algoritmo mod 97):

```python
COMPRIMENTOS = {'AO': 25, 'PT': 25}

def iban_valido(iban: str) -> bool:
    iban = iban.replace(' ', '').upper()
    if not iban.isalnum() or len(iban) < 15 or len(iban) > 34:
        return False
    pais = iban[:2]
    if pais in COMPRIMENTOS and len(iban) != COMPRIMENTOS[pais]:
        return False
    rearranjado = iban[4:] + iban[:4]
    numerico = ''.join(str(int(c, 36)) for c in rearranjado)
    return int(numerico) % 97 == 1
```

A validação só confirma o formato e os dígitos de controlo. **Não prova que a conta existe nem quem é o titular.** Por isso, mostra sempre o nome do beneficiário para a pessoa confirmar.

Para os IBAN virtuais de demonstração, gera um IBAN com formato válido e um prefixo de teste, e mostra na interface que é fictício, para não ser confundido com uma conta real.

## 8. Depósitos em Angola: Multicaixa Express e referência

Contexto (para a apresentação):

- A EMIS administra o arranjo de pagamentos Multicaixa e a infraestrutura central da rede.
- O Multicaixa Express permite associar cartões e fazer pagamentos, consultas, levantamentos e transferências pelo telemóvel. Em 2025, segundo a EMIS, foi responsável por cerca de 62% das operações da rede Multicaixa.
- Os pagamentos por referência na rede Multicaixa podem ser feitos em qualquer ATM ou na internet banking, e a entidade recebe notificação do pagamento.

Para o hackathon, define uma interface que depois possa ser trocada pela ligação real:

```python
class DepositProvider:
    def criar_pedido(self, valor_aoa_minor: int, conta_id: str) -> dict:
        raise NotImplementedError

    def estado(self, pedido_id: str) -> str:
        raise NotImplementedError
```

Implementa `DepositProviderSimulado` (gera referência, muda o estado quando carregas em «Simular pagamento»). Para uma ligação real, precisarias de um banco parceiro e/ou acordo com a EMIS. Não assumas que existe uma API pública pronta a usar; confirma diretamente com eles.

## 9. Pagamentos internacionais e câmbio

- Portugal faz parte da SEPA e Angola não. Enviar EUR para um IBAN português a sério exige acesso à SEPA através de um parceiro licenciado. Na demo, o `PayoutProvider` é simulado.
- Mostra sempre antes de confirmar: taxa de câmbio, taxa de serviço e valor final recebido pelo beneficiário.
- Cálculos de câmbio com inteiros e uma regra de arredondamento escrita e testada.
- Define limites por operação e por dia, e marca como «a rever» as operações acima de um valor.
- Há regras cambiais do BNA a respeitar num produto real. Consulta-as antes de operar.

## 10. Segurança

- Palavras-passe com hash forte (Argon2 ou bcrypt), nunca em texto simples.
- Segundo fator (simulado no MVP) para confirmar envios.
- Limite de tentativas de login e de pedidos (rate limiting).
- Chaves de idempotência em depósitos e transferências.
- Operações financeiras sempre dentro de transações de base de dados.
- Registo de auditoria de todas as ações sensíveis.
- Segredos (chave da Meta Model API, chaves de assinatura) apenas em variáveis de ambiente, nunca no código, no Git ou em mensagens de chat.
- Dados de demonstração fictícios.
- Validação de todas as entradas (valores positivos, moedas permitidas, IBAN válido).

## 11. Assistente de IA com a Meta Model API

**Configuração**

- URL base: `https://api.meta.ai/v1`
- Modelo: `muse-spark-1.3` (modo Standard, em que o conteúdo não é usado para treino)
- Chave: variável de ambiente `MODEL_API_KEY`

```python
import os
from openai import OpenAI

client = OpenAI(api_key=os.environ['MODEL_API_KEY'], base_url='https://api.meta.ai/v1')

def explicar_transferencia(dados: dict) -> str:
    resp = client.chat.completions.create(
        model='muse-spark-1.3',
        messages=[
            {'role': 'system', 'content': 'És o assistente de um banco digital de demonstração. Responde em português, de forma simples. Nunca peças palavras-passe nem números completos de cartão. Não executes operações.'},
            {'role': 'user', 'content': f'Explica esta transferência ao cliente: {dados}'},
        ],
    )
    return resp.choices[0].message.content
```

**Ideias de funcionalidades**

1. Explicar taxas, câmbio e prazos antes de confirmar um envio.
2. Categorizar despesas e resumir o extrato do mês.
3. Alertas de risco: regras fixas detetam o padrão suspeito e a IA explica o alerta ao utilizador.
4. Ajuda em linguagem natural («Como deposito por referência?»).

**Regras**

- A IA **nunca move dinheiro**. Qualquer ação exige confirmação explícita do utilizador, feita pelo sistema.
- Envia ao modelo só os dados mínimos, de preferência fictícios e sem identificadores pessoais.
- Trata a resposta do modelo como texto a apresentar, não como instruções a executar.
- Se usares chamadas de ferramentas, limita-as a leitura (consultar saldo, explicar) e valida tudo no teu código.

## 12. API do backend (proposta)

| Método e rota | Função |
| --- | --- |
| `POST /auth/register` · `POST /auth/login` | Registo e login |
| `GET /accounts` | Contas e saldos |
| `POST /deposits` | Criar depósito (método: `referencia` ou `multicaixa_express`) |
| `POST /webhooks/deposito` | Confirmação simulada de pagamento |
| `POST /transfers/internal` | Envio por número de conta |
| `POST /transfers/iban` | Envio para IBAN |
| `GET /fx/quote` | Cotação e taxas |
| `GET /transactions` | Histórico e extrato |
| `POST /assistant/explain` | Assistente de IA |

## 13. Guia de arranque (Windows, PowerShell)

```powershell
mkdir banco-digital
cd banco-digital
python -m venv .venv
.venv/Scripts/Activate.ps1
pip install fastapi uvicorn openai
$env:MODEL_API_KEY = 'a_tua_chave'
```

Estrutura sugerida:

```
banco-digital/
  app/
    main.py          # rotas FastAPI
    db.py            # ligação e esquema
    ledger.py        # transferências e saldos
    iban.py          # validação
    providers/       # depositos.py, payout.py, fx.py (simulados)
    assistant.py     # Meta Model API
  tests/
  README.md
```

Exemplo de transferência atómica e idempotente (SQLite):

```python
import sqlite3

def transferir(con: sqlite3.Connection, de_conta, para_conta, valor_minor, chave):
    if valor_minor <= 0:
        raise ValueError('valor inválido')
    with con:  # transação: tudo ou nada
        if con.execute('SELECT 1 FROM transactions WHERE idempotency_key=?', (chave,)).fetchone():
            return 'repetido'
        saldo = con.execute('SELECT COALESCE(SUM(amount_minor),0) FROM ledger_entries WHERE account_id=?', (de_conta,)).fetchone()[0]
        if saldo < valor_minor:
            raise ValueError('saldo insuficiente')
        tid = con.execute('INSERT INTO transactions(type,status,idempotency_key) VALUES(?,?,?)', ('transfer', 'completed', chave)).lastrowid
        con.execute('INSERT INTO ledger_entries(transaction_id,account_id,amount_minor,currency) VALUES(?,?,?,?)', (tid, de_conta, -valor_minor, 'AOA'))
        con.execute('INSERT INTO ledger_entries(transaction_id,account_id,amount_minor,currency) VALUES(?,?,?,?)', (tid, para_conta, valor_minor, 'AOA'))
    return 'ok'
```

Com várias pessoas a usar ao mesmo tempo, usa PostgreSQL com bloqueio de linhas, ou `BEGIN IMMEDIATE` no SQLite, para evitar dois débitos em simultâneo sobre o mesmo saldo.

## 14. Plano de 9 dias

O prazo de submissão é a 5 de novembro de 2026, às 6:30 (hora da Índia), o que corresponde a cerca das 2:00 em Luanda. Confirma a hora no portal. Submete com folga na véspera.

| Dia | Objetivo |
| --- | --- |
| Ter 27 e Qua 28 out | Desenho final, base de dados, livro-razão, registo e login |
| Qui 29 out | Contas, IBAN e validação, depósitos simulados |
| Sex 30 out | Transferências internas e para IBAN, câmbio e taxas |
| Sáb 31 out | Assistente de IA com a Meta Model API, segurança |
| Dom 1 e Seg 2 nov | Interface, testes, correção de erros |
| Ter 3 nov | Dados de demonstração, vídeo, README |
| Qua 4 nov | Congelar o código e **submeter** |
| Qui 5 nov (madrugada) | Prazo final. Não deixes para a última hora |

## 15. Distribuição de trabalho entre IAs

Não há uma percentagem certa. Lê as regras oficiais do hackathon para saber que ferramentas são exigidas e como declarar o uso de IA. Uma divisão sensata por tarefa:

| Parte | Quem faz |
| --- | --- |
| Funcionalidades de IA do produto | Meta Model API (`muse-spark-1.3`), parte central do projeto |
| Escrever código (backend, ecrãs, testes) | Muse Code, com outras IAs como apoio |
| Revisão de código, documentação, ideias de arquitetura | Qualquer assistente |
| Autenticação, saldos, transações, segurança | Tu, com revisão cuidadosa e testes |

O desenho do sistema, as decisões e a revisão final são sempre teus.

## 16. Demonstração e submissão

**Checklist**

- Código no repositório com `README.md` (como instalar, correr e testar)
- Vídeo de demonstração de 2 a 3 minutos
- Ligação à demo, se existir
- Explicação clara de **como a Meta Model API é usada**
- Aviso visível de que o dinheiro e as ligações bancárias são simulados
- Roadmap: o que seria preciso para operar a sério (licença, parceiros)

**Guião do pitch**

1. Problema: enviar e receber dinheiro entre Angola e o resto do mundo é difícil e caro.
2. Solução: carteira com depósito por Multicaixa Express ou referência e envio por conta ou IBAN.
3. Demo: depositar por referência → enviar para um IBAN em Portugal → ver o extrato.
4. IA: o assistente explica taxas e assinala operações suspeitas.
5. Impacto e próximos passos: parceiros licenciados, KYC real, mais países.

## 17. Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Querer fazer demasiado em 9 dias | Congelar o âmbito (secção 3); o que sobra vai para o roadmap |
| Erros nos saldos | Livro-razão de dupla entrada, testes automáticos, valores inteiros |
| Fuga da chave da API | Variáveis de ambiente, revogar e gerar nova se for exposta |
| Integrações reais indisponíveis | Adaptadores simulados com a mesma interface |
| Confundir demo com produto real | Aviso visível e IBAN de teste marcados como fictícios |
| Regras do hackathon não cumpridas | Ler as regras oficiais hoje e guardar a lista de requisitos |

## 18. Fontes e verificação

Informação do contexto angolano consultada em: aviso do BNA sobre cartões de pagamento e rede Multicaixa (EMIS); notícia do VerAngola sobre carteiras de moeda eletrónica e licença do BNA; resultados da EMIS para 2025 (VerAngola); brochura de pagamentos por referência do BAI. Dados do hackathon: página de inscrição da competição (Internshala). Dados da Meta Model API: documentação que colaste e resumos de terceiros.

Alguns detalhes (URL base da API, comprimento dos IBAN, regras do hackathon, regras do BNA) vêm de resumos ou da minha leitura. **Confirma-os nas fontes oficiais antes de os usares.**

# 🏦 Bankão — Carteira Digital para Angola e o Mundo

> **Meta Global AI Developer Hackathon (Cerebral Valley)**  
> **Track**: *Build for Your World*  
> **Foco em Bónus**: *Best Agentic Use-Case* · *Best Build on Meta Open Weight Models*

---

## 1. 🌍 Problema & Oportunidade

Enviar e receber dinheiro entre Angola e o resto do mundo (como Portugal, Europa ou Estados Unidos) é hoje um processo caro, lento e repleto de fricção:
- **Dificuldade de acesso a divisas** e burocracia excessiva nos canais tradicionais.
- **Taxas abusivas e pouca transparência** sobre a conversão cambial real.
- **Desconexão com a realidade angolana**, onde a rede **Multicaixa** (especialmente o **Multicaixa Express**, responsável por mais de 62% das transações) é o meio preferencial da população.

### A Solução: **Bankão**
O **Bankão** é uma carteira digital inteligente concebida especificamente para o contexto angolano:
1. **Depósitos Locais em Angola**: Simulação interativa e fiel de pagamentos por **Multicaixa Express** e **Referência Bancária de 9 dígitos** (para ATMs/Internet Banking).
2. **Envio Internacional Descomplicado**: Transferências instantâneas para **IBAN internacional (rede SEPA)** com validação matemática rigorosa de controle **Mod 97 (ISO 7064)**.
3. **Livro-Razão de Dupla Entrada (Ledger Atómico)**: Integridade financeira absoluta com valores inteiros em cêntimos (`minor units`), chaves de idempotência e bloqueio garantido de saldo negativo.
4. **Bankão AI Copilot (Meta Model API)**: Agente de inteligência financeira alimentado por **Meta Muse Spark** (`muse-spark-1.3` / `muse-spark-open-1026`) que explica taxas e câmbio em linguagem clara, monitoriza limites de risco e apoia o utilizador em português.

> ⚠️ **Aviso de Sandbox**: Este projeto foi desenvolvido para o Meta Global AI Developer Hackathon como uma demonstração funcional com fundos e conexões simuladas. Nenhum valor monetário real circula na plataforma.

---

## 2. 🧠 Uso dos Modelos da Meta (Meta Model API)

O Bankão incorpora o modelo **`muse-spark-1.3`** (e os modelos de pesos abertos **`muse-spark-open-1026`** via parceiros Baseten/Fireworks/Modal) nos seguintes fluxos do agente:

* **Explicador de Câmbio e Liquidação**: Descreve com transparência cirúrgica quanto o beneficiário recebe, a cotação aplicada e o tempo de liquidação na rede internacional.
* **Detecção de Riscos e Compliance**: Avalia transferências de alto valor e perfil de KYC, emitindo recomendações pedagógicas de segurança sem jamais movimentar fundos sem confirmação expressa do utilizador (*Human-in-the-loop*).
* **Copilot Conversacional em Português**: Auxilia utilizadores sobre como realizar depósitos e movimentações financeiras.

---

## 3. 🛠️ Arquitetura e Tecnologias

* **Backend**: Python 3.12+, FastAPI, Pydantic v2, Uvicorn.
* **Base de Dados & Ledger**: SQLite com modo `WAL` (Write-Ahead Logging), transações atómicas `BEGIN IMMEDIATE` e registros de auditoria.
* **Criptografia & Segurança**: Senhas com salt e hash `bcrypt`, tokens `JWT (HS256)` e chaves de idempotência em todas as mutações financeiras.
* **Frontend**: Single Page Application (SPA) moderna, estética "Fintech Premium" em dark mode, tipografia Plus Jakarta Sans e simulador de smartphone para o Multicaixa Express.
* **Validação Bancária**: Algoritmo oficial Mod 97 (ISO 7064) para IBANs de Angola (`AO25`) e Portugal (`PT25`).

---

## 4. 🚀 Como Executar o Projeto Localmente

### Pré-requisitos
- Python 3.10 ou superior
- PowerShell (Windows) ou Bash (Linux/macOS)

### Passo a Passo

```powershell
# 1. Clonar o repositório
git clone https://github.com/Lerdin09/bankao-meta-hackathon.git
cd bankao-meta-hackathon

# 2. Criar e ativar o ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # No Linux/macOS: source .venv/bin/activate

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis de ambiente
# (Copie o exemplo .env.example para .env e adicione sua chave MODEL_API_KEY se possuir)
Copy-Item .env.example .env

# 5. Executar os testes automatizados
python -m pytest -v tests/test_ledger.py
python tests/e2e_test.py

# 6. Iniciar o servidor
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Acesse no navegador:
👉 **`http://127.0.0.1:8000/`** (Interface Web)  
👉 **`http://127.0.0.1:8000/docs`** (Documentação Interativa Swagger/OpenAPI)

---

## 5. 🎬 Guião para o Vídeo de Demonstração (3 minutos)

1. **Minuto 0:00 - 0:40 (O Problema)**: Contextualizar a barreira enfrentada por quem vive em Angola ou na diáspora para movimentar recursos com segurança e taxas justas.
2. **Minuto 0:40 - 1:30 (Depósito Multicaixa Express)**: Demonstrar a simulação interativa no smartphone, aprovando uma recarga em Kwanzas creditada instantaneamente no livro-razão.
3. **Minuto 1:30 - 2:15 (Envio Internacional para Portugal)**: Inserir um IBAN português (`PT50...`), exibir a validação Mod 97 em tempo real, a simulação de câmbio transparente e solicitar ao **Bankão Copilot** a explicação detalhada da taxa.
4. **Minuto 2:15 - 3:00 (Meta Model API & Futuro)**: Destacar a integração com o modelo **Muse Spark**, a arquitetura de livro-razão atómico e a prontidão do sistema para integração com parceiros licenciados pelo BNA e SEPA.

---

## 6. 📄 Licença
Distribuído sob licença MIT. Consulte `LICENSE` para mais detalhes.

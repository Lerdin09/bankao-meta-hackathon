"""
Módulo de Integração com a Meta Model API (Muse Spark / Muse Spark Open).
BankAO AI Copilot:
- Explicação pedagógica de taxas cambiais e liquidação internacional.
- Análise de conformidade e detecção de riscos/operações atípicas.
- Resumo inteligente de extrato e categorização financeira.
- Fallback local inteligente quando a chave não estiver preenchida.
"""
import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI
from app.config import settings

logger = logging.getLogger("bankao.assistant")

COUNTRY_MAP = {
    "AO": "Angola 🇦🇴",
    "PT": "Portugal 🇵🇹",
    "ES": "Espanha 🇪🇸",
    "FR": "França 🇫🇷",
    "DE": "Alemanha 🇩🇪",
    "IT": "Itália 🇮🇹",
    "GB": "Reino Unido 🇬🇧",
    "US": "Estados Unidos 🇺🇸",
    "BR": "Brasil 🇧🇷",
    "CV": "Cabo Verde 🇨🇻",
    "MZ": "Moçambique 🇲🇿",
    "ZA": "África do Sul 🇿🇦",
}

def get_meta_client() -> Optional[OpenAI]:
    api_key = settings.MODEL_API_KEY
    if not api_key or api_key == "your_meta_model_api_key_here":
        return None
    return OpenAI(
        api_key=api_key,
        base_url=settings.MODEL_BASE_URL
    )

SYSTEM_PROMPT = """
És o 'BankAO Copilot', o assistente financeiro inteligente e amigável da carteira digital BankAO (voltada para Angola e o mundo).
Diretrizes fundamentais:
1. Responde sempre em Português claro, cordial e acessível, com pleno entendimento do contexto angolano e internacional (Multicaixa Express, referências, BNA, SEPA e envios para Portugal/Europa).
2. Se o utilizador pedir para realizar uma transferência, envio de dinheiro ou depósito (por exemplo: "faça a transferência para AO..., de 10000KZ, nome: ..."):
   - Confirma de forma imediata e amigável que preparaste os dados da operação.
   - Apresenta o resumo detalhado: Nome do beneficiário, Destino (IBAN/Conta), País, Quantia debitada, Taxa de serviço (2%) e Quanto vai/Valor líquido a receber (ex.: 10.000 Kz debitados, taxa de 2% (200 Kz), beneficiário recebe 9.800 Kz).
   - Informa que os dados foram pré-preenchidos no painel de transferências e que só falta o utilizador clicar em Confirmar para executar a operação em segurança.
   - Inclui no final da tua resposta o seguinte bloco JSON estrito:
   ```json:action
   {
      "type": "TRANSFER_IBAN",
      "beneficiary_name": "...",
      "to_iban": "...",
      "amount": 10000.0,
      "currency": "AOA",
      "country_code": "AO",
      "country_name": "Angola 🇦🇴",
      "fee_percent": 2.0,
      "fee_amount": 200.0,
      "net_amount": 9800.0
   }
   ```
3. Se o utilizador pedir para registar ou anotar uma despesa/gasto (ex.: "gastei 15000 kz no supermercado", "regista 20000 kz de combustível", "adiciona gasto de 8000 kz em almoço"):
   - Confirma de forma imediata que a despesa foi registada e categorizada.
   - Informa que a despesa foi adicionada à aba Despesas e já reflete no gráfico donut de divisão de gastos.
   - Inclui no final da tua resposta o seguinte bloco JSON estrito:
   ```json:action
   {
      "type": "REGISTER_EXPENSE",
      "name": "Nome da Despesa",
      "category": "Alimentação",
      "amount": 15000.0,
      "currency": "AOA",
      "notes": "Registado via Copilot IA"
   }
   ```
   (Categorias válidas: Alimentação, Transporte, Habitação, Telecomunicações, Lazer, Saúde, Outros)
4. Explica taxas de câmbio (Kz AOA, EUR, USD), prazos e custos de forma transparente e detalhada.
5. NUNCA peças palavras-passe, PINs ou dados confidenciais de cartões.
6. Lembra sempre que como IA não tens permissão para movimentar dinheiro diretamente — todas as ordens exigem confirmação deliberada do utilizador na plataforma.
"""

def extract_action_intent(message: str, ai_content: str = "") -> Optional[Dict[str, Any]]:
    """Detecta intenção de transferência, depósito ou registo de despesa."""
    # 1. Se o modelo Meta gerou bloco JSON
    if ai_content:
        json_match = re.search(r"```(?:json:action|json)\s*(\{.*?\})\s*```", ai_content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, dict) and data.get("type"):
                    return data
            except Exception:
                pass

    # 2. Parser Determinístico de Intenções em Português
    msg_clean = message.strip()
    msg_lower = msg_clean.lower()

    # Detecção de IBAN (ex: AO000390390404090, PT50003500000000000000000, etc.)
    iban_m = re.search(r"\b([A-Za-z]{2}\d[0-9A-Za-z]{7,32})\b", msg_clean)
    
    # Detecção de Conta interna BankAO (ex: 004012345678)
    acc_m = re.search(r"\b(0040\d{8}|0040[\s.-]?\d{4}[\s.-]?\d{4})\b", msg_clean)

    # Detecção de Depósito Express (telefone 9xx xxx xxx)
    deposit_kw = bool(re.search(r"deposit|multicaixa|express", msg_lower))
    phone_m = re.search(r"\b(9\d{8}|9\d{2}[\s.-]?\d{3}[\s.-]?\d{3})\b", msg_clean)

    # Detecção de Montante
    amt_m = re.search(r"(?:de|quantia|valor|montante|envia|transfere|transferir|depositar)\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(?:kz|kwanza|kwanzas|aoa|eur|€)?", msg_clean, re.IGNORECASE)
    if not amt_m:
        amt_m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:kz|kwanza|kwanzas|aoa)", msg_clean, re.IGNORECASE)
    if not amt_m:
        amt_m = re.search(r"\b(\d{3,9})\b", msg_clean)
        
    amount = float(amt_m.group(1).replace(",", ".")) if amt_m else 10000.0

    # Beneficiário / Nome
    name_m = re.search(r"nome(?:\s*tal|\s*do\s*benefici[aá]rio)?\s*[:=]?\s*([a-zA-ZÀ-ú\s]+?)(?:,|$|\.|\n)", msg_clean, re.IGNORECASE)
    if not name_m:
        name_m = re.search(r"para\s+(?:o|a)?\s*([A-Za-zÀ-ú]+(?:\s+[A-Za-zÀ-ú]+)+)", msg_clean, re.IGNORECASE)
    beneficiary = name_m.group(1).strip() if name_m else "Beneficiário"

    # Detecção de E-mail de cliente BankAO
    email_m = re.search(r"\b([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b", msg_clean)

    # Se for transferência por IBAN
    if iban_m or ("transfer" in msg_lower and not acc_m and not email_m and not deposit_kw):
        to_iban = iban_m.group(1).upper() if iban_m else "AO06999948102938102948102"
        country_code = to_iban[:2].upper()
        country_name = COUNTRY_MAP.get(country_code, f"{country_code} 🌐")
        fee_percent = 2.5
        fee_amount = round(amount * 0.025, 2)
        net_amount = round(amount - fee_amount, 2)
        dest_currency = "EUR" if country_code in ["PT", "ES", "FR", "DE", "IT"] else "AOA"

        return {
            "type": "TRANSFER_IBAN",
            "beneficiary_name": beneficiary,
            "to_iban": to_iban,
            "amount": amount,
            "currency": "AOA",
            "country_code": country_code,
            "country_name": country_name,
            "fee_percent": fee_percent,
            "fee_amount": fee_amount,
            "net_amount": net_amount,
            "dest_currency": dest_currency
        }

    # Se for transferência interna por E-mail ou Conta BankAO
    if email_m or acc_m:
        to_email = email_m.group(1) if email_m else None
        account_number = acc_m.group(1).replace(" ", "").replace("-", "") if acc_m else None
        fee_percent = 1.0
        fee_amount = round(amount * 0.01, 2)
        net_amount = round(amount - fee_amount, 2)
        return {
            "type": "TRANSFER_INTERNAL",
            "to_email": to_email,
            "to_account_number": account_number,
            "amount": amount,
            "currency": "AOA",
            "beneficiary_name": beneficiary,
            "fee_percent": fee_percent,
            "fee_amount": fee_amount,
            "net_amount": net_amount
        }

    # Se for Depósito Multicaixa Express
    if deposit_kw and phone_m:
        phone = phone_m.group(1).replace(" ", "").replace("-", "")
        return {
            "type": "DEPOSIT_EXPRESS",
            "phone_number": phone,
            "amount": amount,
            "currency": "AOA"
        }

    # Se for registo de despesa / gasto
    exp_kw = bool(re.search(r"despesa|gastei|gasto|comprei|compra|paguei|pagamento|regista|registar|anota|anotar|adiciona", msg_lower))
    if exp_kw and not deposit_kw and not iban_m and not acc_m:
        cat = "Outros"
        if re.search(r"supermercado|mercado|comida|almoço|jantar|lanche|restaurante|kero|maxi|candando|alimenta|pão|refeição", msg_lower):
            cat = "Alimentação"
        elif re.search(r"t[aá]xi|yango|uber|combust[ií]vel|gasolina|gas[oó]leo|sonangol|transporte|carro|viagem", msg_lower):
            cat = "Transporte"
        elif re.search(r"renda|casa|energia|luz|ende|água|epal|condom[ií]nio|habita", msg_lower):
            cat = "Habitação"
        elif re.search(r"unitel|zap|dstv|internet|net|saldo|telefone|telecom", msg_lower):
            cat = "Telecomunicações"
        elif re.search(r"praia|festa|cinema|bar|lazer|balada|show", msg_lower):
            cat = "Lazer"
        elif re.search(r"farm[aá]cia|rem[eé]dio|hospital|cl[ií]nica|sa[uú]de|m[eé]dico", msg_lower):
            cat = "Saúde"

        clean_desc = re.sub(r"^(?:regista|registar|anota|anotar|adiciona|coloque|gastei|comprei|paguei)\s*(?:uma)?\s*(?:despesa|gasto)?\s*(?:de)?\s*", "", msg_clean, flags=re.IGNORECASE)
        clean_desc = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:kz|kwanza|kwanzas|aoa)?\b", "", clean_desc, flags=re.IGNORECASE)
        clean_desc = re.sub(r"^(?:\s*\b(?:em|no|na|com|para|de)\b)+\s*", "", clean_desc, flags=re.IGNORECASE).strip()
        if not clean_desc or len(clean_desc) < 3:
            clean_desc = f"Despesa em {cat}"

        return {
            "type": "REGISTER_EXPENSE",
            "name": clean_desc.strip(". ").capitalize(),
            "category": cat,
            "amount": amount,
            "currency": "AOA",
            "notes": "Registado pelo BankAO Copilot IA"
        }

    return None

class BankaoAssistant:
    @staticmethod
    def explain_transfer(
        source_amount: float,
        source_currency: str,
        dest_amount: float,
        dest_currency: str,
        fx_rate: float,
        fee: float,
        dest_iban: str,
        beneficiary_name: str
    ) -> str:
        """Explica detalhadamente o custo, câmbio e trajeto da remessa."""
        client = get_meta_client()
        prompt = f"""
        Explica esta transferência ao cliente de forma clara e amigável:
        - Remetente envia: {source_amount:.2f} {source_currency}
        - Beneficiário: {beneficiary_name} (IBAN: {dest_iban})
        - Valor líquido a receber: {dest_amount:.2f} {dest_currency}
        - Taxa de Câmbio aplicada: 1 {source_currency} = {fx_rate} {dest_currency}
        - Taxa de serviço BankAO: {fee:.2f} {source_currency}
        - Prazo estimado: Simulação SEPA / Rede Bancária Internacional
        """
        if client:
            try:
                response = client.chat.completions.create(
                    model=settings.MODEL_NAME,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=2048,
                    temperature=0.3
                )
                content = response.choices[0].message.content
                if content:
                    return content
            except Exception as e:
                logger.error(f"Erro ao chamar Meta Model API (explain_transfer): {e}")

        # Fallback local humanizado e informativo
        return (
            f"Transferência para **{beneficiary_name}** ({dest_iban[:4]}...{dest_iban[-4:]}):\n"
            f"- **Montante debitado:** {source_amount:,.2f} {source_currency}\n"
            f"- **Taxa de serviço e processamento:** {fee:,.2f} {source_currency}\n"
            f"- **Câmbio aplicado:** 1 {source_currency} = {fx_rate} {dest_currency}\n"
            f"- **O beneficiário receberá:** {dest_amount:,.2f} {dest_currency}\n\n"
            f"💡 *Nota do Copilot:* O envio para IBAN segue os padrões de compensação bancária com total rastreabilidade. Nenhum custo oculto é cobrado ao destinatário."
        )

    @staticmethod
    def analyze_risk(
        amount: float,
        currency: str,
        tx_type: str,
        user_kyc_status: str
    ) -> Dict[str, Any]:
        """Analisa o perfil de risco da operação antes da autorização."""
        is_high_value = False
        if currency == "AOA" and amount >= 2_000_000:
            is_high_value = True
        elif currency in ("EUR", "USD") and amount >= 2_500:
            is_high_value = True

        client = get_meta_client()
        warning_text = ""
        risk_level = "baixo"

        if is_high_value:
            risk_level = "moderado" if user_kyc_status == "verificado" else "elevado"
            prompt = f"""
            Esta operação foi assinalada para verificação de segurança:
            - Tipo: {tx_type}
            - Valor: {amount:,.2f} {currency}
            - Estado KYC do cliente: {user_kyc_status}
            Gera uma curta recomendação de conformidade e segurança bancária para o utilizador.
            """
            if client:
                try:
                    resp = client.chat.completions.create(
                        model=settings.MODEL_NAME,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=2048,
                        temperature=0.2
                    )
                    content = resp.choices[0].message.content
                    if content:
                        warning_text = content
                except Exception as e:
                    logger.error(f"Erro ao chamar Meta Model API (analyze_risk): {e}")

            if not warning_text:
                warning_text = (
                    f"⚠️ **Aviso de Segurança BankAO**: Esta transação de {amount:,.2f} {currency} ultrapassa o limiar de verificação regular. "
                    f"Certifique-se da identidade do beneficiário antes de confirmar com o seu código de segurança."
                )
        else:
            warning_text = "Operação dentro dos padrões habituais de segurança."

        return {
            "risk_level": risk_level,
            "requires_2fa": is_high_value or (tx_type == "transfer_iban"),
            "advice": warning_text
        }

    @staticmethod
    def chat_with_action(message: str, history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """Processa a mensagem com Meta Model API e extrai payload de ação (Action Calling)."""
        client = get_meta_client()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history[-4:])
        messages.append({"role": "user", "content": message})

        ai_content = ""
        if client:
            try:
                response = client.chat.completions.create(
                    model=settings.MODEL_NAME,
                    messages=messages,
                    max_tokens=2048,
                    temperature=0.3
                )
                ai_content = response.choices[0].message.content or ""
            except Exception as e:
                logger.error(f"Erro ao chamar Meta Model API (chat): {e}")

        # Extrair ação pretendida
        action = extract_action_intent(message, ai_content)

        # Se houver ação de transferência
        if action and action.get("type") == "TRANSFER_IBAN":
            clean_reply = re.sub(r"```(?:json:action|json).*?```", "", ai_content, flags=re.DOTALL).strip()
            if not clean_reply or len(clean_reply) < 30:
                clean_reply = (
                    f"Com certeza! Preparei a sua transferência para **{action['beneficiary_name']}** no valor de **{action['amount']:,.2f} {action['currency']}**.\n\n"
                    f"📋 **Resumo da Operação:**\n"
                    f"• **Beneficiário:** {action['beneficiary_name']}\n"
                    f"• **Destino (IBAN):** `{action['to_iban']}`\n"
                    f"• **País:** {action['country_name']}\n"
                    f"• **Quantia enviada:** {action['amount']:,.2f} {action['currency']}\n"
                    f"• **Taxa de serviço ({action['fee_percent']:.0f}%):** {action['fee_amount']:,.2f} {action['currency']}\n"
                    f"• **Valor líquido a receber:** {action['net_amount']:,.2f} {action['currency']}\n\n"
                    f"⚡ *Abri o painel de transferências com todos os dados preenchidos. Só falta conferir e clicar em **Confirmar e enviar**!*"
                )
            return {
                "reply": clean_reply,
                "action": action
            }

        # Se houver ação de registo de despesa
        if action and action.get("type") == "REGISTER_EXPENSE":
            clean_reply = re.sub(r"```(?:json:action|json).*?```", "", ai_content, flags=re.DOTALL).strip()
            if not clean_reply or len(clean_reply) < 20:
                clean_reply = (
                    f"✅ **Despesa registada com sucesso!**\n\n"
                    f"Registei o gasto de **{action['amount']:,.2f} {action.get('currency', 'AOA')}** em **{action.get('category', 'Outros')}** "
                    f"({action.get('name', 'Despesa')}).\n\n"
                    f"📊 Já atualizei a sua aba **Despesas** e o gráfico donut com esta nova divisão de gastos."
                )
            return {
                "reply": clean_reply,
                "action": action
            }

        # Caso geral com resposta da IA
        if ai_content:
            clean_reply = re.sub(r"```(?:json:action|json).*?```", "", ai_content, flags=re.DOTALL).strip()
            return {
                "reply": clean_reply,
                "action": action
            }

        # Resposta inteligente para dúvidas frequentes no modo offline/simulado
        msg_lower = message.lower()
        if "multicaixa" in msg_lower or "depositar" in msg_lower or "referência" in msg_lower:
            fallback = (
                "Para depositar no BankAO em Angola você tem duas opções muito fáceis:\n\n"
                "1. **Multicaixa Express:** Digite o seu número de telemóvel associado ao aplicativo e aprove a notificação no seu telefone.\n"
                "2. **Pagamento por Referência:** Geramos um código de Entidade (00543) e Referência de 9 dígitos para você pagar em qualquer ATM ou no Internet Banking do seu banco (ex: BAI, BFA, BIC)."
            )
        elif "iban" in msg_lower or "portugal" in msg_lower or "europa" in msg_lower or "transferir" in msg_lower:
            fallback = (
                "Para transferir para Portugal ou outro país da Europa:\n\n"
                "1. Acesse **Enviar Dinheiro** e selecione a aba **Para IBAN Internacional**.\n"
                "2. Introduza o IBAN do destinatário (validamos automaticamente o algoritmo Mod 97 para evitar erros).\n"
                "3. Veja a cotação em tempo real entre Kwanzas (AOA) e Euros (EUR) com as taxas transparentes.\n"
                "4. Confirme a operação com o seu código de segurança."
            )
        elif "taxa" in msg_lower or "cambio" in msg_lower or "câmbio" in msg_lower:
            fallback = (
                "No BankAO praticamos uma política de taxa de câmbio transparente: "
                "a cotação de referência é atualizada e aplicamos uma taxa de serviço fixa de apenas 1,5% sobre o valor convertido, sem comissões ocultas para quem recebe."
            )
        else:
            fallback = (
                f"Olá! Sou o **BankAO Copilot**, alimentado pela tecnologia **Meta Muse Spark**.\n\n"
                f"Posso ajudar com:\n"
                f"• Como fazer depósitos por Multicaixa Express ou Referência\n"
                f"• Como enviar dinheiro para contas internas ou IBAN em Portugal/Europa\n"
                f"• Explicação das taxas de câmbio e simulação de valores recebidos\n"
                f"• Esclarecimento sobre segurança e regras de conformidade."
            )

        return {
            "reply": fallback,
            "action": action
        }

    @staticmethod
    def chat(message: str, history: List[Dict[str, str]] = None) -> str:
        """Compatibilidade direta retornando texto da resposta."""
        res = BankaoAssistant.chat_with_action(message, history)
        return res["reply"]

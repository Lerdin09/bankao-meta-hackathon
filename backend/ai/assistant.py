"""
Módulo de Integração com a Meta Model API (Muse Spark / Muse Spark Open).
BankAO AI Copilot:
- Explicação pedagógica de taxas cambiais e liquidação internacional.
- Análise de conformidade e detecção de riscos/operações atípicas.
- Resumo inteligente de extrato e categorização financeira.
- Fallback local inteligente quando a chave não estiver preenchida.
"""

import logging
import re

from typing import Any, Dict, List

from backend.ai.client import extract_reasoning_and_content, get_meta_client
from backend.ai.intents import analyze_action_reply, analyze_message, extract_action_intent
from backend.ai.prompts import COUNTRY_MAP, SYSTEM_PROMPT  # noqa: F401 (reexportados para compatibilidade)
from backend.core.config import settings

logger = logging.getLogger("bankao.assistant")


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
                    model=settings.active_model_name,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=min(settings.AI_MAX_TOKENS, 800),
                    temperature=0.3
                )
                parsed = extract_reasoning_and_content(response.choices[0])
                content = parsed["clean_content"]
                if content:
                    return content
            except Exception as e:
                logger.error(f"Erro ao chamar Meta Model API / Baseten (explain_transfer): {e}")

        # Fallback local curto
        return (
            f"**{beneficiary_name}** ({dest_iban[:4]}...{dest_iban[-4:]}) recebe **{dest_amount:,.2f} {dest_currency}**.\n"
            f"Debitado: {source_amount:,.2f} {source_currency} · Taxa: {fee:,.2f} {source_currency} · Câmbio: 1 {source_currency} = {fx_rate} {dest_currency}."
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
                        model=settings.active_model_name,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=min(settings.AI_MAX_TOKENS, 500),
                        temperature=0.2
                    )
                    parsed = extract_reasoning_and_content(resp.choices[0])
                    content = parsed["clean_content"]
                    if content:
                        warning_text = content
                except Exception as e:
                    logger.error(f"Erro ao chamar Meta Model API / Baseten (analyze_risk): {e}")

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
    def chat_with_action(message: str, history: List[Dict[str, str]] = None, pending: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Processa a mensagem. Pedidos operacionais (poupança, despesa, transferência, depósito) são
        interpretados de forma determinística: a resposta descreve exatamente o que foi preparado e
        NUNCA afirma que algo foi feito — a conclusão é sempre do utilizador, no formulário.
        """
        parsed = analyze_message(message, pending)
        if parsed["reply"]:
            return {"reply": parsed["reply"], "action": parsed["action"], "pending": parsed["pending"]}

        client = get_meta_client()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history[-6:])
        messages.append({"role": "user", "content": message})

        ai_content = ""
        reasoning_trace = None
        if client:
            try:
                response = client.chat.completions.create(
                    model=settings.active_model_name,
                    messages=messages,
                    max_tokens=min(settings.AI_MAX_TOKENS, 1200),
                    temperature=0.3
                )
                parsed = extract_reasoning_and_content(response.choices[0])
                ai_content = parsed["clean_content"]
                reasoning_trace = parsed.get("reasoning")
            except Exception as e:
                logger.error(f"Erro ao chamar Meta Model API / Baseten (chat): {e}")

        # Ação sugerida pelo modelo: só é aceite depois de validada (e recalculada) no backend
        action = extract_action_intent(message, ai_content)
        if action:
            built = analyze_action_reply(action)
            return {"reply": built, "action": action, "pending": None}

        # Caso geral com resposta da IA (os blocos de ação, se existirem, nunca chegam ao utilizador)
        if ai_content:
            clean_reply = re.sub(r"```(?:json:action|json).*?```", "", ai_content, flags=re.DOTALL).strip()
            return {"reply": clean_reply, "action": None, "pending": None}

        # Resposta inteligente para dúvidas frequentes no modo offline/simulado
        msg_lower = message.lower()
        if "multicaixa" in msg_lower or "depositar" in msg_lower or "referência" in msg_lower:
            fallback = "Podes depositar por **Multicaixa Express** (aprovas no telemóvel) ou por **Referência** (pagas em qualquer ATM)."
        elif "iban" in msg_lower or "portugal" in msg_lower or "europa" in msg_lower or "transferir" in msg_lower:
            fallback = "Em **Enviar Dinheiro** escolhe «Para IBAN», indica o IBAN e o valor. Vês a taxa e quanto chega antes de confirmar."
        elif "taxa" in msg_lower or "cambio" in msg_lower or "câmbio" in msg_lower:
            fallback = "Taxas: **1%** entre contas BankAO e **2,5%** por IBAN. O câmbio de referência aparece antes de confirmares."
        elif any(k in msg_lower for k in ["invest", "aplicar", "rendimento", "bodiva", "prazo", "juros", "lucro", "etf"]):
            fallback = (
                "📈 **Investimentos no BankAO:**\n"
                "• **Depósito a Prazo (até 18,5% ao ano):** Capital 100% garantido e juros creditados diretamente na conta.\n"
                "• **Obrigações do Tesouro na BODIVA (17,2% a.a.):** Títulos soberanos com pagamentos de cupão semestrais.\n"
                "• **ETFs Globais:** Proteção cambial e valorização internacional.\n\n"
                "Pode consultar a aba **Investimentos** para aplicar ou pedir-me uma simulação (ex.: *«Se poupar 30 mil por mês, quanto terei daqui a um ano?»*)."
            )
        elif any(k in msg_lower for k in ["despesa", "gasto", "gastei", "compras", "consumo"]):
            fallback = (
                "📊 **Controlo de Despesas:**\n"
                "Analiso os seus consumos por categoria e comparo o mês atual com o anterior.\n\n"
                "Experimente perguntar: *«Quanto gastei este mês?»*, *«Onde estou a gastar mais?»* ou pedir para registar uma despesa (ex.: *«Regista 8000 em combustível»*)."
            )
        elif any(k in msg_lower for k in ["saldo", "dinheiro", "conta"]):
            fallback = "Pode consultar o seu saldo consolidado em Kwanzas, Dólares ou Euros perguntando-me: *«Quanto dinheiro tenho?»* ou *«Qual é o meu saldo?»*."
        else:
            fallback = "Olá! Sou o **BankAO Copilot**. Posso ajudar com consulta de saldos, análise de despesas, simulação de investimentos, depósitos e transferências seguras. Como posso ser útil?"

        return {
            "reply": fallback,
            "action": None,
            "pending": None
        }

    @staticmethod
    def chat(message: str, history: List[Dict[str, str]] = None) -> str:
        """Compatibilidade direta retornando texto da resposta."""
        res = BankaoAssistant.chat_with_action(message, history)
        return res["reply"]

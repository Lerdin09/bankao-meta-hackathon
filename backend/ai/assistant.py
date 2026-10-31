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

from backend.ai.client import get_meta_client
from backend.ai.intents import extract_action_intent
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

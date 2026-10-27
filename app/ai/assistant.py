"""
Módulo de Integração com a Meta Model API (Muse Spark / Muse Spark Open).
Bankão AI Copilot:
- Explicação pedagógica de taxas cambiais e liquidação internacional.
- Análise de conformidade e detecção de riscos/operações atípicas.
- Resumo inteligente de extrato e categorização financeira.
- Fallback local inteligente quando a chave não estiver preenchida.
"""
import os
import json
from typing import Dict, Any, List, Optional
from openai import OpenAI
from app.config import settings

def get_meta_client() -> Optional[OpenAI]:
    api_key = settings.MODEL_API_KEY
    if not api_key or api_key == "your_meta_model_api_key_here":
        return None
    return OpenAI(
        api_key=api_key,
        base_url=settings.MODEL_BASE_URL
    )

SYSTEM_PROMPT = """
És o 'Bankão Copilot', um assistente financeiro inteligente e amigável da carteira digital Bankão (voltada para Angola e o mundo).
Diretrizes fundamentais:
1. Responde sempre em Português claro, cordial e acessível (com sensibilidade ao contexto angolano e internacional).
2. Explica taxas de câmbio (Kz AOA, EUR, USD), prazos e custos de forma transparente e detalhada.
3. Alerta sobre limites diários e boas práticas de segurança contra fraudes.
4. NUNCA peças palavras-passe, PINs ou dados confidenciais de cartões.
5. Lembra sempre que como IA não tens permissão para movimentar dinheiro diretamente — todas as ordens exigem confirmação deliberada do utilizador na plataforma.
"""

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
        - Taxa de serviço Bankão: {fee:.2f} {source_currency}
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
                    max_tokens=400,
                    temperature=0.3
                )
                return response.choices[0].message.content
            except Exception as e:
                # Caso ocorra falha de rede ou chave inválida, recai no gerador local
                pass

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
                        max_tokens=250,
                        temperature=0.2
                    )
                    warning_text = resp.choices[0].message.content
                except Exception:
                    pass

            if not warning_text:
                warning_text = (
                    f"⚠️ **Aviso de Segurança Bankão**: Esta transação de {amount:,.2f} {currency} ultrapassa o limiar de verificação regular. "
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
    def chat(message: str, history: List[Dict[str, str]] = None) -> str:
        """Atendimento em linguagem natural sobre serviços da carteira."""
        client = get_meta_client()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history[-4:])
        messages.append({"role": "user", "content": message})

        if client:
            try:
                response = client.chat.completions.create(
                    model=settings.MODEL_NAME,
                    messages=messages,
                    max_tokens=450,
                    temperature=0.4
                )
                return response.choices[0].message.content
            except Exception as e:
                pass

        # Resposta inteligente para dúvidas frequentes no modo offline/simulado
        msg_lower = message.lower()
        if "multicaixa" in msg_lower or "depositar" in msg_lower or "referência" in msg_lower:
            return (
                "Para depositar no Bankão em Angola você tem duas opções muito fáceis:\n\n"
                "1. **Multicaixa Express:** Digite o seu número de telemóvel associado ao aplicativo e aprove a notificação no seu telefone.\n"
                "2. **Pagamento por Referência:** Geramos um código de Entidade (00543) e Referência de 9 dígitos para você pagar em qualquer ATM ou no Internet Banking do seu banco (ex: BAI, BFA, BIC)."
            )
        elif "iban" in msg_lower or "portugal" in msg_lower or "europa" in msg_lower or "transferir" in msg_lower:
            return (
                "Para transferir para Portugal ou outro país da Europa:\n\n"
                "1. Acesse **Enviar Dinheiro** e selecione a aba **Para IBAN Internacional**.\n"
                "2. Introduza o IBAN do destinatário (validamos automaticamente o algoritmo Mod 97 para evitar erros).\n"
                "3. Veja a cotação em tempo real entre Kwanzas (AOA) e Euros (EUR) com as taxas transparentes.\n"
                "4. Confirme a operação com o seu código de segurança."
            )
        elif "taxa" in msg_lower or "cambio" in msg_lower or "câmbio" in msg_lower:
            return (
                "No Bankão praticamos uma política de taxa de câmbio transparente: "
                "a cotação de referência é atualizada e aplicamos uma taxa de serviço fixa de apenas 1,5% sobre o valor convertido, sem comissões ocultas para quem recebe."
            )
        else:
            return (
                f"Olá! Sou o **Bankão Copilot**, alimentado pela tecnologia **Meta Muse Spark**.\n\n"
                f"Posso ajudar com:\n"
                f"• Como fazer depósitos por Multicaixa Express ou Referência\n"
                f"• Como enviar dinheiro para contas internas ou IBAN em Portugal/Europa\n"
                f"• Explicação das taxas de câmbio e simulação de valores recebidos\n"
                f"• Esclarecimento sobre segurança e regras de conformidade."
            )

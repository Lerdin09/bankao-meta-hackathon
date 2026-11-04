"""
Módulo de Visão Computacional e Multimodalidade (Baseten & Meta Muse Spark Open).
Processa imagens de:
- Comprovativos de transferência bancária (Multicaixa / EMIS / SEPA / IBAN).
- Faturas, talões de supermercado e compras.
- Cartões de débito/crédito ou referências de pagamento.
"""
import json
import logging
import re
from typing import Any, Dict, Optional

from backend.ai.client import build_multimodal_message, extract_reasoning_and_content, get_meta_client
from backend.core.config import settings

logger = logging.getLogger("bankao.ai_vision")

VISION_SYSTEM_PROMPT = """
És o especialista em análise visual de documentos bancários e financeiros do BankAO (Angola e Europa).
A tua missão é examinar faturas, talões de compra (POS/TPA), comprovativos Multicaixa Express ou transferências bancárias e extrair dados rigorosos.

Deves SEMPRE responder com um bloco JSON estrito no seguinte formato:
```json
{
  "document_type": "comprovativo_transferencia" | "recibo_compra" | "fatura" | "cartao_iban" | "outro",
  "merchant_or_entity": "Nome do comerciante, loja, empresa ou beneficiário",
  "amount": 12500.0,
  "currency": "AOA" | "EUR" | "USD",
  "date": "YYYY-MM-DD",
  "category": "Alimentação" | "Transporte" | "Combustível" | "Saúde" | "Educação" | "Habitação" | "Serviços" | "Lazer" | "Outros",
  "beneficiary_iban": "AO06..." ou "PT50..." ou null,
  "beneficiary_name": "Nome de quem recebe" ou null,
  "summary": "Resumo claro em português (ex: Compra de 12.500 Kz no Kero Talatona).",
  "suggested_action": "EXPENSE_REGISTER" | "TRANSFER_PREPARE" | "INFO_ONLY"
}
```
Não inventes valores que não estejam na imagem. Se a moeda for Kwanzas, usa "AOA". Se for Euros, "EUR". Se for Dólares, "USD".
"""


def analyze_financial_document(
    image_bytes_or_b64: Any,
    mime_type: str = "image/jpeg",
    user_hint: Optional[str] = None
) -> Dict[str, Any]:
    """
    Envia a imagem para o Meta Muse Spark Open via Baseten Vision API.
    Retorna os dados estruturados e a ação correspondente no BankAO.
    """
    client = get_meta_client()
    if not client:
        return {
            "ok": False,
            "error": "Cliente de IA não configurado. Adicione a chave BASETEN_API_KEY no ficheiro .env.",
            "provider": "offline",
        }

    prompt = (
        "Analisa detalhadamente este documento/comprovativo e extrai o comerciante/beneficiário, "
        "valor total, moeda, data e categoria bancária correspondente."
    )
    if user_hint:
        prompt += f"\nNota do utilizador: {user_hint}"

    messages = [
        {"role": "system", "content": VISION_SYSTEM_PROMPT},
        *build_multimodal_message(prompt, image_bytes_or_b64, mime_type)
    ]

    try:
        response = client.chat.completions.create(
            model=settings.active_model_name,
            messages=messages,
            max_tokens=settings.AI_MAX_TOKENS,
            temperature=0.1,
            timeout=50,
        )
        choice = response.choices[0]
        parsed = extract_reasoning_and_content(choice)
        content = parsed["clean_content"]
        reasoning = parsed.get("reasoning", "")

        # Extrair JSON da resposta
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if match:
            doc_data = json.loads(match.group(1))
        else:
            # Tenta encontrar primeiro { até último }
            s = content.find("{")
            e = content.rfind("}")
            if s != -1 and e != -1 and e > s:
                doc_data = json.loads(content[s : e + 1])
            else:
                doc_data = {
                    "document_type": "outro",
                    "merchant_or_entity": "Comprovativo",
                    "amount": 0.0,
                    "currency": "AOA",
                    "summary": content.strip()[:200],
                    "suggested_action": "INFO_ONLY"
                }

        # Construir ação de conveniência para o BankAO
        action = None
        sugg = doc_data.get("suggested_action", "")
        amount = float(doc_data.get("amount") or 0.0)
        curr = doc_data.get("currency", "AOA")

        if sugg == "EXPENSE_REGISTER" and amount > 0:
            action = {
                "type": "EXPENSE_REGISTERED",
                "name": doc_data.get("merchant_or_entity", "Despesa por Talão"),
                "amount": amount,
                "currency": curr,
                "category": doc_data.get("category", "Outros"),
                "expense_date": doc_data.get("date"),
                "source": "vision_scan",
                "requires_confirmation": False
            }
        elif sugg == "TRANSFER_PREPARE" and amount > 0:
            action = {
                "type": "TRANSFER_IBAN" if doc_data.get("beneficiary_iban") else "TRANSFER_INTERNAL",
                "beneficiary_name": doc_data.get("beneficiary_name") or doc_data.get("merchant_or_entity", "Beneficiário"),
                "iban": doc_data.get("beneficiary_iban"),
                "amount": amount,
                "currency": curr,
                "requires_confirmation": True
            }

        return {
            "ok": True,
            "document": doc_data,
            "action": action,
            "reasoning": reasoning,
            "model": settings.active_model_name,
            "provider": (
                "Baseten (Meta Muse Spark Open Vision)"
                if settings.active_ai_provider == "baseten"
                else "Meta Vision"
            )
        }
    except Exception as e:
        logger.error("Erro na análise visual de documento com Muse Spark Open: %s", e, exc_info=True)
        return {
            "ok": False,
            "error": f"Falha ao analisar a imagem com a API de Visão: {str(e)}",
            "model": settings.active_model_name,
        }


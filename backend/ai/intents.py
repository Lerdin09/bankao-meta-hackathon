"""
Deteção de intenções (transferência, depósito, registo de despesa) a partir da conversa.
"""
import json
import re
from typing import Any, Dict, Optional
from backend.ai.prompts import COUNTRY_MAP


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

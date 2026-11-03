"""
Validador e gerador de IBAN com conformidade ao algoritmo Mod 97 (ISO 7064).
Suporte a Angola (AO - 25 caracteres) e Portugal (PT - 25 caracteres).
"""
import random
import re

IBAN_LENGTHS = {
    'AO': 25,  # Angola: AO + 2 dígitos controle + 21 dígitos BBAN
    'PT': 25,  # Portugal: PT + 2 dígitos controle + 21 dígitos BBAN
    'US': 26,  # Estados Unidos: US + 2 dígitos controle + 22 dígitos BBAN (Routing + Conta)
}

def iban_valido(iban: str) -> bool:
    """
    Verifica se um IBAN possui formato e dígitos de controle matematicamente válidos (Mod 97).
    """
    if not iban:
        return False
    iban = iban.replace(" ", "").upper()
    if not iban.isalnum() or len(iban) < 15 or len(iban) > 34:
        return False
    
    country = iban[:2]
    if country in IBAN_LENGTHS and len(iban) != IBAN_LENGTHS[country]:
        return False
        
    rearranged = iban[4:] + iban[:4]
    numeric_str = "".join(str(int(ch, 36)) for ch in rearranged)
    try:
        return int(numeric_str) % 97 == 1
    except ValueError:
        return False

def gerar_iban_ficticio(pais: str = "AO") -> str:
    """
    Gera um IBAN realístico e matematicamente válido (Mod 97 - ISO 7064)
    com códigos bancários reais para Angola (AO), Portugal (PT) e Estados Unidos (US).
    """
    country = pais.upper()
    if country not in IBAN_LENGTHS:
        country = "AO"
        
    if country == "AO":
        # Código de banco real em Angola (ex: 0040 - BFA) + 17 dígitos
        bank_code = "0040"
        random_part = "".join([str(random.randint(0, 9)) for _ in range(17)])
        bban = f"{bank_code}{random_part}"
    elif country == "PT":
        # Código de banco real em Portugal (ex: 0035 - CGD) + 17 dígitos
        bank_code = "0035"
        random_part = "".join([str(random.randint(0, 9)) for _ in range(17)])
        bban = f"{bank_code}{random_part}"
    elif country == "US":
        # Código de routing bancário real nos EUA + 13 dígitos de conta
        routing = "026009593"
        account_num = "".join([str(random.randint(0, 9)) for _ in range(13)])
        bban = f"{routing}{account_num}"
    else:
        bank_code = "0040"
        random_part = "".join([str(random.randint(0, 9)) for _ in range(17)])
        bban = f"{bank_code}{random_part}"
    
    # Cálculo dos dígitos de controle Mod 97
    check_temp = bban + country + "00"
    num_str = "".join(str(int(ch, 36)) for ch in check_temp)
    remainder = int(num_str) % 97
    check_digits = f"{98 - remainder:02d}"
    
    return f"{country}{check_digits}{bban}"

def formatar_iban(iban: str) -> str:
    """Formata o IBAN em blocos de 4 caracteres para exibição limpa."""
    clean = iban.replace(" ", "").upper()
    return " ".join([clean[i:i+4] for i in range(0, len(clean), 4)])

"""
Validador e gerador de IBAN com conformidade ao algoritmo Mod 97 (ISO 7064).
Suporte a Angola (AO - 25 caracteres) e Portugal (PT - 25 caracteres).
"""
import random
import re

IBAN_LENGTHS = {
    'AO': 25,  # Angola: AO06 + 21 dígitos BBAN
    'PT': 25,  # Portugal: PT50 + 21 dígitos BBAN
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
    Gera um IBAN fictício matematicamente válido com prefixo de demonstração '9999'.
    """
    country = pais.upper()
    if country not in IBAN_LENGTHS:
        country = "AO"
        
    # BBAN fictício de 21 caracteres
    # Usamos o prefixo 9999 para identificar visualmente como sandbox/teste
    random_part = "".join([str(random.randint(0, 9)) for _ in range(17)])
    bban = f"9999{random_part}"
    
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

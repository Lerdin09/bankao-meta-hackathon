"""
Test Suite for Questions 71–80: Transferências Bancárias e Execução de Operações
Validação dos 9 critérios de segurança e integridade transacional.
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')

from backend.ai.orchestrator import CopilotOrchestrator

USER_ID = '2e0a4847-d1a9-48a6-86de-40229a125b58'

print("=" * 70)
print("TESTE DE SEGURANÇA E OPERAÇÕES BANCÁRIAS (Q71–Q80)")
print("=" * 70)

all_passed = True

# ---------------------------------------------------------------------------
# Q71: Quero transferir 25.000 Kz para João Manuel, conta 004012345678.
# ---------------------------------------------------------------------------
print("\n--- Teste Q71: Transferência Interna por Conta ---")
r71 = CopilotOrchestrator.process_message(USER_ID, "Quero transferir 25.000 Kz para João Manuel, conta 004012345678.")
a71 = r71.get("action") or {}
ok71 = (
    a71.get("type") == "TRANSFER_INTERNAL"
    and a71.get("to_account_number") == "004012345678"
    and "joão manuel" in (a71.get("beneficiary_name") or "").lower()
    and a71.get("amount") == 25000.0
    and a71.get("currency") == "AOA"
    and a71.get("fee_amount") == 250.0  # 1%
    and a71.get("net_amount") == 24750.0
    and r71.get("requires_confirmation") is True
)
print(f"Q71 Status: {'✅ PASS' if ok71 else '❌ FAIL'}")
print(f"  Beneficiário: {a71.get('beneficiary_name')} | Conta: {a71.get('to_account_number')}")
print(f"  Valor: {a71.get('amount')} {a71.get('currency')} | Taxa: {a71.get('fee_amount')} Kz | Líquido: {a71.get('net_amount')} Kz")
print(f"  Aguardando Confirmação: {r71.get('requires_confirmation')}")
if not ok71: all_passed = False

# ---------------------------------------------------------------------------
# Q72: Transfere 150.000 Kz para Maria Silva através do IBAN AO06004000001234567890123.
# ---------------------------------------------------------------------------
print("\n--- Teste Q72: Transferência Interbancária por IBAN ---")
r72 = CopilotOrchestrator.process_message(USER_ID, "Transfere 150.000 Kz para Maria Silva através do IBAN AO06004000001234567890123.")
a72 = r72.get("action") or {}
ok72 = (
    a72.get("type") == "TRANSFER_IBAN"
    and a72.get("to_iban") == "AO06004000001234567890123"
    and "maria silva" in (a72.get("beneficiary_name") or "").lower()
    and a72.get("amount") == 150000.0
    and a72.get("currency") == "AOA"
    and a72.get("fee_amount") == 3750.0  # 2.5%
    and a72.get("net_amount") == 146250.0
    and r72.get("requires_confirmation") is True
)
print(f"Q72 Status: {'✅ PASS' if ok72 else '❌ FAIL'}")
print(f"  Beneficiário: {a72.get('beneficiary_name')} | IBAN: {a72.get('to_iban')}")
print(f"  Valor: {a72.get('amount')} {a72.get('currency')} | Taxa: {a72.get('fee_amount')} Kz | Líquido: {a72.get('net_amount')} Kz")
print(f"  Aguardando Confirmação: {r72.get('requires_confirmation')}")
if not ok72: all_passed = False

# ---------------------------------------------------------------------------
# Q73: Quero enviar 50 mil para o meu irmão.
# ---------------------------------------------------------------------------
print("\n--- Teste Q73: Transferência para Contacto Frequente (Irmão) ---")
r73 = CopilotOrchestrator.process_message(USER_ID, "Quero enviar 50 mil para o meu irmão.")
a73 = r73.get("action") or {}
ok73 = (
    a73.get("type") in ("TRANSFER_IBAN", "TRANSFER_INTERNAL")
    and "paulo" in (a73.get("beneficiary_name") or "").lower()
    and a73.get("amount") == 50000.0
    and a73.get("currency") == "AOA"
    and a73.get("fee_amount") == 1250.0  # 2.5%
    and a73.get("net_amount") == 48750.0
    and r73.get("requires_confirmation") is True
)
print(f"Q73 Status: {'✅ PASS' if ok73 else '❌ FAIL'}")
print(f"  Beneficiário: {a73.get('beneficiary_name')} | Destino: {a73.get('to_iban') or a73.get('to_account_number')}")
print(f"  Valor: {a73.get('amount')} {a73.get('currency')} | Taxa: {a73.get('fee_amount')} Kz | Líquido: {a73.get('net_amount')} Kz")
print(f"  Aguardando Confirmação: {r73.get('requires_confirmation')}")
if not ok73: all_passed = False

# ---------------------------------------------------------------------------
# Q74: Faz uma transferência de 10.500 Kz para a conta que utilizei na última transferência.
# ---------------------------------------------------------------------------
print("\n--- Teste Q74: Repetir Último Destinatário ---")
r74 = CopilotOrchestrator.process_message(USER_ID, "Faz uma transferência de 10.500 Kz para a conta que utilizei na última transferência.")
a74 = r74.get("action") or {}
ok74 = (
    a74.get("type") in ("TRANSFER_IBAN", "TRANSFER_INTERNAL")
    and "paulo" in (a74.get("beneficiary_name") or "").lower()
    and a74.get("amount") == 10500.0
    and a74.get("currency") == "AOA"
    and a74.get("fee_amount") == 262.5  # 2.5%
    and a74.get("net_amount") == 10237.5
    and r74.get("requires_confirmation") is True
)
print(f"Q74 Status: {'✅ PASS' if ok74 else '❌ FAIL'}")
print(f"  Beneficiário: {a74.get('beneficiary_name')} | Destino: {a74.get('to_iban') or a74.get('to_account_number')}")
print(f"  Valor: {a74.get('amount')} {a74.get('currency')} | Taxa: {a74.get('fee_amount')} Kz | Líquido: {a74.get('net_amount')} Kz")
print(f"  Aguardando Confirmação: {r74.get('requires_confirmation')}")
if not ok74: all_passed = False

# ---------------------------------------------------------------------------
# Q75: Quero transferir 100 euros para Portugal.
# ---------------------------------------------------------------------------
print("\n--- Teste Q75: Transferência Internacional em Moeda Estrangeira ---")
r75 = CopilotOrchestrator.process_message(USER_ID, "Quero transferir 100 euros para Portugal.")
reply75 = r75.get("reply", "") or ""
ok75 = (
    len(reply75) > 20
    and ("iban" in reply75.lower() or "destinatário" in reply75.lower() or "portugal" in reply75.lower())
    and r75.get("requires_confirmation") is False  # Não executa sem IBAN!
)
print(f"Q75 Status: {'✅ PASS' if ok75 else '❌ FAIL'}")
print(f"  Resposta da IA: {reply75}")
print(f"  Executou sem IBAN? {r75.get('action') is not None} (esperado: False)")
if not ok75: all_passed = False

# ---------------------------------------------------------------------------
# Q76: Quanto vou pagar de comissão se transferir 200.000 Kz para outro banco?
# ---------------------------------------------------------------------------
print("\n--- Teste Q76: Consulta de Taxas e Comissões ---")
r76 = CopilotOrchestrator.process_message(USER_ID, "Quanto vou pagar de comissão se transferir 200.000 Kz para outro banco?")
reply76 = r76.get("reply", "") or ""
ok76 = (
    "5.000" in reply76 or "5000" in reply76
    and ("2,5%" in reply76 or "2.5%" in reply76 or "comissão" in reply76.lower() or "taxa" in reply76.lower())
)
print(f"Q76 Status: {'✅ PASS' if ok76 else '❌ FAIL'}")
print(f"  Resposta da IA: {reply76}")
print(f"  Identificou 5.000 Kz (2,5%)? {ok76}")
if not ok76: all_passed = False

# ---------------------------------------------------------------------------
# Q77: Quero transferir 15.000 Kz, mas ainda não sei o IBAN. Ajuda-me.
# ---------------------------------------------------------------------------
print("\n--- Teste Q77: Apoio ao Cliente Sem IBAN ---")
r77 = CopilotOrchestrator.process_message(USER_ID, "Quero transferir 15.000 Kz, mas ainda não sei o IBAN. Ajuda-me.")
reply77 = r77.get("reply", "") or ""
ok77 = (
    len(reply77) > 30
    and r77.get("action") is None
    and ("iban" in reply77.lower() or "contacto" in reply77.lower() or "bankao" in reply77.lower())
)
print(f"Q77 Status: {'✅ PASS' if ok77 else '❌ FAIL'}")
print(f"  Resposta da IA: {reply77}")
print(f"  Apoiou sem inventar dados? {ok77}")
if not ok77: all_passed = False

# ---------------------------------------------------------------------------
# Q78: Prepara uma transferência de 75.000 Kz para Carlos, mas não quero confirmar ainda.
# ---------------------------------------------------------------------------
print("\n--- Teste Q78: Preparação Segura para Carlos ---")
r78 = CopilotOrchestrator.process_message(USER_ID, "Prepara uma transferência de 75.000 Kz para Carlos, mas não quero confirmar ainda.")
a78 = r78.get("action") or {}
ok78 = (
    a78.get("type") in ("TRANSFER_IBAN", "TRANSFER_INTERNAL")
    and "carlos" in (a78.get("beneficiary_name") or "").lower()
    and a78.get("amount") == 75000.0
    and a78.get("fee_amount") == 1875.0  # 2.5%
    and a78.get("net_amount") == 73125.0
    and r78.get("requires_confirmation") is True
)
print(f"Q78 Status: {'✅ PASS' if ok78 else '❌ FAIL'}")
print(f"  Beneficiário: {a78.get('beneficiary_name')} | Destino: {a78.get('to_iban') or a78.get('to_account_number')}")
print(f"  Valor: {a78.get('amount')} {a78.get('currency')} | Taxa: {a78.get('fee_amount')} Kz | Líquido: {a78.get('net_amount')} Kz")
print(f"  Aguardando Confirmação: {r78.get('requires_confirmation')}")
if not ok78: all_passed = False

# ---------------------------------------------------------------------------
# Q79: Quero alterar o valor da transferência que acabaste de preparar para 90.000 Kz.
# ---------------------------------------------------------------------------
print("\n--- Teste Q79: Atualização de Montante Preparado ---")
r79 = CopilotOrchestrator.process_message(USER_ID, "Quero alterar o valor da transferência que acabaste de preparar para 90.000 Kz.")
a79 = r79.get("action") or {}
ok79 = (
    a79.get("type") in ("TRANSFER_IBAN", "TRANSFER_INTERNAL")
    and "carlos" in (a79.get("beneficiary_name") or "").lower()
    and a79.get("amount") == 90000.0
    and a79.get("fee_amount") == 2250.0  # 2.5%
    and a79.get("net_amount") == 87750.0
    and r79.get("requires_confirmation") is True
)
print(f"Q79 Status: {'✅ PASS' if ok79 else '❌ FAIL'}")
print(f"  Beneficiário: {a79.get('beneficiary_name')} | Novo Valor: {a79.get('amount')} {a79.get('currency')}")
print(f"  Nova Taxa: {a79.get('fee_amount')} Kz | Novo Líquido: {a79.get('net_amount')} Kz")
print(f"  Aguardando Confirmação: {r79.get('requires_confirmation')}")
if not ok79: all_passed = False

# ---------------------------------------------------------------------------
# Q80: Cancela a transferência que preparaste anteriormente.
# ---------------------------------------------------------------------------
print("\n--- Teste Q80: Cancelamento e Limpeza da Operação ---")
r80 = CopilotOrchestrator.process_message(USER_ID, "Cancela a transferência que preparaste anteriormente.")
a80 = r80.get("action")
ok80 = (
    a80 is None
    and r80.get("requires_confirmation") is False
    and ("sem efeito" in r80.get("reply", "").lower() or "cancel" in r80.get("reply", "").lower() or "descansa" in r80.get("reply", "").lower())
)
print(f"Q80 Status: {'✅ PASS' if ok80 else '❌ FAIL'}")
print(f"  Resposta da IA: {r80.get('reply')}")
print(f"  Operação Cancelada / Limpa: {a80 is None}")
print(f"  Exige Confirmação: {r80.get('requires_confirmation')}")
if not ok80: all_passed = False

print("\n" + "=" * 70)
print(f"RESULTADO FINAL: {'10/10 PASS — TODAS AS OPERAÇÕES CONFORMES' if all_passed else 'FALHA EM ALGUMAS OPERAÇÕES'}")
print("=" * 70)


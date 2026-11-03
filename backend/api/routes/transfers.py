"""
Rotas — Transferências: Transferências internas (taxa 1%) e para IBAN.
"""

import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException

from backend.core.security import get_current_user
from backend.database import get_connection
from backend.providers.payout import PayoutProvider
from backend.schemas import IbanTransferCreate, InternalTransferCreate
from backend.services.ledger import InsufficientFundsError, execute_internal_transfer

router = APIRouter(prefix="/api/transfers", tags=["Transferências"])


@router.post("/internal")
def transfer_internal(
    data: InternalTransferCreate,
    current_user: dict = Depends(get_current_user)
):
    amount_minor = int(round(data.amount * 100))
    if amount_minor <= 0:
        raise HTTPException(status_code=400, detail="O montante deve ser estritamente maior que zero.")

    # Descobrir a conta de destino pelo e-mail ou número de conta
    with get_connection() as conn:
        dest = None
        beneficiary_name = "Cliente BankAO"

        if data.to_email:
            dest_user = conn.execute(
                "SELECT id, nome, primeiro_nome, ultimo_nome, email FROM users WHERE lower(email) = lower(?)",
                (data.to_email.strip(),)
            ).fetchone()
            if not dest_user:
                raise HTTPException(status_code=404, detail=f"Cliente com e-mail '{data.to_email}' não encontrado.")
            
            nome_cand = dest_user["nome"]
            if not nome_cand or nome_cand == "Novo Utilizador":
                nome_cand = f"{dest_user['primeiro_nome'] or ''} {dest_user['ultimo_nome'] or ''}".strip() or dest_user["email"]
            beneficiary_name = nome_cand

            from_acc = conn.execute("SELECT currency FROM accounts WHERE id = ?", (data.from_account_id,)).fetchone()
            curr = from_acc["currency"] if from_acc else "AOA"
            dest = conn.execute(
                "SELECT id, account_number FROM accounts WHERE user_id = ? AND currency = ? AND status = 'active'",
                (dest_user["id"], curr)
            ).fetchone()
            if not dest:
                dest = conn.execute(
                    "SELECT id, account_number FROM accounts WHERE user_id = ? AND status = 'active' LIMIT 1",
                    (dest_user["id"],)
                ).fetchone()

        elif data.to_account_number:
            dest = conn.execute(
                "SELECT a.id, a.account_number, u.nome, u.primeiro_nome, u.ultimo_nome FROM accounts a JOIN users u ON a.user_id = u.id WHERE a.account_number = ?",
                (data.to_account_number.strip(),)
            ).fetchone()
            if dest:
                beneficiary_name = dest["nome"] or f"{dest['primeiro_nome'] or ''} {dest['ultimo_nome'] or ''}".strip() or "Cliente BankAO"
            else:
                dest_direct = conn.execute("SELECT id FROM accounts WHERE account_number = ?", (data.to_account_number.strip(),)).fetchone()
                if dest_direct:
                    dest = dest_direct

        if not dest:
            raise HTTPException(status_code=404, detail="Conta ou e-mail de destino não encontrado.")
        to_account_id = dest["id"]

    # Taxa de 1% para transferência entre contas
    fee_minor = int(round(amount_minor * 0.01))
    dest_amount_minor = max(0, amount_minor - fee_minor)

    try:
        res = execute_internal_transfer(
            from_account_id=data.from_account_id,
            to_account_id=to_account_id,
            amount_minor=amount_minor,
            fee_minor=fee_minor,
            idempotency_key=data.idempotency_key,
            description=data.description,
            beneficiary_name=beneficiary_name
        )
        res["beneficiary_name"] = beneficiary_name
        res["source_amount_decimal"] = amount_minor / 100.0
        res["dest_amount_decimal"] = dest_amount_minor / 100.0
        res["fee_decimal"] = fee_minor / 100.0
        res["fee_percentage"] = 1.0

        # Registar saída nas Despesas do utilizador (categoria 'Transferências')
        try:
            with get_connection() as conn_exp:
                exp_id = str(uuid.uuid4())
                today_iso = datetime.date.today().isoformat()
                from_acc = conn_exp.execute("SELECT currency, user_id FROM accounts WHERE id = ?", (data.from_account_id,)).fetchone()
                curr = from_acc["currency"] if from_acc else "AOA"
                owner_uid = from_acc["user_id"] if from_acc else current_user["id"]
                conn_exp.execute("""
                    INSERT INTO expenses (id, user_id, name, category, amount_minor, currency, expense_date, origin, notes)
                    VALUES (?, ?, ?, 'Transferências', ?, ?, ?, 'transfer', ?)
                """, (
                    exp_id,
                    owner_uid,
                    f"Transferência — {beneficiary_name}",
                    amount_minor,
                    curr,
                    today_iso,
                    f"Transferência enviada para {beneficiary_name}" + (f": {data.description}" if data.description else "")
                ))
                conn_exp.commit()
        except Exception:
            pass

        return res
    except InsufficientFundsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/iban")
def transfer_iban(
    data: IbanTransferCreate,
    current_user: dict = Depends(get_current_user)
):
    amount_minor = int(round(data.amount * 100))
    
    # Identificar moeda da conta de origem
    with get_connection() as conn:
        acc = conn.execute("SELECT currency FROM accounts WHERE id = ?", (data.from_account_id,)).fetchone()
        if not acc:
            raise HTTPException(status_code=404, detail="Conta de origem não encontrada.")
        source_currency = acc["currency"]

    try:
        res = PayoutProvider.transferir_para_iban(
            from_account_id=data.from_account_id,
            to_iban=data.to_iban,
            beneficiary_name=data.beneficiary_name,
            amount_minor=amount_minor,
            source_currency=source_currency,
            dest_currency=data.dest_currency,
            idempotency_key=data.idempotency_key
        )

        # Registar saída nas Despesas do utilizador (categoria 'Transferências')
        try:
            with get_connection() as conn_exp:
                exp_id = str(uuid.uuid4())
                today_iso = datetime.date.today().isoformat()
                label_dest = data.beneficiary_name or data.to_iban
                conn_exp.execute("""
                    INSERT INTO expenses (id, user_id, name, category, amount_minor, currency, expense_date, origin, notes)
                    VALUES (?, ?, ?, 'Transferências', ?, ?, ?, 'transfer', ?)
                """, (
                    exp_id,
                    current_user["id"],
                    f"Transferência IBAN — {label_dest}",
                    amount_minor,
                    source_currency,
                    today_iso,
                    f"Transferência IBAN enviada para {data.to_iban} ({data.beneficiary_name or 'Sem beneficiário'})"
                ))
                conn_exp.commit()
        except Exception:
            pass

        return res
    except InsufficientFundsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

"""
Rotas — Módulo de Investimentos (Catálogo, Carteira Integrada, Operações e Notificações).
Permite consultar produtos de bancos, corretoras (BODIVA, ETFs, DP, Fundos),
registar investimentos internos (com débito em conta) e externos, acompanhar evolução,
sincronizar atualizações de cotações/juros via APIs integradas e gerir resgates e histórico.
"""
import datetime
import math
import random
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.core.security import get_current_user
from backend.database import get_connection
from backend.database.connection import transaction_scope
from backend.providers.investments import fetch_update, settlement_value
from backend.services.ledger import (
    AccountNotFoundError,
    InsufficientFundsError,
    get_account_balance,
    post_investment_movement,
)

router = APIRouter(prefix="/api/investments", tags=["Investimentos"])


# --- Schemas ---

class ApplyIn(BaseModel):
    product_id: str
    amount: float = Field(..., gt=0)
    account_id: Optional[str] = None
    notes: Optional[str] = None


class ExternalInvestIn(BaseModel):
    name: str
    category: str  # 'deposito_prazo', 'obrigacoes', 'etf', 'fundos', 'acoes'
    institution: str
    amount: float = Field(..., gt=0)
    currency: str = "AOA"
    rate_annual: Optional[float] = 0.0
    start_date: str
    maturity_date: Optional[str] = None
    notes: Optional[str] = None


class RedeemIn(BaseModel):
    amount: Optional[float] = None  # None = total
    account_id: Optional[str] = None


# --- Helpers de conversão ---

def _to_minor(v: float) -> int:
    return int(round(float(v) * 100))


def _to_decimal(m: int) -> float:
    return round(float(m) / 100.0, 2)


CATEGORY_LABELS = {
    "deposito_prazo": "Depósito a Prazo",
    "obrigacoes": "Títulos & Obrigações",
    "etf": "ETFs Globais",
    "fundos": "Fundos de Investimento",
    "acoes": "Ações Cotadas",
}

CATEGORY_COLORS = {
    "deposito_prazo": "#38BDF8",  # Sky Blue
    "obrigacoes": "#10B981",       # Emerald
    "etf": "#818CF8",              # Indigo
    "fundos": "#F59E0B",           # Amber
    "acoes": "#EC4899",            # Pink
}


def _product_to_dict(r) -> dict:
    min_dec = _to_decimal(r["min_amount_minor"])
    rate = float(r["rate_annual"])
    term_m = r["term_months"]

    # Simulação de rendimento estimado a 1 ano (ou termo)
    term_factor = (term_m / 12.0) if term_m else 1.0
    sim_yield = round(min_dec * (rate / 100.0) * term_factor, 2)

    return {
        "id": r["id"],
        "name": r["name"],
        "category": r["category"],
        "category_label": CATEGORY_LABELS.get(r["category"], r["category"].title()),
        "category_color": CATEGORY_COLORS.get(r["category"], "#64748B"),
        "institution": r["institution"],
        "provider_api": r["provider_api"],
        "currency": r["currency"],
        "rate_annual": rate,
        "term_months": term_m,
        "term_label": f"{term_m} meses" if term_m else "Sem prazo fixo (Aberto)",
        "min_amount": min_dec,
        "min_amount_minor": r["min_amount_minor"],
        "risk_level": r["risk_level"],
        "liquidity": r["liquidity"],
        "fees_info": r["fees_info"] or "Isento de taxas ocultas.",
        "redemption_conditions": r["redemption_conditions"] or "Resgate disponível no vencimento.",
        "description": r["description"] or "",
        "current_price": float(r["current_price"] or 1.0),
        "simulated_yield_min": sim_yield,
        "is_active": bool(r["is_active"]),
    }


def _investment_to_dict(r) -> dict:
    inv_dec = _to_decimal(r["amount_invested_minor"])
    cur_dec = _to_decimal(r["current_value_minor"])
    yld_dec = _to_decimal(r["accumulated_yield_minor"])

    gain_loss = round(cur_dec - inv_dec, 2)
    gain_pct = round((gain_loss / inv_dec * 100.0), 2) if inv_dec > 0 else 0.0

    return {
        "id": r["id"],
        "product_id": r["product_id"],
        "name": r["name"],
        "category": r["category"],
        "category_label": CATEGORY_LABELS.get(r["category"], r["category"].title()),
        "category_color": CATEGORY_COLORS.get(r["category"], "#64748B"),
        "institution": r["institution"],
        "is_external": bool(r["is_external"]),
        "account_id": r["account_id"],
        "amount_invested": inv_dec,
        "amount_invested_minor": r["amount_invested_minor"],
        "current_value": cur_dec,
        "current_value_minor": r["current_value_minor"],
        "accumulated_yield": yld_dec,
        "accumulated_yield_minor": r["accumulated_yield_minor"],
        "gain_loss": gain_loss,
        "gain_percentage": gain_pct,
        "currency": r["currency"],
        "rate_annual": float(r["rate_annual"] or 0.0),
        "start_date": r["start_date"],
        "maturity_date": r["maturity_date"],
        "status": r["status"],
        "notes": r["notes"] or "",
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }


# =====================================================================
# 1. Catálogo de Investimentos & Detalhes
# =====================================================================

@router.get("/catalog")
def get_catalog(
    category: Optional[str] = None,
    currency: Optional[str] = None,
    risk: Optional[str] = None,
    search: Optional[str] = None,
):
    """Lista todos os produtos de investimento disponíveis para subscrição."""
    with get_connection() as conn:
        q = "SELECT * FROM investment_products WHERE is_active = 1"
        params: List[Any] = []

        if category and category != "all":
            q += " AND category = ?"
            params.append(category)
        if currency and currency != "all":
            q += " AND currency = ?"
            params.append(currency)
        if risk and risk != "all":
            q += " AND risk_level = ?"
            params.append(risk)
        if search:
            q += " AND (name LIKE ? OR institution LIKE ? OR description LIKE ?)"
            s_param = f"%{search.strip()}%"
            params.extend([s_param, s_param, s_param])

        q += " ORDER BY rate_annual DESC, name ASC"
        rows = conn.execute(q, params).fetchall()

        # Categorias disponíveis com contagem
        cat_counts = conn.execute("""
            SELECT category, COUNT(*) as cnt
            FROM investment_products WHERE is_active = 1
            GROUP BY category
        """).fetchall()

        categories_summary = [
            {
                "key": r["category"],
                "label": CATEGORY_LABELS.get(r["category"], r["category"].title()),
                "count": r["cnt"],
            }
            for r in cat_counts
        ]

        return {
            "products": [_product_to_dict(r) for r in rows],
            "categories": categories_summary,
            "total_count": len(rows),
        }


@router.get("/catalog/{product_id}")
def get_catalog_product(product_id: str):
    """Obtém os detalhes completos de um produto e simulações de retorno."""
    with get_connection() as conn:
        r = conn.execute("SELECT * FROM investment_products WHERE id = ?", (product_id,)).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Produto de investimento não encontrado.")

        data = _product_to_dict(r)
        min_amt = data["min_amount"]
        rate = data["rate_annual"]
        term_m = data["term_months"] or 12

        # Gerar simulações para múltiplos montantes
        multipliers = [1.0, 2.5, 5.0, 10.0]
        simulations = []
        for mul in multipliers:
            principal = round(min_amt * mul, 2)
            gross_return = round(principal * (rate / 100.0) * (term_m / 12.0), 2)
            # IACM ou imposto de aplicação de capitais de 10% para depósitos/títulos
            tax = round(gross_return * 0.10, 2) if data["category"] in ("deposito_prazo", "obrigacoes") else 0.0
            net_return = round(gross_return - tax, 2)
            simulations.append({
                "principal": principal,
                "gross_return": gross_return,
                "tax_estimate": tax,
                "net_return": net_return,
                "total_at_maturity": round(principal + net_return, 2),
            })

        data["simulations"] = simulations
        return data


# =====================================================================
# 2. Carteira de Investimentos (Acompanhamento & Alocação)
# =====================================================================

@router.get("/portfolio")
def get_portfolio(user=Depends(get_current_user)):
    """Apresenta a carteira consolidada de investimentos do utilizador."""
    user_id = user["id"]
    with transaction_scope() as _c:
        _settle_matured(_c, user_id)
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM user_investments
            WHERE user_id = ?
            ORDER BY status ASC, created_at DESC
        """, (user_id,)).fetchall()

        # Obter taxas de câmbio para consolidar totais
        fx_rows = conn.execute("SELECT base_currency, quote_currency, rate FROM fx_rates").fetchall()
        fx_map: Dict[str, float] = {}
        for f in fx_rows:
            fx_map[f"{f['base_currency']}_{f['quote_currency']}"] = float(f["rate"])

        def to_aoa(val_dec: float, curr: str) -> float:
            if curr == "AOA":
                return val_dec
            if f"{curr}_AOA" in fx_map:
                return val_dec * fx_map[f"{curr}_AOA"]
            if curr == "USD":
                return val_dec * 1000.0
            if curr == "EUR":
                return val_dec * 1050.0
            return val_dec

        total_inv_aoa = 0.0
        total_cur_aoa = 0.0
        total_yld_aoa = 0.0

        by_currency_inv: Dict[str, float] = {}
        by_currency_cur: Dict[str, float] = {}
        by_category_cur: Dict[str, float] = {}
        by_institution_cur: Dict[str, float] = {}

        next_maturity_date = None
        next_maturity_name = None
        today_str = datetime.date.today().isoformat()

        items = []
        for r in rows:
            it = _investment_to_dict(r)
            items.append(it)

            if it["status"] == "ativo":
                curr = it["currency"]
                c_inv = it["amount_invested"]
                c_val = it["current_value"]
                c_yld = it["accumulated_yield"]

                total_inv_aoa += to_aoa(c_inv, curr)
                total_cur_aoa += to_aoa(c_val, curr)
                total_yld_aoa += to_aoa(c_yld, curr)

                by_currency_inv[curr] = round(by_currency_inv.get(curr, 0.0) + c_inv, 2)
                by_currency_cur[curr] = round(by_currency_cur.get(curr, 0.0) + c_val, 2)

                cat = it["category"]
                by_category_cur[cat] = round(by_category_cur.get(cat, 0.0) + to_aoa(c_val, curr), 2)

                inst = it["institution"]
                by_institution_cur[inst] = round(by_institution_cur.get(inst, 0.0) + to_aoa(c_val, curr), 2)

                mat = it["maturity_date"]
                if mat and mat >= today_str:
                    if next_maturity_date is None or mat < next_maturity_date:
                        next_maturity_date = mat
                        next_maturity_name = it["name"]

        total_gain_aoa = round(total_cur_aoa - total_inv_aoa, 2)
        total_gain_pct = round((total_gain_aoa / total_inv_aoa * 100.0), 2) if total_inv_aoa > 0 else 0.0

        # Alocação por categoria
        allocations_cat = []
        for cat, val_aoa in by_category_cur.items():
            pct = round((val_aoa / total_cur_aoa * 100.0), 1) if total_cur_aoa > 0 else 0.0
            allocations_cat.append({
                "category": cat,
                "label": CATEGORY_LABELS.get(cat, cat.title()),
                "amount_aoa": val_aoa,
                "percentage": pct,
                "color": CATEGORY_COLORS.get(cat, "#38BDF8"),
            })
        allocations_cat.sort(key=lambda x: x["amount_aoa"], reverse=True)

        # Alocação por instituição
        allocations_inst = []
        for inst, val_aoa in by_institution_cur.items():
            pct = round((val_aoa / total_cur_aoa * 100.0), 1) if total_cur_aoa > 0 else 0.0
            allocations_inst.append({
                "institution": inst,
                "amount_aoa": val_aoa,
                "percentage": pct,
            })
        allocations_inst.sort(key=lambda x: x["amount_aoa"], reverse=True)

        # Evolução mensal: cada ativo ativo entra na data de início e o seu rendimento
        # acumula de forma linear (pro-rata) até ao valor atual.
        evolution = []
        now_dt = datetime.date.today()
        active_rows = [it for it in items if it["status"] == "ativo"]
        for i in range(5, -1, -1):
            point = now_dt - datetime.timedelta(days=i * 30)
            inv_p = val_p = 0.0
            for it in active_rows:
                try:
                    start = datetime.date.fromisoformat(it["start_date"])
                except Exception:
                    start = now_dt
                if start > point:
                    continue
                span = max(1, (now_dt - start).days)
                frac = min(1.0, max(0.0, (point - start).days / span))
                gain = it["current_value"] - it["amount_invested"]
                inv_p += to_aoa(it["amount_invested"], it["currency"])
                val_p += to_aoa(it["amount_invested"] + gain * frac, it["currency"])
            evolution.append({
                "label": point.strftime("%d/%m"),
                "invested_aoa": round(inv_p, 2),
                "value_aoa": round(val_p, 2),
            })

        return {
            "summary": {
                "total_invested_aoa": round(total_inv_aoa, 2),
                "total_current_aoa": round(total_cur_aoa, 2),
                "total_yield_aoa": round(total_yld_aoa, 2),
                "total_gain_aoa": total_gain_aoa,
                "total_gain_percentage": total_gain_pct,
                "by_currency_invested": by_currency_inv,
                "by_currency_current": by_currency_cur,
                "active_count": len([i for i in items if i["status"] == "ativo"]),
                "next_maturity_date": next_maturity_date,
                "next_maturity_name": next_maturity_name,
            },
            "allocations": {
                "categories": allocations_cat,
                "institutions": allocations_inst,
            },
            "investments": items,
            "evolution": evolution,
        }


# =====================================================================
# 3. Aplicações e Registo de Investimentos Externos
# =====================================================================

@router.post("/portfolio/apply")
def apply_investment(data: ApplyIn, user=Depends(get_current_user)):
    """Subscreve um produto do catálogo debitando na conta do BankAO."""
    user_id = user["id"]
    with transaction_scope() as conn:
        prod = conn.execute("SELECT * FROM investment_products WHERE id = ?", (data.product_id,)).fetchone()
        if not prod:
            raise HTTPException(status_code=404, detail="Produto de investimento não encontrado.")

        amt_minor = _to_minor(data.amount)
        if amt_minor < prod["min_amount_minor"]:
            min_dec = _to_decimal(prod["min_amount_minor"])
            raise HTTPException(
                status_code=400,
                detail=f"O montante mínimo de subscrição para este produto é {min_dec:,.2f} {prod['currency']}.",
            )

        # Se for produto interno ou com conta especificada, debitar conta
        account_id = data.account_id
        tx_id = None
        if account_id:
            acc = conn.execute(
                "SELECT id, currency, status FROM accounts WHERE id = ? AND user_id = ?",
                (account_id, user_id),
            ).fetchone()
            if not acc:
                raise HTTPException(status_code=404, detail="Conta selecionada não encontrada.")
            if acc["currency"] != prod["currency"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"A conta selecionada ({acc['currency']}) deve coincidir com a moeda do produto ({prod['currency']}).",
                )

            # Debitar livro-razão (-amt_minor)
            idem_key = f"inv_apply_{uuid.uuid4().hex[:12]}"
            desc = f"Subscrição de Investimento — {prod['name']}"
            try:
                res = post_investment_movement(
                    conn=conn,
                    account_id=account_id,
                    amount_minor=-amt_minor,
                    idempotency_key=idem_key,
                    description=desc,
                    tx_type="investment_apply",
                )
                tx_id = res["transaction_id"]
            except InsufficientFundsError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Erro ao processar débito em conta: {str(e)}")

        # Calcular data de vencimento
        today = datetime.date.today()
        mat_date = None
        if prod["term_months"]:
            # Adicionar meses
            m_add = prod["term_months"]
            year = today.year + (today.month + m_add - 1) // 12
            month = (today.month + m_add - 1) % 12 + 1
            day = min(today.day, 28)
            mat_date = datetime.date(year, month, day).isoformat()

        inv_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO user_investments (
                id, user_id, product_id, name, category, institution, is_external,
                account_id, amount_invested_minor, current_value_minor,
                accumulated_yield_minor, currency, rate_annual, start_date,
                maturity_date, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 'ativo', ?)
        """, (
            inv_id,
            user_id,
            prod["id"],
            prod["name"],
            prod["category"],
            prod["institution"],
            0 if account_id else 1,
            account_id,
            amt_minor,
            amt_minor,  # Valor atual inicial é o aplicado
            prod["currency"],
            prod["rate_annual"],
            today.isoformat(),
            mat_date,
            data.notes or "",
        ))

        # Registar operação no histórico
        op_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO investment_operations (
                id, investment_id, user_id, operation_type, amount_minor,
                currency, operation_date, description, transaction_id
            ) VALUES (?, ?, ?, 'aplicacao', ?, ?, ?, ?, ?)
        """, (
            op_id,
            inv_id,
            user_id,
            amt_minor,
            prod["currency"],
            today.isoformat(),
            f"Aplicação inicial em {prod['name']} ({prod['institution']})",
            tx_id,
        ))

        # Notificação de confirmação
        conn.execute("""
            INSERT INTO investment_notifications (
                id, user_id, investment_id, type, title, message
            ) VALUES (?, ?, ?, 'aplicacao_confirmada', ?, ?)
        """, (
            str(uuid.uuid4()),
            user_id,
            inv_id,
            "Subscrição Concluída",
            f"O seu investimento de {data.amount:,.2f} {prod['currency']} em '{prod['name']}' foi ativado com sucesso.",
        ))

        # Registar saída nas Despesas do utilizador (categoria 'Investimentos', origin='investment')
        exp_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO expenses (
                id, user_id, name, category, amount_minor, currency,
                expense_date, origin, notes
            ) VALUES (?, ?, ?, 'Investimentos', ?, ?, ?, 'investment', ?)
        """, (
            exp_id,
            user_id,
            f"Investimento — {prod['name']}",
            amt_minor,
            prod["currency"],
            today.isoformat(),
            f"Aplicação no produto {prod['name']} ({prod['institution']})"
        ))

        return {
            "success": True,
            "investment_id": inv_id,
            "message": f"Investimento em '{prod['name']}' subscrito com sucesso!",
        }


@router.post("/portfolio/external")
def register_external_investment(data: ExternalInvestIn, user=Depends(get_current_user)):
    """Regista um investimento efetuado fora do Bankao (outro banco, corretora ou ativo físico)."""
    user_id = user["id"]
    with transaction_scope() as conn:
        inv_id = str(uuid.uuid4())
        amt_minor = _to_minor(data.amount)

        conn.execute("""
            INSERT INTO user_investments (
                id, user_id, product_id, name, category, institution, is_external,
                account_id, amount_invested_minor, current_value_minor,
                accumulated_yield_minor, currency, rate_annual, start_date,
                maturity_date, status, notes
            ) VALUES (?, ?, NULL, ?, ?, ?, 1, NULL, ?, ?, 0, ?, ?, ?, ?, 'ativo', ?)
        """, (
            inv_id,
            user_id,
            data.name.strip(),
            data.category,
            data.institution.strip(),
            amt_minor,
            amt_minor,
            data.currency.upper(),
            data.rate_annual or 0.0,
            data.start_date,
            data.maturity_date,
            data.notes or "",
        ))

        # Registar operação
        conn.execute("""
            INSERT INTO investment_operations (
                id, investment_id, user_id, operation_type, amount_minor,
                currency, operation_date, description
            ) VALUES (?, ?, ?, 'aplicacao_externa', ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            inv_id,
            user_id,
            amt_minor,
            data.currency.upper(),
            data.start_date,
            f"Registo de ativo externo em {data.institution} ({data.name})",
        ))

        # Notificação
        conn.execute("""
            INSERT INTO investment_notifications (
                id, user_id, investment_id, type, title, message
            ) VALUES (?, ?, ?, 'ativo_registado', ?, ?)
        """, (
            str(uuid.uuid4()),
            user_id,
            inv_id,
            "Ativo Externo Adicionado",
            f"'{data.name}' ({data.institution}) agora faz parte da sua carteira consolidada BankAO.",
        ))

        # Registar ativo nas Despesas do utilizador (categoria 'Investimentos', origin='investment')
        exp_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO expenses (
                id, user_id, name, category, amount_minor, currency,
                expense_date, origin, notes
            ) VALUES (?, ?, ?, 'Investimentos', ?, ?, ?, 'investment', ?)
        """, (
            exp_id,
            user_id,
            f"Investimento Externo — {data.name}",
            amt_minor,
            data.currency.upper(),
            data.start_date,
            f"Aplicação externa em {data.institution} ({data.name})"
        ))

        return {
            "success": True,
            "investment_id": inv_id,
            "message": "Investimento externo adicionado à sua carteira!",
        }


# =====================================================================
# 4. Resgate & Liquidação
# =====================================================================

@router.post("/portfolio/{investment_id}/redeem")
def redeem_investment(investment_id: str, data: RedeemIn, user=Depends(get_current_user)):
    """Efetua o resgate total ou parcial de um investimento com crédito em conta."""
    user_id = user["id"]
    with transaction_scope() as conn:
        inv = conn.execute("""
            SELECT * FROM user_investments WHERE id = ? AND user_id = ?
        """, (investment_id, user_id)).fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Investimento não encontrado.")
        if inv["status"] != "ativo":
            raise HTTPException(status_code=400, detail="Este investimento já foi resgatado ou expirou.")

        cur_val_minor = inv["current_value_minor"]
        req_minor = _to_minor(data.amount) if data.amount else cur_val_minor
        if req_minor <= 0 or req_minor > cur_val_minor:
            raise HTTPException(
                status_code=400,
                detail=f"Montante de resgate inválido. Disponível: {_to_decimal(cur_val_minor):,.2f} {inv['currency']}.",
            )

        is_total = (req_minor >= cur_val_minor)
        new_val_minor = 0 if is_total else (cur_val_minor - req_minor)
        new_status = "resgatado" if is_total else "ativo"

        # Se houver conta para creditar
        account_id = None if inv["is_external"] else (data.account_id or inv["account_id"])
        tx_id = None
        if account_id:
            acc = conn.execute(
                "SELECT id, currency, status FROM accounts WHERE id = ? AND user_id = ?",
                (account_id, user_id),
            ).fetchone()
            if acc and acc["status"] == "active" and acc["currency"] == inv["currency"]:
                idem = f"inv_redeem_{uuid.uuid4().hex[:12]}"
                res = post_investment_movement(
                    conn=conn,
                    account_id=account_id,
                    amount_minor=req_minor,
                    idempotency_key=idem,
                    description=f"Resgate de Investimento — {inv['name']}",
                    tx_type="investment_redeem",
                )
                tx_id = res["transaction_id"]

        today_str = datetime.date.today().isoformat()
        conn.execute("""
            UPDATE user_investments
            SET current_value_minor = ?,
                status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_val_minor, new_status, investment_id))

        # Registar operação
        conn.execute("""
            INSERT INTO investment_operations (
                id, investment_id, user_id, operation_type, amount_minor,
                currency, operation_date, description, transaction_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            investment_id,
            user_id,
            "resgate_total" if is_total else "resgate_parcial",
            req_minor,
            inv["currency"],
            today_str,
            f"Resgate {'total' if is_total else 'parcial'} de {inv['name']}",
            tx_id,
        ))

        # Notificação
        conn.execute("""
            INSERT INTO investment_notifications (
                id, user_id, investment_id, type, title, message
            ) VALUES (?, ?, ?, 'resgate_confirmado', ?, ?)
        """, (
            str(uuid.uuid4()),
            user_id,
            investment_id,
            "Resgate Confirmado",
            f"Resgate de {_to_decimal(req_minor):,.2f} {inv['currency']} concluído com sucesso.",
        ))

        return {
            "success": True,
            "is_total": is_total,
            "redeemed_amount": _to_decimal(req_minor),
            "remaining_value": _to_decimal(new_val_minor),
            "status": new_status,
            "message": f"Resgate de {_to_decimal(req_minor):,.2f} {inv['currency']} concluído!",
        }


# =====================================================================
# 5. Sincronização em Tempo Real via APIs Integradas
# =====================================================================

@router.post("/portfolio/{investment_id}/sync")
def sync_investment(investment_id: str, user=Depends(get_current_user)):
    """Atualiza cotações, juros e dividendos através do fornecedor integrado do ativo."""
    with transaction_scope() as conn:
        _settle_matured(conn, user["id"])
        cur = conn.execute(
            "SELECT status FROM user_investments WHERE id = ? AND user_id = ?", (investment_id, user["id"])
        ).fetchone()
        if cur and cur["status"] == "vencido":
            return {"success": True, "investment_id": investment_id, "matured": True,
                    "message": "O investimento venceu e foi liquidado."}
        return _sync_one(conn, investment_id, user["id"])


def _sync_one(conn, investment_id: str, user_id: str) -> dict:
    inv = conn.execute(
        "SELECT * FROM user_investments WHERE id = ? AND user_id = ?", (investment_id, user_id)
    ).fetchone()
    if not inv:
        raise HTTPException(status_code=404, detail="Investimento não encontrado.")
    if inv["status"] != "ativo":
        raise HTTPException(status_code=400, detail="Apenas investimentos ativos podem ser sincronizados.")

    provider_api = None
    if inv["product_id"]:
        p = conn.execute("SELECT provider_api FROM investment_products WHERE id = ?", (inv["product_id"],)).fetchone()
        provider_api = p["provider_api"] if p else None

    old_val = inv["current_value_minor"]
    upd = fetch_update(dict(inv), provider_api)
    new_val = upd.new_value_minor
    accrued = max(0, upd.accumulated_yield_minor)
    diff = new_val - old_val

    conn.execute(
        """UPDATE user_investments
           SET current_value_minor = ?, accumulated_yield_minor = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (new_val, accrued, investment_id),
    )

    if diff != 0:
        op_type = "ajuste_cotacao" if upd.event == "cotacao" else "juros_dividendo"
        conn.execute(
            """INSERT INTO investment_operations (id, investment_id, user_id, operation_type,
                   amount_minor, currency, operation_date, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), investment_id, user_id, op_type, abs(diff), inv["currency"],
             datetime.date.today().isoformat(), f"{upd.note} ({upd.source})" + (" — descida" if diff < 0 else "")),
        )
        if upd.event in ("juros", "dividendo") and diff > 0:
            _notify(conn, user_id, investment_id, "rendimento_creditado", "Rendimento atualizado",
                    f"{inv['name']}: +{_to_decimal(diff):,.2f} {inv['currency']} em rendimentos ({upd.source}).")
        elif upd.event == "cotacao" and abs(diff) >= inv["current_value_minor"] * 0.01:
            _notify(conn, user_id, investment_id, "atualizacao_mercado", "Variação de cotação",
                    f"{inv['name']} {'valorizou' if diff > 0 else 'desvalorizou'} "
                    f"{abs(diff) / max(1, old_val) * 100:.1f}% ({upd.source}).")

    return {
        "success": True,
        "investment_id": investment_id,
        "source": upd.source,
        "old_value": _to_decimal(old_val),
        "new_value": _to_decimal(new_val),
        "accumulated_yield": _to_decimal(accrued),
        "updated_at": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


def _notify(conn, user_id: str, investment_id: Optional[str], ntype: str, title: str, message: str) -> None:
    conn.execute(
        """INSERT INTO investment_notifications (id, user_id, investment_id, type, title, message)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), user_id, investment_id, ntype, title, message),
    )


def _settle_matured(conn, user_id: str) -> int:
    """Liquida investimentos vencidos (data de vencimento <= hoje).

    Fixa os juros até à data de vencimento, credita a conta BankAO (internos), passa o ativo a
    `vencido`, regista a operação e notifica. Idempotente: só atua sobre `ativo` e o movimento
    no livro-razão usa chave idempotente por investimento. Internos sem conta creditável
    ficam `ativo` (resgate manual com outra conta) em vez de perder o valor.
    """
    today = datetime.date.today()
    rows = conn.execute(
        """SELECT * FROM user_investments
           WHERE user_id = ? AND status = 'ativo' AND maturity_date IS NOT NULL AND maturity_date <= ?""",
        (user_id, today.isoformat()),
    ).fetchall()
    settled = 0
    for inv in rows:
        final_minor = settlement_value(dict(inv))
        tx_id = None
        credited = False
        if not inv["is_external"]:
            acc = None
            if inv["account_id"]:
                acc = conn.execute(
                    "SELECT id, currency, status FROM accounts WHERE id = ? AND user_id = ?",
                    (inv["account_id"], user_id),
                ).fetchone()
            if not acc or acc["status"] != "active" or acc["currency"] != inv["currency"]:
                continue
            res = post_investment_movement(
                conn=conn,
                account_id=acc["id"],
                amount_minor=final_minor,
                idempotency_key=f"inv_mature_{inv['id']}",
                description=f"Vencimento de Investimento — {inv['name']}",
                tx_type="investment_redeem",
            )
            tx_id = res["transaction_id"]
            credited = True

        yield_minor = max(0, final_minor - inv["amount_invested_minor"])
        conn.execute(
            """UPDATE user_investments
               SET current_value_minor = ?, accumulated_yield_minor = ?, status = 'vencido',
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (final_minor, yield_minor, inv["id"]),
        )
        conn.execute(
            """INSERT INTO investment_operations (id, investment_id, user_id, operation_type,
                   amount_minor, currency, operation_date, description, transaction_id)
               VALUES (?, ?, ?, 'vencimento', ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), inv["id"], user_id, final_minor, inv["currency"], inv["maturity_date"],
             f"Vencimento de {inv['name']}" + (" — creditado em conta" if credited else " — registo externo"),
             tx_id),
        )
        amt = f"{_to_decimal(final_minor):,.2f} {inv['currency']}"
        _notify(conn, user_id, inv["id"], "vencimento_liquidado", "Investimento vencido",
                f"{inv['name']} venceu a {inv['maturity_date']}. "
                + (f"{amt} (capital + juros) creditados na sua conta."
                   if credited else f"Valor final: {amt}. Registo externo: o crédito é feito na instituição."))
        settled += 1
    return settled


def _generate_maturity_alerts(conn, user_id: str) -> None:
    """Cria alertas de vencimento (30/15/7/1 dias) uma única vez por ativo e janela."""
    today = datetime.date.today()
    rows = conn.execute(
        """SELECT id, name, maturity_date, current_value_minor, currency FROM user_investments
           WHERE user_id = ? AND status = 'ativo' AND maturity_date IS NOT NULL""", (user_id,)
    ).fetchall()
    for r in rows:
        try:
            left = (datetime.date.fromisoformat(r["maturity_date"]) - today).days
        except Exception:
            continue
        if left < 0 or left > 30:
            continue
        window = 1 if left <= 1 else 7 if left <= 7 else 15 if left <= 15 else 30
        title = f"Vencimento em {window} dia{'s' if window > 1 else ''}" if window > 1 else "Vence amanhã ou hoje"
        exists = conn.execute(
            """SELECT 1 FROM investment_notifications
               WHERE user_id = ? AND investment_id = ? AND type = 'vencimento_proximo' AND title = ?""",
            (user_id, r["id"], title),
        ).fetchone()
        if exists:
            continue
        _notify(conn, user_id, r["id"], "vencimento_proximo", title,
                f"{r['name']} vence a {r['maturity_date']} (faltam {left} dia{'s' if left != 1 else ''}). "
                f"Valor atual: {_to_decimal(r['current_value_minor']):,.2f} {r['currency']}.")


@router.post("/portfolio/sync-all")
def sync_all_investments(user=Depends(get_current_user)):
    """Atualiza em lote todos os investimentos ativos junto dos fornecedores."""
    ok, failed = 0, 0
    with transaction_scope() as conn:
        matured = _settle_matured(conn, user["id"])
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM user_investments WHERE user_id = ? AND status = 'ativo'", (user["id"],)
        ).fetchall()]
        for iid in ids:
            try:
                _sync_one(conn, iid, user["id"])
                ok += 1
            except Exception:
                failed += 1
        _generate_maturity_alerts(conn, user["id"])
    msg = f"{ok} ativo{'s' if ok != 1 else ''} sincronizado{'s' if ok != 1 else ''} com os fornecedores."
    if matured:
        msg += f" {matured} vencido{'s' if matured != 1 else ''} e liquidado{'s' if matured != 1 else ''}."
    if failed:
        msg += f" {failed} falharam."
    return {"success": True, "synced_count": ok, "failed_count": failed, "matured_count": matured, "message": msg}


# =====================================================================
# 6. Histórico de Operações & Notificações
# =====================================================================

@router.get("/operations")
def get_operations(
    investment_id: Optional[str] = None,
    op_type: Optional[str] = None,
    limit: int = 100,
    user=Depends(get_current_user),
):
    """Retorna o histórico completo de movimentações de investimento."""
    user_id = user["id"]
    with get_connection() as conn:
        q = """
            SELECT o.*, i.name as investment_name, i.institution
            FROM investment_operations o
            JOIN user_investments i ON o.investment_id = i.id
            WHERE o.user_id = ?
        """
        params: List[Any] = [user_id]
        if investment_id:
            q += " AND o.investment_id = ?"
            params.append(investment_id)
        if op_type:
            q += " AND o.operation_type = ?"
            params.append(op_type)

        q += " ORDER BY o.operation_date DESC, o.created_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 1000)))
        rows = conn.execute(q, params).fetchall()

        TYPE_LABELS = {
            "aplicacao": "Aplicação / Compra",
            "aplicacao_externa": "Registo Externo",
            "reforco": "Reforço",
            "vencimento": "Vencimento",
            "resgate_total": "Resgate Total",
            "resgate_parcial": "Resgate Parcial",
            "juros_dividendo": "Crédito de Rendimentos",
            "ajuste_cotacao": "Atualização de Cotação",
        }

        return [
            {
                "id": r["id"],
                "investment_id": r["investment_id"],
                "investment_name": r["investment_name"],
                "institution": r["institution"],
                "operation_type": r["operation_type"],
                "type_label": TYPE_LABELS.get(r["operation_type"], r["operation_type"].title()),
                "amount": _to_decimal(r["amount_minor"]),
                "amount_minor": r["amount_minor"],
                "currency": r["currency"],
                "operation_date": r["operation_date"],
                "description": r["description"],
                "transaction_id": r["transaction_id"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]


@router.get("/notifications")
def get_notifications(user=Depends(get_current_user)):
    """Retorna alertas de vencimento próximo, rendimentos e atualizações de mercado."""
    user_id = user["id"]
    with transaction_scope() as _c:
        _settle_matured(_c, user_id)
        _generate_maturity_alerts(_c, user_id)
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT n.*, i.name as investment_name, i.maturity_date
            FROM investment_notifications n
            LEFT JOIN user_investments i ON n.investment_id = i.id
            WHERE n.user_id = ?
            ORDER BY n.created_at DESC LIMIT 30
        """, (user_id,)).fetchall()

        return [
            {
                "id": r["id"],
                "investment_id": r["investment_id"],
                "investment_name": r["investment_name"],
                "type": r["type"],
                "title": r["title"],
                "message": r["message"],
                "is_read": bool(r["is_read"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str, user=Depends(get_current_user)):
    """Marca uma notificação como lida."""
    user_id = user["id"]
    with transaction_scope() as conn:
        conn.execute("""
            UPDATE investment_notifications
            SET is_read = 1
            WHERE id = ? AND user_id = ?
        """, (notification_id, user_id))
    return {"success": True}

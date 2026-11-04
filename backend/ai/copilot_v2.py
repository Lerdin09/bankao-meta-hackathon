"""
Copilot v2 — Sistema avançado de IA financeira com contexto real do utilizador,
memória persistente, auto-registo de operações, análise de hábitos e geração de
dados de gráficos inline (donut, linha, barra).
"""
import datetime
import json
import re
import uuid
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from backend.database import get_connection

logger = logging.getLogger("bankao.copilot_v2")

# ─── Constantes de Categorias ─────────────────────────────────────────────────

CATEGORY_EMOJIS = {
    "Alimentação": "🛒", "Restaurantes": "🍽️", "Supermercado": "🛒",
    "Transporte": "🚖", "Combustível": "⛽", "Saúde": "💊",
    "Educação": "🎓", "Vestuário": "👗", "Eletrónica": "💻", "Eletrónicos": "💻",
    "Lazer": "🎬", "Viagens": "✈️", "Telecomunicações": "📱",
    "Serviços": "⚙️", "Poupança": "🏦", "Investimento": "📈",
    "Habitação": "🏠", "Outros": "💳",
}

MONTHS_PT = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]

MERCHANT_TO_EXPENSE_CAT = {
    "supermercado": "Alimentação",
    "restauracao": "Alimentação",
    "restaurante": "Alimentação",
    "alimentacao": "Alimentação",
    "combustivel": "Transporte",
    "transportes": "Transporte",
    "transporte": "Transporte",
    "viagens": "Transporte",
    "habitacao": "Habitação",
    "servicos": "Habitação",
    "telecomunicacoes": "Telecomunicações",
    "saude": "Saúde",
    "lazer": "Lazer",
    "poupanca": "Poupança",
    "investimento": "Investimento",
    "outros": "Outros",
}


def find_unrecorded_expenses(user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Deteta pagamentos com cartão ou transferências a débito que ainda
    não foram anotados na tabela de despesas (expenses).
    """
    conn = get_connection()
    unrecorded = []
    try:
        # 1. Movimentos de cartão
        card_mvts = conn.execute("""
            SELECT id, amount_minor, currency, merchant_name, merchant_category, operation_type, created_at
            FROM card_movements
            WHERE user_id = ? AND is_debit = 1 AND status = 'completed'
            ORDER BY created_at DESC LIMIT 25
        """, (user_id,)).fetchall()

        for cm in card_mvts:
            amt = round(cm["amount_minor"] / 100.0, 2)
            c_date = cm["created_at"][:10]
            exists = conn.execute("""
                SELECT 1 FROM expenses
                WHERE user_id = ? AND ABS(amount_minor - ?) < 100
                  AND (expense_date = ? OR expense_date = date(?, '+1 day') OR expense_date = date(?, '-1 day'))
            """, (user_id, cm["amount_minor"], c_date, c_date, c_date)).fetchone()

            if not exists:
                cat = MERCHANT_TO_EXPENSE_CAT.get((cm["merchant_category"] or "").lower(), "Outros")
                merchant = cm["merchant_name"] or "Pagamento TPA / Cartão"
                unrecorded.append({
                    "id": cm["id"],
                    "source": "card",
                    "amount": amt,
                    "currency": cm["currency"],
                    "date": c_date,
                    "merchant": merchant,
                    "suggested_category": cat,
                    "description": f"{cm['operation_type'].capitalize()} em {merchant}"
                })
                if len(unrecorded) >= limit:
                    break

        # 2. Transferências enviadas para terceiros / IBAN
        if len(unrecorded) < limit:
            transfers = conn.execute("""
                SELECT t.id, t.source_amount_minor, t.source_currency, t.beneficiary_name, t.to_iban, t.created_at
                FROM transfers t
                JOIN accounts a ON a.id = t.from_account_id
                WHERE a.user_id = ? AND t.status = 'completed'
                ORDER BY t.created_at DESC LIMIT 20
            """, (user_id,)).fetchall()

            for tf in transfers:
                amt = round(tf["source_amount_minor"] / 100.0, 2)
                t_date = tf["created_at"][:10]
                exists = conn.execute("""
                    SELECT 1 FROM expenses
                    WHERE user_id = ? AND ABS(amount_minor - ?) < 100
                      AND (expense_date = ? OR expense_date = date(?, '+1 day') OR expense_date = date(?, '-1 day'))
                """, (user_id, tf["source_amount_minor"], t_date, t_date, t_date)).fetchone()

                if not exists:
                    beneficiary = tf["beneficiary_name"] or (f"IBAN {tf['to_iban'][:4]}...{tf['to_iban'][-4:]}" if tf["to_iban"] else "Transferência enviada")
                    unrecorded.append({
                        "id": tf["id"],
                        "source": "transfer",
                        "amount": amt,
                        "currency": tf["source_currency"],
                        "date": t_date,
                        "merchant": beneficiary,
                        "suggested_category": "Outros",
                        "description": f"Transferência para {beneficiary}"
                    })
                    if len(unrecorded) >= limit:
                        break
    except Exception as e:
        logger.warning(f"Erro ao procurar despesas não registadas: {e}")
    finally:
        conn.close()

    return unrecorded


def format_unrecorded_alert(unrecorded: List[Dict[str, Any]]) -> str:
    """Gera o texto cordial e proativo perguntando ao cliente se quer registar a compra."""
    if not unrecorded:
        return ""
    if len(unrecorded) == 1:
        u = unrecorded[0]
        return (
            f"🛍️ **Compra por registar:**\n"
            f"Identifiquei um débito de **{u['amount']:,.2f} {u['currency']}** em **{u['merchant']}** ({u['date']}) "
            f"que ainda não consta nas suas Despesas.\n"
            f"Deseja que eu anote como despesa de **{u['suggested_category']}** para manter o seu balanço contabilístico exato?"
        )
    lines = [f"🛍️ **Encontrei {len(unrecorded)} operações recentes por registar nas suas Despesas:**"]
    for u in unrecorded:
        lines.append(f"• **{u['merchant']}** ({u['date']}): **{u['amount']:,.2f} {u['currency']}** → Sugestão: *{u['suggested_category']}*")
    lines.append("\nDiga-me qual deseja que eu anote (ou responda «anotar todas») para manter o seu controlo 100% atualizado! 📝")
    return "\n".join(lines)


def analyze_spending_habits(user_id: str) -> Dict[str, Any]:
    """Analisa hábitos de compra, saúde financeira e desvios de consumo."""
    conn = get_connection()
    try:
        today = datetime.date.today()
        month_start = today.replace(day=1).isoformat()
        prev_month_end = (today.replace(day=1) - datetime.timedelta(days=1))
        prev_month_start = prev_month_end.replace(day=1).isoformat()

        curr_res = conn.execute(
            "SELECT COALESCE(SUM(amount_minor), 0), COUNT(*) FROM expenses WHERE user_id=? AND expense_date >= ?",
            (user_id, month_start)
        ).fetchone()
        curr_total = round(float(curr_res[0]) / 100.0, 2)
        curr_count = int(curr_res[1])

        prev_total_minor = conn.execute(
            "SELECT COALESCE(SUM(amount_minor), 0) FROM expenses WHERE user_id=? AND expense_date >= ? AND expense_date <= ?",
            (user_id, prev_month_start, prev_month_end.isoformat())
        ).fetchone()[0]
        prev_total = round(float(prev_total_minor) / 100.0, 2)

        cats = conn.execute("""
            SELECT category, SUM(amount_minor) as total_minor, COUNT(*) as qty
            FROM expenses WHERE user_id=? AND expense_date >= ?
            GROUP BY category ORDER BY total_minor DESC
        """, (user_id, month_start)).fetchall()

        top_categories = [
            {
                "category": r["category"],
                "total": round(float(r["total_minor"]) / 100.0, 2),
                "count": r["qty"],
                "pct": round(((float(r["total_minor"]) / 100.0) / curr_total * 100), 1) if curr_total > 0 else 0,
                "emoji": CATEGORY_EMOJIS.get(r["category"], "💳")
            }
            for r in cats
        ]

        unrecorded = find_unrecorded_expenses(user_id)
        var_pct = round(((curr_total - prev_total) / prev_total) * 100, 1) if prev_total > 0 else 0.0
        daily_avg = round(curr_total / max(1, today.day), 2)

        return {
            "current_month_total": curr_total,
            "current_month_count": curr_count,
            "previous_month_total": prev_total,
            "variation_pct": var_pct,
            "daily_average": daily_avg,
            "top_categories": top_categories,
            "unrecorded": unrecorded
        }
    except Exception as e:
        logger.error(f"Erro ao analisar hábitos: {e}")
        return {}
    finally:
        conn.close()


def format_spending_habits_response(habits: Dict[str, Any]) -> str:
    """Formata a análise de hábitos de compras como um experte contabilístico."""
    if not habits:
        return "Ainda não tenho dados suficientes de despesas para analisar os seus hábitos de compras. Registe as suas despesas para começar!"

    curr_total = habits.get("current_month_total", 0)
    prev_total = habits.get("previous_month_total", 0)
    var = habits.get("variation_pct", 0)
    daily = habits.get("daily_average", 0)
    top = habits.get("top_categories", [])
    unrecorded = habits.get("unrecorded", [])

    lines = ["📊 **Análise Contabilística dos seus Hábitos de Compra**\n"]
    lines.append(f"• **Despesas este mês:** **{curr_total:,.2f} Kz** (Média: **{daily:,.2f} Kz/dia**)")
    if prev_total > 0:
        sinal = "+" if var > 0 else ""
        emoji = "📈" if var > 0 else "📉"
        lines.append(f"• **Comparação com mês anterior:** {emoji} **{sinal}{var}%** vs mês passado ({prev_total:,.2f} Kz)")

    if top:
        lines.append("\n**Fatias do seu orçamento:**")
        for c in top[:3]:
            lines.append(f"  {c['emoji']} **{c['category']}:** {c['total']:,.2f} Kz ({c['pct']}%) · {c['count']} compras")

    # Dica contábil personalizada
    if top:
        biggest = top[0]
        if biggest["category"] in ("Alimentação", "Restaurantes") and biggest["pct"] > 40:
            lines.append(f"\n💡 *Conselho Contábil:* A categoria **{biggest['category']}** consome {biggest['pct']}% do seu orçamento. Estabelecer um teto semanal para refeições fora pode poupar até 15% do seu rendimento.")
        elif biggest["category"] == "Transporte" and biggest["pct"] > 25:
            lines.append(f"\n💡 *Conselho Contábil:* O gasto em **Transporte** está acima da média recomendada (25%). Agrupar deslocações e avaliar rotas pode gerar poupança direta.")

    if unrecorded:
        lines.append("\n" + format_unrecorded_alert(unrecorded[:2]))

    return "\n".join(lines)


def explain_balance_forecast(forecast_data: Optional[Dict[str, Any]] = None, current_balance: float = 0.0) -> str:
    """Explicação didática e contábil de como funciona a previsão de saldo futuro."""
    bal_str = f"**{current_balance:,.2f} Kz**" if current_balance > 0 else "o seu saldo atual"
    return (
        "🔮 **Como Funciona a Previsão de Saldo BankAO (Projeção Contabilística):**\n\n"
        "A previsão utiliza um modelo de **Demonstração de Fluxo de Caixa Projetado (DCF Pessoal)** "
        "com base em 4 pilares rigorosos:\n\n"
        f"1. **Ponto de Partida:** Começamos com {bal_str} nas suas contas ativas.\n"
        "2. **Entradas Médias Reais (+):** Apuramos os seus depósitos, salários e transferências recebidas nos últimos 90 dias.\n"
        "3. **Despesas Operacionais (-):** Calculamos a média ponderada das suas despesas (custos essenciais e estilo de vida).\n"
        "4. **Compromissos de Poupança (-):** Deduzimos os débitos programados das suas metas de poupança (que se tornam património acumulado).\n"
        "5. **Rendimentos de Investimentos (+):** Somamos juros contratuais de Depósitos a Prazo (até 18,5% a.a.) e títulos BODIVA.\n\n"
        "📈 *Para quê serve?* Permite antecipar meses com risco de aperto financeiro e saber com exatidão quando atingirá a sua liberdade económica!"
    )


# ─── Contexto financeiro real do utilizador ───────────────────────────────────

def build_user_context(user_id: str) -> Dict[str, Any]:
    """Constrói um contexto financeiro rico a partir da BD para alimentar a IA."""
    conn = get_connection()
    ctx: Dict[str, Any] = {}

    try:
        # Utilizador (Nome e Identificação)
        user_row = conn.execute(
            "SELECT id, nome, primeiro_nome, ultimo_nome, email FROM users WHERE id=?",
            (user_id,)
        ).fetchone()
        u_name = "Cliente BankAO"
        if user_row:
            u_name = (user_row["nome"] or "").strip()
            if not u_name or u_name == "Novo Utilizador":
                u_name = f"{user_row['primeiro_nome'] or ''} {user_row['ultimo_nome'] or ''}".strip()
            u_name = u_name or "Cliente BankAO"
        ctx["user_name"] = u_name

        # Saldos
        accounts = conn.execute(
            "SELECT a.id, a.currency, COALESCE(SUM(le.amount_minor),0) as balance_minor "
            "FROM accounts a LEFT JOIN ledger_entries le ON le.account_id = a.id "
            "WHERE a.user_id = ? GROUP BY a.id, a.currency",
            (user_id,)
        ).fetchall()
        ctx["accounts"] = [
            {"currency": r["currency"], "balance": round(r["balance_minor"] / 100, 2)}
            for r in accounts
        ]
        ctx["total_aoa"] = sum(
            r["balance"] for r in ctx["accounts"] if r["currency"] == "AOA"
        )

        # Últimas 30 despesas
        expenses = conn.execute("""
            SELECT name, amount_minor, currency, category, expense_date as date
            FROM expenses WHERE user_id = ?
            ORDER BY expense_date DESC LIMIT 30
        """, (user_id,)).fetchall()
        ctx["recent_expenses"] = [
            {"name": r["name"], "amount": round(r["amount_minor"] / 100, 2),
             "category": r["category"], "date": r["date"]}
            for r in expenses
        ]

        # Total mensal de despesas (mês corrente)
        month_start = datetime.date.today().replace(day=1).isoformat()
        monthly_total = conn.execute(
            "SELECT COALESCE(SUM(amount_minor),0) FROM expenses WHERE user_id=? AND expense_date >= ?",
            (user_id, month_start)
        ).fetchone()[0]
        ctx["monthly_expenses"] = round(float(monthly_total) / 100, 2)

        # Top categorias (últimos 3 meses)
        three_months_ago = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()
        top_cats = conn.execute("""
            SELECT category, SUM(amount_minor) as total
            FROM expenses WHERE user_id=? AND expense_date >= ?
            GROUP BY category ORDER BY total DESC LIMIT 5
        """, (user_id, three_months_ago)).fetchall()
        ctx["top_categories"] = [
            {"category": r["category"], "total": round(float(r["total"]) / 100, 2)}
            for r in top_cats
        ]

        # Metas de poupança ativas
        goals = conn.execute(
            "SELECT name, target_minor, saved_minor, deadline FROM savings_goals "
            "WHERE user_id=? AND status != 'completed' LIMIT 5",
            (user_id,)
        ).fetchall()
        ctx["savings_goals"] = [
            {"name": r["name"],
             "target": round(float(r["target_minor"]) / 100, 2),
             "saved": round(float(r["saved_minor"]) / 100, 2),
             "deadline": r["deadline"]}
            for r in goals
        ]

        # Investimentos ativos
        investments = conn.execute(
            "SELECT name, current_value_minor, rate_annual, status FROM user_investments "
            "WHERE user_id=? AND status='ativo' LIMIT 5",
            (user_id,)
        ).fetchall()
        ctx["investments"] = [
            {"name": r["name"],
             "value": round(float(r["current_value_minor"]) / 100, 2),
             "rate": r["rate_annual"]}
            for r in investments
        ]

        # Memória permanente (preferências, salário declarado, nome, interesses)
        memory = conn.execute(
            "SELECT memory_key, memory_value, updated_at FROM copilot_memory "
            "WHERE user_id=? ORDER BY updated_at DESC LIMIT 50",
            (user_id,)
        ).fetchall()
        ctx["memory"] = {r["memory_key"]: r["memory_value"] for r in memory}
        if ctx["memory"].get("nome_preferido"):
            ctx["user_name"] = ctx["memory"]["nome_preferido"]

        # Compras não registadas
        ctx["unrecorded_expenses"] = find_unrecorded_expenses(user_id, limit=5)

    except Exception as e:
        logger.warning(f"Erro ao construir contexto: {e}")
    finally:
        conn.close()

    return ctx


def build_context_summary(ctx: Dict[str, Any]) -> str:
    """Resume o contexto em texto para injetar no system prompt."""
    lines = []

    # Saldo
    for acc in ctx.get("accounts", []):
        bal = acc["balance"]
        cur = acc["currency"]
        lines.append(f"• Saldo {cur}: {bal:,.2f}")

    # Despesas do mês
    monthly = ctx.get("monthly_expenses", 0)
    if monthly:
        lines.append(f"• Despesas este mês: {monthly:,.2f} AOA")

    # Top categorias
    top = ctx.get("top_categories", [])
    if top:
        cats_str = ", ".join(f"{c['category']} ({c['total']:,.0f} Kz)" for c in top[:3])
        lines.append(f"• Maiores gastos (3 meses): {cats_str}")

    # Metas
    goals = ctx.get("savings_goals", [])
    if goals:
        g = goals[0]
        pct = int((g["saved"] / g["target"]) * 100) if g["target"] else 0
        lines.append(f"• Meta principal: {g['name']} — {pct}% concluída")

    # Memória
    memory = ctx.get("memory", {})
    if memory:
        mem_lines = [f"{k}: {v}" for k, v in list(memory.items())[:5]]
        lines.append("• Contexto anterior: " + "; ".join(mem_lines))

    # Compras não registadas
    unrec = ctx.get("unrecorded_expenses", [])
    if unrec:
        unrec_txt = ", ".join(f"{u['merchant']} ({u['amount']:,.0f} Kz)" for u in unrec[:2])
        lines.append(f"• Compras pendentes por registar em despesas: {len(unrec)} ({unrec_txt})")

    return "\n".join(lines) if lines else "Sem dados financeiros disponíveis."


# ─── Geração de dados de gráficos ─────────────────────────────────────────────

def get_chart_data(user_id: str, chart_type: str, params: Dict) -> Optional[Dict]:
    """Gera dados estruturados para gráficos inline na conversa."""
    conn = get_connection()
    try:
        if chart_type == "donut_expenses_month":
            month = params.get("month")  # "2026-08" ou None = mês atual
            if not month:
                month = datetime.date.today().strftime("%Y-%m")
            rows = conn.execute("""
                SELECT category, SUM(amount_minor) as total_minor
                FROM expenses WHERE user_id=? AND expense_date LIKE ?
                GROUP BY category ORDER BY total_minor DESC
            """, (user_id, f"{month}%")).fetchall()

            if not rows:
                return None
            total_minor = sum(r["total_minor"] for r in rows)
            if total_minor <= 0:
                return None
            total = total_minor / 100.0
            month_idx = int(month.split("-")[1]) - 1
            month_label = f"{MONTHS_PT[month_idx]} {month.split('-')[0]}"
            return {
                "type": "donut",
                "title": f"Despesas — {month_label}",
                "total": round(float(total), 2),
                "segments": [
                    {
                        "label": r["category"],
                        "value": round(float(r["total_minor"]) / 100.0, 2),
                        "pct": round((r["total_minor"] / total_minor) * 100, 1),
                        "emoji": CATEGORY_EMOJIS.get(r["category"], "💳"),
                    }
                    for r in rows
                ]
            }

        elif chart_type == "line_expenses_months":
            n_months = int(params.get("months", 4))
            today = datetime.date.today()
            result = []
            for i in range(n_months - 1, -1, -1):
                month_num = ((today.month - 1 - i) % 12) + 1
                year_num = today.year - ((today.month - 1 - i) < 0)
                month_str = f"{year_num}-{month_num:02d}"
                total_minor = conn.execute(
                    "SELECT COALESCE(SUM(amount_minor),0) FROM expenses WHERE user_id=? AND expense_date LIKE ?",
                    (user_id, f"{month_str}%")
                ).fetchone()[0]
                result.append({
                    "label": MONTHS_PT[month_num - 1],
                    "month": month_str,
                    "value": round(float(total_minor) / 100.0, 2)
                })
            return {
                "type": "line",
                "title": f"Evolução de Despesas — {n_months} meses",
                "points": result
            }

        elif chart_type == "bar_categories_period":
            n_months = int(params.get("months", 3))
            start = (datetime.date.today() - datetime.timedelta(days=30 * n_months)).isoformat()
            rows = conn.execute("""
                SELECT category, SUM(amount_minor) as total_minor
                FROM expenses WHERE user_id=? AND expense_date >= ?
                GROUP BY category ORDER BY total_minor DESC LIMIT 8
            """, (user_id, start)).fetchall()
            if not rows:
                return None
            max_val = max(r["total_minor"] for r in rows)
            return {
                "type": "bar",
                "title": f"Categorias — últimos {n_months} meses",
                "bars": [
                    {
                        "label": r["category"],
                        "value": round(float(r["total_minor"]) / 100.0, 2),
                        "pct": round((r["total_minor"] / max_val) * 100, 1) if max_val > 0 else 0,
                        "emoji": CATEGORY_EMOJIS.get(r["category"], "💳"),
                    }
                    for r in rows
                ]
            }

        elif chart_type == "balance_forecast":
            # Previsão de saldo com base em hábitos reais
            conn2 = get_connection()
            # Média de entradas mensais (últimas transações positivas)
            avg_in = conn2.execute("""
                SELECT COALESCE(AVG(monthly_total),0) FROM (
                    SELECT strftime('%Y-%m', le.created_at) as m, SUM(le.amount_minor) as monthly_total
                    FROM ledger_entries le
                    JOIN accounts a ON a.id = le.account_id AND a.user_id = ?
                    WHERE le.amount_minor > 0
                    GROUP BY m ORDER BY m DESC LIMIT 3
                )
            """, (user_id,)).fetchone()[0]
            # Média de saídas mensais (despesas registadas)
            avg_out = conn2.execute("""
                SELECT COALESCE(AVG(monthly_total),0) FROM (
                    SELECT strftime('%Y-%m', expense_date) as m, SUM(amount_minor) as monthly_total
                    FROM expenses WHERE user_id=?
                    GROUP BY m ORDER BY m DESC LIMIT 3
                )
            """, (user_id,)).fetchone()[0]
            conn2.close()

            current_balance = sum(
                acc["balance"] * 100
                for acc in (build_user_context(user_id).get("accounts", []))
                if acc["currency"] == "AOA"
            )

            points = []
            balance = float(current_balance)
            today = datetime.date.today()
            net_change = float(avg_in) - float(avg_out)
            for i in range(6):
                month_num = ((today.month - 1 + i) % 12) + 1
                label = MONTHS_PT[month_num - 1]
                balance += net_change
                points.append({"label": label, "value": round(balance / 100, 2)})

            return {
                "type": "forecast",
                "title": "Previsão de Saldo (6 meses)",
                "current": round(float(current_balance) / 100, 2),
                "points": points,
                "note": "Estimativa baseada no seu saldo e hábitos dos últimos 3 meses"
            }

    except Exception as e:
        logger.error(f"Erro ao gerar chart_data ({chart_type}): {e}")
    finally:
        conn.close()

    return None


# ─── Recomendação personalizada de investimento ──────────────────────────────

def build_personalized_investment_recommendation(user_id: str, inline_salary: Optional[float] = None) -> str:
    """
    Gera uma recomendação personalizada de investimento com base na memória do
    utilizador (salário, perfil de risco, metas de vida) e no catálogo BankAO.
    Nunca retorna uma saudação genérica — começa sempre com dados concretos.
    """
    conn = get_connection()
    memory: Dict[str, str] = {}
    try:
        rows = conn.execute(
            "SELECT memory_key, memory_value FROM copilot_memory WHERE user_id=?",
            (user_id,)
        ).fetchall()
        memory = {r["memory_key"]: r["memory_value"] for r in rows}
    except Exception:
        pass
    finally:
        conn.close()

    # Salário: inline (declarado na mesma mensagem) > memória persistente
    salary: Optional[float] = inline_salary
    if salary is None and memory.get("rendimento_mensal_numerico"):
        try:
            salary = float(memory["rendimento_mensal_numerico"])
        except Exception:
            pass

    salary_label = f"{salary:,.0f} Kz/mês" if salary else None
    risk_profile = memory.get("perfil_risco", "")

    # Determinar postura de risco
    if "conserv" in risk_profile.lower():
        risk = "conservador"
    elif "arrojado" in risk_profile.lower() or "agressivo" in risk_profile.lower():
        risk = "arrojado"
    else:
        risk = "moderado"  # padrão equilibrado

    # Metas de vida detectadas na memória
    has_car = bool(memory.get("interesse_carro"))
    has_house = bool(memory.get("interesse_casa"))
    has_travel = bool(memory.get("interesse_viagem"))
    has_studies = bool(memory.get("interesse_estudos"))
    has_reserve = bool(memory.get("interesse_reserva"))

    lines = []

    # Cabeçalho personalizado
    if salary_label:
        lines.append(f"💡 **Recomendação Personalizada de Investimento BankAO** para um rendimento de **{salary_label}:**\n")
    else:
        lines.append("💡 **Recomendação de Investimento BankAO (perfil equilibrado):**\n")

    # Calcular montantes sugeridos (regra 20% para investimento)
    if salary:
        invest_20pct = salary * 0.20
        reserve_10pct = salary * 0.10
        invest_label_20 = f"{invest_20pct:,.0f} Kz"
        reserve_label_10 = f"{reserve_10pct:,.0f} Kz"
    else:
        invest_20pct = None
        invest_label_20 = "20% do seu salário"
        reserve_label_10 = "10% do seu salário"

    # Produto 1: Depósito a Prazo (recomendado para todos os perfis)
    lines.append("**1. 🏦 Depósito a Prazo BankAO (18,5% a.a. — Capital 100% Garantido):**")
    lines.append(f"   • Aplique **{invest_label_20}** todos os meses e veja o seu dinheiro crescer com segurança total.")
    if invest_20pct:
        # Projeção simples a 12 meses com juro composto mensal
        monthly_rate = 0.185 / 12
        balance = 0.0
        for _ in range(12):
            balance = (balance + invest_20pct) * (1 + monthly_rate)
        interest = balance - (invest_20pct * 12)
        lines.append(f"   • Projeção a 12 meses: **{balance:,.0f} Kz** acumulados (juros: **+{interest:,.0f} Kz**).")
    lines.append("")

    # Produto 2: BODIVA (para moderado e arrojado)
    if risk in ("moderado", "arrojado"):
        lines.append("**2. 🏛️ Obrigações do Tesouro na BODIVA (17,2% a.a. — Cupão Semestral):**")
        lines.append("   • Títulos soberanos do Estado Angolano com pagamentos de juros a cada 6 meses.")
        lines.append("   • Liquidez no mercado secundário caso precise do dinheiro antes do vencimento.\n")

    # Produto 3: ETF (só para arrojado)
    if risk == "arrojado":
        lines.append("**3. 📊 ETF Global em Dólares (S&P 500 / All-World — Proteção Cambial):**")
        lines.append("   • Diversificação internacional em USD, ideal para proteger o seu poder de compra a longo prazo.\n")

    # Sugestão de alocação
    if salary:
        lines.append(f"**📐 Alocação Sugerida para {salary_label} (Regra 50/30/20):**")
        essential = salary * 0.50
        lifestyle = salary * 0.30
        lines.append(f"• {essential:,.0f} Kz → Necessidades essenciais (renda, alimentação, transporte)")
        lines.append(f"• {lifestyle:,.0f} Kz → Estilo de vida (lazer, restaurantes, compras pessoais)")
        lines.append(f"• **{invest_20pct:,.0f} Kz → Investimento e poupança** (Depósito a Prazo + reserva de emergência)")
        lines.append("")

    # Metas de vida
    goal_lines = []
    if has_car:
        goal_lines.append("🚗 *Viatura:* Crie uma meta de poupança BankAO com contribuição mensal automática.")
    if has_house:
        goal_lines.append("🏠 *Casa Própria:* Combine Depósito a Prazo (1-2 anos) com Obrigações do Tesouro para acumular o fundo de entrada.")
    if has_travel:
        goal_lines.append("✈️ *Viagens:* Use uma meta de poupança de curto prazo no BankAO.")
    if has_studies:
        goal_lines.append("🎓 *Estudos:* O Depósito a Prazo é ideal — sem risco, com rentabilidade fixa.")
    if has_reserve and salary:
        reserve_target = salary * 6
        goal_lines.append(f"🆘 *Fundo de Emergência:* Meta de **{reserve_target:,.0f} Kz** (6 meses do seu salário).")
    if goal_lines:
        lines.append("**🎯 Alinhado com os seus objetivos:**")
        lines.extend(goal_lines)
        lines.append("")

    lines.append("💬 *Deseja que eu simule um valor específico? Diga, por exemplo: «Simula 100 mil a 12 meses no Depósito a Prazo».*")
    return "\n".join(lines)


# ─── Memória persistente ────────────────────────────────────────────────────────

def save_memory(user_id: str, key: str, value: str):
    """Persiste uma memória do utilizador no Copilot."""
    conn = get_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO copilot_memory (id, user_id, memory_key, memory_value)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, memory_key) DO UPDATE SET
                    memory_value = excluded.memory_value,
                    updated_at = CURRENT_TIMESTAMP
            """, (str(uuid.uuid4()), user_id, key[:80], str(value)[:500]))
    except Exception as e:
        logger.warning(f"Erro ao salvar memória: {e}")
    finally:
        conn.close()


def extract_memories_from_reply(user_id: str, user_msg: str, ai_reply: str = ""):
    """Extrai e persiste memórias permanentes relevantes da conversa."""
    msg_lower = user_msg.lower()

    # 1. Nome do utilizador
    m_name = re.search(r"(?:o\s+meu\s+nome\s+[eé]|chamo-me|meu\s+nome\s+[eé]|podes\s+(?:me\s+)?chamar\s+de)\s+([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)?)", user_msg, re.IGNORECASE)
    if m_name:
        extracted_name = m_name.group(1).strip().title()
        save_memory(user_id, "nome_preferido", extracted_name)

    # 2. Rendimento / Salário declarado
    if any(w in msg_lower for w in ["salário", "salario", "recebo", "ganho", "rendimento", "ordenado"]):
        m_num = re.search(r"(?:sal[aá]rio|recebo|ganho|rendimento|ordenado)(?:\s+(?:[eé]|de|cerca\s+de|aproximadamente))?\s*(\d+(?:[.,]\d+)?)\s*(mil|k|milh[aã]o|milh[oõ]es)?", msg_lower)
        if not m_num:
            m_num = re.search(r"(\d+(?:[.,]\d+)?)\s*(mil|k|milh[aã]o|milh[oõ]es)\s*(?:de\s+)?(?:kz|kzs|kwanzas|aoa)?", msg_lower)
        if m_num:
            val_raw = m_num.group(1).replace(".", "").replace(",", ".")
            mult_word = (m_num.group(2) or "").lower()
            try:
                base_val = float(val_raw)
                if "milh" in mult_word:
                    final_val = base_val * 1_000_000
                elif "mil" in mult_word or "k" in mult_word or base_val < 1000:
                    final_val = base_val * 1000
                else:
                    final_val = base_val
                save_memory(user_id, "rendimento_mensal", f"{final_val:,.0f} Kz")
                save_memory(user_id, "rendimento_mensal_numerico", str(final_val))
            except Exception:
                pass
        else:
            save_memory(user_id, "rendimento_mensal", "Mencionou rendimento mensal")

    # 3. Perfil de Risco e Preferências
    if any(w in msg_lower for w in ["conservador", "baixo risco", "sem risco", "seguro", "capital garantido"]):
        save_memory(user_id, "perfil_risco", "Conservador (foco em capital 100% garantido)")
    elif any(w in msg_lower for w in ["moderado", "equilibrado"]):
        save_memory(user_id, "perfil_risco", "Moderado (equilíbrio entre taxa fixa e crescimento)")
    elif any(w in msg_lower for w in ["arrojado", "agressivo", "alto risco", "ações", "etf"]):
        save_memory(user_id, "perfil_risco", "Arrojado (foco em valorização e proteção cambial)")

    # 4. Gostos, Interesses e Objetivos de Vida
    if any(w in msg_lower for w in ["carro", "automóvel", "automovel", "viatura"]):
        save_memory(user_id, "interesse_carro", "Meta/Gosto: Compra de viatura própria")

    if any(w in msg_lower for w in ["casa", "habitação", "habitacao", "moradia", "apartamento", "imóvel", "imovel"]):
        save_memory(user_id, "interesse_casa", "Meta/Gosto: Habitação própria")

    if any(w in msg_lower for w in ["viagem", "férias", "ferias", "viajar", "turismo"]):
        save_memory(user_id, "interesse_viagem", "Meta/Gosto: Planos de viagens")

    if any(w in msg_lower for w in ["estudos", "faculdade", "universidade", "curso", "mestrado", "propina"]):
        save_memory(user_id, "interesse_estudos", "Meta/Gosto: Formação académica")

    if any(w in msg_lower for w in ["reserva", "emergência", "emergencia"]):
        save_memory(user_id, "interesse_reserva", "Meta/Gosto: Fundo de reserva de emergência")

    if any(w in msg_lower for w in ["poupar", "poupança", "poupanca"]):
        save_memory(user_id, "habito_poupanca", "Hábito: Foco em poupar regularmente")


# ─── Deteção de intenção de gráfico ──────────────────────────────────────────

CHART_PATTERNS = [
    # Donut de despesas por mês específico
    (r"gr[aá]fico.{0,20}despesas? (?:de |do |em )?(?:agosto|setembro|outubro|novembro|dezembro|janeiro|fevereiro|março|abril|maio|junho|julho)",
     "donut_expenses_month", {}),
    (r"gr[aá]fico.{0,20}despesas?", "donut_expenses_month", {}),
    (r"donut.{0,20}despesas?", "donut_expenses_month", {}),
    # Evolução ao longo de meses
    (r"evolu[çc][aã]o.{0,30}(?:4|quatro|3|tr[eê]s|6|seis) m[eê]ses?", "line_expenses_months", {"months": 4}),
    (r"gr[aá]fico.{0,30}evolu[çc][aã]o", "line_expenses_months", {"months": 4}),
    (r"gr[aá]fico.{0,30}m[eê]ses", "line_expenses_months", {"months": 4}),
    # Barras por categoria
    (r"gr[aá]fico.{0,30}categori", "bar_categories_period", {"months": 3}),
    # Previsão
    (r"gr[aá]fico.{0,20}previs[aã]o", "balance_forecast", {}),
    (r"previs[aã]o\s+(?:de\s+)?saldo", "balance_forecast", {}),
    (r"gr[aá]fico.{0,20}futuro", "balance_forecast", {}),
]

MONTH_MAP = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "abril": "04",
    "maio": "05", "junho": "06", "julho": "07", "agosto": "08",
    "setembro": "09", "outubro": "10", "novembro": "11", "dezembro": "12"
}

def detect_chart_intent(message: str) -> Optional[tuple]:
    """Retorna (chart_type, params) se a mensagem pede um gráfico."""
    msg_lower = message.lower().strip()
    # Perguntas pedagógicas/explicativas/simulações não são pedidos de renderização de gráfico
    if re.search(r"^(?:como\s+funciona|o\s+que\s+[eé]|explica|como\s+calculas|se\s+poupar|quanto\s+gastei)\b", msg_lower):
        return None
    for pattern, chart_type, base_params in CHART_PATTERNS:
        if re.search(pattern, msg_lower):
            params = dict(base_params)
            # Detectar mês específico
            for month_name, month_num in MONTH_MAP.items():
                if month_name in msg_lower:
                    year = datetime.date.today().year
                    if int(month_num) > datetime.date.today().month:
                        year -= 1
                    params["month"] = f"{year}-{month_num}"
                    break
            # Detectar número de meses
            n_match = re.search(r"(\d+) m[eê]ses?", msg_lower)
            if n_match:
                params["months"] = int(n_match.group(1))
            return chart_type, params
    return None


# ─── Auto-registo de operações ─────────────────────────────────────────────────

def auto_register_operation(user_id: str, op_type: str, details: Dict) -> bool:
    """Regista automaticamente uma despesa/poupança/investimento com base em ação confirmada."""
    conn = get_connection()
    try:
        if op_type == "expense":
            exp_id = str(uuid.uuid4())
            amount = details.get("amount", 0)
            amount_minor = details.get("amount_minor")
            if amount_minor is None:
                amount_minor = int(round(float(amount) * 100))
            expense_date = details.get("expense_date") or details.get("date") or datetime.date.today().isoformat()
            with conn:
                conn.execute("""
                    INSERT INTO expenses (id, user_id, name, amount_minor, currency, category, expense_date, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    exp_id, user_id,
                    details.get("name", "Despesa auto-registada"),
                    amount_minor,
                    details.get("currency", "AOA"),
                    details.get("category", "Outros"),
                    expense_date,
                    details.get("notes", "Registado automaticamente pelo Copilot")
                ))
            return True
    except Exception as e:
        logger.error(f"Erro no auto-registo: {e}")
    finally:
        conn.close()
    return False


# ─── Análise de balanço geral ──────────────────────────────────────────────────

def get_general_balance(user_id: str) -> str:
    """Gera um resumo textual do balanço financeiro do utilizador."""
    conn = get_connection()
    try:
        # Saldos
        accounts = conn.execute(
            "SELECT a.currency, COALESCE(SUM(le.amount_minor),0) as balance_minor "
            "FROM accounts a LEFT JOIN ledger_entries le ON le.account_id = a.id "
            "WHERE a.user_id = ? GROUP BY a.currency",
            (user_id,)
        ).fetchall()

        month_start = datetime.date.today().replace(day=1).isoformat()

        monthly_exp_minor = conn.execute(
            "SELECT COALESCE(SUM(amount_minor),0) FROM expenses WHERE user_id=? AND expense_date>=?",
            (user_id, month_start)
        ).fetchone()[0]

        inv_total = conn.execute(
            "SELECT COALESCE(SUM(current_value_minor),0) FROM user_investments WHERE user_id=? AND status='ativo'",
            (user_id,)
        ).fetchone()[0]

        savings_total = conn.execute(
            "SELECT COALESCE(SUM(saved_minor),0) FROM savings_goals WHERE user_id=? AND status!='completed'",
            (user_id,)
        ).fetchone()[0]

        lines = ["**📊 Balanço Geral BankAO**\n"]
        for r in accounts:
            bal = round(r["balance_minor"] / 100, 2)
            lines.append(f"• Conta {r['currency']}: **{bal:,.2f} {r['currency']}**")

        if monthly_exp_minor:
            lines.append(f"• Despesas este mês: **{float(monthly_exp_minor)/100:,.2f} AOA**")
        if inv_total:
            lines.append(f"• Carteira de investimentos: **{float(inv_total)/100:,.2f} AOA**")
        if savings_total:
            lines.append(f"• Poupanças (metas): **{float(savings_total)/100:,.2f} AOA**")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Erro balanço geral: {e}")
        return "Não consegui calcular o balanço neste momento."
    finally:
        conn.close()


def init_copilot_tables():
    """Cria as tabelas necessárias para o Copilot v2."""
    conn = get_connection()
    try:
        with conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS copilot_memory (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                memory_key TEXT NOT NULL,
                memory_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, memory_key),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS copilot_events (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_copilot_mem_user ON copilot_memory(user_id);
            CREATE INDEX IF NOT EXISTS idx_copilot_ev_user ON copilot_events(user_id);
            """)
    except Exception as e:
        logger.warning(f"Erro ao criar tabelas copilot: {e}")
    finally:
        conn.close()


def handle_direct_simple_question(msg: str, ctx: dict, user_id: str) -> Optional[str]:
    """
    Responde a perguntas simples de forma direta, clara e concisa (1-2 frases).
    Para perguntas conceituais/contábeis, responde de forma instrutiva e didática.
    """
    m = msg.strip().lower()

    # 0. Recomendação de investimento com ou sem salário inline
    if re.search(r"(?:qual|que|quais)\s+(?:tipo\s+de\s+|tipos?\s+de\s+)?investimentos?\s+(?:recomendas?|sugere|devo\s+fazer|posso\s+fazer|me\s+aconselhas?)", m) or \
       re.search(r"(?:recomenda(?:-me|r)?|sugere|aconselhas?)\s+(?:o\s+melhor\s+|um\s+tipo\s+de\s+|algum\s+)?investimento", m) or \
       re.search(r"pedi\s+para\s+(?:me\s+)?recomendar\s+(?:um\s+)?(?:tipo\s+de\s+)?investimento", m) or \
       re.search(r"onde\s+(?:devo|posso|devia)\s+investir", m) or \
       re.search(r"(?:melhor|melhores)\s+investimento(?:s)?\s+para\s+(?:mim|o\s+meu\s+caso)", m) or \
       (re.search(r"investimento", m) and re.search(r"ganho|recebo|sal[aá]rio|rendimento|ordenado", m)):
        # Tentar extrair salário inline (ex: "sendo que eu ganho 500 mil")
        inline_salary: Optional[float] = None
        m_sal = re.search(r"(?:ganho|recebo|sal[aá]rio|rendimento|ordenado)[^\d]*(\d+(?:[.,]\d+)?)\s*(mil|k|milh[aã]o|milh[oõ]es)?", m)
        if not m_sal:
            m_sal = re.search(r"(\d+(?:[.,]\d+)?)\s*(mil|k)\s*(?:kz|kwanzas?)?", m)
        if m_sal:
            val_raw = m_sal.group(1).replace(".", "").replace(",", ".")
            mult_word = (m_sal.group(2) or "").lower()
            try:
                base_val = float(val_raw)
                if "milh" in mult_word:
                    inline_salary = base_val * 1_000_000
                elif "mil" in mult_word or "k" in mult_word or base_val < 1000:
                    inline_salary = base_val * 1000
                else:
                    inline_salary = base_val
                # Persistir o salário imediatamente
                save_memory(user_id, "rendimento_mensal", f"{inline_salary:,.0f} Kz")
                save_memory(user_id, "rendimento_mensal_numerico", str(inline_salary))
            except Exception:
                pass
        return build_personalized_investment_recommendation(user_id, inline_salary)

    # 1. Saldo direto
    if re.search(r"^(?:qual\s+(?:[eé]\s+o\s+)?(?:meu\s+)?saldo|quanto\s+(?:dinheiro\s+)?tenho|meu\s+saldo|saldo\s+atual|ver\s+saldo)(?:\s+(?:na|da)\s+conta(?:\s+principal)?)?\??$", m) or re.search(r"quanto\s+(?:dinheiro\s+)?tenho|qual\s+(?:[eé]\s+o\s+)?(?:meu\s+)?saldo|quanto\s+tenho\s+na\s+conta", m):
        aoa = ctx.get("total_aoa", 0)
        out = [f"O seu saldo total em Kwanza é **{aoa:,.2f} Kz**."]
        other = [a for a in ctx.get("accounts", []) if a["currency"] != "AOA" and a["balance"] > 0]
        for a in other:
            sym = "€" if a["currency"] == "EUR" else ("$" if a["currency"] == "USD" else a["currency"])
            out.append(f"• Conta {a['currency']}: **{a['balance']:,.2f} {sym}**")
        return "\n".join(out)

    # 2. Despesas de hoje
    if re.search(r"^(?:quanto\s+gastei\s+hoje|despesas?\s+de\s+hoje|gastos?\s+de\s+hoje)\??$", m):
        today_iso = datetime.date.today().isoformat()
        today_items = [e for e in ctx.get("recent_expenses", []) if e.get("date") == today_iso]
        if today_items:
            tot = sum(e["amount"] for e in today_items)
            return f"Hoje registou **{tot:,.2f} Kz** em despesas ({len(today_items)} registo(s))."
        return "Hoje ainda não registou qualquer despesa. O seu saldo mantém-se intacto! 👏"

    # 3. Despesas do mês
    if re.search(r"^(?:quanto\s+gastei\s+este\s+m[eê]s|gastos?\s+deste\s+m[eê]s|total\s+de\s+despesas?\s+do\s+m[eê]s)\??$", m):
        tot = ctx.get("monthly_expenses", 0)
        top = ctx.get("top_categories", [])
        if tot > 0:
            top_str = f" · Maior gasto: **{top[0]['category']}** ({top[0]['total']:,.0f} Kz)" if top else ""
            return f"Este mês gastou um total de **{tot:,.2f} Kz** em despesas{top_str}."
        return "Este mês ainda não tem despesas registadas."

    # 4. IBAN / Conta
    if re.search(r"^(?:qual\s+(?:[eé]\s+o\s+)?(?:meu\s+)?iban|meu\s+iban|meu\s+n[uú]mero\s+de\s+conta)\??$", m):
        conn = get_connection()
        acc = conn.execute("SELECT account_number, iban_virtual FROM accounts WHERE user_id=? AND currency='AOA' LIMIT 1", (user_id,)).fetchone()
        conn.close()
        if acc:
            return f"O seu IBAN principal BankAO é `{acc['iban_virtual']}` (Conta `{acc['account_number']}`)."
        return "Não foi possível localizar o seu IBAN no momento."

    # 5. Metas
    if re.search(r"^(?:quantas\s+metas\s+tenho|minhas\s+metas(?:\s+de\s+poupan[cç]a)?|estado\s+das\s+metas)\??$", m):
        goals = ctx.get("savings_goals", [])
        if not goals:
            return "Não tem metas de poupança ativas. Quer criar uma agora? Diga-me o objetivo e o valor! 🎯"
        lines = [f"Tem **{len(goals)}** meta(s) de poupança ativa(s):"]
        for g in goals:
            pct = int((g["saved"] / g["target"]) * 100) if g["target"] else 0
            lines.append(f"• **{g['name']}:** {g['saved']:,.0f} / {g['target']:,.0f} Kz ({pct}%)")
        return "\n".join(lines)

    # 6. Compras não registadas / pendentes
    if re.search(r"compras?\s+n[aã]o\s+registadas?|despesas?\s+pendentes?|compras?\s+pendentes?|o\s+que\s+falta\s+registar", m):
        unrecorded = find_unrecorded_expenses(user_id)
        if unrecorded:
            return format_unrecorded_alert(unrecorded)
        return "Todas as suas compras e pagamentos conhecidos estão devidamente registados nas despesas! Parabéns pelo rigor contábil! ✅"

    # 7. Hábitos de compra
    if re.search(r"h[aá]bitos?\s+de\s+compras?|analis(?:e|ar)\s+(?:os\s+meus\s+)?gastos?|como\s+ando\s+a\s+gastar|padr[aã]o\s+de\s+gastos?", m):
        habits = analyze_spending_habits(user_id)
        return format_spending_habits_response(habits)

    # 8. Explicação didática da previsão / projeção futura
    if re.search(r"(?:como\s+funciona|o\s+que\s+[eé]|como\s+calculas)\s+(?:a\s+)?previs[aã]o|como\s+projetas\s+o\s+futuro", m):
        return explain_balance_forecast(current_balance=ctx.get("total_aoa", 0))

    # 9. Explicação didática de Depósito a Prazo
    if re.search(r"(?:como\s+funciona|o\s+que\s+[eé])\s+(?:um\s+)?dep[oó]sito\s+a\s+prazo", m):
        return (
            "🏦 **Depósito a Prazo BankAO (Guia Instrutivo):**\n\n"
            "O Depósito a Prazo é uma aplicação de capital garantido onde o seu dinheiro rende juros pré-fixados:\n\n"
            "• **Rentabilidade Elevada:** Até **18,5% ao ano** em Kwanzas (AOA) e **4,5% a.a.** em Dólares (USD).\n"
            "• **Juro Composto:** Pode optar por capitalização periódica (os juros geram mais juros).\n"
            "• **Risco Zero:** Isento de volatilidade de mercado, com garantia integral de capital.\n"
            "• **Exemplo Numérico:** Se aplicar **500.000 Kz** a 18,5% a 1 ano, no vencimento recebe **592.500 Kz** (**+92.500 Kz** de rendimento bruto).\n\n"
            "Deseja que eu ajude a escolher o melhor depósito para o seu saldo atual?"
        )

    # 10. Regra 50/30/20
    if re.search(r"regra\s+50\s*30\s*20|regra\s+50/30/20", m):
        monthly = ctx.get("monthly_expenses", 0)
        return (
            "📐 **A Regra Contabilística 50/30/20 (Adaptada a Angola):**\n\n"
            "É o padrão de excelência de gestão orçamental pessoal:\n\n"
            "1. **50% — Necessidades Essenciais:** Renda da casa, contas de luz (ENDE), água (EPAL), supermercado básico e transporte diário.\n"
            "2. **30% — Estilo de Vida:** Restaurantes, lazer, compras pessoais, passeios e subscrições.\n"
            "3. **20% — Futuro e Liberdade:** Poupança em metas BankAO e investimentos (Depósitos a Prazo, Obrigações do Tesouro na BODIVA).\n\n"
            f"💡 *Para o seu mês atual ({monthly:,.0f} Kz em despesas):* Certifique-se de que pelo menos 20% do seu rendimento líquido mensal é reservado antes de gastar em supérfluos!"
        )

    # 11. O que é um ETF
    if re.search(r"(?:o\s+que\s+[eé]|como\s+funciona)\s+(?:um\s+)?etf\b", m):
        return (
            "📊 **O que é um ETF (Exchange Traded Fund)?**\n\n"
            "Um ETF é um fundo de investimento cotado em bolsa que replica um índice de mercado (como o S&P 500 ou o MSCI World):\n\n"
            "• **Diversificação Instantânea:** Ao comprar uma unidade de ETF, você investe indiretamente em centenas de empresas líderes mundiais (Apple, Microsoft, Nvidia, etc.).\n"
            "• **Custos Reduzidos:** Taxas de gestão (TER) muito mais baixas do que fundos tradicionais (geralmente entre 0,07% e 0,22% ao ano).\n"
            "• **Liquidez Diária:** Pode ser comprado e vendido em dias úteis no horário das bolsas mundiais.\n"
            "• **Risco de Mercado:** O valor varia diariamente de acordo com o mercado (não tem capital garantido como um Depósito a Prazo).\n\n"
            "No BankAO, disponibilizamos ETFs globais em Dólares (USD) para diversificação internacional da sua carteira."
        )

    # 12. Diferença entre Depósito a Prazo e ETF
    if re.search(r"diferen[cç]a\s+entre\s+(?:um\s+)?dep[oó]sito\s+a\s+prazo\s+e\s+(?:um\s+)?etf|etf\s+(?:ou|vs)\s+dep[oó]sito\s+a\s+prazo", m):
        return (
            "⚖️ **Comparativo: Depósito a Prazo vs. ETF**\n\n"
            "Ambos são excelentes instrumentos, mas atendem a objetivos financeiros distintos:\n\n"
            "1. **Depósito a Prazo BankAO (Até 18,5% a.a.):**\n"
            "   • **Garantia:** Capital 100% garantido pelo banco.\n"
            "   • **Rentabilidade:** Pré-fixada e previsível.\n"
            "   • **Risco:** Zero volatilidade.\n"
            "   • **Ideal para:** Fundo de emergência e metas de curto/médio prazo (1 a 2 anos).\n\n"
            "2. **ETF Global (ex: S&P 500 / All-World em USD):**\n"
            "   • **Garantia:** Sem capital garantido (sujeito à oscilação das ações mundiais).\n"
            "   • **Rentabilidade:** Variável, com histórico de valorização de longo prazo (média histórica de 8% a 12% a.a. em moeda forte).\n"
            "   • **Ideal para:** Construção de património a longo prazo (> 3 a 5 anos) e proteção cambial contra a desvalorização do Kwanza.\n\n"
            "💡 *Recomendação BankAO:* Comece por garantir o seu fundo de emergência num Depósito a Prazo antes de alocar capital em ETFs."
        )

    # 13. Obrigações do Tesouro e BODIVA
    if re.search(r"(?:o\s+que\s+[eé]|como\s+funciona)\s+(?:a\s+)?bodiva|(?:o\s+que\s+s[aã]o|como\s+funcionam)\s+(?:as\s+)?obriga[cç][oõ]es\s+do\s+tesouro", m):
        return (
            "🏛️ **Obrigações do Tesouro & BODIVA (Guia do Investidor):**\n\n"
            "As **Obrigações do Tesouro (OT)** são títulos de dívida pública emitidos pelo Estado Angolano (Ministério das Finanças):\n\n"
            "• **Como funciona:** Você empresta dinheiro ao Estado e recebe cupões de juros periódicos (ex: **17,2% ao ano** com pagamentos semestrais).\n"
            "• **BODIVA:** É a Bolsa de Dívida e Valores de Angola, onde esses títulos são negociados de forma transparente.\n"
            "• **Liquidez Secundária:** Se precisar do dinheiro antes do vencimento, pode vender os títulos no mercado secundário da BODIVA.\n"
            "• **Segurança:** Risco soberano (garantia direta da República de Angola).\n\n"
            "O BankAO permite subscrever e acompanhar títulos da BODIVA diretamente na sua carteira de investimentos."
        )

    # 14. Diferença entre Juros Simples e Compostos
    if re.search(r"diferen[cç]a\s+entre\s+juros?\s+simples?\s+e\s+juros?\s+compostos?", m):
        return (
            "🧮 **Diferença entre Juros Simples e Juros Compostos:**\n\n"
            "• **Juros Simples:** O rendimento é calculado sempre apenas sobre o capital inicial depositado, mantendo o ganho fixo em cada período.\n"
            "  *Exemplo:* 100.000 Kz a 15% ao ano gera 15.000 Kz no 1.º ano e outros 15.000 Kz no 2.º ano (total: 30.000 Kz de juros).\n\n"
            "• **Juros Compostos («Juro sobre Juro»):** Os rendimentos obtidos acumulam ao capital e passam também a render juros no período seguinte, gerando crescimento exponencial.\n"
            "  *Exemplo no BankAO:* 100.000 Kz a 18,5% ao ano capitalizados mensalmente acumulam cerca de 120.152 Kz no fim de 12 meses (+20.152 Kz de juros).\n\n"
            "No BankAO, os Depósitos a Prazo e Planos de Poupança utilizam **juros compostos** para maximizar o seu património!"
        )

    # 15. Comparativo: Obrigações vs. Depósitos a Prazo vs. ETFs
    if re.search(r"diferen[cç]a\s+entre\s+(?:investir\s+em\s+)?obriga[cç][oõ]es,\s*dep[oó]sitos?\s+a\s+prazo\s+e\s+etfs?", m) or \
       (re.search(r"obriga[cç][oõ]es", m) and re.search(r"dep[oó]sito", m) and re.search(r"etf", m)):
        return (
            "⚖️ **Comparativo: Obrigações vs. Depósitos a Prazo vs. ETFs**\n\n"
            "1. **Depósitos a Prazo (até 18,5% a.a.):**\n"
            "   • **Garantia:** Capital 100% garantido pelo Fundo de Garantia de Depósitos (FGD).\n"
            "   • **Risco:** Zero volatilidade. Retorno pré-fixado e previsível.\n"
            "   • **Ideal para:** Fundo de emergência e metas a 6-12 meses.\n\n"
            "2. **Obrigações do Tesouro na BODIVA (17,2% a.a.):**\n"
            "   • **Garantia:** Soberana (República de Angola).\n"
            "   • **Rendimento:** Pagamentos semestrais de cupões de juros.\n"
            "   • **Liquidez:** Podem ser vendidas antes da maturidade no mercado secundário da BODIVA.\n\n"
            "3. **ETFs Globais em Dólares (S&P 500 / MSCI World):**\n"
            "   • **Garantia:** Sem capital garantido (sujeito às oscilações das bolsas internacionais).\n"
            "   • **Rentabilidade:** Variável, com histórico de valorização de longo prazo (8% a 12% a.a. em USD).\n"
            "   • **Ideal para:** Proteção cambial contra desvalorização do Kwanza e património a longo prazo (> 3 anos)."
        )

    # 16. Análise de Risco / Posso perder dinheiro
    if re.search(r"posso\s+perder\s+dinheiro|risco\s+de\s+perder|posso\s+ter\s+preju[ií]zo", m):
        return (
            "🛡️ **Análise de Risco de Capital no BankAO:**\n\n"
            "Depende do tipo de investimento selecionado:\n\n"
            "• **Depósitos a Prazo (BankAO 18,5%, BFA 15,0%):** **NÃO pode perder dinheiro.** O capital investido e os juros acordados são 100% garantidos pelo banco e pelo Fundo de Garantia de Depósitos (FGD) de Angola.\n\n"
            "• **Obrigações e Bilhetes do Tesouro (BODIVA):** Risco soberano (muito baixo). O reembolso do valor nominal no vencimento é garantido pelo Estado Angolano. Se mantiver o título até ao vencimento, não há perda de capital.\n\n"
            "• **ETFs Internacionais (S&P 500, VWCE):** **SIM, há risco de mercado.** Como são cotados em bolsa, o valor varia diariamente. Em períodos de crise ou desvalorização bolsista, o valor da cotação pode descer temporariamente.\n\n"
            "💡 *Princípio de Segurança:* Nunca aplique a sua reserva de emergência em ações ou ETFs; mantenha-a sempre em Depósitos a Prazo com capital 100% garantido."
        )

    # 17. Vantagens e Desvantagens de investir agora
    if re.search(r"vantagens?\s+e\s+desvantagens?\s+de\s+investir\s+agora", m):
        return (
            "⚖️ **Vantagens e Desvantagens de Investir Agora:**\n\n"
            "**Vantagens:**\n"
            "• **Taxas de juro atrativas em Kwanzas:** Até **18,5% ao ano** no Depósito a Prazo BankAO e **17,2%** nas Obrigações do Tesouro na BODIVA, protegendo o seu capital contra a inflação.\n"
            "• **Efeito do Juro Composto:** Quanto mais cedo o dinheiro for aplicado, maior a multiplicação dos rendimentos ao longo do tempo.\n"
            "• **Proteção Cambial:** Acesso a produtos em USD (ETFs e Depósitos em moeda estrangeira a 4,5% a.a.).\n\n"
            "**Desvantagens / Cuidados:**\n"
            "• **Imobilização do Capital:** No Depósito a Prazo a 12 meses, o resgate antecipado antes do vencimento sofre penalização sobre os juros corridos.\n"
            "• **Volatilidade de Mercado:** Nos produtos de renda variável (ETFs), pode haver oscilação a curto prazo."
        )

    # 18. Recomendação para quem nunca investiu
    if re.search(r"(?:para\s+algu[eé]m\s+que|para\s+quem)\s+nunca\s+investiu|primeiro\s+investimento|come[cç]ar\s+do\s+zero", m):
        return (
            "🌱 **Recomendação para Quem Nunca Investiu:**\n\n"
            "Para dar os primeiros passos sem qualquer receio, o BankAO recomenda:\n\n"
            "1. **Depósito a Prazo Super Rendimento BankAO (18,5% a.a.):**\n"
            "   • **Porquê?** Risco zero de perda de capital, rentabilidade garantida e fixa desde o primeiro dia.\n"
            "   • **Mínimo:** 100.000 Kz a 12 meses (ao fim do prazo, 100.000 Kz tornam-se ~120.150 Kz).\n\n"
            "2. **Fundo de Liquidez e Tesouraria BAI (16,6% a.a.):**\n"
            "   • **Porquê?** Entrada mínima de apenas **25.000 Kz** e **resgate diário** (pode retirar o dinheiro a qualquer momento se precisar dele para o dia a dia).\n\n"
            "💡 *Regra de Ouro:* Comece com um valor que não comprometa as suas despesas essenciais do mês!"
        )

    # 19. Investimentos de Menor Risco
    if re.search(r"(?:menor|baixo|m[ií]nimo)\s+risco\s+(?:dispon[ií]ve(?:l|is)|no\s+banco)", m):
        return (
            "🛡️ **Investimentos de Menor Risco no BankAO:**\n\n"
            "1. **Depósito a Prazo Super Rendimento BankAO (18,5% a.a.):**\n"
            "   • Risco: **Baixo / Zero** — Capital e juros 100% garantidos pelo Fundo de Garantia de Depósitos (FGD).\n"
            "   • Prazo: 12 meses | Entrada mínima: 100.000 Kz.\n\n"
            "2. **Depósito Trimestral Crescente BFA (15,0% a.a.):**\n"
            "   • Risco: **Baixo** — Capital 100% garantido pelo FGD com liquidez trimestral (mínimo 50.000 Kz).\n\n"
            "3. **Bilhetes do Tesouro BT 364 (16,4% a.a.) e Obrigações OT 2027 (17,2% a.a.):**\n"
            "   • Risco: **Baixo** — Garantia soberana do Estado Angolano (Ministério das Finanças).\n\n"
            "4. **Fundo de Liquidez e Tesouraria BAI (16,6% a.a.):**\n"
            "   • Risco: **Baixo** — Carteira de dívida pública de curto prazo com liquidez diária."
        )

    # 20. Maior Rentabilidade Atualmente
    if re.search(r"(?:maior|mais\s+alta)\s+rentabilidade\s+(?:atualmente|dispon[ií]vel|no\s+banco)", m):
        return (
            "🏆 **Investimento com Maior Rentabilidade Atualmente:**\n\n"
            "O produto com a taxa de rendimento mais elevada no catálogo BankAO é:\n\n"
            "• **Depósito a Prazo Super Rendimento BankAO:**\n"
            "  - **Taxa Anual:** **18,5% ao ano** em Kwanzas (AOA)\n"
            "  - **Garantia:** Capital 100% garantido pelo FGD\n"
            "  - **Prazo:** 12 meses (liquidação no vencimento)\n"
            "  - **Entrada Mínima:** 100.000 Kz\n\n"
            "Em títulos negociáveis de bolsa, a taxa mais alta são as **Obrigações do Tesouro OT-NR 2027 na BODIVA** com **17,2% ao ano** e cupão semestral."
        )

    # 21. Recuperar dinheiro mais rapidamente (Liquidez)
    if re.search(r"recuperar\s+o\s+dinheiro\s+mais\s+rapid(?:o|amente)|maior\s+liquidez|resgate\s+mais\s+r[aá]pido", m):
        return (
            "⚡ **Investimentos com Liquidez Mais Rápida no BankAO:**\n\n"
            "1. **Fundo de Liquidez e Tesouraria BAI (16,6% a.a.):**\n"
            "   • **Liquidez: Diária** — É o produto que permite recuperar o dinheiro mais rapidamente! Pode resgatar o capital a qualquer dia útil sem perder os rendimentos já gerados.\n"
            "   • Mínimo: 25.000 Kz.\n\n"
            "2. **Obrigações do Tesouro na BODIVA (17,2% a.a.):**\n"
            "   • **Liquidez: Mercado Secundário** — Pode vender os seus títulos a outros investidores na BODIVA caso necessite de liquidez antes do vencimento.\n\n"
            "3. **Depósito Trimestral Crescente BFA (15,0% a.a.):**\n"
            "   • **Liquidez: Trimestral (a cada 90 dias)** — Janela de resgate regular a cada 3 meses.\n\n"
            "⚠️ *Nota:* O Depósito a Prazo BankAO (18,5%) só liquida no vencimento (12 meses); o resgate antecipado acarreta penalização de 35% dos juros corridos."
        )

    # 22. Valor mínimo para começar a investir
    if re.search(r"valor\s+m[ií]nimo\s+(?:necess[aá]rio\s+)?para\s+(?:come[cç]ar\s+a\s+)?investir|quanto\s+preciso\s+para\s+come[cç]ar\s+a\s+investir", m):
        return (
            "💰 **Valores Mínimos para Começar a Investir no BankAO:**\n\n"
            "• **Fundo de Liquidez e Tesouraria BAI:** apenas **25.000 Kz** (a entrada mais acessível em Kwanzas).\n"
            "• **Depósito Trimestral Crescente BFA:** **50.000 Kz**.\n"
            "• **Depósito a Prazo Super Rendimento BankAO:** **100.000 Kz**.\n"
            "• **Bilhetes do Tesouro BT 364 Dias:** **100.000 Kz**.\n"
            "• **Obrigações do Tesouro OT-NR 2027 (BODIVA):** **250.000 Kz**.\n"
            "• **ETFs Internacionais (VWCE / CSPX):** a partir de **50 USD** (~50.000 Kz).\n\n"
            "💡 Ou seja, com apenas **25.000 Kz** já pode colocar o seu dinheiro a render a uma taxa de 16,6% ao ano!"
        )

    # 23. Comparar os 3 mais rentáveis
    if re.search(r"compara\s+(?:os\s+)?(?:3|tr[eê]s)\s+investimentos?\s+mais\s+rent[aá]ve(?:l|is)", m):
        return (
            "📊 **Comparativo dos 3 Investimentos Mais Rentáveis no BankAO:**\n\n"
            "| Produto | Taxa Anual | Prazo | Mínimo | Risco | Liquidez |\n"
            "|---|---|---|---|---|---|\n"
            "| **1. Depósito a Prazo Super Rendimento** | **18,5% a.a.** | 12 meses | 100.000 Kz | Baixo (FGD) | No vencimento |\n"
            "| **2. Obrigações do Tesouro OT 2027 (BODIVA)** | **17,2% a.a.** | 24 meses | 250.000 Kz | Baixo (Soberano) | Secundário (BODIVA) |\n"
            "| **3. Fundo de Liquidez BAI** | **16,6% a.a.** | Aberto | 25.000 Kz | Baixo | Diária |\n\n"
            "💡 *Conclusão:* Se não vai precisar do dinheiro nos próximos 12 meses, o **Depósito a Prazo (18,5%)** oferece o maior ganho com capital 100% garantido. Se precisa de flexibilidade, o **Fundo BAI (16,6%)** é a escolha ideal."
        )

    # 24. Tenho 100.000 Kz disponíveis
    if re.search(r"(?:tenho|com)\s+100\.?000\s*(?:kz|kzs|kwanzas)?(?:\s+dispon[ií]ve(?:l|is))?.*?onde\s+(?:seria\s+)?melhor\s+investir", m):
        return (
            "💡 **Melhor Opção para Investir 100.000 Kz:**\n\n"
            "Com **100.000 Kz**, atinge exatamente o valor mínimo do produto mais rentável do catálogo:\n\n"
            "• **Opção Principal — Depósito a Prazo Super Rendimento BankAO (18,5% a.a.):**\n"
            "  - **Capital Aplicado:** 100.000 Kz\n"
            "  - **Prazo:** 12 meses\n"
            "  - **Garantia:** Capital 100% garantido pelo FGD\n"
            "  - **Ganho em juros:** **+18.500 Kz** (ou cerca de **+20.150 Kz** com capitalização mensal de juros compostos)\n"
            "  - **Saldo Final no Vencimento:** **~120.150 Kz**\n\n"
            "• **Alternativa com Liquidez Diária — Fundo BAI (16,6% a.a.):**\n"
            "  - Ganho de ~16.600 Kz/ano, com a vantagem de poder resgatar quando quiser.\n\n"
            "Deseja que eu prepare a subscrição do Depósito a Prazo de 100.000 Kz?"
        )

    # 25. Simulações com valores específicos
    if re.search(r"investir\s+500\.?000\s*(?:kz)?\s+durante\s+12\s+meses.*?quanto\s+(?:poderei|vou)\s+ganhar", m):
        return (
            "🧮 **Simulação: 500.000 Kz a 12 Meses no BankAO:**\n\n"
            "Ao aplicar no **Depósito a Prazo Super Rendimento BankAO (18,5% ao ano)**:\n\n"
            "• **Capital Inicial Aplicado:** 500.000,00 Kz\n"
            "• **Taxa Anual:** 18,5% a.a.\n"
            "• **Juros Brutos Anuais (simples):** **+92.500,00 Kz**\n"
            "• **Valor Final Acumulado com Juros Compostos (capitalização mensal):** **~600.760,00 Kz**\n"
            "• **Lucro Total em Juros:** **+100.760,00 Kz**\n\n"
            "O seu capital rende mais de **8.300 Kz por mês** sem qualquer risco de perda! Deseja subscrever este depósito?"
        )

    if re.search(r"investir\s+200\.?000\s*(?:kz)?.*15%.*quanto\s+receberei\s+ao\s+fim\s+de\s+um\s+ano", m):
        return (
            "🧮 **Cálculo de Rendimento: 200.000 Kz a 15% ao ano (12 meses):**\n\n"
            "• **Capital Investido:** 200.000,00 Kz\n"
            "• **Taxa Anual:** 15,0%\n"
            "• **Juros Gerados (1 ano):** 200.000 × 15% = **+30.000,00 Kz**\n"
            "• **Valor Total a Receber ao Fim de Um Ano:** **230.000,00 Kz**\n\n"
            "💡 *Dica BankAO:* Se optar pelo nosso **Depósito a Prazo Super Rendimento**, a taxa sobe para **18,5% ao ano**, recebendo **237.000 Kz** (mais 7.000 Kz de lucro)!"
        )

    if re.search(r"investir\s+50\.?000\s*(?:kz)?.*todos\s+os\s+meses.*(?:um\s+ano|12\s+meses).*quanto\s+(?:poderei\s+)?acumular", m):
        return (
            "🧮 **Simulação de Poupança Recorrente: 50.000 Kz/mês durante 1 ano (12 meses):**\n\n"
            "Aplicando 50.000 Kz todos os meses no Depósito a Prazo BankAO (18,5% ao ano com capitalização composta):\n\n"
            "• **Total do seu Bolso Depositado:** 50.000 × 12 = **600.000,00 Kz**\n"
            "• **Juros Compostos Capitalizados:** **+63.210,00 Kz**\n"
            "• **Saldo Total Acumulado:** **~663.210,00 Kz**\n\n"
            "Ou seja, ao fim de 12 meses terá acumulado mais de **663 mil Kwanzas**, com mais de 63 mil Kwanzas gerados inteiramente pelo efeito multiplicador do juro composto!"
        )

    return None


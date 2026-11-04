"""
Rotas — Assistente IA: Copilot v2 com contexto real, memória, gráficos e análise.
"""
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any, Dict

import datetime

from backend.ai.assistant import BankaoAssistant
from backend.ai.client import get_meta_client
from backend.ai.copilot_v2 import (
    build_user_context, build_context_summary, get_chart_data,
    detect_chart_intent, get_general_balance, extract_memories_from_reply,
    save_memory, init_copilot_tables, auto_register_operation,
    find_unrecorded_expenses, format_unrecorded_alert,
    analyze_spending_habits, format_spending_habits_response,
    explain_balance_forecast
)
from backend.ai.ideal_pace import compute_ideal_pace
from backend.ai.intents import analyze_action_reply, analyze_message, extract_action_intent
from backend.ai.orchestrator import CopilotOrchestrator
from backend.ai.prompts import SYSTEM_PROMPT
from backend.core.config import settings
from backend.core.security import get_current_user
from backend.schemas import AIChatRequest, AIExplainTransferRequest, IdealPaceRequest

logger = logging.getLogger("bankao.ai_routes")
router = APIRouter(prefix="/api/ai", tags=["Assistente IA"])

# Garantir tabelas ao iniciar
init_copilot_tables()


# ─── Schemas novos ────────────────────────────────────────────────────────────

class ChatV2Request(BaseModel):
    message: str
    history: Optional[List[dict]] = None
    pending: Optional[dict] = None
    context: Optional[dict] = None  # Contexto extra do frontend (saldo visível, etc.)


# ─── Deteção de intenções especiais sem IA ────────────────────────────────────

def handle_direct_simple_question(msg: str, ctx: dict, user_id: str) -> Optional[str]:
    """
    Responde a perguntas simples de forma direta, clara e concisa (1-2 frases).
    Para perguntas conceituais/contábeis, responde de forma instrutiva e didática.
    """
    m = msg.strip().lower()

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
        from backend.database import get_connection
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

    return None


def detect_balance_request(msg: str) -> bool:
    terms = ["balanço", "balanco", "balanço geral", "resumo financeiro",
             "situação financeira", "total de tudo", "balanço completo"]
    return any(t in msg.lower() for t in terms)


def detect_advice_request(msg: str) -> bool:
    terms = ["dica", "conselho", "como poupar", "como economizar", "o que devo fazer",
             "melhorar finanças", "como investir", "onde poupar"]
    return any(t in msg.lower() for t in terms)


# ─── Geração de dicas personalizadas ─────────────────────────────────────────

def generate_personalized_advice(ctx: dict) -> str:
    lines = ["💡 **Dicas personalizadas para si:**\n"]
    monthly_exp = ctx.get("monthly_expenses", 0)
    total_aoa = ctx.get("total_aoa", 0)
    top_cats = ctx.get("top_categories", [])
    goals = ctx.get("savings_goals", [])
    investments = ctx.get("investments", [])

    # Rácio despesa/saldo
    if total_aoa > 0 and monthly_exp > 0:
        ratio = monthly_exp / total_aoa
        if ratio > 0.5:
            lines.append("⚠️ As suas despesas representam mais de 50% do saldo — considere reduzir gastos variáveis.")
        elif ratio < 0.2:
            lines.append("✅ Excelente! As suas despesas estão bem controladas em relação ao saldo.")

    # Maior categoria de gasto
    if top_cats:
        biggest = top_cats[0]
        if biggest["category"] not in ("Poupança", "Investimento", "Habitação"):
            lines.append(f"📊 O seu maior gasto é **{biggest['category']}** ({biggest['total']:,.0f} Kz/mês) — há margem para otimizar?")

    # Metas de poupança
    if not goals:
        lines.append("🎯 Não tem metas de poupança ativas. Criar uma meta (ex: fundo de emergência de 3 meses de despesas) é o primeiro passo para a liberdade financeira.")
    else:
        for g in goals[:1]:
            pct = int((g["saved"] / g["target"]) * 100) if g["target"] else 0
            lines.append(f"🏦 Meta **{g['name']}**: {pct}% concluída. {'Bom progresso! 💪' if pct > 50 else 'Continue a poupar mensalmente!'}")

    # Investimentos
    if not investments:
        lines.append("📈 Ainda não tem investimentos. Um Depósito a Prazo BankAO (18,5% ao ano) é um excelente começo.")
    else:
        total_inv = sum(i["value"] for i in investments)
        lines.append(f"📈 Carteira de investimentos: **{total_inv:,.2f} Kz** em {len(investments)} produto(s).")

    # Regra 50/30/20
    lines.append("\n💰 **Regra 50/30/20:** 50% para necessidades, 30% para desejos, 20% para poupança/investimento.")

    return "\n".join(lines)


# ─── Endpoint principal: Chat V2 ─────────────────────────────────────────────

@router.post("/chat-v2")
def ai_chat_v2(data: ChatV2Request, current_user: dict = Depends(get_current_user)):
    """
    Copilot v2: chat com contexto real do utilizador, memória persistente,
    análise de hábitos, gráficos inline, tool calling e auto-registo de operações.
    """
    user_id = current_user["id"]
    from backend.services.user_settings import get_settings
    if not get_settings(user_id).get("ai_enabled", True):
        raise HTTPException(status_code=403, detail="O assistente IA está desativado nas Definições.")
    return CopilotOrchestrator.process_message(
        user_id=user_id,
        message=data.message,
        history=data.history,
        pending=data.pending,
        client_context=data.context
    )


# ─── Endpoint legado (compatibilidade) ───────────────────────────────────────

@router.post("/chat")
def ai_chat(data: AIChatRequest):
    res = BankaoAssistant.chat_with_action(data.message, data.history, data.pending)
    return {
        "reply": res["reply"],
        "action": res.get("action"),
        "pending": res.get("pending"),
        "model": settings.MODEL_NAME,
        "provider": "Meta Model API / Muse Spark"
    }


@router.post("/explain-transfer")
def ai_explain_transfer(data: AIExplainTransferRequest):
    explanation = BankaoAssistant.explain_transfer(
        source_amount=data.source_amount,
        source_currency=data.source_currency,
        dest_amount=data.dest_amount,
        dest_currency=data.dest_currency,
        fx_rate=data.fx_rate,
        fee=data.fee,
        dest_iban=data.dest_iban,
        beneficiary_name=data.beneficiary_name
    )
    return {"explanation": explanation, "model": settings.MODEL_NAME}


@router.get("/analyze-risk")
def ai_analyze_risk(
    amount: float,
    currency: str,
    tx_type: str,
    current_user: dict = Depends(get_current_user)
):
    analysis = BankaoAssistant.analyze_risk(
        amount=amount, currency=currency, tx_type=tx_type,
        user_kyc_status=current_user.get("kyc_status", "verificado")
    )
    return analysis


@router.post("/ideal-pace")
def ai_ideal_pace(data: IdealPaceRequest, current_user: dict = Depends(get_current_user)):
    return compute_ideal_pace(
        currency=data.currency,
        income_month=data.income_month,
        expense_month=data.expense_month,
        budget_month=data.budget_month,
        goals=[g.model_dump() for g in data.goals],
    )


@router.get("/memory")
def get_memory(current_user: dict = Depends(get_current_user)):
    """Retorna a memória do utilizador."""
    from backend.database import get_connection
    conn = get_connection()
    rows = conn.execute(
        "SELECT memory_key, memory_value, updated_at FROM copilot_memory WHERE user_id=? ORDER BY updated_at DESC",
        (current_user["id"],)
    ).fetchall()
    conn.close()
    return {"memory": [{"key": r["memory_key"], "value": r["memory_value"], "at": r["updated_at"]} for r in rows]}

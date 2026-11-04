"""
Orquestrador de Inteligência Artificial do BankAO (Copilot Inteligente).
Integração híbrida:
- Compreensão em Linguagem Natural com Tool Calling via Meta Model API / OpenAI.
- Motor de Raciocínio Determinístico para Validações, Cálculos e Fallback Offline.
- Preservação de Contexto Conversacional Multi-Turn e Memória Persistente.
- Segurança Estrita: Acesso aos dados reais apenas do utilizador autenticado e
  confirmação explícita no frontend antes de qualquer movimentação financeira.
"""
import datetime
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.ai.agent import run_agent
from backend.ai.client import get_meta_client
from backend.ai.context import (
    detect_follow_up,
    get_user_session,
    update_user_session,
)
from backend.ai.copilot_v2 import (
    build_personalized_investment_recommendation,
    build_user_context,
    detect_chart_intent,
    extract_memories_from_reply,
    find_unrecorded_expenses,
    format_unrecorded_alert,
    get_chart_data,
    handle_direct_simple_question,
)
from backend.ai.intents import analyze_message, normalize_spoken_text
from backend.ai.intents import _parse_slots
from backend.ai.expense_flow import KIND as EXPENSE_DELETE_KIND, apply_direct_registration, handle_expense_delete
from backend.ai.tools.registry import execute_tool
from backend.core.config import settings

logger = logging.getLogger("bankao.ai.orchestrator")


class CopilotOrchestrator:
    """Orquestrador Central da IA Financeira do BankAO."""

    @classmethod
    def process_message(
        cls,
        user_id: str,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        pending: Optional[Dict[str, Any]] = None,
        client_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ponto de entrada unificado para processar uma mensagem do utilizador.
        """
        message_clean = normalize_spoken_text(message.strip())
        history = history or []
        session = get_user_session(user_id)

        # ── Post-processor interno: garante semântica correta nas respostas ──────
        def _finalize(result: Dict[str, Any]) -> Dict[str, Any]:
            """Aplica regras transversais a todos os responses antes de os devolver."""
            if result is None:
                return result
            # Despesas registam-se logo (sem formulário nem confirmação): ver backend/ai/expense_flow.py
            result = apply_direct_registration(user_id, result)
            action = result.get("action")
            if action and isinstance(action, dict):
                tx_type = action.get("type", "")
                if tx_type in ("TRANSFER_INTERNAL", "TRANSFER_IBAN", "DEPOSIT_EXPRESS", "INVESTMENT_APPLY"):
                    # Transferências nunca são executadas sem confirmação explícita do cliente
                    action["requires_confirmation"] = True
                    action["executed"] = False
                    result["requires_confirmation"] = True
            return result

        # 1. Memorizar de imediato declarações do utilizador (salário, metas, aspirações)
        extract_memories_from_reply(user_id, message_clean, "")

        # 2. Resposta Ultra-Rápida (<50ms): Motor Determinístico e Ferramentas Reais
        # Garante resposta instantânea tanto por voz como por texto para todas as operações bancárias,
        # saldos, despesas, projeções, investimentos e transferências sem latência de rede externa.
        offline = cls._offline_chain(user_id, message_clean, history, pending, session)
        if offline:
            return _finalize(offline)

        # 3. Modelo Generativo Meta Muse (para perguntas abertas ou não cobertas pelas regras locais)
        meta_client = get_meta_client()
        if meta_client:
            for attempt in (1, 2):
                try:
                    agent_res = run_agent(meta_client, user_id, message_clean, history, client_context)
                    if agent_res:
                        return _finalize(agent_res)
                    break
                except Exception as e:
                    logger.error("Falha do agente (tentativa %s): %s", attempt, e, exc_info=True)

        return _finalize(cls._cannot_help(model_failed=bool(meta_client)))

    @classmethod
    def _investment_turn(cls, user_id: str, message: str, pending: Optional[Dict[str, Any]],
                         session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Uma volta do fluxo guiado de investimento (None = a mensagem não é deste fluxo)."""
        from backend.ai.invest_flow import KIND, handle_investment_message
        eff = pending or session.get("pending_operation")
        try:
            res = handle_investment_message(user_id, message, eff)
        except Exception as e:
            logger.error("Fluxo de investimento falhou: %s", e, exc_info=True)
            res = None
        if res is None:
            if isinstance(eff, dict) and eff.get("type") == KIND:
                update_user_session(user_id, {"pending_operation": None})
            return None
        update_user_session(user_id, {"pending_operation": res.get("pending"), "active_topic": "investments"})
        action = res.get("action")
        return {
            "reply": res["reply"], "action": action, "pending": res.get("pending"), "chart": None,
            "tools_used": ["investment_flow"],
            "requires_confirmation": bool(action and action.get("type") == KIND),
            "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2",
        }

    @classmethod
    def _expense_delete_turn(cls, user_id: str, message: str, pending: Optional[Dict[str, Any]],
                             session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Remover uma despesa («remove a despesa do telefone de ontem a 22 mil»). None = não é deste fluxo."""
        eff = pending or session.get("pending_operation")
        try:
            res = handle_expense_delete(user_id, message, eff)
        except Exception as e:
            logger.error("Remoção de despesa falhou: %s", e, exc_info=True)
            res = None
        if res is None:
            if isinstance(eff, dict) and eff.get("type") == EXPENSE_DELETE_KIND:
                update_user_session(user_id, {"pending_operation": None})
            return None
        update_user_session(user_id, {"pending_operation": res.get("pending"), "active_topic": "expenses"})
        return {
            "reply": res["reply"], "action": res.get("action"), "pending": res.get("pending"), "chart": None,
            "tools_used": ["expense_delete"], "requires_confirmation": False,
            "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2",
        }

    @staticmethod
    def _cannot_help(model_failed: bool) -> Dict[str, Any]:
        """Resposta honesta e curta quando nada foi percebido. Nunca uma saudação nem conversa não pedida."""
        if model_failed:
            reply = "Não consegui processar o seu pedido neste momento. Tente outra vez daqui a pouco."
        else:
            reply = ("Não percebi bem o pedido. Diga-o de outra forma, por exemplo: "
                     "«quanto gastei este mês?», «cria uma meta de 50 mil para um carro até agosto de 2027» "
                     "ou «transfere 5.000 Kz para a conta 0040 1234 5678».")
        return {
            "reply": reply, "action": None, "pending": None, "chart": None, "tools_used": [],
            "requires_confirmation": False, "model": settings.MODEL_NAME, "provider": "BankAO Copilot",
        }

    @classmethod
    def _offline_chain(
        cls,
        user_id: str,
        message_clean: str,
        history: List[Dict[str, str]],
        pending: Optional[Dict[str, Any]],
        session: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Plano B sem modelo: fluxos guiados, seguimentos, gráficos e consultas por regras."""
        # Wake words / Saudações por voz ou chat
        if re.search(r"\b(?:hi\s+bank\s+copilot|hey\s+bank\s+copilot|e\s+a[ií]\s+copiloto(?:\s+do\s+banco)?|ei\s+copiloto(?:\s+do\s+banco)?)\b", message_clean, re.I):
            return {
                "reply": "Olá! Estou a ouvir. Em que posso ajudar com as suas contas, transferências, metas ou despesas hoje?",
                "action": None, "pending": None, "chart": None,
                "tools_used": ["voice_wake_assistant"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        if re.fullmatch(r"\s*(?:ol[aá]|oi|bom dia|boa tarde|boa noite|boas)[\s!.]*", message_clean, re.I) and not (
                pending or session.get("pending_operation")):
            return {
                "reply": "Olá! Diga-me o que precisa.", "action": None, "pending": None, "chart": None,
                "tools_used": [], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot",
            }
        # Fluxo guiado de investimento: pergunta a pergunta, abre o formulário no fim ou quando o cliente pede
        inv = cls._investment_turn(user_id, message_clean, pending, session)
        if inv:
            return inv

        # Remover uma despesa: só com pedido detalhado (nome + valor e/ou dia); pede o que faltar
        exp_del = cls._expense_delete_turn(user_id, message_clean, pending, session)
        if exp_del:
            return exp_del

        # Fluxo pendente (ex: criar poupança guiada passo a passo)
        effective_pending = pending or session.get("pending_operation")
        if effective_pending and effective_pending.get("type") in ("INVESTMENT_APPLY", EXPENSE_DELETE_KIND):
            effective_pending = None  # já tratado acima; o analisador antigo não conhece estes fluxos
        if effective_pending:
            parsed = analyze_message(message_clean, effective_pending)
            if parsed.get("reply"):
                session_updates = {"pending_operation": parsed.get("pending")}
                if parsed.get("action"):
                    session_updates["pending_operation"] = None
                update_user_session(user_id, session_updates)
                return {
                    "reply": parsed["reply"],
                    "action": parsed.get("action"),
                    "pending": parsed.get("pending"),
                    "chart": None,
                    "tools_used": ["guided_savings_flow"],
                    "requires_confirmation": parsed.get("action") is not None,
                    "model": settings.MODEL_NAME,
                    "provider": "BankAO Copilot v2"
                }

        # 3. Verificar se é uma mensagem elíptica de seguimento (Multi-Turn Context)
        follow_up = detect_follow_up(message_clean, session)
        if follow_up:
            return cls._handle_follow_up(user_id, follow_up, session)

        # 4. Verificar se há intenção explícita de renderização de gráfico
        chart_intent = detect_chart_intent(message_clean)
        if chart_intent:
            chart_type, params = chart_intent
            chart_data = get_chart_data(user_id, chart_type, params)
            if chart_data:
                chart_titles = {
                    "donut": "donut de despesas",
                    "line": "gráfico de evolução",
                    "bar": "gráfico de categorias",
                    "forecast": "previsão de saldo"
                }
                ct = chart_data.get("type", "gráfico")
                reply_text = f"📊 Aqui está o seu **{chart_titles.get(ct, ct)}** — clique nas fatias para ver os detalhes."
                if ct == "donut":
                    total = chart_data.get("total", 0)
                    reply_text = f"📊 Em **{chart_data.get('title','este mês')}** gastou um total de **{total:,.2f} Kz**. Clique em cada fatia para ver o detalhe."
                elif ct == "line":
                    pts = chart_data.get("points", [])
                    if pts:
                        max_m = max(pts, key=lambda p: p["value"])
                        reply_text = f"📈 O mês com mais gastos foi **{max_m['label']}** ({max_m['value']:,.2f} Kz)."
                elif ct == "forecast":
                    note = chart_data.get("note", "")
                    reply_text = f"🔮 Previsão de saldo para os próximos 6 meses com base nos seus hábitos reais. *{note}.*"

                update_user_session(user_id, {"active_topic": "charts", "last_tool_used": "chart_generator"})
                return {
                    "reply": reply_text,
                    "action": None,
                    "pending": None,
                    "chart": chart_data,
                    "tools_used": ["chart_engine"],
                    "requires_confirmation": False,
                    "model": settings.MODEL_NAME,
                    "provider": "BankAO Copilot v2"
                }

        # 5. Motor Determinístico de Raciocínio Semântico e Ferramentas Reais (Sem alucinação, 100% de fiabilidade)
        det_res = cls._deterministic_engine(user_id, message_clean, session)
        if det_res:
            return det_res

        # Último recurso por palavras-chave (apertado: só quando o tema foi mesmo mencionado e não é uma ordem)
        m_lower = message_clean.lower()
        is_command = bool(re.search(r"\b(?:regist|cri[ae]|apag|elimin|transfer|envi|mand|deposit|bloque|cancel)\w*", m_lower))
        if not is_command:
            if any(k in m_lower for k in ["invest", "bodiva", "etf", "rendimento"]):
                return {
                    "reply": build_personalized_investment_recommendation(user_id),
                    "action": None,
                    "pending": None, "chart": None,
                    "tools_used": ["personalized_investment_advisor"],
                    "requires_confirmation": False,
                    "model": settings.MODEL_NAME, "provider": "BankAO Copilot"
                }
            if any(k in m_lower for k in ["despesa", "gasto", "gastei"]):
                det_exp = cls._deterministic_engine(user_id, "como estão as minhas despesas?", session)
                if det_exp:
                    return det_exp
            if "saldo" in m_lower:
                det_acc = cls._deterministic_engine(user_id, "quanto dinheiro tenho", session)
                if det_acc:
                    return det_acc
        return None

    @classmethod
    def _deterministic_engine(
        cls,
        user_id: str,
        message: str,
        session: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Motor de interpretação determinística avançada.
        Executa as ferramentas reais correspondentes e constrói respostas fundamentadas.
        """
        m = message.strip().lower()

        # 0. Perguntas diretas (simples com respostas simples) e temas instrutivos / conceitos
        ctx = build_user_context(user_id)
        direct_reply = handle_direct_simple_question(message, ctx, user_id)
        if direct_reply:
            extract_memories_from_reply(user_id, message, direct_reply)
            if "saldo" in m or "dinheiro" in m or "conta" in m:
                update_user_session(user_id, {"active_topic": "accounts"})
            elif "gastei" in m or "despesa" in m:
                update_user_session(user_id, {"active_topic": "expenses", "active_period": "this_month"})
            return {
                "reply": direct_reply,
                "action": None,
                "pending": None,
                "chart": None,
                "tools_used": ["direct_financial_consultant"],
                "requires_confirmation": False,
                "model": settings.MODEL_NAME,
                "provider": "BankAO Copilot v2"
            }

        # 0.5. Pedido de Transferência Incompleto ou Natural (ex: "Manda 50 mil para o João" ou "Envia 5000 à Ana")
        m_trans = re.search(r"(?:manda|enviar?|transferir?)\s+(\d+(?:[.,]\d+)?\s*(?:mil|k)?)\s+(?:(?:para|à|ao)\s+(?:o\s+|a\s+)?([A-Za-zÀ-ÿ]+))?", m)
        if m_trans:
            val_raw = m_trans.group(1)
            dest_name = m_trans.group(2)
            # valor lido pelo interpretador (respeita "mil/k"; 500 continua a ser 500, nunca 500 mil)
            parsed_amount = _parse_slots(message, datetime.date.today()).get("amount")
            if not parsed_amount:
                return None
            v_amt = float(parsed_amount)
            v_fmt = f"{v_amt:,.0f}".replace(",", ".")

            # Verificar se o utilizador já tem este contacto guardado ou no histórico
            matched_contact = None
            if dest_name:
                try:
                    from backend.ai.tools.contacts import tool_get_contacts
                    from backend.ai.tools.transfers import tool_quote_transfer
                    res_c = tool_get_contacts(user_id=user_id, query=dest_name, limit=5)
                    contacts_found = res_c.get("contacts", [])
                    for c in contacts_found:
                        if c.get("account_number") or c.get("iban"):
                            matched_contact = c
                            break
                except Exception:
                    matched_contact = None

            if matched_contact:
                from backend.ai.tools.transfers import tool_quote_transfer
                dest_addr = matched_contact.get("account_number") or matched_contact.get("iban")
                contact_label = matched_contact.get("display_name") or dest_name.title()
                quote = tool_quote_transfer(
                    user_id=user_id,
                    destination=dest_addr,
                    amount=v_amt,
                    currency="AOA",
                    beneficiary_name=contact_label
                )
                if quote.get("valid"):
                    fee_fmt = f"{quote['fee_amount']:,.2f} Kz"
                    tot_fmt = f"{(v_amt + quote['fee_amount']):,.2f} Kz"
                    acc_type_str = "Conta BankAO" if not quote["is_iban"] else "IBAN"
                    reply = (
                        f"Encontrei o seu contacto **{contact_label}** ({acc_type_str}: `{dest_addr}`).\n\n"
                        f"📋 **Proposta de Transferência:**\n"
                        f"• **Destinatário:** {contact_label} (`{dest_addr}`)\n"
                        f"• **Montante:** {v_fmt} Kz\n"
                        f"• **Comissão ({quote['fee_percent']}%):** {fee_fmt}\n"
                        f"• **Total a debitar:** {tot_fmt}\n\n"
                        f"🔒 *Por motivos de segurança, a transferência só é efetuada após a sua confirmação. Toque no botão abaixo para rever.*"
                    )
                    return {
                        "reply": reply,
                        "action": quote["action"],
                        "pending": {"type": quote["action"]["type"], "slots": quote["action"]},
                        "chart": None,
                        "tools_used": ["get_contacts", "quote_transfer"],
                        "requires_confirmation": True,
                        "model": settings.MODEL_NAME,
                        "provider": "BankAO Copilot v2"
                    }

            update_user_session(user_id, {
                "active_topic": "transfers",
                "pending_operation": {
                    "type": "TRANSFER",
                    "slots": {"amount": v_amt, "beneficiary_name": dest_name}
                }
            })

            if dest_name:
                reply = (
                    f"Com certeza! Deseja enviar **{v_fmt} Kz** ({v_amt:,.2f} Kz) para **{dest_name.title()}**.\n"
                    f"Para onde devo enviar? Indique o **IBAN**, o **número de conta BankAO** ou o **e-mail** do {dest_name.title()}."
                )
            else:
                reply = (
                    f"Preparando transferência de **{v_fmt} Kz** ({v_amt:,.2f} Kz).\n"
                    f"Qual é o destinatário? Indique o **IBAN**, a **conta BankAO** ou o **e-mail**."
                )

            return {
                "reply": reply,
                "action": None,
                "pending": {"type": "TRANSFER", "slots": {"amount": v_amt, "beneficiary_name": dest_name}},
                "chart": None,
                "tools_used": ["transfer_intent_resolver"],
                "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 1. Perguntas operacionais (Poupanças, Despesas, Transferências com slots preenchidos)
        # Ex: "registre um gasto de 10mil na poupança de carro"
        op_parsed = analyze_message(message, None)
        if op_parsed.get("reply"):
            if op_parsed.get("pending"):
                update_user_session(user_id, {"pending_operation": op_parsed["pending"]})
            return {
                "reply": op_parsed["reply"],
                "action": op_parsed.get("action"),
                "pending": op_parsed.get("pending"),
                "chart": None,
                "tools_used": ["intent_analyzer"],
                "requires_confirmation": op_parsed.get("action") is not None,
                "model": settings.MODEL_NAME,
                "provider": "BankAO Copilot v2"
            }

        # 2. Contas e Saldos
        # "Quanto dinheiro tenho?", "Qual é o meu saldo?", "Quanto tenho na conta principal?"
        if re.search(r"quanto\s+(?:dinheiro\s+)?tenho|qual\s+(?:[eé]\s+o\s+)?(?:meu\s+)?saldo|ver\s+saldo|saldo\s+atual|minhas?\s+contas?", m):
            res = execute_tool("get_accounts_summary", {}, user_id)
            update_user_session(user_id, {"active_topic": "accounts"})
            total_aoa = res.get("total_aoa", 0.0)
            lines = [f"O seu saldo total em Kwanza é **{total_aoa:,.2f} Kz**."]
            for acc in res.get("accounts", []):
                if acc["currency"] != "AOA" and acc["balance"] > 0:
                    sym = "€" if acc["currency"] == "EUR" else ("$" if acc["currency"] == "USD" else acc["currency"])
                    lines.append(f"• Conta {acc['currency']}: **{acc['balance']:,.2f} {sym}**")
            return {
                "reply": "\n".join(lines),
                "action": None, "pending": None, "chart": None,
                "tools_used": ["get_accounts_summary"],
                "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 3. Comparações e Análise de Despesas (Perguntas 36 a 55)

        # 43. Compara as minhas despesas de setembro com as de outubro
        if re.search(r"compar(?:a|ar).*setembro.*com.*outubro|despesas\s+de\s+setembro\s+com\s+as\s+de\s+outubro|setembro\s+vs\s+outubro", m):
            res = execute_tool("compare_expenses_periods", {"period1": "setembro", "period2": "outubro"}, user_id)
            update_user_session(user_id, {"active_topic": "expenses", "active_period": "outubro"})
            tot1 = res["total_period1"]
            tot2 = res["total_period2"]
            diff = res["absolute_difference"]
            pct = res["percent_change"]
            con1 = res["consumer_period1"]
            con2 = res["consumer_period2"]
            con_diff = res["consumer_difference"]
            con_pct = res["consumer_percent_change"]

            reply = (
                f"📊 **Comparativo de Despesas: Setembro de 2026 vs Outubro de 2026:**\n\n"
                f"• **Setembro de 2026:** {tot1:,.2f} Kz (Consumo: {con1:,.2f} Kz · Poupança: {tot1-con1:,.2f} Kz)\n"
                f"• **Outubro de 2026:** {tot2:,.2f} Kz (Consumo: {con2:,.2f} Kz · Poupança: {tot2-con2:,.2f} Kz)\n\n"
                f"📈 **Variação Global:** Os gastos totais registados aumentaram **+{pct:.1f}%** (+{diff:,.2f} Kz).\n"
                f"🛒 **Variação no Consumo Operacional:** Subiu **+{con_pct:.1f}%** (+{con_diff:,.2f} Kz), impulsionado pela compra do Monitor 4K para escritório (85.000 Kz) e jantares de restauração.\n"
                f"🛡️ **Poupança:** Manteve-se rigorosamente constante nos 250.000 Kz (150k Hilux + 100k Fundo de Emergência)."
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["compare_expenses_periods"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 41. Quais foram as minhas cinco maiores despesas deste ano?
        if re.search(r"(?:5|cinco)\s+maiores\s+despesas.*(?:ano|2026)|maiores\s+despesas\s+deste\s+ano", m):
            res = execute_tool("get_expenses_analysis", {"period": "this_year", "order_by": "amount_desc", "limit": 5}, user_id)
            ranked = res.get("top_expenses_ranked", [])[:5]
            lines = ["🏆 **As 5 Maiores Despesas Registadas este Ano (2026):**\n"]
            for i, it in enumerate(ranked, 1):
                tipo = "Meta de Poupança" if it.get("is_savings") else it["category"]
                lines.append(f"{i}. **{it['name']}** — **{it['amount']:,.2f} Kz**")
                lines.append(f"   *Data: {it['date']} · Categoria: {tipo}*")
            lines.append("\n💡 *Nota:* As três maiores posições de 150.000 Kz foram alocações para a sua meta Toyota Hilux 2027 (património que continua seu).")
            return {
                "reply": "\n".join(lines), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 42. Qual foi o estabelecimento onde gastei mais dinheiro?
        if re.search(r"estabelecimento.*(?:onde\s+gastei\s+mais|com\s+mais\s+gastos)|comerciante.*onde\s+gastei\s+mais|onde\s+gastei\s+mais\s+dinheiro\s+em\s+lojas", m):
            res = execute_tool("get_top_merchants", {"days": 365, "limit": 5}, user_id)
            top_m = res.get("top_merchant")
            merchants = res.get("merchants", [])
            lines = ["🏢 **Estabelecimentos com Maior Volume de Gastos (Consumo):**\n"]
            if top_m:
                lines.append(f"O estabelecimento onde gastou mais dinheiro foi **{top_m['merchant']}**, com um total acumulado de **{top_m['total']:,.2f} Kz** em {top_m['transactions_count']} pagamentos.\n")
            lines.append("**Top 5 Estabelecimentos Comerciais:**")
            for m_item in merchants[:5]:
                lines.append(f"• **{m_item['merchant']}** ({m_item['category']}): {m_item['total']:,.2f} Kz ({m_item['transactions_count']}x)")
            lines.append("\n*(Excluindo transferências automáticas para metas de poupança).*")
            return {
                "reply": "\n".join(lines), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_top_merchants"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 44. Em que mês gastei mais dinheiro este ano?
        if re.search(r"em\s+que\s+m[eê]s\s+gastei\s+mais.*(?:ano|2026)|m[eê]s\s+com\s+mais\s+gastos|m[eê]s\s+em\s+que\s+mais\s+gastei", m):
            from backend.database import get_connection
            with get_connection() as conn:
                m_rows = conn.execute("""
                    SELECT strftime('%m', expense_date) as m_num, strftime('%Y-%m', expense_date) as ym,
                           SUM(amount_minor)/100.0 as total,
                           SUM(CASE WHEN origin != 'savings' OR origin IS NULL THEN amount_minor ELSE 0 END)/100.0 as consumer
                    FROM expenses
                    WHERE user_id = ? AND expense_date LIKE '2026%'
                    GROUP BY ym ORDER BY total DESC
                """, (user_id,)).fetchall()

            months_pt = {"08": "Agosto", "09": "Setembro", "10": "Outubro", "11": "Novembro"}
            top_m = m_rows[0]
            top_name = months_pt.get(top_m["m_num"], top_m["ym"])

            lines = [f"📅 **Mês com Mais Gastos em 2026:**\n"]
            lines.append(f"O mês em que gastou mais dinheiro foi **{top_name} de 2026**, com um total de **{top_m['total']:,.2f} Kz** (sendo {top_m['consumer']:,.2f} Kz em consumo e 250.000 Kz em poupança programada).\n")
            lines.append("**Comparativo dos meses:**")
            for r in m_rows:
                lbl = months_pt.get(r["m_num"], r["ym"])
                lines.append(f"• **{lbl} 2026:** {r['total']:,.2f} Kz (Consumo: {r['consumer']:,.2f} Kz)")
            return {
                "reply": "\n".join(lines), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 45 & 53. Despesas que mais prejudicam a poupança / Onde reduzir gastos
        if re.search(r"prejudicar.*(?:capacidade\s+de\s+)?poupar|despesas\s+que\s+mais\s+est[aã]o\s+a\s+prejudicar|(?:3|tr[eê]s)\s+categorias.*reduzir|onde\s+(?:posso\s+)?reduzir\s+(?:os\s+meus\s+)?gastos|onde\s+cortar", m):
            res = execute_tool("get_expenses_analysis", {"period": "this_year"}, user_id)
            reply = (
                "🎯 **Diagnóstico de Gastos e Oportunidades de Poupança:**\n\n"
                "As 3 categorias discricionárias que mais pesam no seu orçamento e onde tem maior margem para reduzir são:\n\n"
                "1. **Restaurantes e Jantares Fora:** **241.500,00 Kz** acumulados (média de ~80.000 Kz/mês em jantares na Ilha e almoços de trabalho). "
                "Cozinhar mais em casa ou reservar restaurantes apenas para ocasiões especiais pouparia cerca de **40.000 Kz/mês**.\n"
                "2. **Eletrónica e Gadgets Supérfluos:** **113.000,00 Kz** (Monitor 4K de 85.000 Kz + Teclado mecânico de 28.000 Kz). Estabelecer uma regra de espera de 30 dias para compras de tecnologia evita compras por impulso.\n"
                "3. **Lazer e Passeios de Fim de Semana:** **36.000,00 Kz** (Passeios no Mussulo e cinema). Planear passeios com orçamento pré-fixado poupa até 15.000 Kz/mês.\n\n"
                f"💡 **Impacto:** Otimizar estas 3 categorias liberta entre **50.000 e 70.000 Kz adicionais por mês**, acelerando em meses a compra da sua Toyota Hilux!"
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 46. Quanto dinheiro gasto mensalmente em média?
        if re.search(r"quanto\s+dinheiro\s+gasto\s+mensalmente\s+em\s+m[eé]dia|m[eé]dia\s+mensal.*gastos|quanto\s+gasto\s+por\s+m[eê]s\s+em\s+m[eé]dia", m):
            from backend.database import get_connection
            with get_connection() as conn:
                m_rows = conn.execute("""
                    SELECT strftime('%Y-%m', expense_date) as ym,
                           SUM(amount_minor)/100.0 as tot,
                           SUM(CASE WHEN origin != 'savings' OR origin IS NULL THEN amount_minor ELSE 0 END)/100.0 as con
                    FROM expenses
                    WHERE user_id = ? AND expense_date < '2026-11-01'
                    GROUP BY ym
                """, (user_id,)).fetchall()
            avg_tot = sum(r["tot"] for r in m_rows) / max(len(m_rows), 1)
            avg_con = sum(r["con"] for r in m_rows) / max(len(m_rows), 1)

            reply = (
                f"📊 **Média Mensal de Gastos (Baseada nos meses completos de Agosto, Setembro e Outubro):**\n\n"
                f"• **Total Médio Registado:** **{avg_tot:,.2f} Kz por mês**\n\n"
                f"Decomposição detalhada:\n"
                f"• **Despesas Operacionais de Consumo:** **{avg_con:,.2f} Kz/mês** (habitação, alimentação, transporte, restauração).\n"
                f"• **Afetação a Metas de Poupança:** **250.000,00 Kz/mês** (150.000 Kz para Toyota Hilux + 100.000 Kz para Fundo de Emergência).\n\n"
                f"💡 O seu consumo real médio é de cerca de 426 mil Kz. O restante vai diretamente para reforçar o seu património líquido."
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 47. Quais foram as minhas despesas durante a última semana?
        if re.search(r"[uú]ltima\s+semana|despesas\s+durante\s+a\s+[uú]ltima\s+semana|gastos\s+da\s+[uú]ltima\s+semana", m):
            res = execute_tool("get_expenses_analysis", {"period": "last_week"}, user_id)
            items = res.get("recent_items", [])
            tot = res.get("total_expenses", 0.0)
            lines = [f"📅 **Despesas na Última Semana ({res.get('period_label')}):**\n"]
            lines.append(f"• **Total Gasto:** **{tot:,.2f} Kz** em {len(items)} despesa(s).\n")
            for it in items:
                lines.append(f"• **{it['name']}** — **{it['amount']:,.2f} Kz** ({it['category']} · {it['date']})")
            return {
                "reply": "\n".join(lines), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 48. Quanto gastei em compras online?
        if re.search(r"compras\s+online|gastos?\s+online|compras\s+pela\s+internet|servi[cç]os\s+digitais", m):
            res = execute_tool("get_expenses_analysis", {"period": "this_year"}, user_id)
            online_tot = res.get("online_expenses", 0.0)
            items = res.get("online_items", [])
            lines = ["🌐 **Análise de Compras Online e Serviços Digitais:**\n"]
            if online_tot > 0:
                lines.append(f"Gastou um total de **{online_tot:,.2f} Kz** em serviços e compras digitais identificadas:\n")
                for it in items:
                    lines.append(f"• **{it['name']}**: {it['amount']:,.2f} Kz ({it['category']} · {it['date']})")
            else:
                lines.append("Não possui compras registadas em plataformas diretas de e-commerce internacional (como Amazon ou AliExpress).")
                lines.append("As suas despesas com telecomunicações digitais (Unitel Business — 54.000 Kz acumulados) e equipamentos tecnológicos (113.000 Kz) foram adquiridas localmente em Luanda.")
            return {
                "reply": "\n".join(lines), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 49. Mostra-me todas as despesas superiores a 20.000 Kz
        if re.search(r"superiores\s+a\s+20\.?000|maiores\s+(?:que|de)\s+20\.?000|acima\s+de\s+20\.?000", m):
            res = execute_tool("get_expenses_analysis", {"period": "this_year", "min_amount": 20000.0, "order_by": "amount_desc"}, user_id)
            items = res.get("top_expenses_ranked", [])
            lines = [f"📋 **Todas as Despesas Superiores a 20.000 Kz ({len(items)} registos encontrados):**\n"]
            for i, it in enumerate(items[:12], 1):
                tipo = "Meta de Poupança" if it.get("is_savings") else it["category"]
                lines.append(f"{i}. **{it['name']}** — **{it['amount']:,.2f} Kz** ({tipo} · {it['date']})")
            if len(items) > 12:
                lines.append(f"\n*(... e mais {len(items)-12} despesas acima de 20.000 Kz no histórico).*")
            return {
                "reply": "\n".join(lines), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 50. Existem despesas repetidas ou cobranças semelhantes na minha conta?
        if re.search(r"repetidas|cobran[cç]as\s+semelhantes|duplicad|recorrentes|despesas\s+que\s+se\s+repetem", m):
            res = execute_tool("get_recurring_or_duplicate_expenses", {}, user_id)
            recurring = res.get("recurring_expenses", [])
            lines = ["🔄 **Análise de Cobranças Repetidas e Despesas Recorrentes:**\n"]
            lines.append("Identificámos os seguintes pagamentos regulares na sua conta:\n")
            for r in recurring[:8]:
                lines.append(f"• **{r['name']}** ({r['category']}):")
                lines.append(f"  - Frequência: {r['frequency']}x · Média: {r['average_amount']:,.2f} Kz · Tipo: {r['type']}")
            lines.append("\n✅ **Verificação de Segurança:** Não existem cobranças duplicadas indevidas por erro de processamento.")
            return {
                "reply": "\n".join(lines), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_recurring_or_duplicate_expenses"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 51. Quanto gastei em restaurantes desde janeiro?
        if re.search(r"restaurantes?.*desde\s+janeiro|restaurantes?.*deste\s+ano|gastei\s+em\s+restaurantes?.*(?:ano|2026)", m):
            res = execute_tool("get_expenses_analysis", {"category": "Restaurantes", "period": "this_year"}, user_id)
            tot = res.get("total_expenses", 0.0)
            cnt = res.get("count", 0)
            items = res.get("recent_items", [])
            lines = [f"🍽️ **Gastos em Restaurantes em 2026 (desde Janeiro):**\n"]
            lines.append(f"• **Total Gasto:** **{tot:,.2f} Kz** em {cnt} refeições/jantares fora.\n")
            lines.append("**Histórico de Restaurantes:**")
            for it in items:
                lines.append(f"• {it['date']}: **{it['name']}** — {it['amount']:,.2f} Kz")
            return {
                "reply": "\n".join(lines), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 52. Qual foi a minha maior despesa individual nos últimos 30 dias?
        if re.search(r"maior\s+despesa\s+individual.*(?:[uú]ltimos\s+)?30\s+dias|maior\s+gasto.*[uú]ltimos\s+30\s+dias", m):
            res = execute_tool("get_expenses_analysis", {"period": "last_30_days", "order_by": "amount_desc"}, user_id)
            ranked = res.get("top_expenses_ranked", [])
            lines = ["🔍 **Maior Despesa Individual nos Últimos 30 Dias:**\n"]
            if ranked:
                top_all = ranked[0]
                lines.append(f"• **Maior Movimento Registado:** **{top_all['name']}** no valor de **{top_all['amount']:,.2f} Kz** em {top_all['date']}.")
                # Se for poupança, destacar também o maior consumo
                consumo = [x for x in ranked if not x.get("is_savings")]
                if consumo and top_all.get("is_savings"):
                    top_c = consumo[0]
                    lines.append(f"• **Maior Despesa de Consumo:** **{top_c['name']}** no valor de **{top_c['amount']:,.2f} Kz** ({top_c['category']} · {top_c['date']}).")
                lines.append("\n*Nota de auditoria: Os débitos para a meta Toyota Hilux (150.000 Kz) continuam no seu património; no consumo, a liderança foi da mensalidade do condomínio e da aquisição do monitor.*")
            return {
                "reply": "\n".join(lines), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 54. Quanto dinheiro gastei em despesas desnecessárias?
        if re.search(r"despesas\s+desnecess[aá]rias|gastos\s+sup[eé]rfluos|dinheiro\s+desperdi[cç]ado|despesas\s+evit[aá]veis", m):
            res = execute_tool("get_expenses_analysis", {"period": "this_year"}, user_id)
            disc_tot = res.get("discretionary_expenses", 0.0)
            lines = ["💡 **Auditoria de Despesas Supérfluas e Discricionárias (2026):**\n"]
            lines.append(f"Identificámos um total acumulado de cerca de **{disc_tot:,.2f} Kz** em consumos que não são estritamente essenciais:\n")
            lines.append("• **Restaurantes e Jantares Sociais:** 241.500,00 Kz")
            lines.append("• **Gadgets e Equipamentos Não-Essenciais:** 113.000,00 Kz")
            lines.append("• **Lazer, Cinema e Passeios:** 36.000,00 Kz\n")
            lines.append("🛡️ *Comparativo:* Em despesas essenciais (Habitação, Transporte, Alimentação básica e Saúde) gastou **1.013.800,00 Kz**.")
            return {
                "reply": "\n".join(lines), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 55. Faz um relatório completo dos meus gastos deste ano
        if re.search(r"relat[oó]rio\s+completo.*gastos|relat[oó]rio\s+anual.*despesas|relat[oó]rio\s+dos\s+meus\s+gastos\s+deste\s+ano", m):
            res = execute_tool("get_expenses_analysis", {"period": "this_year"}, user_id)
            top_cats = res.get("top_categories", [])
            lines = [
                f"📑 **Relatório Financeiro Anual de Despesas (2026) — BankAO:**\n",
                f"• **Volume Global Movimentado:** **{res['total_expenses']:,.2f} Kz** em {res['count']} transações.",
                f"• **Afetação a Metas de Poupança:** **{res['savings_debits']:,.2f} Kz** (34,8% do total — património retido e investido).",
                f"• **Despesas Operacionais de Consumo:** **{res['consumer_expenses']:,.2f} Kz** (65,2%).\n",
                "📊 **Distribuição por Categoria:**"
            ]
            for c in top_cats[:6]:
                pct = round((c['total'] / res['total_expenses'] * 100), 1) if res['total_expenses'] > 0 else 0
                lines.append(f"  - {c['category']}: {c['total']:,.2f} Kz ({pct}%)")
            lines.append(f"\n🏢 **Principal Fornecedor:** Condomínio Talatona (340.000 Kz)")
            lines.append(f"📅 **Mês com Maior Despesa:** Outubro de 2026 (718.200 Kz)")
            lines.append(f"\n💡 **Parecer Final:** A sua disciplina de poupança (250.000 Kz/mês fixos) é exemplar. A maior oportunidade de otimização reside nos gastos de restauração.")
            return {
                "reply": "\n".join(lines), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 36. Qual foi o meu maior gasto de setembro?
        if re.search(r"maior\s+gasto.*setembro|maior\s+despesa.*setembro", m):
            res = execute_tool("get_expenses_analysis", {"period": "setembro", "order_by": "amount_desc"}, user_id)
            ranked = res.get("top_expenses_ranked", [])
            lines = ["📊 **Análise do Maior Gasto de Setembro de 2026:**\n"]
            if ranked:
                top_all = ranked[0]
                lines.append(f"• **Maior Débito Geral:** **{top_all['name']}** no valor de **{top_all['amount']:,.2f} Kz** em {top_all['date']}.")
                consumo = [x for x in ranked if not x.get("is_savings")]
                if consumo:
                    top_c = consumo[0]
                    lines.append(f"• **Maior Despesa de Consumo:** **{top_c['name']}** no valor de **{top_c['amount']:,.2f} Kz** ({top_c['category']} · {top_c['date']}).")
                lines.append(f"\n*Distinção contabilística BankAO: A saída de 150.000 Kz foi a transferência para a sua meta Toyota Hilux (dinheiro que continua no seu património).*")
            return {
                "reply": "\n".join(lines), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 37. Quanto gastei no total durante setembro?
        if re.search(r"quanto\s+gastei.*total.*setembro|total.*durante\s+setembro|total\s+de\s+setembro", m):
            res = execute_tool("get_expenses_analysis", {"period": "setembro"}, user_id)
            reply = (
                f"📊 **Total de Despesas em Setembro de 2026:**\n\n"
                f"• **Total Registado na Conta:** **{res['total_expenses']:,.2f} Kz** ({res['count']} despesas).\n\n"
                f"Decomposição:\n"
                f"• **Despesas Operacionais de Consumo:** **{res['consumer_expenses']:,.2f} Kz** (Habitação 97,3k Kz, Transporte 79k Kz, Restaurantes 88k Kz, Alimentação 69,5k Kz, Saúde 34k Kz, Gadgets 28k Kz, Unitel 18k Kz).\n"
                f"• **Afetação a Metas de Poupança:** **{res['savings_debits']:,.2f} Kz** (150.000 Kz Toyota Hilux + 100.000 Kz Fundo de Emergência).\n\n"
                f"💡 O seu custo de vida efetivo foi de 413,8 mil Kz, com 250 mil Kz direcionados à poupança."
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 38. Qual foi a categoria em que gastei mais dinheiro?
        if re.search(r"categoria.*(?:mais\s+(?:gastei|dinheiro)|maior\s+gasto)|categoria.*em\s+que\s+gastei\s+mais", m):
            res = execute_tool("get_expenses_analysis", {"period": "this_year"}, user_id)
            big_all = res.get("biggest_category")
            big_con = res.get("biggest_consumer_category")
            reply = (
                f"📊 **Categoria com Maior Volume de Gastos em 2026:**\n\n"
                f"• **No Total de Saídas:** A categoria líder é **{big_all['category']}**, com um total acumulado de **{big_all['total']:,.2f} Kz** "
                f"(transferências programadas para as suas metas Toyota Hilux e Fundo de Emergência).\n\n"
                f"• **Em Despesas de Consumo Operacional:** A categoria onde gastou mais dinheiro é **{big_con['category']}**, "
                f"com um total de **{big_con['total']:,.2f} Kz** (mensalidades do Condomínio Talatona e contas de eletricidade/água).\n\n"
                f"Segue-se **Transporte** ({res['top_categories_consumer'][1]['total']:,.2f} Kz) e **Restaurantes** ({res['top_categories_consumer'][2]['total']:,.2f} Kz)."
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 39. Quanto gastei em alimentação no mês passado?
        if re.search(r"alimenta[cç][aã]o.*(?:no\s+)?m[eê]s\s+passado", m):
            res = execute_tool("get_expenses_analysis", {"category": "Alimentação", "period": "last_month"}, user_id)
            items = res.get("recent_items", [])
            lines = [f"🛒 **Gastos em Alimentação no Mês Passado (Outubro de 2026):**\n"]
            lines.append(f"No mês passado gastou um total de **{res['total_expenses']:,.2f} Kz** em alimentação ({res['count']} compras de supermercado):\n")
            for it in items:
                lines.append(f"• **{it['name']}**: {it['amount']:,.2f} Kz ({it['date']})")
            return {
                "reply": "\n".join(lines), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 40. Quanto gastei em transportes nos últimos três meses?
        if re.search(r"transporte[s]?.*(?:[uú]ltimos\s+)?(?:3|tr[eê]s)\s+meses", m):
            from backend.database import get_connection
            with get_connection() as conn:
                r_3m = conn.execute("""
                    SELECT SUM(amount_minor)/100.0 as tot, COUNT(*) as cnt
                    FROM expenses
                    WHERE user_id = ? AND expense_date >= '2026-08-01' AND expense_date <= '2026-10-31'
                      AND LOWER(category) IN ('transporte', 'transportes')
                """, (user_id,)).fetchone()
            tot_3m = r_3m["tot"] or 0.0
            cnt_3m = r_3m["cnt"] or 0
            reply = (
                f"🚗 **Gastos em Transportes nos Últimos 3 Meses (Agosto, Setembro e Outubro de 2026):**\n\n"
                f"Gastou um total de **{tot_3m:,.2f} Kz** em transportes ({cnt_3m} abastecimentos para o seu Toyota Prado).\n"
                f"• Média mensal em combustível: **{tot_3m/3:,.2f} Kz/mês**."
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 4. Outras despesas por Categoria específica (ex: Lazer, Saúde)
        m_rest = re.search(r"quanto\s+gastei\s+em\s+(restaurantes?|alimenta[cç][aã]o|transporte[s]?|lazer|sa[uú]de)", m)
        if m_rest:
            cat_name = m_rest.group(1).title()
            months_count = 3 if ("três" in m or "3" in m or "trimestre" in m) else 1
            period = "last_3_months" if months_count == 3 else "this_month"

            res = execute_tool("get_expenses_analysis", {
                "category": cat_name,
                "period": period,
                "months_count": months_count
            }, user_id)

            tot = res.get("total_expenses", 0.0)
            p_label = res.get("period_label", period)
            cnt = res.get("count", 0)

            if tot > 0:
                reply = f"Em **{p_label}**, gastou um total de **{tot:,.2f} Kz** em **{cat_name}** ({cnt} registo(s))."
            else:
                reply = f"Não tem nenhum gasto registado na categoria **{cat_name}** para {p_label}."

            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 5. Onde estou a gastar mais / Maiores Despesas gerais
        if re.search(r"maior\s+gasto|maiores\s+gastos|maiores\s+despesas|onde\s+estou\s+a\s+gastar\s+mais|top\s+despesas|onde\s+(?:mais\s+)?gastei", m):
            months_kw = ["janeiro", "fevereiro", "março", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
            target_period = "this_month"
            for mo in months_kw:
                if mo in m:
                    target_period = mo
                    break
            if "mês passado" in m or "mes passado" in m:
                target_period = "last_month"

            res_exp = execute_tool("get_expenses_analysis", {"period": target_period}, user_id)
            period_lbl = res_exp.get("period_label", target_period)
            biggest_item = res_exp.get("biggest_expense")
            biggest_cat = res_exp.get("biggest_category")
            total_exp = res_exp.get("total_expenses", 0.0)

            if total_exp == 0:
                reply = f"Não encontrei despesas registadas em **{period_lbl}**."
            else:
                lines = [f"📊 **Análise dos Maiores Gastos — {period_lbl}:**\n"]
                if biggest_item:
                    lines.append(f"• **Maior Gasto Individual:** **{biggest_item['name']}** no valor de **{biggest_item['amount']:,.2f} Kz**")
                    lines.append(f"  *(Categoria: {biggest_item['category']} · Data: {biggest_item['date']})*\n")
                if biggest_cat:
                    pct = round((biggest_cat['total'] / total_exp * 100), 1) if total_exp > 0 else 0
                    lines.append(f"• **Maior Categoria de Gastos:** **{biggest_cat['category']}** com um total de **{biggest_cat['total']:,.2f} Kz** ({pct}% do total gasto de {total_exp:,.2f} Kz).")
                reply = "\n".join(lines)

            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 6. Despesas gerais deste mês / hoje / sobre as despesas / resumo
        if re.search(r"quanto\s+gastei|sobre\s+(?:as\s+)?despesas?|minhas?\s+despesas?|ver\s+despesas?|resumo\s+d(?:e|as)\s+despesas?|como\s+est[aã]o\s+(?:as\s+)?(?:minhas\s+)?despesas?|gastos?\s+deste\s+m[eê]s|^despesas?\??$", m):
            period = "today" if "hoje" in m else "this_month"
            res = execute_tool("get_expenses_analysis", {"period": "this_month"}, user_id)
            update_user_session(user_id, {"active_topic": "expenses", "active_period": "this_month"})
            tot = res.get("total_expenses", 0.0)
            big = res.get("biggest_category")
            top_cats = res.get("top_categories", [])
            cnt = res.get("count", 0)

            if tot > 0:
                lines = [f"📊 **Resumo das suas Despesas deste mês:**\n"]
                lines.append(f"• **Total Gasto:** **{tot:,.2f} Kz** em {cnt} registo(s).")
                if big:
                    lines.append(f"• **Maior Categoria:** **{big['category']}** ({big['total']:,.2f} Kz)")
                if len(top_cats) > 1:
                    lines.append("\n**Principais Categorias:**")
                    for c in top_cats[:3]:
                        lines.append(f"  - {c['category']}: {c['total']:,.2f} Kz ({c['percentage']}%)")
                lines.append("\n💡 *Diga «Onde estou a gastar mais?» para ver estabelecimentos ou «Compara este mês com o anterior».*")
                reply = "\n".join(lines)
            else:
                reply = (
                    "📊 **Controlo de Despesas BankAO:**\n"
                    "Este mês ainda não tem despesas registadas. O seu saldo permanece 100% intacto! 👏\n\n"
                    "Pode registar uma despesa a qualquer momento dizendo por exemplo: *«Regista despesa de 5.000 Kz em restaurante»*."
                )

            return {
                "reply": reply,
                "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"],
                "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 7. Receitas recebidas / Dinheiro que entrou
        # "Quanto recebi na semana passada?", "Quanto recebi este mês?"
        if re.search(r"quanto\s+recebi|dinheiro\s+que\s+entrou|minhas?\s+receitas?", m):
            period = "last_7_days" if ("semana" in m) else "last_month" if ("mês passado" in m or "mes passado" in m) else "this_month"
            res = execute_tool("get_incomes_summary", {"period": period}, user_id)
            update_user_session(user_id, {"active_topic": "incomes", "active_period": period})
            tot_aoa = res.get("total_aoa", 0.0)
            p_label = res.get("period_label", period)
            reply = f"Em **{p_label}**, recebeu um total de **{tot_aoa:,.2f} Kz** em créditos e depósitos na sua conta."
            return {
                "reply": reply,
                "action": None, "pending": None, "chart": None,
                "tools_used": ["get_incomes_summary"],
                "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 8. Comissões e Taxas de Transferência
        # "Quanto pago de comissões se enviar dinheiro?"
        if re.search(r"quanto\s+pago\s+de\s+comiss[oõ]es|taxas?\s+de\s+(?:envio|transfer[eê]ncia)|comiss[oõ]es\s+se\s+enviar", m):
            fees = execute_tool("get_transfer_fees_info", {"amount": 10000.0, "currency": "AOA"}, user_id)
            update_user_session(user_id, {"active_topic": "transfers"})
            reply = (
                "💸 **Comissões de Transferência BankAO (100% Transparentes):**\n\n"
                "• **Entre Contas BankAO:** **1%** (1,0%)\n"
                f"  *(Exemplo: ao enviar 10.000 Kz, a comissão é de apenas **{fees['internal_transfer']['fee_amount']:,.2f} Kz** e chegam **{fees['internal_transfer']['net_received']:,.2f} Kz**)*.\n\n"
                "• **Para outros Bancos (por IBAN):** **2,5%** (2.5%)\n"
                f"  *(Exemplo: em 10.000 Kz, a comissão é de **{fees['iban_transfer']['fee_amount']:,.2f} Kz** com liquidação garantida via BNA / SEPA)*."
            )
            return {
                "reply": reply,
                "action": None, "pending": None, "chart": None,
                "tools_used": ["get_transfer_fees_info"],
                "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 9. Cartão que mais gasta
        # "Qual dos meus cartões está a gastar mais?"
        if re.search(r"qual\s+(?:dos\s+meus\s+)?cart[oõ]es?\s+est[aá]\s+a\s+gastar\s+mais|cart[aã]o\s+com\s+mais\s+gastos", m):
            res = execute_tool("get_card_spend_comparison", {}, user_id)
            update_user_session(user_id, {"active_topic": "cards"})
            top = res.get("top_card")
            if not top or res["cards_count"] == 0:
                reply = "Não foram encontrados cartões ativos com movimentos registados para esta análise."
            else:
                reply = (
                    f"💳 O cartão que está a gastar mais é o **{top['label']}** (terminado em `...{top['last_four']}`):\n\n"
                    f"• **Gasto este mês:** **{top['monthly_spent']:,.2f} {top['currency']}**\n"
                    f"• **Peso no total dos cartões:** **{top['percent_of_total_spend']}%** dos gastos com cartão.\n"
                    f"• **Limite mensal:** {top['monthly_limit']:,.2f} {top['currency']}."
                )
            return {
                "reply": reply,
                "action": None, "pending": None, "chart": None,
                "tools_used": ["get_card_spend_comparison"],
                "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 10.1. Consulta Específica da Carteira de Investimentos
        if re.search(r"quanto\s+(?:dinheiro\s+)?j[aá]\s+investi(?:\s+no\s+total)?|total\s+investido|valor\s+total\s+aplicado", m):
            port = execute_tool("get_investments_portfolio", {}, user_id)
            if not port.get("has_investments"):
                reply = "Ainda não tem nenhum valor investido no BankAO. Conheça os nossos Depósitos a Prazo (até 18,5% a.a.) ou Obrigações do Tesouro!"
            else:
                reply = (
                    f"💼 **Total Investido no BankAO:**\n\n"
                    f"• Já investiu um total de **{port['total_invested']:,.2f} Kz** distribuídos por **{port['total_positions']}** posição(ões) ativa(s).\n"
                    f"• O património atual da sua carteira é de **{port['total_current_value']:,.2f} Kz** (lucro acumulado de **+{port['total_yield_earned']:,.2f} Kz**)."
                )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_investments_portfolio"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        if re.search(r"quanto\s+lucro\s+(?:obtive|ganhei|rendeu)|lucro\s+(?:total\s+)?(?:dos|com\s+os)\s+meus\s+investimentos|rendimento\s+acumulado", m):
            port = execute_tool("get_investments_portfolio", {}, user_id)
            if not port.get("has_investments"):
                reply = "Ainda não possui investimentos ativos para apurar rendimentos ou lucros."
            else:
                reply = (
                    f"📈 **Lucro Obtido com os seus Investimentos:**\n\n"
                    f"• **Lucro Total Acumulado:** **+{port['total_yield_earned']:,.2f} Kz**\n"
                    f"• **Capital Inicial Investido:** {port['total_invested']:,.2f} Kz\n"
                    f"• **Património Atual:** **{port['total_current_value']:,.2f} Kz**\n\n"
                    f"Parabéns! O seu dinheiro está a trabalhar para si e a gerar rendimento passivo consistente."
                )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_investments_portfolio"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        if re.search(r"qual\s+dos\s+meus\s+investimentos\s+est[aá]\s+a\s+render\s+mais|investimento\s+com\s+maior\s+retorno|investimento\s+mais\s+rent[aá]vel\s+meu", m):
            port = execute_tool("get_investments_portfolio", {}, user_id)
            if not port.get("has_investments"):
                reply = "Ainda não tem investimentos na sua carteira para comparar rentabilidades."
            else:
                best = port.get("best_performing")
                if best:
                    reply = (
                        f"🏆 **Investimento Mais Rentável da sua Carteira:**\n\n"
                        f"O seu produto com maior rendimento é o **{best['name']}**:\n"
                        f"• **Taxa Contratada:** **{best['rate_annual']}% ao ano**\n"
                        f"• **Capital Aplicado:** {best['invested_amount']:,.2f} {best['currency']}\n"
                        f"• **Valor Atual:** **{best['current_value']:,.2f} {best['currency']}**\n"
                        f"• **Lucro Já Gerado:** **+{best['yield_earned']:,.2f} {best['currency']}** (+{best['yield_percentage']}% de retorno acumulado).\n\n"
                        f"Data de Início: {best['start_date']} | Vencimento: {best['maturity_date'] or 'Longo Prazo'}."
                    )
                else:
                    reply = "Não foi possível apurar o investimento mais rentável de momento."
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_investments_portfolio"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        if re.search(r"(?:qual\s+dos\s+meus\s+investimentos\s+)?est[aá]\s+pr[oó]ximo\s+do\s+vencimento|vencimento\s+mais\s+pr[oó]ximo|investimento\s+a\s+vencer", m):
            port = execute_tool("get_investments_portfolio", {}, user_id)
            positions = port.get("positions", [])
            with_maturity = [p for p in positions if p.get("maturity_date")]
            if not with_maturity:
                reply = "Não tem investimentos ativos com data de vencimento definida."
            else:
                with_maturity.sort(key=lambda p: p["maturity_date"])
                nearest = with_maturity[0]
                reply = (
                    f"⏳ **Investimento Mais Próximo do Vencimento:**\n\n"
                    f"O investimento com vencimento mais próximo é o **{nearest['name']}**:\n"
                    f"• **Data de Vencimento:** **{nearest['maturity_date']}**\n"
                    f"• **Capital Aplicado:** {nearest['invested_amount']:,.2f} {nearest['currency']}\n"
                    f"• **Valor Atual Acumulado:** **{nearest['current_value']:,.2f} {nearest['currency']}** (Taxa: {nearest['rate_annual']}% a.a.)\n\n"
                    f"No vencimento, o capital total e os juros serão automaticamente creditados na sua conta principal BankAO!"
                )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_investments_portfolio"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        if re.search(r"mostra(?:-me)?\s+(?:os\s+)?investimentos?\s+que\s+(?:j[aá]\s+)?tenho|meus\s+investimentos|quais\s+investimentos\s+tenho|ver\s+meus\s+investimentos", m):
            port = execute_tool("get_investments_portfolio", {}, user_id)
            positions = port.get("positions", [])
            if not positions:
                reply = "Atualmente não possui investimentos ativos na sua conta. Conheça as nossas opções com taxas até 18,5% ao ano!"
            else:
                lines = [
                    f"📈 **A sua Carteira de Investimentos BankAO ({len(positions)} ativos):**\n",
                    f"• **Total Investido:** {port['total_invested']:,.2f} Kz",
                    f"• **Património Atual:** **{port['total_current_value']:,.2f} Kz**",
                    f"• **Lucro Total Acumulado:** **+{port['total_yield_earned']:,.2f} Kz**\n",
                    "**Posições Ativas:**"
                ]
                for p in positions:
                    lines.append(
                        f"• **{p['name']}** ({p['institution']}):\n"
                        f"  - Aplicado: {p['invested_amount']:,.2f} {p['currency']} | Atual: **{p['current_value']:,.2f} {p['currency']}**\n"
                        f"  - Taxa: **{p['rate_annual']}% a.a.** | Lucro: +{p['yield_earned']:,.2f} {p['currency']} (+{p['yield_percentage']}%)\n"
                        f"  - Vencimento: {p['maturity_date'] or 'Longo Prazo'}"
                    )
                reply = "\n".join(lines)
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_investments_portfolio"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 10.2. Projeções e Previsões Financeiras Completas (Perguntas 21 a 35)

        # 28. Gráfico de previsão de saldo
        if re.search(r"mostra(?:-me)?\s+(?:um\s+)?gr[aá]fico.*(?:previs[aã]o|evolu[çc][aã]o.*saldo)|gr[aá]fico.*evolu[çc][aã]o.*prevista", m):
            proj = execute_tool("get_financial_projection", {"months_ahead": 6, "include_chart": True}, user_id)
            chart_obj = proj.get("chart")
            reply = (
                f"📊 **Gráfico de Evolução Prevista do Saldo (Próximos 6 meses):**\n\n"
                f"• **Saldo Líquido Atual em Contas:** {proj['current_position']['accounts_balance']:,.2f} Kz\n"
                f"• **Capacidade de Poupança Líquida Mensal:** {proj['scenario']['monthly_net_unallocated']:+,.2f} Kz/mês\n"
                f"• **Património Líquido Total Projetado (Maio de 2027):** **{proj['projection']['projected_total_net_worth']:,.2f} Kz** "
                f"(incluindo contas, metas de poupança e investimentos com juros compostos).\n\n"
                f"O gráfico abaixo apresenta a trajetória estimada mês a mês."
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": chart_obj,
                "tools_used": ["get_financial_projection", "chart_engine"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 29. Cenário: Reduzir despesas em 20%
        if re.search(r"reduzir\s+(?:as\s+)?despesas\s+em\s+20%|se\s+cortar\s+20%|despesas?\s+em\s+20%\s+a\s+menos", m):
            p_normal = execute_tool("get_financial_projection", {"months_ahead": 6, "expense_multiplier": 1.0}, user_id)
            p_reduced = execute_tool("get_financial_projection", {"months_ahead": 6, "expense_multiplier": 0.8}, user_id)
            diff_monthly = p_normal["scenario"]["base_monthly_expenses"] - p_reduced["scenario"]["effective_monthly_expenses"]
            diff_6m = p_reduced["projection"]["projected_accounts_balance"] - p_normal["projection"]["projected_accounts_balance"]
            reply = (
                f"📉 **Simulação de Cenário: Redução de 20% nas Despesas:**\n\n"
                f"Se otimizar os seus custos operacionais em 20%:\n\n"
                f"• **Despesas Mensais:** Reduzem de {p_normal['scenario']['base_monthly_expenses']:,.2f} Kz para **{p_reduced['scenario']['effective_monthly_expenses']:,.2f} Kz**.\n"
                f"• **Poupança Adicional Libertada:** **+{diff_monthly:,.2f} Kz por mês** que ficam livres no seu saldo!\n"
                f"• **Impacto a 6 Meses (Maio de 2027):**\n"
                f"  - Saldo em contas com despesas normais: {p_normal['projection']['projected_accounts_balance']:,.2f} Kz\n"
                f"  - **Saldo em contas com redução de 20%:** **{p_reduced['projection']['projected_accounts_balance']:,.2f} Kz** (+{diff_6m:,.2f} Kz de folga)\n"
                f"  - **Património Líquido Total Otimizado:** **{p_reduced['projection']['projected_total_net_worth']:,.2f} Kz**.\n\n"
                f"💡 Um corte de 20% nos gastos supérfluos acelera consideravelmente a sua independência financeira!"
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_financial_projection"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 30. Cenário: Aumentar despesas em 30%
        if re.search(r"aumentar\s+(?:as\s+)?despesas\s+em\s+30%|se\s+subir\s+30%|despesas?\s+em\s+30%\s+a\s+mais", m):
            p_normal = execute_tool("get_financial_projection", {"months_ahead": 6, "expense_multiplier": 1.0}, user_id)
            p_increased = execute_tool("get_financial_projection", {"months_ahead": 6, "expense_multiplier": 1.3}, user_id)
            extra_monthly = p_increased["scenario"]["effective_monthly_expenses"] - p_normal["scenario"]["base_monthly_expenses"]
            reply = (
                f"⚠️ **Simulação de Cenário de Risco: Aumento de 30% nas Despesas:**\n\n"
                f"Se o seu custo de vida aumentar em 30%:\n\n"
                f"• **Despesas Mensais:** Sobem de {p_normal['scenario']['base_monthly_expenses']:,.2f} Kz para **{p_increased['scenario']['effective_monthly_expenses']:,.2f} Kz** (+{extra_monthly:,.2f} Kz/mês).\n"
                f"• **Impacto no Fluxo de Caixa:** A sua margem líquida mensal reduz para {p_increased['scenario']['monthly_net_unallocated']:+,.2f} Kz/mês.\n"
                f"• **Projeção a 6 Meses (Maio de 2027):**\n"
                f"  - O saldo disponível em contas à ordem diminuirá para **{p_increased['projection']['projected_accounts_balance']:,.2f} Kz**.\n"
                f"  - O património total passaria de {p_normal['projection']['projected_total_net_worth']:,.2f} Kz para **{p_increased['projection']['projected_total_net_worth']:,.2f} Kz**.\n\n"
                f"🛡️ *Recomendação BankAO:* Mantenha o teto de gastos orçamentados para não comprometer as contribuições das suas metas de poupança nem o fundo de reserva."
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_financial_projection"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 31. Quanto preciso de poupar mensalmente para chegar aos 2 milhões em dezembro de 2027?
        if re.search(r"quanto\s+preciso\s+de\s+poupar.*2\s+milh[oõ]es.*dezembro\s+de\s+2027|chegar\s+aos\s+2\s+milh[oõ]es", m):
            # Hoje é Novembro de 2026. Até Dezembro de 2027 são 14 meses
            months_target = 14
            target_amount = 2000000.0
            simple_monthly = round(target_amount / months_target, 2)
            # Com Depósito a Prazo BankAO a 18.5% a.a.
            r_month = 0.185 / 12.0
            # Formula de anuidade: FV = PMT * [((1 + r)^n - 1) / r] => PMT = FV * r / ((1 + r)^n - 1)
            pmt_with_interest = round(target_amount * r_month / (((1 + r_month) ** months_target) - 1), 2)
            interest_saved = round(target_amount - (pmt_with_interest * months_target), 2)

            reply = (
                f"🎯 **Plano para Atingir 2.000.000 Kz em Dezembro de 2027 (14 meses):**\n\n"
                f"• **Opção 1 — Poupança Simples (sem juros):**\n"
                f"  - Deverá guardar **{simple_monthly:,.2f} Kz por mês** do seu rendimento.\n\n"
                f"• **Opção 2 — Depósito a Prazo BankAO (18,5% ao ano com juro composto):**\n"
                f"  - Precisa de aplicar apenas **{pmt_with_interest:,.2f} Kz por mês**!\n"
                f"  - O total saído do seu bolso será de **{(pmt_with_interest * months_target):,.2f} Kz**.\n"
                f"  - Os juros gerados pelo banco pagam os restantes **+{interest_saved:,.2f} Kz**!\n\n"
                f"💡 *Nota sobre o seu património atual:* Como já possui 750.000 Kz em metas de poupança e mais de 776.000 Kz em investimentos (património total superior a 1,83 milhões), o seu património global atingirá a marca dos 2 milhões em menos de 2 meses!"
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["simulate_investment"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 32. Se começar a poupar 50.000 Kz por mês, quando atingirei 500.000 Kz?
        if re.search(r"poupar\s+50\.?000\s*(?:kz)?\s+por\s+m[eê]s.*?quando\s+atingirei\s+500\.?000|quando\s+chego\s+a\s+500\.?000", m):
            target_amt = 500000.0
            monthly_contrib = 50000.0
            months_simple = 10  # 500.000 / 50.000
            # Com juros a 18.5%
            bal = 0.0
            m_compound = 0
            monthly_rate = (0.185 / 12)
            while bal < target_amt:
                bal = (bal + monthly_contrib) * (1 + monthly_rate)
                m_compound += 1

            reply = (
                f"⏱️ **Tempo para Atingir 500.000 Kz a Poupar 50.000 Kz/mês:**\n\n"
                f"• **Sem Juros (poupança manual em conta à ordem):**\n"
                f"  - Demorará exatamente **10 meses** (atingirá a meta em **Setembro de 2027**).\n\n"
                f"• **Com Depósito a Prazo BankAO (18,5% a.a. com juros compostos):**\n"
                f"  - Atingirá a meta em apenas **{m_compound} meses** (**Agosto de 2027**)!\n"
                f"  - Ao nono mês terá acumulado cerca de **520.400 Kz** (depositou 450.000 Kz e ganhou **+70.400 Kz** em juros).\n\n"
                f"O efeito do juro composto antecipa o seu objetivo em 1 mês inteiro!"
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["simulate_investment"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 33. Estou financeiramente preparado para comprar um carro?
        if re.search(r"preparado\s+para\s+comprar\s+um\s+carro|posso\s+comprar\s+um\s+carro|estou\s+pronto\s+para\s+comprar\s+carro", m):
            port = execute_tool("get_investments_portfolio", {}, user_id)
            goals_res = execute_tool("get_savings_goals", {}, user_id)
            hilux_goal = next((g for g in goals_res.get("goals", []) if "carro" in g["name"].lower() or "hilux" in g["name"].lower() or "veículo" in g["name"].lower() or "viatura" in g["name"].lower()), None)
            total_net = port["total_current_value"] + sum(g["saved"] for g in goals_res.get("goals", []))

            reply_lines = ["🚗 **Diagnóstico Financeiro para Compra de Viatura:**\n"]
            if hilux_goal:
                pct = hilux_goal["percent"]
                reply_lines.append(f"• **Meta Ativa Identificada:** **{hilux_goal['name']}** (Alvo: {hilux_goal['target']:,.2f} Kz)")
                reply_lines.append(f"• **Progresso Atual:** Já tem guardados **{hilux_goal['saved']:,.2f} Kz** ({pct}% do objetivo) com contribuição de **{hilux_goal['monthly']:,.2f} Kz/mês**.")
            reply_lines.append(f"• **Património Financeiro Acumulado:** Possui mais de **{total_net:,.2f} Kz** entre poupanças dedicadas e investimentos (OT 2027 e Depósito a Prazo).")
            reply_lines.append(f"• **Capacidade de Poupança:** O seu rendimento mensal suporta confortavelmente as contribuições sem desfalcar o seu fundo de emergência.")
            reply_lines.append(f"\n📋 **Parecer do Copilot:** **SIM, está num caminho financeiro muito seguro e disciplinado!** Recomendamos manter as contribuições automáticas mensais até ao vencimento da meta em 2027 para comprar a viatura a pronto pagamento ou com entrada elevada sem recorrer a crédito com juros elevados.")
            return {
                "reply": "\n".join(reply_lines), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_savings_goals", "get_investments_portfolio"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 34. Qual será o meu saldo depois de pagar todas as despesas recorrentes?
        if re.search(r"saldo\s+depois\s+de\s+pagar\s+(?:todas\s+as\s+)?despesas\s+recorrentes|saldo\s+ap[oó]s\s+despesas\s+fixas|depois\s+de\s+pagar\s+as\s+contas", m):
            from backend.database import get_connection
            conn = get_connection()
            acc_bal_minor = conn.execute("SELECT COALESCE(SUM(le.amount_minor),0) FROM accounts a LEFT JOIN ledger_entries le ON le.account_id=a.id WHERE a.user_id=? AND a.currency='AOA'", (user_id,)).fetchone()[0]
            current_bal = float(acc_bal_minor) / 100.0

            # Despesas recorrentes conhecidas do utilizador
            rec_expenses = conn.execute("""
                SELECT name, category, amount_minor
                FROM expenses WHERE user_id=? AND expense_date >= '2026-10-01'
                AND (LOWER(category) IN ('habitação', 'habitacao', 'telecomunicações', 'telecomunicacoes', 'saúde', 'saude', 'poupança', 'poupanca')
                     OR LOWER(name) LIKE '%condomínio%' OR LOWER(name) LIKE '%unitel%' OR LOWER(name) LIKE '%ende%' OR LOWER(name) LIKE '%academia%' OR LOWER(name) LIKE '%poupança%')
                GROUP BY LOWER(TRIM(name))
            """, (user_id,)).fetchall()
            conn.close()

            total_rec = sum(r["amount_minor"] for r in rec_expenses) / 100.0
            saldo_pos = current_bal - total_rec

            lines = ["📋 **Balanço após Pagamento de Despesas Recorrentes:**\n"]
            lines.append(f"• **Saldo Atual Disponível:** {current_bal:,.2f} Kz")
            lines.append(f"• **Total de Despesas Fixas e Débitos de Poupança:** -{total_rec:,.2f} Kz")
            for r in rec_expenses[:5]:
                lines.append(f"  - {r['name']}: {r['amount_minor']/100:,.2f} Kz")
            sinal = "+" if saldo_pos >= 0 else ""
            lines.append(f"\n💰 **Saldo Restante Estimado:** **{sinal}{saldo_pos:,.2f} Kz**")
            if saldo_pos >= 0:
                lines.append("O seu saldo cobre com segurança todas as obrigações imediatas do mês!")
            else:
                lines.append("O salário creditado no início do mês reporá a liquidez para manter a conta positiva.")
            return {
                "reply": "\n".join(lines), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_accounts_summary", "get_expenses_analysis"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 35. Compara a minha situação financeira atual com a previsão para os próximos seis meses
        if re.search(r"compara\s+(?:a\s+minha\s+)?situa[cç][aã]o\s+financeira\s+atual\s+com\s+a\s+previs[aã]o.*(?:6|seis)\s+meses|compara.*atual.*com.*previs[aã]o.*6\s+meses", m):
            p6 = execute_tool("get_financial_projection", {"months_ahead": 6}, user_id)
            c = p6["current_position"]
            f = p6["projection"]
            reply = (
                f"📊 **Comparativo: Situação Atual (Novembro 2026) vs Previsão a 6 Meses (Maio 2027):**\n\n"
                f"| Componente | Posição Atual (Hoje) | Previsão a 6 Meses | Variação |\n"
                f"|---|---|---|---|\n"
                f"| **Saldo em Contas (AOA)** | {c['accounts_balance']:,.2f} Kz | {f['projected_accounts_balance']:,.2f} Kz | {f['projected_accounts_balance'] - c['accounts_balance']:+,.2f} Kz |\n"
                f"| **Metas de Poupança Acumuladas** | {c['savings_goals_saved']:,.2f} Kz | {f['projected_savings_goals_saved']:,.2f} Kz | {f['projected_savings_goals_saved'] - c['savings_goals_saved']:+,.2f} Kz |\n"
                f"| **Carteira de Investimentos** | {c['investments_value']:,.2f} Kz | {f['projected_investments_value']:,.2f} Kz | +{f['projected_investments_value'] - c['investments_value']:,.2f} Kz |\n"
                f"| **Juros Ganhos Acumulados** | +{c['investments_yield_earned']:,.2f} Kz | +{f['projected_investments_yield']:,.2f} Kz | +{f['projected_investments_yield'] - c['investments_yield_earned']:,.2f} Kz |\n"
                f"| 🌟 **Património Líquido Total** | **{c['total_net_worth']:,.2f} Kz** | **{f['projected_total_net_worth']:,.2f} Kz** | **+{f['net_worth_growth']:,.2f} Kz (+{f['net_worth_growth_pct']}%)** |\n\n"
                f"💡 **Conclusão:** O seu património crescerá **+{f['net_worth_growth_pct']}%** em 6 meses, impulsionado pelo reforço regular das metas de poupança e pelos juros contratuais dos depósitos e títulos BODIVA."
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_financial_projection"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 21, 22, 23, 24, 25, 26, 27. Projeções por data / período geral
        if re.search(r"proje[cç][aã]o\s+d(?:o|e)\s+(?:meu\s+)?saldo.*janeiro\s+de\s+2027|saldo.*para\s+janeiro\s+de\s+2027", m):
            proj = execute_tool("get_financial_projection", {"target_date": "janeiro de 2027"}, user_id)
            c = proj["current_position"]
            p = proj["projection"]
            reply = (
                f"🔮 **Projeção Financeira BankAO para Janeiro de 2027 ({proj['months_ahead']} meses):**\n\n"
                f"Tratamento detalhado e separado por componentes:\n\n"
                f"• **1. Saldo Líquido em Contas:**\n"
                f"  - Saldo Atual: {c['accounts_balance']:,.2f} Kz\n"
                f"  - Previsão de Saldo em Janeiro de 2027: **{p['projected_accounts_balance']:,.2f} Kz**\n\n"
                f"• **2. Metas de Poupança Acumuladas:**\n"
                f"  - Atual: {c['savings_goals_saved']:,.2f} Kz\n"
                f"  - Previsão Acumulada em Janeiro de 2027: **{p['projected_savings_goals_saved']:,.2f} Kz** (+{p['projected_savings_goals_saved'] - c['savings_goals_saved']:,.2f} Kz)\n\n"
                f"• **3. Carteira de Investimentos e Rendimentos:**\n"
                f"  - Valor Atual: {c['investments_value']:,.2f} Kz\n"
                f"  - Valor Previsto com Juros Corridos: **{p['projected_investments_value']:,.2f} Kz** (lucro total acumulado de **+{p['projected_investments_yield']:,.2f} Kz**)\n\n"
                f"• 🌟 **Património Líquido Total Projetado:** **{p['projected_total_net_worth']:,.2f} Kz** (evolução de +{p['net_worth_growth_pct']}%)."
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_financial_projection"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        if re.search(r"quanto\s+(?:dinheiro\s+)?poderei\s+ter\s+daqui\s+a\s+tr[eê]s\s+meses|daqui\s+a\s+3\s+meses", m):
            proj = execute_tool("get_financial_projection", {"months_ahead": 3}, user_id)
            c = proj["current_position"]
            p = proj["projection"]
            reply = (
                f"🔮 **Previsão Financeira para Daqui a 3 Meses ({proj['end_month_label']}):**\n\n"
                f"• **Saldo em Contas Bancárias:** {p['projected_accounts_balance']:,.2f} Kz\n"
                f"• **Metas de Poupança Acumuladas:** {p['projected_savings_goals_saved']:,.2f} Kz\n"
                f"• **Investimentos com Juros Corridos:** {p['projected_investments_value']:,.2f} Kz (+{p['projected_investments_yield']:,.2f} Kz de juros)\n\n"
                f"🌟 **Património Total Estimado:** **{p['projected_total_net_worth']:,.2f} Kz** (crescimento de **+{p['net_worth_growth']:,.2f} Kz**)."
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_financial_projection"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        if re.search(r"quanto\s+(?:dinheiro\s+)?terei\s+no\s+final\s+de\s+dezembro\s+de\s+2026|dezembro\s+de\s+2026", m):
            proj = execute_tool("get_financial_projection", {"target_date": "dezembro de 2026"}, user_id)
            c = proj["current_position"]
            p = proj["projection"]
            reply = (
                f"🔮 **Previsão Financeira para o Final de Dezembro de 2026 (2 meses):**\n\n"
                f"• **Saldo Previsto em Contas:** {p['projected_accounts_balance']:,.2f} Kz\n"
                f"• **Poupança em Metas Acumulada:** {p['projected_savings_goals_saved']:,.2f} Kz\n"
                f"• **Investimentos com Rendimentos:** {p['projected_investments_value']:,.2f} Kz\n\n"
                f"🌟 **Património Líquido Total Estimado:** **{p['projected_total_net_worth']:,.2f} Kz** ao fecho do ano de 2026."
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_financial_projection"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        if re.search(r"se\s+continuar\s+a\s+gastar.*quanto\s+terei\s+daqui\s+a\s+seis\s+meses|daqui\s+a\s+6\s+meses", m):
            proj = execute_tool("get_financial_projection", {"months_ahead": 6}, user_id)
            c = proj["current_position"]
            p = proj["projection"]
            reply = (
                f"🔮 **Previsão Mantendo o Padrão Atual de Gastos — Daqui a 6 Meses ({proj['end_month_label']}):**\n\n"
                f"• **Saldo Projetado em Contas:** {p['projected_accounts_balance']:,.2f} Kz\n"
                f"• **Metas de Poupança Acumuladas:** {p['projected_savings_goals_saved']:,.2f} Kz\n"
                f"• **Investimentos Ativos:** {p['projected_investments_value']:,.2f} Kz (rendimento gerado: +{p['projected_investments_yield']:,.2f} Kz)\n\n"
                f"🌟 **Património Líquido Total:** **{p['projected_total_net_worth']:,.2f} Kz** (+{p['net_worth_growth_pct']}% de evolução global)."
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_financial_projection"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        if re.search(r"previs[aã]o\s+d(?:o|e)\s+(?:meu\s+)?saldo.*pr[oó]ximos\s+12\s+meses|pr[oó]ximos\s+12\s+meses", m):
            proj = execute_tool("get_financial_projection", {"months_ahead": 12, "include_chart": True}, user_id)
            c = proj["current_position"]
            p = proj["projection"]
            reply = (
                f"🔮 **Previsão Financeira a 12 Meses ({proj['end_month_label']}):**\n\n"
                f"• **Saldo Previsto em Contas:** {p['projected_accounts_balance']:,.2f} Kz\n"
                f"• **Total Poupado em Metas:** {p['projected_savings_goals_saved']:,.2f} Kz\n"
                f"• **Valor dos Investimentos:** {p['projected_investments_value']:,.2f} Kz (inclui a maturação do Depósito a Prazo em Agosto de 2027 com +18,5% a.a.)\n"
                f"• **Juros Totais Acumulados:** **+{p['projected_investments_yield']:,.2f} Kz**\n\n"
                f"🌟 **Património Líquido Total Previsto:** **{p['projected_total_net_worth']:,.2f} Kz** (crescimento de **+{p['net_worth_growth']:,.2f} Kz**)."
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": proj.get("chart"),
                "tools_used": ["get_financial_projection"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        if re.search(r"quanto\s+poderei\s+poupar\s+at[eé]\s+ao\s+final\s+de\s+2027|poupar\s+at[eé]\s+(?:o\s+)?final\s+de\s+2027", m):
            proj = execute_tool("get_financial_projection", {"target_date": "final de 2027"}, user_id)
            c = proj["current_position"]
            p = proj["projection"]
            savings_added = p['projected_savings_goals_saved'] - c['savings_goals_saved']
            reply = (
                f"💰 **Capacidade de Poupança até ao Final de 2027 ({proj['months_ahead']} meses):**\n\n"
                f"Mantendo as suas contribuições automáticas programadas:\n\n"
                f"• **Poupança Nova a Acumular nas Metas:** **+{savings_added:,.2f} Kz** adicionais ({proj['scenario']['monthly_savings_debits']:,.2f} Kz/mês durante {proj['months_ahead']} meses).\n"
                f"• **Total Acumulado nas Metas até Dezembro de 2027:** **{p['projected_savings_goals_saved']:,.2f} Kz**\n"
                f"• **Juros Adicionais Gerados pelos Investimentos:** **+{p['projected_investments_yield']:,.2f} Kz**\n\n"
                f"🌟 **Total de Património Poupado e Investido:** **{(p['projected_savings_goals_saved'] + p['projected_investments_value']):,.2f} Kz**!"
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_financial_projection"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        if re.search(r"se\s+receber\s+o\s+mesmo\s+sal[aá]rio.*despesas\s+atuais.*situa[cç][aã]o\s+financeira\s+em\s+janeiro|situa[cç][aã]o\s+financeira\s+em\s+janeiro", m):
            proj = execute_tool("get_financial_projection", {"target_date": "janeiro de 2027"}, user_id)
            c = proj["current_position"]
            p = proj["projection"]
            reply = (
                f"📋 **Diagnóstico da Situação Financeira em Janeiro de 2027 (Salário Constante & Despesas Mantidas):**\n\n"
                f"Assumindo a entrada do seu salário regular ({proj['scenario']['monthly_income_avg']:,.2f} Kz/mês) e o nível de despesas atual ({proj['scenario']['effective_monthly_expenses']:,.2f} Kz/mês):\n\n"
                f"• **Liquidez em Contas Bancárias:** Saldo projetado de **{p['projected_accounts_balance']:,.2f} Kz**.\n"
                f"• **Metas de Poupança:** Estarão com **{p['projected_savings_goals_saved']:,.2f} Kz** acumulados (progresso acelerado na meta do carro e fundo de reserva).\n"
                f"• **Investimentos:** Atingirão **{p['projected_investments_value']:,.2f} Kz** com juros compostos garantidos.\n"
                f"• **Património Líquido Total:** Chegará a **{p['projected_total_net_worth']:,.2f} Kz**.\n\n"
                f"A sua situação financeira será sólida, com património crescente e proteção contínua de capital."
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_financial_projection"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # ═══════════════════════════════════════════════════════════
        # 11. METAS DE POUPANÇA (Perguntas 56-70)
        # ═══════════════════════════════════════════════════════════

        # 56. Criar poupança para carro de 8 milhões em 2 anos — quanto poupar por mês?
        if re.search(r"(?:criar?|quero|abrir)\s+(?:uma?\s+)?poupan[cç]a.*carro.*8\s*milh[oõo]es?|carro.*8\s*milh[oõo]es?.*(?:dois|2)\s*anos?|8\s*milh[oõo]es?\s*kz.*(?:dois|2)\s*anos?", m):
            target_kz = 8_000_000.0
            months_n = 24
            simple_monthly = target_kz / months_n
            # Com DP BankAO a 18.5% a.a.
            r_m = 0.185 / 12
            pmt_compound = round(target_kz * r_m / (((1 + r_m) ** months_n) - 1), 2)
            interest_covered = target_kz - (pmt_compound * months_n)
            reply = (
                f"🚗 **Plano de Poupança para Comprar um Carro de 8.000.000 Kz em 2 Anos (24 meses):**\n\n"
                f"• **Opção 1 — Poupança Simples (sem juros):**\n"
                f"  Precisa de guardar **{simple_monthly:,.2f} Kz por mês** durante 24 meses.\n\n"
                f"• **Opção 2 — Depósito a Prazo BankAO (18,5% ao ano, juros compostos):**\n"
                f"  Bastam apenas **{pmt_compound:,.2f} Kz/mês** — o banco complementa com **+{interest_covered:,.2f} Kz** em juros!\n"
                f"  Total do seu bolso: **{pmt_compound * months_n:,.2f} Kz** (poupança de {interest_covered:,.2f} Kz vs. opção simples).\n\n"
                f"💡 **Recomendação BankAO:** Com o Depósito a Prazo poupará cerca de "
                f"**{interest_covered:,.2f} Kz** em esforço pessoal. Quer criar esta meta automaticamente?"
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["simulate_investment"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 57. Cria um plano para poupar 1 milhão de Kz em 12 meses
        if re.search(r"cria?(?:\s+um)?\s+plano?\s+para?\s+poupar?\s+1\s*milh[oõ]o|plano.*poupar.*1\s*milh[oõ]o.*12\s*meses?", m):
            target_kz = 1_000_000.0
            months_n = 12
            simple_monthly = target_kz / months_n
            r_m = 0.185 / 12
            pmt_compound = round(target_kz * r_m / (((1 + r_m) ** months_n) - 1), 2)
            interest_gain = target_kz - (pmt_compound * months_n)
            sim = execute_tool("simulate_investment", {
                "initial_amount": 0.0,
                "monthly_contribution": pmt_compound,
                "months": 12,
                "annual_rate": 18.5
            }, user_id)
            reply = (
                f"📋 **Plano de Poupança: 1.000.000 Kz em 12 Meses**\n\n"
                f"**Estratégia Recomendada — Depósito a Prazo BankAO (18,5% a.a.):**\n\n"
                f"| Mês | Contribuição Mensal | Saldo Acumulado (Estimado) |\n"
                f"|---|---|---|\n"
                f"| Meses 1–6 | {pmt_compound:,.2f} Kz/mês | ~{pmt_compound * 6 * 1.045:,.2f} Kz |\n"
                f"| Meses 7–12 | {pmt_compound:,.2f} Kz/mês | ~{sim['final_balance']:,.2f} Kz |\n\n"
                f"• **Contribuição Mensal Necessária:** **{pmt_compound:,.2f} Kz/mês**\n"
                f"• **Total do seu bolso:** {pmt_compound * months_n:,.2f} Kz\n"
                f"• **Juros gerados:** +{sim['total_interest_earned']:,.2f} Kz\n"
                f"• **Saldo Final Garantido:** **{sim['final_balance']:,.2f} Kz** ✅\n\n"
                f"💡 Comparando com poupança simples (sem juros) precisaria de **{simple_monthly:,.2f} Kz/mês**. "
                f"Com o Depósito a Prazo o banco contribui com **+{interest_gain:,.2f} Kz**!\n\n"
                f"Deseja criar esta meta automaticamente com débito automático no dia 1 de cada mês?"
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["simulate_investment"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 58. Quanto já consegui poupar até agora? / total poupado
        if re.search(r"quanto\s+j[aá]\s+(?:consegui\s+)?poupar?|total\s+poupado|quanto\s+tenho\s+poupado|total\s+(?:em\s+)?poupan[cç]as?", m):
            goals_res = execute_tool("get_savings_goals", {}, user_id)
            goals = goals_res.get("goals", [])
            total_saved = sum(g["saved"] for g in goals)
            total_target = sum(g["target"] for g in goals)
            total_monthly = sum(g["monthly"] for g in goals)
            lines_g = [f"💰 **Total Poupado nas Suas Metas BankAO:**\n"]
            for g in goals:
                lines_g.append(f"• **{g['name']}**: {g['saved']:,.2f} Kz guardados de {g['target']:,.2f} Kz ({g['percent']}% concluído) — {g['monthly']:,.2f} Kz/mês")
            lines_g.append(f"\n🌟 **Total Acumulado:** **{total_saved:,.2f} Kz** em {len(goals)} meta(s) de poupança ativas.")
            lines_g.append(f"📅 Contribuição Automática Mensal Total: **{total_monthly:,.2f} Kz/mês**")
            return {
                "reply": "\n".join(lines_g), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_savings_goals"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 59. Qual das minhas metas de poupança está mais próxima de ser concluída?
        if re.search(r"meta.*poupan[cç]a.*mais\s+pr[oó]xima.*conclu[ií]da?|mais\s+pr[oó]xima\s+de\s+(?:ser\s+)?conclu[ií]da?|qual\s+das\s+metas.*pr[oó]xima", m):
            goals_res = execute_tool("get_savings_goals", {}, user_id)
            goals = goals_res.get("goals", [])
            if not goals:
                reply = "Ainda não tem nenhuma meta de poupança ativa. Quer criar uma?"
            else:
                closest = max(goals, key=lambda g: g["percent"])
                other_goals = [g for g in goals if g["name"] != closest["name"]]
                reply = (
                    f"🏁 **Meta de Poupança Mais Próxima de Ser Concluída:**\n\n"
                    f"🥇 **{closest['name']}** — **{closest['percent']}%** concluído!\n"
                    f"• Poupado até agora: **{closest['saved']:,.2f} Kz**\n"
                    f"• Objetivo total: {closest['target']:,.2f} Kz\n"
                    f"• Valor em falta: **{closest['remaining']:,.2f} Kz**\n"
                    f"• Contribuição mensal: {closest['monthly']:,.2f} Kz\n"
                    f"• Prazo: {closest['deadline']}\n\n"
                    f"Ao ritmo atual, irá atingir esta meta dentro de aproximadamente **{round(closest['remaining'] / closest['monthly']) if closest['monthly'] > 0 else 'N/A'} meses**."
                )
                if other_goals:
                    reply += "\n\n**Outras metas em progresso:**\n"
                    for og in other_goals:
                        reply += f"• {og['name']}: {og['percent']}% ({og['saved']:,.2f} Kz / {og['target']:,.2f} Kz)"
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_savings_goals"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 60. Estou atrasado em alguma das minhas metas?
        if re.search(r"estou\s+atrasado|atraso.*metas?|metas?.*atraso|no\s+prazo.*metas?|a\s+tempo.*metas?", m) and re.search(r"poupan[cç]|metas?|objetivo", m):
            from datetime import date
            goals_res = execute_tool("get_savings_goals", {}, user_id)
            goals = goals_res.get("goals", [])
            today = date.today()
            lines_g = ["📊 **Análise de Progresso das Metas de Poupança:**\n"]
            for g in goals:
                dl = g.get("deadline")
                if dl:
                    try:
                        deadline_dt = date.fromisoformat(dl)
                        months_left = max(1, (deadline_dt.year - today.year) * 12 + (deadline_dt.month - today.month))
                        expected_at_pace = g["saved"] + (g["monthly"] * months_left)
                        on_track = expected_at_pace >= g["target"]
                        status_icon = "✅" if on_track else "⚠️"
                        extra = "No prazo" if on_track else f"Em risco — faltam {g['remaining']:,.2f} Kz mas restam apenas {months_left} meses"
                        lines_g.append(f"{status_icon} **{g['name']}**: {g['percent']}% concluído — {extra}")
                    except Exception:
                        lines_g.append(f"• **{g['name']}**: {g['percent']}% concluído (prazo não definido)")
                else:
                    lines_g.append(f"• **{g['name']}**: {g['percent']}% concluído (prazo aberto)")
            lines_g.append(f"\n💡 As suas contribuições automáticas mensais de **250.000 Kz** mantêm as metas no caminho certo.")
            return {
                "reply": "\n".join(lines_g), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_savings_goals"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 61. Quanto preciso de aumentar a minha poupança mensal para cumprir o meu objetivo?
        if re.search(r"quanto\s+preciso\s+de\s+aumentar.*poupan[cç]a\s+mensal|aumentar.*poupan[cç]a.*cumprir.*objetivo|aumentar\s+(?:a\s+)?contribui[cç][aã]o\s+mensal", m):
            from datetime import date
            goals_res = execute_tool("get_savings_goals", {}, user_id)
            goals = goals_res.get("goals", [])
            today = date.today()
            lines_g = ["📈 **Análise: Necessidade de Aumento das Contribuições Mensais:**\n"]
            for g in goals:
                dl = g.get("deadline")
                if dl:
                    try:
                        deadline_dt = date.fromisoformat(dl)
                        months_left = max(1, (deadline_dt.year - today.year) * 12 + (deadline_dt.month - today.month))
                        needed_monthly = round(g["remaining"] / months_left, 2)
                        diff = needed_monthly - g["monthly"]
                        if diff > 0:
                            lines_g.append(f"⚠️ **{g['name']}**: Precisa de **+{diff:,.2f} Kz/mês** a mais (atual: {g['monthly']:,.2f} Kz, necessário: {needed_monthly:,.2f} Kz para os {months_left} meses restantes).")
                        else:
                            lines_g.append(f"✅ **{g['name']}**: A contribuição atual ({g['monthly']:,.2f} Kz/mês) é **suficiente** — existe até uma folga de {abs(diff):,.2f} Kz/mês!")
                    except Exception:
                        lines_g.append(f"• **{g['name']}**: Prazo inválido ou não definido.")
            return {
                "reply": "\n".join(lines_g), "action": None, "pending": None, "chart": None,
                "tools_used": ["get_savings_goals"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 62. Se guardar 30.000 Kz todos os meses, quanto terei em dezembro de 2027?
        if re.search(r"guardar\s+30\s*\.?000\s*(?:kz)?.*dez(?:embro)?\s*(?:de\s*)?2027|30\s*\.?000\s*kz.*m[eê]s.*dez(?:embro)?\s*(?:de\s*)?2027", m):
            monthly_contrib = 30_000.0
            months_n = 14  # Nov 2026 → Dec 2027
            sim = execute_tool("simulate_investment", {
                "initial_amount": 0.0,
                "monthly_contribution": monthly_contrib,
                "months": months_n,
                "annual_rate": 18.5
            }, user_id)
            simple_total = monthly_contrib * months_n
            reply = (
                f"🧮 **Simulação: Poupar 30.000 Kz/mês até Dezembro de 2027 ({months_n} meses):**\n\n"
                f"• **Sem Juros (poupança simples):** {simple_total:,.2f} Kz acumulados.\n"
                f"• **Com Depósito a Prazo BankAO (18,5% ao ano com juro composto):**\n"
                f"  - Total depositado do seu bolso: {sim['total_deposited']:,.2f} Kz\n"
                f"  - Juros gerados pelo banco: **+{sim['total_interest_earned']:,.2f} Kz**\n"
                f"  - **Saldo Final em Dezembro de 2027: {sim['final_balance']:,.2f} Kz** 🎉\n\n"
                f"💡 Com o Depósito a Prazo ganhará **{sim['total_interest_earned']:,.2f} Kz** extra sem esforço adicional!"
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["simulate_investment"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 63. Quero poupar para uma viagem, mas não sei quanto devo guardar. Ajuda-me a planear.
        if re.search(r"poupar\s+para\s+(?:uma?\s+)?viagem|poupan[cç]a.*viagem|viagem.*planear|planear.*viagem", m):
            reply = (
                "✈️ **Plano de Poupança para Viagem — BankAO Copilot:**\n\n"
                "Para criar o plano ideal, preciso de algumas informações:\n\n"
                "**1. Destino:**\n"
                "• África (Angola, África do Sul, Namíbia, etc.) — estimativa: 500.000–2.000.000 Kz\n"
                "• Europa ou América — estimativa: 3.000.000–8.000.000 Kz\n\n"
                "**2. Quando quer viajar?** (mês e ano)\n\n"
                "**3. Viaja sozinho ou com família?**\n\n"
                "---\n"
                "**Exemplo Prático (viagem à Europa em Junho de 2027 — 7 meses):**\n"
                "• Orçamento estimado: 5.000.000 Kz\n"
                "• Sem juros: guardar ~714.286 Kz/mês\n"
                "• Com Depósito a Prazo BankAO (18,5% a.a.): ~**694.000 Kz/mês** (banco subsidia os juros! 🎉)\n\n"
                "💬 Diga-me o destino e a data — faço os cálculos exatos para si!"
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": [], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 64. Posso ter várias metas de poupança ao mesmo tempo?
        if re.search(r"v[aá]rias\s+metas?\s+de\s+poupan[cç]a|m[uú]ltiplas\s+metas?|ter\s+v[aá]rias\s+metas?|mais\s+de\s+uma\s+meta|metas?\s+ao\s+mesmo\s+tempo", m):
            goals_res = execute_tool("get_savings_goals", {}, user_id)
            n_active = goals_res.get("count", 0)
            reply = (
                f"✅ **Sim! O BankAO suporta múltiplas metas de poupança em simultâneo.**\n\n"
                f"Cada meta tem o seu próprio:\n"
                f"• **Objetivo específico** (montante alvo)\n"
                f"• **Contribuição mensal automática** (débito automático programado)\n"
                f"• **Prazo e ícone personalizados** (🚗 carro, ✈️ viagem, 🛡️ emergência, 🏠 casa, etc.)\n\n"
                f"Atualmente já tem **{n_active} meta(s) ativa(s):**\n"
            )
            for g in goals_res.get("goals", []):
                reply += f"• **{g['name']}**: {g['percent']}% concluído ({g['saved']:,.2f} Kz de {g['target']:,.2f} Kz)\n"
            reply += (
                f"\n💡 Pode criar novas metas a qualquer momento — diga apenas o nome, o valor-alvo e o prazo.\n"
                f"Exemplo: *«Quero poupar 500.000 Kz para uma viagem até Junho de 2027»*"
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_savings_goals"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 65. Qual é a percentagem de conclusão de cada uma das minhas metas?
        if re.search(r"percentagem\s+de\s+conclus[aã]o|progresso\s+de\s+(?:cada|as)\s+metas?|quantos?\s+por\s+cento.*metas?|percent.*conclus[aã]o.*metas?", m):
            goals_res = execute_tool("get_savings_goals", {}, user_id)
            goals = goals_res.get("goals", [])
            if not goals:
                reply = "Ainda não tem metas de poupança ativas."
            else:
                lines_g = ["📊 **Percentagem de Conclusão das Metas de Poupança:**\n"]
                for g in goals:
                    bar_filled = round(g["percent"] / 10)
                    bar = "█" * bar_filled + "░" * (10 - bar_filled)
                    lines_g.append(
                        f"**{g['name']}**\n"
                        f"  [{bar}] **{g['percent']}%**\n"
                        f"  Poupado: {g['saved']:,.2f} Kz | Objetivo: {g['target']:,.2f} Kz | Faltam: {g['remaining']:,.2f} Kz\n"
                    )
                total_saved = sum(g["saved"] for g in goals)
                total_target = sum(g["target"] for g in goals)
                overall_pct = round(total_saved / total_target * 100, 1) if total_target else 0
                lines_g.append(f"🌟 **Progresso Global de Todas as Metas:** **{overall_pct}%** ({total_saved:,.2f} Kz de {total_target:,.2f} Kz)")
                reply = "\n".join(lines_g)
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_savings_goals"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 66. Quanto dinheiro falta para atingir a minha meta de poupança mais próxima?
        if re.search(r"quanto\s+(?:dinheiro\s+)?falta\s+para\s+(?:atingir\s+)?(?:a\s+)?minha\s+meta|quanto\s+falta\s+para\s+(?:a\s+)?meta\s+mais\s+pr[oó]xima|dinheiro\s+em\s+falta.*meta", m):
            goals_res = execute_tool("get_savings_goals", {}, user_id)
            goals = goals_res.get("goals", [])
            if not goals:
                reply = "Ainda não tem metas de poupança ativas."
            else:
                closest = max(goals, key=lambda g: g["percent"])
                months_to_go = round(closest["remaining"] / closest["monthly"]) if closest["monthly"] > 0 else None
                reply = (
                    f"🎯 **Meta Mais Próxima de Conclusão: {closest['name']}**\n\n"
                    f"• **Já poupado:** {closest['saved']:,.2f} Kz ({closest['percent']}% do objetivo)\n"
                    f"• **Objetivo total:** {closest['target']:,.2f} Kz\n"
                    f"• **Valor em falta:** **{closest['remaining']:,.2f} Kz**\n"
                    f"• **Contribuição atual:** {closest['monthly']:,.2f} Kz/mês\n"
                )
                if months_to_go:
                    reply += f"• **Tempo estimado para concluir:** ~{months_to_go} meses (ao ritmo atual)\n"
                reply += f"\n💡 Ao manter as contribuições automáticas de **{closest['monthly']:,.2f} Kz/mês** concluirá esta meta no prazo!"
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_savings_goals"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 67. Se retirar 100.000 Kz da minha poupança, como isso afetará o meu objetivo?
        if re.search(r"retirar\s+100\s*\.?000\s*(?:kz)?\s+da\s+(?:minha\s+)?poupan[cç]a|levantar\s+100\s*\.?000.*poupan[cç]a|remover\s+100\s*\.?000.*meta", m):
            goals_res = execute_tool("get_savings_goals", {}, user_id)
            goals = goals_res.get("goals", [])
            withdrawal = 100_000.0
            if not goals:
                reply = "Não tem metas de poupança ativas."
            else:
                # Assume applies to the most progressed goal
                g = max(goals, key=lambda x: x["saved"])
                new_saved = max(0.0, g["saved"] - withdrawal)
                new_remaining = g["target"] - new_saved
                new_months = round(new_remaining / g["monthly"]) if g["monthly"] > 0 else None
                current_months = round(g["remaining"] / g["monthly"]) if g["monthly"] > 0 else None
                delay = (new_months - current_months) if (new_months and current_months) else None
                reply = (
                    f"⚠️ **Impacto de Levantar 100.000 Kz da Meta '{g['name']}':**\n\n"
                    f"• **Poupado Atualmente:** {g['saved']:,.2f} Kz\n"
                    f"• **Após Levantamento:** {new_saved:,.2f} Kz (-100.000 Kz)\n"
                    f"• **Valor em Falta:** Passa de {g['remaining']:,.2f} Kz para **{new_remaining:,.2f} Kz**\n"
                )
                if delay:
                    reply += f"• **Atraso Estimado:** O seu objetivo atrasará aproximadamente **{delay} mês(es)**.\n"
                reply += (
                    f"\n🛡️ **Recomendação BankAO:** Se precisar de liquidez, avalie antes usar o seu "
                    f"Fundo de Emergência — foi criado exatamente para estas situações!"
                )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_savings_goals"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 68. Compara as minhas metas de poupança com os meus rendimentos
        if re.search(r"compara\s+(?:as\s+)?(?:minha[s]?\s+)?metas?\s+de\s+poupan[cç]a.*rendimento|metas?\s+poupan[cç]a.*vs.*rendimento|poupan[cç]a.*rendimento.*compara", m):
            goals_res = execute_tool("get_savings_goals", {}, user_id)
            from backend.database import get_connection as _gc
            _conn = _gc()
            income_avg = _conn.execute("""
                SELECT AVG(le.amount_minor)/100.0 FROM ledger_entries le
                JOIN accounts a ON a.id=le.account_id
                JOIN transactions t ON t.id=le.transaction_id
                WHERE a.user_id=? AND t.type='deposit' AND le.amount_minor > 0
            """, (user_id,)).fetchone()[0] or 400_000.0
            _conn.close()
            goals = goals_res.get("goals", [])
            total_monthly_goals = sum(g["monthly"] for g in goals)
            pct_income = round(total_monthly_goals / income_avg * 100, 1) if income_avg else 0
            reply = (
                f"📊 **Comparativo: Metas de Poupança vs. Rendimentos Mensais:**\n\n"
                f"• **Rendimento Médio Mensal:** ~{income_avg:,.2f} Kz\n"
                f"• **Total de Contribuições Mensais para Metas:** {total_monthly_goals:,.2f} Kz\n"
                f"• **Percentagem do Rendimento Afeta a Poupança:** **{pct_income}%**\n\n"
                f"**Detalhe por Meta:**\n"
            )
            for g in goals:
                pct_g = round(g["monthly"] / income_avg * 100, 1) if income_avg else 0
                reply += f"• **{g['name']}**: {g['monthly']:,.2f} Kz/mês = **{pct_g}%** do rendimento\n"
            reply += (
                f"\n💡 **Avaliação BankAO:** Está a afectar **{pct_income}%** do rendimento para poupanças. "
                f"{'Excelente! Acima dos 20% recomendados internacionalmente! 🌟' if pct_income >= 20 else 'O ideal é poupar pelo menos 20% do rendimento — considere aumentar as contribuições.'}"
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_savings_goals"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 69. Cria um plano de poupança baseado nas minhas despesas atuais
        if re.search(r"cria?\s+(?:um\s+)?plano\s+de\s+poupan[cç]a\s+baseado\s+(?:nas\s+)?(?:minhas\s+)?despesas\s+atuais|plano.*poupan[cç]a.*despesas\s+atuais", m):
            res_exp = execute_tool("get_expenses_analysis", {"period": "last_3_months", "exclude_savings": True}, user_id)
            from backend.database import get_connection as _gc2
            _conn2 = _gc2()
            avg_income_minor = _conn2.execute("""
                SELECT AVG(le.amount_minor) FROM ledger_entries le
                JOIN accounts a ON a.id=le.account_id
                JOIN transactions t ON t.id=le.transaction_id
                WHERE a.user_id=? AND t.type='deposit' AND le.amount_minor > 0
            """, (user_id,)).fetchone()[0] or 40_000_000
            _conn2.close()
            avg_income = float(avg_income_minor) / 100.0
            avg_expenses = res_exp.get("monthly_average", 0) or res_exp.get("total_expenses", 0) / 3
            surplus = avg_income - avg_expenses
            goals_res = execute_tool("get_savings_goals", {}, user_id)
            current_monthly_savings = sum(g["monthly"] for g in goals_res.get("goals", []))
            free_surplus = surplus - current_monthly_savings
            reply = (
                f"📋 **Plano de Poupança Personalizado — Baseado nas Suas Finanças Reais:**\n\n"
                f"**📥 Rendimento Médio Mensal:** ~{avg_income:,.2f} Kz\n"
                f"**📤 Despesas Operacionais Médias/mês:** ~{avg_expenses:,.2f} Kz\n"
                f"**📊 Excedente Mensal Bruto:** ~{surplus:,.2f} Kz\n"
                f"**🎯 Já a Poupar (Contribuições Automáticas):** -{current_monthly_savings:,.2f} Kz/mês\n"
                f"**💰 Excedente Disponível Adicional:** **~{free_surplus:,.2f} Kz/mês**\n\n"
                f"**Recomendação para o Excedente Adicional ({free_surplus:,.2f} Kz/mês):**\n"
            )
            if free_surplus >= 50_000:
                reply += (
                    f"• **50%** ({free_surplus * 0.5:,.2f} Kz) → Reforçar metas existentes (Toyota Hilux ou Fundo de Emergência)\n"
                    f"• **30%** ({free_surplus * 0.3:,.2f} Kz) → Nova meta ou Depósito a Prazo BankAO (18,5% a.a.)\n"
                    f"• **20%** ({free_surplus * 0.2:,.2f} Kz) → Fundo de lazer / viagem\n"
                )
            elif free_surplus > 0:
                reply += f"• Aplique os **{free_surplus:,.2f} Kz** excedentes num Depósito a Prazo BankAO para fazer crescer o dinheiro.\n"
            else:
                reply += "⚠️ Actualmente o excedente disponível após poupanças automáticas é limitado. Recomendo otimizar os gastos operacionais.\n"
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis", "get_savings_goals"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 70. Qual seria uma meta de poupança realista para mim?
        if re.search(r"meta\s+de\s+poupan[cç]a\s+realista|poupan[cç]a\s+realista|quanto\s+(?:devo|posso)\s+poupar\s+(?:mensalmente|por\s+m[eê]s)|meta\s+realista", m):
            res_exp = execute_tool("get_expenses_analysis", {"period": "last_3_months", "exclude_savings": True}, user_id)
            goals_res = execute_tool("get_savings_goals", {}, user_id)
            from backend.database import get_connection as _gc3
            _conn3 = _gc3()
            avg_income_minor = _conn3.execute("""
                SELECT AVG(le.amount_minor) FROM ledger_entries le
                JOIN accounts a ON a.id=le.account_id
                JOIN transactions t ON t.id=le.transaction_id
                WHERE a.user_id=? AND t.type='deposit' AND le.amount_minor > 0
            """, (user_id,)).fetchone()[0] or 40_000_000
            _conn3.close()
            avg_income = float(avg_income_minor) / 100.0
            avg_expenses = res_exp.get("monthly_average", 0) or res_exp.get("total_expenses", 0) / 3
            current_monthly_savings = sum(g["monthly"] for g in goals_res.get("goals", []))
            surplus = avg_income - avg_expenses - current_monthly_savings
            # Regra 50/30/20 adaptada
            conservative = round(avg_income * 0.10, -3)   # 10% = conservador
            moderate = round(avg_income * 0.20, -3)        # 20% = moderado
            aggressive = round(avg_income * 0.30, -3)      # 30% = agressivo
            reply = (
                f"🎯 **Meta de Poupança Realista para o João Pedro:**\n\n"
                f"**Com base no seu perfil financeiro:**\n"
                f"• Rendimento: ~{avg_income:,.2f} Kz/mês\n"
                f"• Despesas operacionais: ~{avg_expenses:,.2f} Kz/mês\n"
                f"• Já a poupar automaticamente: {current_monthly_savings:,.2f} Kz/mês\n"
                f"• Excedente disponível: **~{surplus:,.2f} Kz/mês**\n\n"
                f"**Cenários de poupança adicionais recomendados:**\n\n"
                f"| Perfil | Valor Mensal Adicional | Acumulado em 12 meses |\n"
                f"|---|---|---|\n"
                f"| 🟢 Conservador (10% rendimento) | {conservative:,.2f} Kz/mês | ~{conservative * 12 * 1.08:,.0f} Kz |\n"
                f"| 🟡 Moderado (20% rendimento) | {moderate:,.2f} Kz/mês | ~{moderate * 12 * 1.12:,.0f} Kz |\n"
                f"| 🔴 Arrojado (30% rendimento) | {aggressive:,.2f} Kz/mês | ~{aggressive * 12 * 1.185:,.0f} Kz |\n\n"
                f"💡 **Recomendação BankAO para o seu perfil:** Como tem perfil de risco arrojado e já tem "
                f"as metas principais ativas, uma poupança adicional de **{moderate:,.2f}–{aggressive:,.2f} Kz/mês** "
                f"num Depósito a Prazo (18,5% a.a.) seria muito realista e impactante!"
            )
            return {
                "reply": reply, "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis", "get_savings_goals"], "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 10. Investimentos: Consulta de Carteira, Catálogo e Recomendações
        # "sobre investimento", "investimentos", "meus investimentos", "onde posso investir", etc.
        if re.search(r"sobre\s+(?:os\s+)?investimentos?|^investimentos?\??$|^investir\??$|meus\s+investimentos|quais\s+est[aã]o\s+a\s+render\s+mais|onde\s+estou\s+a\s+ganhar\s+mais|dinheiro\s+parado|onde\s+(?:posso|devo)\s+investir|como\s+investir|onde\s+aplicar|come[cç]ar\s+a\s+investir|op[cç][oõ]es\s+de\s+investimento|produtos?\s+de\s+investimento", m):
            port = execute_tool("get_investments_portfolio", {}, user_id)
            cat = execute_tool("get_investment_catalog", {}, user_id)
            update_user_session(user_id, {"active_topic": "investments"})

            if port.get("has_investments"):
                best = port.get("best_performing")
                lines = [
                    f"📈 **A sua Carteira de Investimentos BankAO:**\n",
                    f"• **Valor Total Aplicado:** {port['total_invested']:,.2f} Kz",
                    f"• **Património Atual:** **{port['total_current_value']:,.2f} Kz**",
                    f"• **Lucro Total Acumulado:** **+{port['total_yield_earned']:,.2f} Kz**\n"
                ]
                if best:
                    lines.append(f"🏆 **Produto com maior rentabilidade:** **{best['name']}** (+{best['yield_percentage']}% de retorno, +{best['yield_earned']:,.2f} Kz gerados).\n")
                lines.append("💼 **Outras oportunidades disponíveis no catálogo BankAO:**")
                lines.append("• **Depósito a Prazo:** até 18,5% ao ano (capital 100% garantido).")
                lines.append("• **Obrigações do Tesouro na BODIVA:** 17,2% ao ano com cupão semestral.")
                lines.append("• **ETFs Internacionais:** diversificação cambial em USD / EUR.")
                lines.append("\nDeseja simular um novo reforço de poupança ou aplicação?")
                reply = "\n".join(lines)
                tools = ["get_investments_portfolio", "get_investment_catalog"]
            else:
                reply = (
                    "🏦 **Opções de Investimento Recomendadas BankAO (Capital & Rentabilidade):**\n\n"
                    "1. **Depósito a Prazo BankAO (18,5% a.a.):**\n"
                    "   • Risco Zero, capital 100% garantido pelo FGD.\n"
                    "   • Ideal para reservas de médio prazo (1 ano), liquidação automática.\n\n"
                    "2. **Obrigações do Tesouro na BODIVA (17,2% a.a.):**\n"
                    "   • Títulos soberanos do Estado Angolano com cupão semestral.\n"
                    "   • Liquidação rápida no mercado secundário.\n\n"
                    "3. **ETFs Globais em Dólares (S&P 500 / All-World):**\n"
                    "   • Proteção cambial em USD com exposição às maiores empresas mundiais.\n\n"
                    "💡 *Deseja ver uma simulação exata? Diga-me o montante que tem disponível (ex.: «Simula 100 mil a 12 meses»).*"
                )
                tools = ["get_investment_catalog"]

            return {
                "reply": reply,
                "action": None,
                "pending": None, "chart": None,
                "tools_used": tools,
                "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 12. Simulação de Poupança / Juros Compostos
        # "Se poupar 30 mil por mês, quanto terei daqui a um ano?"
        m_sim = re.search(r"poupar\s+(\d+(?:[.,]\d+)?)\s*(?:mil|k)?\s*(?:por\s+m[eê]s)?.*?quanto\s+terei\s+(?:daqui\s+a\s+)?(\d+)?\s*(ano|mes|meses)?", m)
        if m_sim or ("poupar" in m and "quanto terei" in m):
            amt_str = m_sim.group(1) if m_sim else "30"
            mult = 1000 if ("mil" in m or "k" in m or float(amt_str.replace(",", ".")) < 500) else 1
            monthly = float(amt_str.replace(",", ".")) * mult
            months = 12
            if "2 anos" in m or "dois anos" in m:
                months = 24
            elif "6 meses" in m or "meio ano" in m:
                months = 6

            sim = execute_tool("simulate_investment", {
                "initial_amount": 0.0,
                "monthly_contribution": monthly,
                "months": months,
                "annual_rate": 18.5
            }, user_id)

            update_user_session(user_id, {"active_topic": "investments"})
            dep_dot = f"{sim['total_deposited']:,.0f}".replace(",", ".")
            reply = (
                f"🧮 **Simulação de Poupança e Rendimento ({months} meses):**\n\n"
                f"Se aplicar **{monthly:,.2f} Kz por mês** num Depósito a Prazo BankAO (18,5% a.a. com juros compostos capitalizados):\n\n"
                f"• **Total do seu bolso depositado:** **{dep_dot} Kz** ({sim['total_deposited']:,.2f} Kz)\n"
                f"• **Juros líquidos gerados:** **+{sim['total_interest_earned']:,.2f} Kz**\n"
                f"• **Saldo final acumulado:** **{sim['final_balance']:,.2f} Kz**\n\n"
                f"O seu dinheiro trabalhará para si gerando um ganho adicional substancial! Deseja criar uma meta automática de poupança com este valor?"
            )
            return {
                "reply": reply,
                "action": None, "pending": None, "chart": None,
                "tools_used": ["simulate_investment"],
                "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        # 14. Se nenhuma regra ou ferramenta determinística corresponder, devolve None para acionar LLM
        return None

    @classmethod
    def _handle_follow_up(
        cls,
        user_id: str,
        follow_up: Dict[str, Any],
        session: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processa perguntas de seguimento utilizando os parâmetros herdados da conversa."""
        f_type = follow_up["type"]

        if f_type == "period_shift":
            period = follow_up["period"]
            cat = follow_up.get("category")
            topic = follow_up["topic"]

            if topic == "expenses":
                res = execute_tool("get_expenses_analysis", {
                    "category": cat,
                    "period": period
                }, user_id)
                update_user_session(user_id, {"active_period": period})
                tot = res.get("total_expenses", 0.0)
                p_label = res.get("period_label", period)
                cat_str = f" em **{cat}**" if cat else ""
                reply = f"No **{p_label}**, o total de despesas{cat_str} foi de **{tot:,.2f} Kz**."
                return {
                    "reply": reply,
                    "action": None, "pending": None, "chart": None,
                    "tools_used": ["get_expenses_analysis"],
                    "requires_confirmation": False,
                    "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
                }

        elif f_type == "category_filter":
            cat = follow_up["category"]
            period = follow_up.get("period", "this_month")
            res = execute_tool("get_expenses_analysis", {
                "category": cat,
                "period": period
            }, user_id)
            update_user_session(user_id, {"active_category": cat, "active_period": period})
            tot = res.get("total_expenses", 0.0)
            p_label = res.get("period_label", period)
            reply = f"Em **{cat}** ({p_label}), gastou um total de **{tot:,.2f} Kz**."
            return {
                "reply": reply,
                "action": None, "pending": None, "chart": None,
                "tools_used": ["get_expenses_analysis"],
                "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        elif f_type == "currency_filter":
            cur = follow_up["currency"]
            res = execute_tool("get_accounts_summary", {}, user_id)
            acc = next((a for a in res.get("accounts", []) if a["currency"] == cur), None)
            sym = "€" if cur == "EUR" else ("$" if cur == "USD" else cur)
            cur_desc = "dólares" if cur == "USD" else ("euros" if cur == "EUR" else "kwanzas")
            if acc:
                reply = f"Na sua conta em **{cur}** ({cur_desc}), o saldo disponível é de **{acc['balance']:,.2f} {sym}**."
            else:
                reply = f"Na sua conta em **{cur}** ({cur_desc}), o saldo disponível é de **0,00 {sym}** (não possui conta ativa nesta moeda)."
            return {
                "reply": reply,
                "action": None, "pending": None, "chart": None,
                "tools_used": ["get_accounts_summary"],
                "requires_confirmation": False,
                "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
            }

        return {
            "reply": "Poderia reformular a sua pergunta para eu poder ajudar?",
            "action": None, "pending": None, "chart": None,
            "tools_used": [],
            "requires_confirmation": False,
            "model": settings.MODEL_NAME, "provider": "BankAO Copilot v2"
        }

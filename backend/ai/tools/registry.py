"""
Registo Central de Ferramentas (Tool Registry) para a IA do BankAO.
Define esquemas OpenAPI / OpenAI Tools e despacha a execução segura.
"""
from typing import Any, Callable, Dict, List, Optional
import json
import logging

from backend.ai.tools.accounts import (
    tool_get_accounts,
    tool_get_incomes,
    tool_get_statement,
)
from backend.ai.tools.expenses import (
    tool_compare_expenses_periods,
    tool_get_expenses_analysis,
    tool_get_recurring_or_duplicate_expenses,
    tool_get_top_merchants,
)
from backend.ai.tools.cards import (
    tool_get_card_spend_comparison,
    tool_get_cards,
)
from backend.ai.tools.investments import (
    tool_get_investment_catalog,
    tool_get_investments_portfolio,
    tool_simulate_investment,
)
from backend.ai.tools.transfers import (
    tool_get_transfer_fees_info,
    tool_quote_transfer,
)
from backend.ai.tools.contacts import (
    tool_get_contacts,
)
from backend.ai.tools.actions import (
    tool_prepare_deposit,
    tool_prepare_expense,
    tool_prepare_savings_goal,
    tool_prepare_transfer,
)
from backend.ai.tools.overview import (
    tool_get_financial_projection,
    tool_get_financial_snapshot,
    tool_get_savings_goals,
    tool_get_unrecorded_purchases,
    tool_show_chart,
)

logger = logging.getLogger("bankao.ai.tools")


# Definição dos Schemas de Ferramentas compatíveis com OpenAI / Meta Model API
BANKAO_TOOLS_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_accounts_summary",
            "description": "Consulta todas as contas e saldos reais em tempo real do utilizador autenticado (AOA, EUR, USD).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_account_statement",
            "description": "Consulta o histórico de movimentos e transações recentes do utilizador.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Número de dias para trás a consultar (ex: 7, 30, 90). Padrão: 30."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Número máximo de movimentos a listar. Padrão: 20."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_incomes_summary",
            "description": "Consulta as receitas e dinheiro recebido pelo cliente num período específico (depósitos, transferências recebidas, salários).",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["this_month", "last_month", "last_7_days", "last_30_days"],
                        "description": "Período temporal da consulta de receitas."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_expenses_analysis",
            "description": "Analisa despesas reais do cliente por categoria (ex: 'Alimentação', 'Restaurantes', 'Transporte'), período temporal (ex: 'setembro', 'outubro', 'last_month', 'last_week', 'this_year'), valor mínimo e ordenação.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Categoria específica de despesa (ex: 'Restaurantes', 'Alimentação', 'Transporte', 'Lazer', 'Saúde', etc.)."
                    },
                    "period": {
                        "type": "string",
                        "description": "Período temporal da análise: 'this_month', 'last_month', 'last_3_months', 'last_week', 'this_year', 'last_30_days', ou mês específico (ex: 'setembro', 'agosto', 'outubro', '2026-09')."
                    },
                    "months_count": {
                        "type": "integer",
                        "description": "Quantidade de meses a analisar (ex: 3 para últimos 3 meses)."
                    },
                    "min_amount": {
                        "type": "number",
                        "description": "Filtro de valor mínimo em Kz (ex: 20000 para despesas superiores a 20.000 Kz)."
                    },
                    "order_by": {
                        "type": "string",
                        "enum": ["amount_desc", "date_desc"],
                        "description": "Ordenação das despesas: 'amount_desc' para maiores gastos primeiro, ou 'date_desc'."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Limite máximo de despesas a devolver (ex: 5 para as 5 maiores)."
                    },
                    "exclude_savings": {
                        "type": "boolean",
                        "description": "Se verdadeiro, exclui débitos automáticos para metas de poupança e mostra apenas consumo operacional."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_expenses_periods",
            "description": "Compara matematicamente os gastos entre dois períodos (ex: setembro vs outubro, este mês versus mês passado).",
            "parameters": {
                "type": "object",
                "properties": {
                    "period1": {
                        "type": "string",
                        "description": "Período 1 a comparar (ex: 'setembro', 'this_month', 'last_month')."
                    },
                    "period2": {
                        "type": "string",
                        "description": "Período 2 a comparar (ex: 'outubro', 'last_month', 'this_month')."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_merchants",
            "description": "Identifica os estabelecimentos comerciais onde o utilizador mais gastou dinheiro.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Janela temporal em dias (ex: 30 para últimos 30 dias, 365 para este ano). Padrão: 365."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Quantidade máxima de estabelecimentos a listar. Padrão: 5."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recurring_or_duplicate_expenses",
            "description": "Identifica cobranças repetidas, despesas fixas recorrentes e potenciais cobranças duplicadas na conta do cliente.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_cards_overview",
            "description": "Lista todos os cartões do cliente com respetivos limites, gastos do mês e estado (ativo/bloqueado).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_card_spend_comparison",
            "description": "Compara os consumos entre os vários cartões do cliente e responde qual cartão está a gastar mais.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_investments_portfolio",
            "description": "Consulta a carteira de investimentos ativa do cliente, mostrando os valores investidos, rendimentos acumulados e qual produto rende mais.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_investment_catalog",
            "description": "Consulta os produtos de investimento disponíveis no BankAO (Depósitos a Prazo até 18.5%, Obrigações BODIVA, Bilhetes do Tesouro, ETFs).",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Filtro opcional por tipo de produto ('deposito_prazo', 'obrigacoes', 'etf', 'fundos')."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_investment",
            "description": "Simula com exatidão matemática o crescimento de poupanças e investimentos com juros compostos periódicos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "initial_amount": {
                        "type": "number",
                        "description": "Montante inicial a aplicar em Kz ou moeda indicada."
                    },
                    "monthly_contribution": {
                        "type": "number",
                        "description": "Reforço mensal programado (ex: 30000 para 30 mil/mês)."
                    },
                    "months": {
                        "type": "integer",
                        "description": "Duração da simulação em meses (ex: 12 para um ano)."
                    },
                    "annual_rate": {
                        "type": "number",
                        "description": "Taxa de juro anual em percentagem (ex: 18.5 para Depósito a Prazo BankAO). Padrão: 18.5."
                    }
                },
                "required": ["initial_amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_transfer_fees_info",
            "description": "Consulta as regras, percentagens e valores exatos das comissões de transferência do BankAO.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "Montante de exemplo para cálculo da taxa. Padrão: 10000."
                    },
                    "currency": {
                        "type": "string",
                        "description": "Moeda da operação. Padrão: AOA."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "quote_transfer",
            "description": "Prepara e valida uma cotação de transferência bancária, calculando saldo disponível e taxas. Requer confirmação posterior do utilizador.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "Destinatário (IBAN, número de conta BankAO ou e-mail)."
                    },
                    "amount": {
                        "type": "number",
                        "description": "Montante a enviar."
                    },
                    "currency": {
                        "type": "string",
                        "description": "Moeda da transferência (AOA, EUR, USD). Padrão: AOA."
                    },
                    "beneficiary_name": {
                        "type": "string",
                        "description": "Nome do beneficiário, se disponível."
                    }
                },
                "required": ["destination", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_contacts",
            "description": "Consulta os contactos guardados e destinatários frequentes do utilizador para transferências rápidas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de pesquisa por nome, apelido, número de conta ou IBAN."
                    },
                    "favorites_only": {
                        "type": "boolean",
                        "description": "Se verdadeiro, filtra apenas contactos marcados como favoritos."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Número máximo de contactos a listar. Padrão: 10."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_snapshot",
            "description": "Foto geral do cliente: saldos, despesas do mês, maiores categorias, metas, investimentos e notas que o cliente partilhou. Usa para perguntas abertas (balanço, 'como estou', conselhos).",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_projection",
            "description": "Calcula projeções e previsões financeiras determinísticas precisas para datas futuras ou meses à frente. Trata e distingue separadamente saldo em contas bancárias, metas de poupança acumuladas, valor de investimentos e juros gerados. Suporta simulação de cenários (reduzir/aumentar despesas).",
            "parameters": {
                "type": "object",
                "properties": {
                    "months_ahead": {
                        "type": "integer",
                        "description": "Número de meses para projeção futura (ex: 1, 2, 3, 6, 12, 14)."
                    },
                    "target_date": {
                        "type": "string",
                        "description": "Mês ou data alvo específica (ex: 'janeiro de 2027', 'dezembro de 2026', 'final de 2027')."
                    },
                    "expense_multiplier": {
                        "type": "number",
                        "description": "Multiplicador de despesas: 0.8 para redução de 20%, 1.3 para aumento de 30%, 1.0 para ritmo atual."
                    },
                    "monthly_savings_extra": {
                        "type": "number",
                        "description": "Valor extra a poupar por mês além das metas já existentes."
                    },
                    "include_chart": {
                        "type": "boolean",
                        "description": "Se verdadeiro, gera dados para exibição de gráfico de previsão de saldo."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_savings_goals",
            "description": "Lista as metas de poupança do cliente com progresso, falta, prestação mensal e prazo.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_unrecorded_purchases",
            "description": "Compras com cartão que ainda não estão nas Despesas. Usar SÓ se o cliente perguntar por compras por registar.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_chart",
            "description": "Mostra um gráfico interativo na conversa. donut_expenses_month = despesas por categoria num mês; line_expenses_months = evolução mensal; bar_categories_period = barras por categoria; balance_forecast = previsão do saldo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chart_type": {"type": "string", "enum": ["donut_expenses_month", "line_expenses_months", "bar_categories_period", "balance_forecast"]},
                    "month": {"type": "string", "description": "Mês no formato AAAA-MM (só para donut). Omitir = mês atual."},
                    "months": {"type": "integer", "description": "Número de meses (evolução/barras). Padrão 4."}
                },
                "required": ["chart_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_savings_goal",
            "description": "PREPARA uma META DE POUPANÇA nova (ex.: 'quero poupar 50 mil para um carro até agosto de 2027'). Não cria nada: devolve o plano para o cliente rever e confirmar. Usa isto — e NUNCA prepare_expense — sempre que o pedido for poupar/juntar/guardar dinheiro para um objetivo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Objetivo, curto (ex.: 'Carro', 'Casa', 'Viagem a Lisboa')."},
                    "icon_key": {"type": "string", "enum": ["target", "home", "car", "travel", "laptop", "education", "award", "shield"], "description": "Ícone que melhor representa o objetivo."},
                    "target_amount": {"type": "number", "description": "Valor TOTAL da meta em Kz (50 mil = 50000)."},
                    "months": {"type": "integer", "description": "Duração em meses, se o cliente disser a duração."},
                    "deadline": {"type": "string", "description": "Mês final AAAA-MM, se o cliente disser 'até agosto de 2027' (=2027-08)."},
                    "monthly_amount": {"type": "number", "description": "Quanto guarda por mês, se o cliente disser."},
                    "initial_saved": {"type": "number", "description": "Valor que já quer pôr logo no início, se disser."},
                    "auto_debit": {"type": "boolean", "description": "false só se o cliente não quiser débito automático. Omitir = automático."},
                    "start_month": {"type": "string", "description": "Mês de início AAAA-MM, se disser. Omitir = este mês."},
                    "debit_day": {"type": "integer", "description": "Dia do mês do débito automático (1-31). Se faltar, pergunta ao cliente."}
                },
                "required": ["name", "target_amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_expense",
            "description": "PREPARA o REGISTO de uma despesa que o cliente JÁ fez (ex.: 'gastei 5000 em táxi', 'regista 12 mil de supermercado'). Não regista: o cliente confirma no formulário. NÃO usar para criar metas de poupança.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Descrição curta (ex.: 'Táxi', 'Supermercado')."},
                    "amount": {"type": "number", "description": "Valor em Kz."},
                    "category": {"type": "string", "enum": ["Alimentação", "Transporte", "Habitação", "Telecomunicações", "Lazer", "Saúde", "Poupança", "Outros"]},
                    "expense_date": {"type": "string", "description": "Data AAAA-MM-DD (hoje/ontem convertidos). Omitir = hoje."}
                },
                "required": ["amount", "category"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_transfer",
            "description": "PREPARA uma transferência (não envia). method='account' para conta BankAO (nº de conta de 8-14 dígitos ou e-mail do cliente); method='iban' para IBAN de outro banco. Escolhe o method pelo que o cliente deu: IBAN (começa por letras, ex. AO06...) → 'iban'; número de conta/e-mail → 'account'. Se o cliente só deu um nome, procura primeiro em get_contacts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["account", "iban"]},
                    "destination": {"type": "string", "description": "Nº de conta BankAO, e-mail ou IBAN, exatamente como o cliente deu."},
                    "amount": {"type": "number", "description": "Valor a enviar (5 mil = 5000)."},
                    "currency": {"type": "string", "enum": ["AOA", "EUR", "USD"]},
                    "beneficiary_name": {"type": "string", "description": "Nome do destinatário, se souberes."}
                },
                "required": ["method", "destination", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_deposit",
            "description": "PREPARA um Depósito Express via Multicaixa Express (não executa). Precisa do telemóvel (9 dígitos, começa por 9) e do valor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone_number": {"type": "string"},
                    "amount": {"type": "number", "description": "Valor em Kz."}
                },
                "required": ["phone_number", "amount"]
            }
        }
    }
]


def execute_tool(tool_name: str, arguments: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Executa de forma segura uma ferramenta autorizada para o utilizador autenticado.
    O `user_id` é sempre injetado pelo backend autenticado e nunca pelo modelo.
    """
    logger.info(f"Executando ferramenta '{tool_name}' para user_id='{user_id}' com args={arguments}")

    try:
        if tool_name == "get_accounts_summary":
            return tool_get_accounts(user_id)

        elif tool_name == "get_account_statement":
            days = arguments.get("days", 30)
            limit = arguments.get("limit", 20)
            return tool_get_statement(user_id, days=days, limit=limit)

        elif tool_name == "get_incomes_summary":
            period = arguments.get("period", "this_month")
            return tool_get_incomes(user_id, period=period)

        elif tool_name == "get_expenses_analysis":
            category = arguments.get("category")
            period = arguments.get("period", "this_month")
            months_count = arguments.get("months_count", 1)
            min_amount = arguments.get("min_amount")
            order_by = arguments.get("order_by", "date_desc")
            limit = arguments.get("limit")
            exclude_savings = bool(arguments.get("exclude_savings", False))
            return tool_get_expenses_analysis(
                user_id,
                category=category,
                period=period,
                months_count=months_count,
                min_amount=min_amount,
                order_by=order_by,
                limit=limit,
                exclude_savings=exclude_savings
            )

        elif tool_name == "compare_expenses_periods":
            period1 = arguments.get("period1", "setembro")
            period2 = arguments.get("period2", "outubro")
            return tool_compare_expenses_periods(user_id, period1=period1, period2=period2)

        elif tool_name == "get_top_merchants":
            days = arguments.get("days", 365)
            limit = arguments.get("limit", 5)
            return tool_get_top_merchants(user_id, limit=limit, days=days)

        elif tool_name == "get_recurring_or_duplicate_expenses":
            return tool_get_recurring_or_duplicate_expenses(user_id)

        elif tool_name == "get_cards_overview":
            return tool_get_cards(user_id)

        elif tool_name == "get_card_spend_comparison":
            return tool_get_card_spend_comparison(user_id)

        elif tool_name == "get_investments_portfolio":
            return tool_get_investments_portfolio(user_id)

        elif tool_name == "get_investment_catalog":
            category = arguments.get("category")
            return tool_get_investment_catalog(category=category)

        elif tool_name == "simulate_investment":
            initial_amount = arguments.get("initial_amount", 0.0)
            monthly_contribution = arguments.get("monthly_contribution", 0.0)
            months = arguments.get("months", 12)
            annual_rate = arguments.get("annual_rate", 18.5)
            return tool_simulate_investment(
                initial_amount=initial_amount,
                monthly_contribution=monthly_contribution,
                months=months,
                annual_rate=annual_rate
            )

        elif tool_name == "get_transfer_fees_info":
            amount = arguments.get("amount", 10000.0)
            currency = arguments.get("currency", "AOA")
            return tool_get_transfer_fees_info(amount=amount, currency=currency)

        elif tool_name == "quote_transfer":
            destination = arguments.get("destination", "")
            amount = arguments.get("amount", 0.0)
            currency = arguments.get("currency", "AOA")
            beneficiary_name = arguments.get("beneficiary_name")
            return tool_quote_transfer(
                user_id=user_id,
                destination=destination,
                amount=amount,
                currency=currency,
                beneficiary_name=beneficiary_name
            )

        elif tool_name == "get_contacts":
            query = arguments.get("query")
            favorites_only = arguments.get("favorites_only", False)
            limit = arguments.get("limit", 10)
            return tool_get_contacts(
                user_id=user_id,
                query=query,
                favorites_only=favorites_only,
                limit=limit
            )

        elif tool_name == "get_financial_snapshot":
            return tool_get_financial_snapshot(user_id)

        elif tool_name == "get_financial_projection":
            months_ahead = arguments.get("months_ahead", 3)
            target_date = arguments.get("target_date")
            expense_multiplier = arguments.get("expense_multiplier", 1.0)
            monthly_savings_extra = arguments.get("monthly_savings_extra", 0.0)
            include_chart = arguments.get("include_chart", False)
            return tool_get_financial_projection(
                user_id,
                months_ahead=months_ahead,
                target_date=target_date,
                expense_multiplier=expense_multiplier,
                monthly_savings_extra=monthly_savings_extra,
                include_chart=include_chart
            )

        elif tool_name == "get_savings_goals":
            return tool_get_savings_goals(user_id)

        elif tool_name == "get_unrecorded_purchases":
            return tool_get_unrecorded_purchases(user_id)

        elif tool_name == "show_chart":
            return tool_show_chart(
                user_id,
                chart_type=arguments.get("chart_type", ""),
                month=arguments.get("month"),
                months=arguments.get("months"),
            )

        elif tool_name == "prepare_savings_goal":
            return tool_prepare_savings_goal(
                user_id,
                name=arguments.get("name"),
                icon_key=arguments.get("icon_key"),
                target_amount=arguments.get("target_amount"),
                months=arguments.get("months"),
                deadline=arguments.get("deadline"),
                monthly_amount=arguments.get("monthly_amount"),
                initial_saved=arguments.get("initial_saved"),
                auto_debit=arguments.get("auto_debit"),
                start_month=arguments.get("start_month"),
                debit_day=arguments.get("debit_day"),
            )

        elif tool_name == "prepare_expense":
            return tool_prepare_expense(
                user_id,
                name=arguments.get("name"),
                amount=arguments.get("amount"),
                category=arguments.get("category"),
                expense_date=arguments.get("expense_date"),
            )

        elif tool_name == "prepare_transfer":
            return tool_prepare_transfer(
                user_id,
                method=arguments.get("method", ""),
                destination=arguments.get("destination", ""),
                amount=arguments.get("amount", 0),
                currency=arguments.get("currency", "AOA"),
                beneficiary_name=arguments.get("beneficiary_name"),
            )

        elif tool_name == "prepare_deposit":
            return tool_prepare_deposit(
                user_id,
                phone_number=arguments.get("phone_number", ""),
                amount=arguments.get("amount", 0),
            )

        else:
            return {"error": f"Ferramenta desconhecida ou não autorizada: {tool_name}"}

    except Exception as e:
        logger.error(f"Erro na execução da ferramenta '{tool_name}': {e}", exc_info=True)
        return {"error": f"Falha ao executar a ferramenta: {str(e)}"}

import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')
from backend.database import get_connection

conn = get_connection()
user = conn.execute("SELECT id, nome FROM users WHERE email='joao.makiesse@bankao.ao'").fetchone()
user_id = user["id"]

print(f"Analyzing user: {user['nome']} ({user_id})\n")

# Q36: Maior gasto de setembro
q36 = conn.execute("SELECT name, category, amount_minor/100.0 as amt, expense_date FROM expenses WHERE user_id=? AND expense_date LIKE '2026-09%' ORDER BY amount_minor DESC LIMIT 3", (user_id,)).fetchall()
print("Q36 (Maior gasto setembro):")
for r in q36:
    print(f"  {r['expense_date']} | {r['name']} | {r['category']} | {r['amt']:,.2f} Kz")

# Q37: Total durante setembro
q37_all = conn.execute("SELECT SUM(amount_minor)/100.0 as tot, COUNT(*) as cnt FROM expenses WHERE user_id=? AND expense_date LIKE '2026-09%'", (user_id,)).fetchone()
q37_nosave = conn.execute("SELECT SUM(amount_minor)/100.0 as tot, COUNT(*) as cnt FROM expenses WHERE user_id=? AND expense_date LIKE '2026-09%' AND (origin != 'savings' OR origin IS NULL)", (user_id,)).fetchone()
print(f"\nQ37 (Total setembro): Total registado = {q37_all['tot']:,.2f} Kz ({q37_all['cnt']} itens); Apenas consumo = {q37_nosave['tot']:,.2f} Kz (excluindo 250k de poupança)")

# Q38: Categoria em que gastei mais dinheiro
q38 = conn.execute("SELECT category, SUM(amount_minor)/100.0 as tot, COUNT(*) as cnt FROM expenses WHERE user_id=? GROUP BY category ORDER BY tot DESC", (user_id,)).fetchall()
print("\nQ38 (Categoria com mais gastos no total):")
for r in q38:
    print(f"  {r['category']}: {r['tot']:,.2f} Kz")

# Q39: Alimentação no mês passado (outubro 2026)
q39 = conn.execute("SELECT SUM(amount_minor)/100.0 as tot, COUNT(*) as cnt FROM expenses WHERE user_id=? AND expense_date LIKE '2026-10%' AND (LOWER(category)='alimentação' OR LOWER(category)='alimentacao')", (user_id,)).fetchone()
q39_items = conn.execute("SELECT name, amount_minor/100.0 as amt, expense_date FROM expenses WHERE user_id=? AND expense_date LIKE '2026-10%' AND (LOWER(category)='alimentação' OR LOWER(category)='alimentacao')", (user_id,)).fetchall()
print(f"\nQ39 (Alimentação outubro 2026): {q39['tot']:,.2f} Kz ({q39['cnt']} itens)")
for it in q39_items:
    print(f"  {it['expense_date']}: {it['name']} = {it['amt']:,.2f} Kz")

# Q40: Transportes nos últimos 3 meses (agosto, setembro, outubro 2026)
q40 = conn.execute("SELECT SUM(amount_minor)/100.0 as tot, COUNT(*) as cnt FROM expenses WHERE user_id=? AND expense_date >= '2026-08-01' AND expense_date <= '2026-10-31' AND LOWER(category)='transporte'", (user_id,)).fetchone()
print(f"\nQ40 (Transportes últimos 3 meses: ago-out): {q40['tot']:,.2f} Kz ({q40['cnt']} itens)")

# Q41: 5 maiores despesas deste ano
q41 = conn.execute("SELECT expense_date, name, category, amount_minor/100.0 as amt, origin FROM expenses WHERE user_id=? AND expense_date LIKE '2026%' ORDER BY amount_minor DESC LIMIT 8", (user_id,)).fetchall()
print("\nQ41 (5 maiores despesas deste ano):")
for r in q41[:5]:
    print(f"  {r['expense_date']} | {r['amt']:,.2f} Kz | {r['category']} | {r['name']} ({r['origin']})")

# Q42: Estabelecimento onde gastei mais dinheiro
q42 = conn.execute("SELECT name, category, SUM(amount_minor)/100.0 as tot, COUNT(*) as cnt FROM expenses WHERE user_id=? AND (origin != 'savings' OR origin IS NULL) GROUP BY LOWER(TRIM(name)) ORDER BY tot DESC LIMIT 5", (user_id,)).fetchall()
print("\nQ42 (Top estabelecimentos de consumo):")
for r in q42:
    print(f"  {r['name']}: {r['tot']:,.2f} Kz ({r['cnt']} compras)")

# Q43: Compara setembro com outubro
q43_sep = conn.execute("SELECT SUM(amount_minor)/100.0 as tot FROM expenses WHERE user_id=? AND expense_date LIKE '2026-09%'", (user_id,)).fetchone()[0]
q43_oct = conn.execute("SELECT SUM(amount_minor)/100.0 as tot FROM expenses WHERE user_id=? AND expense_date LIKE '2026-10%'", (user_id,)).fetchone()[0]
print(f"\nQ43 (Setembro vs Outubro): Setembro = {q43_sep:,.2f} Kz | Outubro = {q43_oct:,.2f} Kz | Diferença = {(q43_oct - q43_sep):+,.2f} Kz")

# Q44: Em que mês gastei mais dinheiro este ano
q44 = conn.execute("SELECT strftime('%Y-%m', expense_date) as ym, SUM(amount_minor)/100.0 as tot FROM expenses WHERE user_id=? AND expense_date LIKE '2026%' GROUP BY ym ORDER BY tot DESC", (user_id,)).fetchall()
print("\nQ44 (Meses por ordem de gastos):")
for r in q44:
    print(f"  {r['ym']}: {r['tot']:,.2f} Kz")

# Q46: Quanto gasto mensalmente em média
q46_months = conn.execute("SELECT strftime('%Y-%m', expense_date) as ym, SUM(amount_minor)/100.0 as tot, SUM(CASE WHEN origin!='savings' THEN amount_minor ELSE 0 END)/100.0 as consumer_tot FROM expenses WHERE user_id=? AND expense_date < '2026-11-01' GROUP BY ym", (user_id,)).fetchall()
print("\nQ46 (Médias mensais meses completos):")
for m in q46_months:
    print(f"  {m['ym']}: Total={m['tot']:,.2f} Kz, Consumo={m['consumer_tot']:,.2f} Kz")
avg_tot = sum(m['tot'] for m in q46_months) / len(q46_months)
avg_con = sum(m['consumer_tot'] for m in q46_months) / len(q46_months)
print(f"  Média Total: {avg_tot:,.2f} Kz/mês | Média Consumo: {avg_con:,.2f} Kz/mês")

# Q47: Despesas durante a última semana (2026-10-27 a 2026-11-02)
q47 = conn.execute("SELECT expense_date, name, category, amount_minor/100.0 as amt FROM expenses WHERE user_id=? AND expense_date >= '2026-10-27' ORDER BY expense_date DESC", (user_id,)).fetchall()
print(f"\nQ47 (Despesas na última semana - 2026-10-27 a 2026-11-02): {len(q47)} itens")
for r in q47:
    print(f"  {r['expense_date']} | {r['amt']:,.2f} Kz | {r['name']} ({r['category']})")

# Q49: Despesas superiores a 20.000 Kz
q49 = conn.execute("SELECT expense_date, name, category, amount_minor/100.0 as amt FROM expenses WHERE user_id=? AND amount_minor > 2000000 ORDER BY amount_minor DESC", (user_id,)).fetchall()
print(f"\nQ49 (Despesas > 20.000 Kz): {len(q49)} itens")
for r in q49[:8]:
    print(f"  {r['expense_date']} | {r['amt']:,.2f} Kz | {r['name']} ({r['category']})")

# Q50: Despesas repetidas ou semelhantes
q50 = conn.execute("SELECT name, category, COUNT(*) as cnt, AVG(amount_minor)/100.0 as avg_amt, SUM(amount_minor)/100.0 as tot FROM expenses WHERE user_id=? GROUP BY LOWER(TRIM(name)) HAVING cnt > 1 ORDER BY cnt DESC", (user_id,)).fetchall()
print(f"\nQ50 (Despesas recorrentes / repetidas):")
for r in q50:
    print(f"  {r['name']} ({r['category']}): {r['cnt']}x (Média: {r['avg_amt']:,.2f} Kz)")

# Q51: Restaurantes desde janeiro
q51 = conn.execute("SELECT SUM(amount_minor)/100.0 as tot, COUNT(*) as cnt FROM expenses WHERE user_id=? AND (LOWER(category)='restaurantes' OR LOWER(category)='restaurante' OR LOWER(name) LIKE '%restaurante%') AND expense_date LIKE '2026%'", (user_id,)).fetchone()
print(f"\nQ51 (Restaurantes em 2026): {q51['tot']:,.2f} Kz ({q51['cnt']} refeições/jantares)")

# Q52: Maior despesa nos últimos 30 dias (desde 2026-10-03)
q52 = conn.execute("SELECT expense_date, name, category, amount_minor/100.0 as amt, origin FROM expenses WHERE user_id=? AND expense_date >= '2026-10-03' ORDER BY amount_minor DESC LIMIT 3", (user_id,)).fetchall()
print(f"\nQ52 (Maior despesa últimos 30 dias):")
for r in q52:
    print(f"  {r['expense_date']} | {r['amt']:,.2f} Kz | {r['name']} ({r['category']})")

conn.close()


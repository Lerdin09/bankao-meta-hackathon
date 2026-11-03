import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')
from backend.database import get_connection

conn = get_connection()
user = conn.execute("SELECT id, nome FROM users WHERE email='joao.makiesse@bankao.ao'").fetchone()
user_id = user["id"]
print("User:", user["nome"], user_id)

exp_cols = [c[1] for c in conn.execute("PRAGMA table_info(expenses)").fetchall()]
print("Expenses columns:", exp_cols)

count = conn.execute("SELECT count(*) FROM expenses WHERE user_id=?", (user_id,)).fetchone()[0]
print(f"Total expenses: {count}")

rows = conn.execute("SELECT * FROM expenses WHERE user_id=? ORDER BY expense_date DESC LIMIT 15", (user_id,)).fetchall()
for r in rows:
    print(dict(r))

# Categories
cats = conn.execute("SELECT category, count(*), sum(amount_minor)/100.0 as tot FROM expenses WHERE user_id=? GROUP BY category ORDER BY tot DESC", (user_id,)).fetchall()
print("\nCategories summary:")
for c in cats:
    print(f"  {c['category']}: {c['tot']:,.2f} Kz ({c['count(*)']} items)")

# Months
months = conn.execute("SELECT strftime('%Y-%m', expense_date) as ym, count(*), sum(amount_minor)/100.0 as tot FROM expenses WHERE user_id=? GROUP BY ym ORDER BY ym", (user_id,)).fetchall()
print("\nMonths summary:")
for m in months:
    print(f"  {m['ym']}: {m['tot']:,.2f} Kz ({m['count(*)']} items)")

conn.close()


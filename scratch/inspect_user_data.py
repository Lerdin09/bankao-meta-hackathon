import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')
from backend.database import get_connection

conn = get_connection()
user = conn.execute("SELECT id, nome FROM users WHERE email='joao.makiesse@bankao.ao'").fetchone()
user_id = user["id"]

print("=== ALL EXPENSES FOR JOÃO PEDRO ===")
all_exp = conn.execute("SELECT expense_date, name, category, amount_minor/100.0 as amt, origin, notes FROM expenses WHERE user_id=? ORDER BY expense_date DESC", (user_id,)).fetchall()
for e in all_exp:
    print(f"{e['expense_date']} | {e['amt']:>10,.2f} Kz | {e['category']:<16} | {e['name']} (origin: {e['origin']})")

print("\n=== LEDGER ENTRIES FOR JOÃO PEDRO (MOVIMENTOS BANCÁRIOS) ===")
ledgers = conn.execute("""
    SELECT le.created_at, le.entry_type, le.amount_minor/100.0 as amt, le.balance_after_minor/100.0 as bal, le.description
    FROM ledger_entries le
    JOIN accounts a ON a.id = le.account_id
    WHERE a.user_id = ?
    ORDER BY le.created_at DESC
    LIMIT 20
""", (user_id,)).fetchall()
for l in ledgers:
    print(f"{l['created_at']} | {l['amt']:>10,.2f} Kz | {l['entry_type']:<7} | {l['description']}")

conn.close()


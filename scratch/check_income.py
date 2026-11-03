import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
from backend.database import get_connection

USER_ID = '2e0a4847-d1a9-48a6-86de-40229a125b58'

with get_connection() as conn:
    # Get user's account details
    print("--- USER ACCOUNTS ---")
    accounts = conn.execute("SELECT * FROM accounts WHERE user_id=?", (USER_ID,)).fetchall()
    for a in accounts:
        print(dict(a))
    
    # Get ledger entries for user's accounts
    if accounts:
        account_ids = [a['id'] for a in accounts]
        print(f"\n--- LEDGER ENTRIES (account_ids: {account_ids}) ---")
        for acc_id in account_ids:
            entries = conn.execute(
                "SELECT le.*, t.type, t.description FROM ledger_entries le "
                "JOIN transactions t ON le.transaction_id = t.id "
                "WHERE le.account_id=? ORDER BY le.created_at DESC LIMIT 10",
                (acc_id,)
            ).fetchall()
            if entries:
                for e in entries:
                    print(dict(e))
            else:
                print(f"No entries for account {acc_id}")
    
    # Check deposits (income sources)
    print("\n--- DEPOSITS ---")
    deps = conn.execute("""
        SELECT d.*, a.user_id FROM deposits d 
        JOIN accounts a ON d.account_id = a.id 
        WHERE a.user_id=? ORDER BY d.created_at DESC LIMIT 10
    """, (USER_ID,)).fetchall()
    for d in deps: print(dict(d))
    if not deps: print("No deposits")
    
    # Check copilot_memory
    print("\n--- COPILOT MEMORY ---")
    mem = conn.execute("SELECT * FROM copilot_memory WHERE user_id=?", (USER_ID,)).fetchall()
    for m in mem: print(dict(m))
    if not mem: print("No memory entries")


import sys
import os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')
from backend.ai.orchestrator import CopilotOrchestrator
from backend.database import get_connection

conn = get_connection()
user = conn.execute("SELECT id FROM users WHERE email='joao.makiesse@bankao.ao'").fetchone()
conn.close()

res = CopilotOrchestrator.process_message(
    user_id=user["id"],
    message="Se começar a poupar 50.000 Kz por mês, quando atingirei 500.000 Kz?"
)
print("Tools:", res.get("tools_used"))
print("Reply:\n", res.get("reply"))

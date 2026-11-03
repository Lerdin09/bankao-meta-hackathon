import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
import uuid
from backend.database import get_connection

USER_ID = '2e0a4847-d1a9-48a6-86de-40229a125b58'
CARLOS_IBAN = 'AO06004000001298765432101' # IBAN angolano

with get_connection() as conn:
    # Check if Carlos already exists
    existing = conn.execute("SELECT * FROM contacts WHERE user_id=? AND (name LIKE '%Carlos%' OR nickname LIKE '%Carlos%')", (USER_ID,)).fetchone()
    if not existing:
        ref_key = f"i:{CARLOS_IBAN}"
        conn.execute(
            """INSERT INTO contacts (id, user_id, kind, ref_key, name, nickname, iban, favorite)
               VALUES (?, ?, 'iban', ?, 'Carlos Silva', 'Carlos', ?, 1)""",
            (str(uuid.uuid4()), USER_ID, ref_key, CARLOS_IBAN)
        )
        conn.commit()
        print("Contact Carlos inserted successfully!")
    else:
        print("Carlos already exists:", dict(existing))


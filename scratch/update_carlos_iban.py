import sys, os
sys.path.insert(0, os.path.abspath('.'))
from backend.database import get_connection

USER_ID = '2e0a4847-d1a9-48a6-86de-40229a125b58'
VALID_IBAN = 'AO80004085549593785637273'

with get_connection() as conn:
    conn.execute("UPDATE contacts SET iban=?, ref_key=? WHERE user_id=? AND name LIKE '%Carlos%'", (VALID_IBAN, f"i:{VALID_IBAN}", USER_ID))
    conn.commit()
    print("Updated Carlos with valid IBAN:", VALID_IBAN)


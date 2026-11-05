"""
Script utilitário para popular manualmente utilizadores de demonstração.
(Nota: o BankAO agora também executa este seed automaticamente no arranque se a base estiver vazia).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database.seed import seed_demo_users

if __name__ == "__main__":
    seed_demo_users()
    print("Seed de demonstração verificado e pronto.")

"""
Agregador das rotas da API. Para criar uma nova rota:
  1. criar backend/api/routes/<nome>.py com `router = APIRouter(prefix="/api/<nome>", ...)`;
  2. adicioná-la à lista abaixo.
"""
from fastapi import APIRouter

from backend.api.routes import (
    auth,
    kyc,
    accounts,
    deposits,
    users,
    transfers,
    iban,
    fx,
    transactions,
    expenses,
    savings,
    ai,
    analytics,
    investments,
    cards,
    contacts,
    settings,
    eleven,
)

api_router = APIRouter()
for _module in (
    auth,
    kyc,
    accounts,
    deposits,
    users,
    transfers,
    iban,
    fx,
    transactions,
    expenses,
    savings,
    ai,
    analytics,
    investments,
    cards,
    contacts,
    settings,
    eleven,
):
    api_router.include_router(_module.router)

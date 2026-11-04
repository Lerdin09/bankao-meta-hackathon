"""
Modelos Pydantic — despesas, orçamentos por categoria e metas de poupança.
Os valores chegam e saem em unidades decimais (ex.: 15000.50 Kz); na base de dados guardam-se em cêntimos.
"""
import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

CATEGORIAS = ("Alimentação", "Transporte", "Habitação", "Telecomunicações", "Eletrónicos", "Lazer", "Saúde", "Poupança", "Transferências", "Investimentos", "Outros")
_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ExpenseIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = "Outros"
    amount: float = Field(gt=0)
    currency: str = "AOA"
    date: str
    origin: str = "manual"
    notes: Optional[str] = Field(default="", max_length=300)

    @field_validator("date")
    @classmethod
    def _valida_data(cls, v: str) -> str:
        if not _DATA.match(v):
            raise ValueError("Data inválida (use AAAA-MM-DD).")
        return v

    @field_validator("category")
    @classmethod
    def _valida_categoria(cls, v: str) -> str:
        return v if v in CATEGORIAS else "Outros"

    @field_validator("origin")
    @classmethod
    def _valida_origem(cls, v: str) -> str:
        return v if v in ("manual", "ai", "savings", "transfer", "investment") else "manual"


class BudgetIn(BaseModel):
    amount: float = Field(gt=0)


class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    target: float = Field(gt=0)
    saved: float = Field(default=0, ge=0)
    monthly: float = Field(default=0, ge=0)
    deadline: Optional[str] = Field(default="Indefinido", max_length=40)
    icon_key: str = "target"
    status: str = "on-track"
    debit_day: Optional[int] = Field(default=None, ge=1, le=31)   # dia do mês do débito automático
    start_date: Optional[str] = None                              # primeira data de débito (AAAA-MM-DD)

    @field_validator("start_date")
    @classmethod
    def _valida_inicio(cls, v):
        if v in (None, ""):
            return None
        if not _DATA.match(v):
            raise ValueError("Data de início inválida (use AAAA-MM-DD).")
        return v

    @field_validator("status")
    @classmethod
    def _valida_estado(cls, v: str) -> str:
        return v if v in ("on-track", "at-risk", "completed") else "on-track"


class GoalDepositIn(BaseModel):
    amount: float = Field(gt=0)
    date: Optional[str] = None
    idempotency_key: Optional[str] = Field(default=None, max_length=80)
    notes: Optional[str] = Field(default="", max_length=300)

    @field_validator("date")
    @classmethod
    def _valida_data(cls, v):
        if v is not None and not _DATA.match(v):
            raise ValueError("Data inválida (use AAAA-MM-DD).")
        return v

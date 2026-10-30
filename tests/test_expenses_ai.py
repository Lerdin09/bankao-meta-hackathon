# -*- coding: utf-8 -*-
from app.ai.assistant import extract_action_intent

def test_extract_expense_intent_supermarket():
    action = extract_action_intent("gastei 15000 kz no supermercado maxi")
    assert action is not None
    assert action["type"] == "REGISTER_EXPENSE"
    assert "Alimentação" in action["category"]
    assert action["amount"] == 15000.0
    assert "maxi" in action["name"].lower()

def test_extract_expense_intent_fuel():
    action = extract_action_intent("regista 25000 kz de combustivel sonangol")
    assert action is not None
    assert action["type"] == "REGISTER_EXPENSE"
    assert action["category"] == "Transporte"
    assert action["amount"] == 25000.0
    assert "sonangol" in action["name"].lower()

def test_extract_expense_intent_rent():
    action = extract_action_intent("anota despesa de 60000 kz renda de casa")
    assert action is not None
    assert action["type"] == "REGISTER_EXPENSE"
    assert "Habitação" in action["category"]
    assert action["amount"] == 60000.0

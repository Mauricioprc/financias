"""Atalho de lançamento rápido em texto livre: "<valor> <resto>" (ex.: "50
mercado", "45,90 uber", "gastei 120 farmacia") — o número pode estar em
qualquer posição do texto, não precisa ser o primeiro token.

Reconhece SEMPRE despesa, nunca receita: texto livre é ambíguo demais pra
tentar adivinhar o tipo (nada no texto indica "isso foi um recebimento"),
e despesa é disparadamente o caso de uso dominante de lançamento rápido —
"50 mercado" é claramente um gasto, não uma receita. Quem quiser lançar
receita usa o menu normal (bot/handlers/transactions.py, pergunta o tipo
explicitamente).
"""

import re

from bot.formatting import parse_amount

_TOKEN_RE = re.compile(r"\S+")


def try_parse_quick_entry(text: str) -> dict | None:
    """{"amount": Decimal, "description_hint": str} se algum token do texto
    for reconhecível como valor (bot.formatting.parse_amount); `None` se
    nenhum token parsear — nesse caso não é um lançamento rápido, quem
    chamou deve cair no comportamento normal (menu/'não entendi')."""
    if not text:
        return None

    tokens = _TOKEN_RE.findall(text)
    for index, token in enumerate(tokens):
        amount = parse_amount(token)
        if amount is None:
            continue
        remaining = tokens[:index] + tokens[index + 1 :]
        return {"amount": amount, "description_hint": " ".join(remaining).strip()}

    return None

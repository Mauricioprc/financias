"""Formatação de texto pra respostas do bot (sem depender de locale do SO)."""

from decimal import Decimal, InvalidOperation


def money(value) -> str:
    n = Decimal(value)
    sign = "-" if n < 0 else ""
    formatted = f"{abs(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sign}R$ {formatted}"


def parse_amount(text: str) -> Decimal | None:
    """Aceita '50', '50,00', '50.00', 'R$ 50,00'. Retorna None se inválido
    ou <= 0."""
    cleaned = text.strip().replace("R$", "").replace(" ", "")
    if not cleaned:
        return None

    # Se tem os dois separadores, o último é o decimal (ex.: "1.234,56").
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None

    if value <= 0:
        return None
    return value

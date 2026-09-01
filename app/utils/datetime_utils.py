"""Aritmética de datas por mês — usada por qualquer coisa que precise
avançar N meses preservando o dia (fatura de cartão, recorrência, parcelas).

Extraído daqui porque `invoice_service` e `recurring_transaction_service` já
tinham cada um sua própria cópia dessas duas funções antes desta mudança —
`create_installment_purchase` (parcelamento, Fase 6.1) precisava da mesma
lógica, então virou utilitário único em vez de uma terceira cópia."""

import calendar
from datetime import date


def clamped_date(year: int, month: int, day: int) -> date:
    """`day` limitado ao último dia real de `month/year` — evita erro em
    meses mais curtos (ex.: dia 31 de janeiro + 1 mês -> 28/29 de fevereiro,
    não uma exceção)."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def add_months(year: int, month: int, months: int) -> tuple[int, int]:
    """(ano, mês) resultante de somar `months` a `year/month` (`months` pode
    ser negativo). Não lida com o dia — combine com `clamped_date`."""
    total = (year * 12) + (month - 1) + months
    return total // 12, (total % 12) + 1


def shift_date(reference: date, months: int) -> date:
    """`reference` deslocada em `months`, preservando o dia (com clamp)."""
    year, month = add_months(reference.year, reference.month, months)
    return clamped_date(year, month, reference.day)

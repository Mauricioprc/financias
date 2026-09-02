"""Categorização automática por padrão description -> category. SEM
machine learning: contagem simples de quantas vezes uma descrição
normalizada já foi lançada em cada categoria — sugere a mais frequente
depois de um mínimo de ocorrências."""

import re

from app.extensions import db
from app.models.category_suggestion_pattern import CategorySuggestionPattern

MIN_MATCHES_FOR_SUGGESTION = 2

_DIGIT_SEQUENCE_RE = re.compile(r"\d+")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_description(description: str) -> str:
    """Normalização "boa o suficiente", não perfeita: lowercase + trim +
    remove sequências de dígitos (números de transação/código que variam a
    cada lançamento mas não mudam o "tipo" do gasto — ex.: "UBER *TRIP
    8829" e "UBER *TRIP 4471" viram o mesmo padrão "uber *trip ").

    Limitação conhecida e aceita: não lida com variação de texto livre
    (abreviações diferentes, erro de digitação, ordem de palavras trocada)
    — é normalização de string, não NLP. Descrições genuinamente diferentes
    que "deveriam" ser o mesmo padrão na cabeça do usuário não vão casar;
    isso é aceitável porque o pior caso é só "não sugere nada", nunca
    sugere errado por aproximação demais.
    """
    normalized = description.strip().lower()
    normalized = _DIGIT_SEQUENCE_RE.sub("", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized


def record_pattern(user_id: int, description: str, category_id: int | None) -> None:
    """Registra (ou reforça) o padrão description->category. Chamada
    interna e silenciosa — não é uma decisão do usuário, roda sempre que
    uma transação com categoria é criada/atualizada (ver
    transaction_service.create_transaction/update_transaction). Não
    comita: fica dentro da mesma transação de banco do commit que o
    chamador já vai fazer, pra não persistir o padrão se o resto da
    operação falhar.

    Sem categoria, não há o que aprender — `category_id=None` é um no-op.
    """
    if category_id is None:
        return

    normalized = normalize_description(description)
    if not normalized:
        return

    pattern = (
        db.session.query(CategorySuggestionPattern)
        .filter_by(user_id=user_id, normalized_description=normalized, category_id=category_id)
        .first()
    )
    if pattern is not None:
        # Incremento simples em Python, não UPDATE atômico via SQL: ao
        # contrário de campos monetários (ver ledger_utils.py),
        # match_count é só um contador heurístico de sugestão — uma
        # eventual escrita perdida sob concorrência quase inexistente
        # (mesmo usuário lançando a mesma descrição ao mesmo tempo em duas
        # abas) não tem consequência financeira nenhuma, só atrasa um
        # pouco a sugestão ficar mais confiável.
        pattern.match_count += 1
    else:
        db.session.add(
            CategorySuggestionPattern(
                user_id=user_id,
                normalized_description=normalized,
                category_id=category_id,
                match_count=1,
            )
        )


def suggest_category(user_id: int, description: str) -> int | None:
    """Categoria mais frequentemente associada a essa descrição (depois de
    normalizada), desde que tenha aparecido pelo menos
    `MIN_MATCHES_FOR_SUGGESTION` vezes — uma ocorrência isolada não é
    padrão confiável o suficiente pra sugerir. `None` quando não há
    nenhum padrão que bata (ou nenhum confiável o bastante)."""
    normalized = normalize_description(description)
    if not normalized:
        return None

    pattern = (
        db.session.query(CategorySuggestionPattern)
        .filter(
            CategorySuggestionPattern.user_id == user_id,
            CategorySuggestionPattern.normalized_description == normalized,
            CategorySuggestionPattern.match_count >= MIN_MATCHES_FOR_SUGGESTION,
        )
        .order_by(CategorySuggestionPattern.match_count.desc())
        .first()
    )
    return pattern.category_id if pattern is not None else None

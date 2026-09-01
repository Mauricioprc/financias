"""'Metas' — direto, só leitura. Criar/editar meta continua exclusivo do
dashboard por enquanto: tem mais campos (nome, data alvo) do que vale a pena
pedir em passos separados no WhatsApp antes de validar que faz sentido."""

from app.services import goal_service
from bot import whatsapp_client
from bot.conversation import to_wa_id
from bot.formatting import money

_STATUS_LABELS = {
    "in_progress": "Em andamento",
    "achieved": "Concluída",
    "abandoned": "Abandonada",
}


def handle_goals(user) -> None:
    goals = goal_service.list_goals(user.id)
    to = to_wa_id(user.phone_number)

    if not goals:
        whatsapp_client.send_text(to, "Você ainda não tem nenhuma meta cadastrada.")
        return

    lines = ["Suas metas:", ""]
    for goal in goals:
        status_label = _STATUS_LABELS.get(goal.status, goal.status)
        pct = (
            0
            if goal.target_amount <= 0
            else min(100, int(goal.current_amount / goal.target_amount * 100))
        )
        lines.append(
            f"• {goal.name} ({status_label}): {money(goal.current_amount)} de "
            f"{money(goal.target_amount)} ({pct}%)"
        )

    whatsapp_client.send_text(to, "\n".join(lines))

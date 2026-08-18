"""Bot do WhatsApp — cliente HTTP da mesma API que o dashboard web usa.

Nunca acessa o banco direto nem duplica regra de negócio: cada handler em
bot/handlers/ chama o service correspondente em app/services/, exatamente
como as rotas de app/api/v1/ fazem. Ver ARCHITECTURE.md seção 3.2 e o plano
da Fase D para o design completo dos fluxos.

Fase D1 (fundação, atual): só bot/webhook.py existe, com a verificação GET
do webhook funcionando. Os módulos abaixo chegam nas fases seguintes:

- whatsapp_client.py — wrapper fino da API de envio da Meta.
- auth.py — valida assinatura do webhook, resolve user_id a partir do telefone.
- conversation.py — máquina de estados (lê/grava BotConversationState).
- menus.py — definição declarativa dos menus/fluxos.
- handlers/ — um módulo por entidade (transactions, accounts, goals, ...).
"""

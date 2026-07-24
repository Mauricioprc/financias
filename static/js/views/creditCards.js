/* Cartões de crédito. */

function renderCreditCardsView(container) {
  mountCrudView(container, {
    title: "Cartões",
    icon: "💳",
    emptyText: "Cadastre seu primeiro cartão de crédito.",
    fields: [
      { name: "name", label: "Nome", required: true },
      { name: "credit_limit", label: "Limite (R$)", type: "number", step: "0.01", required: true },
      {
        name: "closing_day",
        label: "Dia de fechamento",
        type: "number",
        min: 1,
        max: 31,
        required: true,
      },
      {
        name: "due_day",
        label: "Dia de vencimento",
        type: "number",
        min: 1,
        max: 31,
        required: true,
      },
    ],
    editFields: [
      { name: "name", label: "Nome", required: true },
      { name: "credit_limit", label: "Limite (R$)", type: "number", step: "0.01" },
      { name: "closing_day", label: "Dia de fechamento", type: "number", min: 1, max: 31 },
      { name: "due_day", label: "Dia de vencimento", type: "number", min: 1, max: 31 },
      { name: "is_archived", label: "Arquivado", type: "checkbox" },
    ],
    loadItems: () => Api.creditCards.list(),
    createItem: (data) => Api.creditCards.create(data),
    updateItem: (id, data) => Api.creditCards.update(id, data),
    removeItem: (id) => Api.creditCards.remove(id),
    renderItem: (c) => ({
      title: c.name + (c.is_archived ? " (arquivado)" : ""),
      subtitle: `Limite ${UI.money(c.credit_limit)} · fecha dia ${c.closing_day}, vence dia ${c.due_day}`,
      value: null,
    }),
    extraRowActions: (card) => [
      UI.el(
        "button",
        {
          class: "btn btn--secondary btn--sm",
          onclick: () => Router.navigate(`/credit-cards/${card.id}/invoices`),
        },
        "Faturas"
      ),
    ],
  });
}

Router.register("/credit-cards", renderCreditCardsView);

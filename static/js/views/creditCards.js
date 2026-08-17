/* Cartões de crédito. */

function renderCreditCardsView(container) {
  mountCrudView(container, {
    title: "Cartões",
    icon: "credit-card",
    emptyText: "Cadastre seu primeiro cartão de crédito.",
    fields: [
      { name: "name", label: "Nome", required: true },
      { name: "bank_name", label: "Banco (opcional)" },
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
      { name: "bank_name", label: "Banco (opcional)" },
      { name: "credit_limit", label: "Limite (R$)", type: "number", step: "0.01" },
      { name: "closing_day", label: "Dia de fechamento", type: "number", min: 1, max: 31 },
      { name: "due_day", label: "Dia de vencimento", type: "number", min: 1, max: 31 },
      { name: "is_archived", label: "Arquivado", type: "checkbox" },
    ],
    loadItems: async () => {
      const cards = await Api.creditCards.list();
      const openInvoices = await Promise.all(
        cards.map((c) =>
          Api.invoices.list({ credit_card_id: c.id, status: "open" }).catch(() => [])
        )
      );
      return cards.map((c, i) => ({
        ...c,
        usedAmount: openInvoices[i].reduce((sum, inv) => sum + Number(inv.total_amount), 0),
      }));
    },
    createItem: (data) => Api.creditCards.create(data),
    updateItem: (id, data) => Api.creditCards.update(id, data),
    removeItem: (id) => Api.creditCards.remove(id),
    renderItem: (c) => {
      const limit = Number(c.credit_limit) || 1;
      const pct = Math.min(100, Math.round((c.usedAmount / limit) * 100));
      return {
        title:
          (c.bank_name ? `${c.bank_name} · ` : "") + c.name + (c.is_archived ? " (arquivado)" : ""),
        subtitle: `${UI.money(c.usedAmount)} de ${UI.money(c.credit_limit)} usados (${pct}%) · fecha dia ${c.closing_day}, vence dia ${c.due_day}`,
        value: null,
        progress: c.is_archived
          ? null
          : { pct, className: pct >= 90 ? "progress-bar__fill--danger" : pct >= 70 ? "progress-bar__fill--warning" : "" },
      };
    },
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

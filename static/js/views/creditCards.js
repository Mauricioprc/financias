/* Cartões de crédito. */

async function renderCreditCardsView(container) {
  container.appendChild(UI.el("div", { class: "loading" }, "Carregando..."));

  let accounts;
  try {
    accounts = await Api.accounts.list();
  } catch (err) {
    container.innerHTML = "";
    UI.showApiError(err);
    return;
  }
  container.innerHTML = "";

  const accountOptions = [{ value: "", label: "(nenhuma)" }].concat(
    accounts.map((a) => ({ value: a.id, label: a.name }))
  );
  const accountNameById = Object.fromEntries(accounts.map((a) => [String(a.id), a.name]));

  const accountField = {
    name: "account_id",
    label: "Conta vinculada (opcional)",
    type: "select",
    options: accountOptions,
  };

  // Vincular um cartão a uma conta é o que permite ao formulário de Nova
  // Transação filtrar/pré-selecionar o cartão certo pra conta escolhida —
  // ver categoryOptionsForType/creditCardOptionsForAccount em transactions.js.
  function toAccountId(values) {
    return { ...values, account_id: values.account_id ? Number(values.account_id) : null };
  }

  mountCrudView(container, {
    title: "Cartões",
    icon: "credit-card",
    emptyText: "Cadastre seu primeiro cartão de crédito.",
    fields: [
      { name: "name", label: "Nome", required: true },
      { name: "bank_name", label: "Banco (opcional)" },
      accountField,
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
      accountField,
      { name: "credit_limit", label: "Limite (R$)", type: "number", step: "0.01" },
      { name: "closing_day", label: "Dia de fechamento", type: "number", min: 1, max: 31 },
      { name: "due_day", label: "Dia de vencimento", type: "number", min: 1, max: 31 },
      { name: "is_archived", label: "Arquivado", type: "checkbox" },
    ],
    transformSubmit: toAccountId,
    loadItems: async () => {
      const cards = await Api.creditCards.list();
      const [openInvoices, currentInvoices] = await Promise.all([
        Promise.all(
          cards.map((c) =>
            Api.invoices.list({ credit_card_id: c.id, status: "open" }).catch(() => [])
          )
        ),
        Promise.all(cards.map((c) => Api.creditCards.currentInvoice(c.id).catch(() => null))),
      ]);
      return cards.map((c, i) => ({
        ...c,
        usedAmount: openInvoices[i].reduce((sum, inv) => sum + Number(inv.total_amount), 0),
        currentInvoice: currentInvoices[i],
      }));
    },
    createItem: (data) => Api.creditCards.create(data),
    updateItem: (id, data) => Api.creditCards.update(id, data),
    removeItem: (id) => Api.creditCards.remove(id),
    renderItem: (c) => {
      const limit = Number(c.credit_limit) || 1;
      const pct = Math.min(100, Math.round((c.usedAmount / limit) * 100));
      const accountLabel = c.account_id ? accountNameById[String(c.account_id)] : null;
      const currentInvoiceLabel = c.currentInvoice
        ? c.currentInvoice.persisted
          ? `fatura atual: ${UI.money(c.currentInvoice.total_amount)}`
          : "fatura atual: ainda sem compras"
        : null;
      const subtitleParts = [
        `${UI.money(c.usedAmount)} de ${UI.money(c.credit_limit)} usados (${pct}%)`,
        `fecha dia ${c.closing_day}, vence dia ${c.due_day}`,
        accountLabel ? `conta: ${accountLabel}` : null,
        currentInvoiceLabel,
      ].filter(Boolean);
      return {
        title:
          (c.bank_name ? `${c.bank_name} · ` : "") + c.name + (c.is_archived ? " (arquivado)" : ""),
        subtitle: subtitleParts.join(" · "),
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

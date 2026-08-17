/* Contas bancárias / carteiras. */

const ACCOUNT_TYPE_LABELS = {
  checking: "Conta corrente",
  savings: "Poupança",
  wallet: "Carteira",
  other: "Outro",
};

function renderAccountsView(container) {
  mountCrudView(container, {
    title: "Contas",
    icon: "landmark",
    emptyText: "Cadastre sua primeira conta para começar.",
    fields: [
      { name: "name", label: "Nome", required: true },
      {
        name: "type",
        label: "Tipo",
        type: "select",
        required: true,
        options: Object.entries(ACCOUNT_TYPE_LABELS).map(([value, label]) => ({ value, label })),
      },
      { name: "initial_balance", label: "Saldo inicial (R$)", type: "number", step: "0.01" },
    ],
    editFields: [
      { name: "name", label: "Nome", required: true },
      {
        name: "type",
        label: "Tipo",
        type: "select",
        required: true,
        options: Object.entries(ACCOUNT_TYPE_LABELS).map(([value, label]) => ({ value, label })),
      },
      { name: "is_archived", label: "Arquivada", type: "checkbox" },
    ],
    loadItems: () => Api.accounts.list(),
    createItem: (data) => Api.accounts.create(data),
    updateItem: (id, data) => Api.accounts.update(id, data),
    removeItem: (id) => Api.accounts.remove(id),
    renderItem: (a) => ({
      title: a.name + (a.is_archived ? " (arquivada)" : ""),
      subtitle: ACCOUNT_TYPE_LABELS[a.type] || a.type,
      value: UI.money(a.current_balance),
      valueClass: Number(a.current_balance) >= 0 ? "value--positive" : "value--negative",
    }),
    transformSubmit: (v) => ({
      ...v,
      initial_balance: v.initial_balance === null ? 0 : v.initial_balance,
    }),
  });
}

Router.register("/accounts", renderAccountsView);

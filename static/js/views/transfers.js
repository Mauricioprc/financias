/* Transferências entre contas. */

async function renderTransfersView(container) {
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

  const accountOptions = accounts.map((a) => ({ value: a.id, label: a.name }));
  const accountNameById = Object.fromEntries(accounts.map((a) => [String(a.id), a.name]));

  mountCrudView(container, {
    title: "Transferências",
    icon: "arrow-left-right",
    emptyText: "Nenhuma transferência registrada ainda.",
    fields: [
      {
        name: "from_account_id",
        label: "De",
        type: "select",
        required: true,
        options: accountOptions,
      },
      {
        name: "to_account_id",
        label: "Para",
        type: "select",
        required: true,
        options: accountOptions,
      },
      { name: "amount", label: "Valor (R$)", type: "number", step: "0.01", required: true },
      { name: "date", label: "Data", type: "date", required: true },
      { name: "description", label: "Descrição (opcional)" },
    ],
    loadItems: () => Api.transfers.list(),
    createItem: (data) => Api.transfers.create(data),
    removeItem: (id) => Api.transfers.remove(id),
    renderItem: (t) => ({
      title: `${accountNameById[String(t.from_account_id)] || "?"} → ${
        accountNameById[String(t.to_account_id)] || "?"
      }`,
      subtitle: UI.dateBR(t.date) + (t.description ? ` · ${t.description}` : ""),
      value: UI.money(t.amount),
    }),
    transformSubmit: (v) => ({
      ...v,
      from_account_id: Number(v.from_account_id),
      to_account_id: Number(v.to_account_id),
    }),
  });
}

Router.register("/transfers", renderTransfersView);

/* Transações recorrentes (salário, assinaturas, parcelas fixas). */

const RECURRING_FREQUENCY_LABELS = { monthly: "Mensal", weekly: "Semanal", yearly: "Anual" };

async function renderRecurringView(container) {
  container.appendChild(UI.el("div", { class: "loading" }, "Carregando..."));
  let accounts;
  let categories;
  try {
    [accounts, categories] = await Promise.all([Api.accounts.list(), Api.categories.list()]);
  } catch (err) {
    container.innerHTML = "";
    UI.showApiError(err);
    return;
  }
  container.innerHTML = "";

  const accountOptions = accounts.map((a) => ({ value: a.id, label: a.name }));
  const categoryOptions = [{ value: "", label: "(sem categoria)" }].concat(
    categories.map((c) => ({ value: c.id, label: c.name }))
  );

  mountCrudView(container, {
    title: "Recorrências",
    icon: "refresh-cw",
    emptyText: "Nenhuma transação recorrente cadastrada ainda.",
    fields: [
      { name: "account_id", label: "Conta", type: "select", required: true, options: accountOptions },
      { name: "category_id", label: "Categoria", type: "select", options: categoryOptions },
      { name: "description", label: "Descrição", required: true },
      {
        name: "type",
        label: "Tipo",
        type: "select",
        required: true,
        options: [
          { value: "income", label: "Receita" },
          { value: "expense", label: "Despesa" },
        ],
      },
      { name: "amount", label: "Valor (R$)", type: "number", step: "0.01", required: true },
      {
        name: "frequency",
        label: "Frequência",
        type: "select",
        required: true,
        options: Object.entries(RECURRING_FREQUENCY_LABELS).map(([value, label]) => ({
          value,
          label,
        })),
      },
      {
        name: "day_of_month",
        label: "Dia do mês (se mensal)",
        type: "number",
        min: 1,
        max: 31,
      },
      { name: "start_date", label: "Início", type: "date", required: true },
      { name: "end_date", label: "Fim (opcional)", type: "date" },
    ],
    editFields: [
      { name: "category_id", label: "Categoria", type: "select", options: categoryOptions },
      { name: "description", label: "Descrição", required: true },
      { name: "amount", label: "Valor (R$)", type: "number", step: "0.01" },
      { name: "day_of_month", label: "Dia do mês (se mensal)", type: "number", min: 1, max: 31 },
      { name: "end_date", label: "Fim (opcional)", type: "date" },
      { name: "is_active", label: "Ativa", type: "checkbox" },
    ],
    loadItems: () => Api.recurring.list(),
    createItem: (data) => Api.recurring.create(data),
    updateItem: (id, data) => Api.recurring.update(id, data),
    removeItem: (id) => Api.recurring.remove(id),
    renderItem: (r) => ({
      title: r.description + (r.is_active ? "" : " (inativa)"),
      subtitle: `${RECURRING_FREQUENCY_LABELS[r.frequency]} · desde ${UI.dateBR(r.start_date)}${
        r.last_generated ? ` · última geração ${UI.dateBR(r.last_generated)}` : ""
      }`,
      value: (r.type === "income" ? "+ " : "- ") + UI.money(r.amount),
      valueClass: r.type === "income" ? "value--positive" : "value--negative",
    }),
    extraRowActions: (item, refresh) => [
      UI.el(
        "button",
        {
          class: "btn btn--secondary btn--sm",
          onclick: () => handleGenerate(item, refresh),
        },
        "Gerar"
      ),
    ],
    transformSubmit: (v) => ({
      ...v,
      account_id: Number(v.account_id),
      category_id: v.category_id ? Number(v.category_id) : null,
    }),
  });

  async function handleGenerate(item, refresh) {
    try {
      const result = await Api.recurring.generate(item.id);
      UI.toast(`${result.meta.total} transação(ões) gerada(s).`, "success");
      refresh();
    } catch (err) {
      UI.showApiError(err);
    }
  }
}

Router.register("/recurring", renderRecurringView);

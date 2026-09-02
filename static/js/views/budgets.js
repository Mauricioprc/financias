/* Orçamentos por categoria. */

function renderBudgetsView(container) {
  // Array mutado in-place (nunca reatribuído) depois que loadItems roda —
  // o field def abaixo guarda essa mesma referência, e UI.buildForm só lê
  // `field.options` na hora de abrir o modal (depois que a lista já
  // carregou), então isso resolve sem precisar mexer no crud.js genérico.
  const categoryOptions = [];

  mountCrudView(container, {
    title: "Orçamentos",
    icon: "wallet",
    emptyText: "Cadastre seu primeiro orçamento por categoria.",
    fields: [
      { name: "category_id", label: "Categoria", type: "select", required: true, options: categoryOptions },
      { name: "monthly_limit", label: "Limite mensal (R$)", type: "number", step: "0.01", required: true },
    ],
    editFields: [
      { name: "monthly_limit", label: "Limite mensal (R$)", type: "number", step: "0.01" },
    ],
    loadItems: async () => {
      const categories = await Api.categories.list();
      categoryOptions.length = 0;
      categoryOptions.push(...categoryOptionsForType(categories, "expense"));

      const [budgets, progress] = await Promise.all([Api.budgets.list(), Api.budgets.progress()]);
      const progressByBudgetId = Object.fromEntries(progress.map((p) => [p.budget_id, p]));
      return budgets.map((b) => ({ ...b, progress: progressByBudgetId[b.id] }));
    },
    createItem: (data) => Api.budgets.create({ ...data, category_id: Number(data.category_id) }),
    updateItem: (id, data) => Api.budgets.update(id, data),
    removeItem: (id) => Api.budgets.remove(id),
    renderItem: (b) => {
      const p = b.progress;
      if (!p) {
        return { title: `Categoria #${b.category_id}`, subtitle: UI.money(b.monthly_limit), value: null };
      }
      const pct = Math.round(Number(p.pct_used));
      const className = p.is_over_budget
        ? "progress-bar__fill--danger"
        : pct >= 80
          ? "progress-bar__fill--warning"
          : "";
      return {
        title: p.category_name,
        subtitle:
          `${UI.money(p.current_month_total)} de ${UI.money(p.monthly_limit)} (${pct}%) · ` +
          `faltam ${p.days_remaining_in_month} dias`,
        value: null,
        progress: { pct: Math.min(100, pct), className },
      };
    },
  });
}

Router.register("/budgets", renderBudgetsView);

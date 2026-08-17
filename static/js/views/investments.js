/* Investimentos. */

const INVESTMENT_TYPE_LABELS = {
  fixed_income: "Renda fixa",
  stock: "Ação",
  fund: "Fundo",
  crypto: "Cripto",
  other: "Outro",
};

function renderInvestmentsView(container) {
  mountCrudView(container, {
    title: "Investimentos",
    icon: "trending-up",
    emptyText: "Cadastre seu primeiro investimento.",
    fields: [
      { name: "name", label: "Nome", required: true },
      {
        name: "type",
        label: "Tipo",
        type: "select",
        required: true,
        options: Object.entries(INVESTMENT_TYPE_LABELS).map(([value, label]) => ({ value, label })),
      },
      { name: "broker", label: "Corretora (opcional)" },
      {
        name: "invested_amount",
        label: "Valor investido (R$)",
        type: "number",
        step: "0.01",
        required: true,
      },
      { name: "current_amount", label: "Valor atual (opcional)", type: "number", step: "0.01" },
      { name: "acquired_at", label: "Data de aquisição", type: "date", required: true },
      { name: "notes", label: "Notas (opcional)", type: "textarea" },
    ],
    editFields: [
      { name: "name", label: "Nome", required: true },
      { name: "broker", label: "Corretora (opcional)" },
      { name: "current_amount", label: "Valor atual (R$)", type: "number", step: "0.01" },
      { name: "notes", label: "Notas (opcional)", type: "textarea" },
    ],
    loadItems: () => Api.investments.list(),
    createItem: (data) => Api.investments.create(data),
    updateItem: (id, data) => Api.investments.update(id, data),
    removeItem: (id) => Api.investments.remove(id),
    renderItem: (i) => {
      const invested = Number(i.invested_amount);
      const diff = Number(i.current_amount) - invested;
      const pct = invested > 0 ? (diff / invested) * 100 : 0;
      const isPositive = diff >= 0;
      return {
        title: i.name,
        subtitle: [
          `${INVESTMENT_TYPE_LABELS[i.type] || i.type}${i.broker ? " · " + i.broker : ""} · `,
          UI.el(
            "span",
            { class: `badge ${isPositive ? "badge--income" : "badge--expense"}` },
            `${isPositive ? "+" : ""}${pct.toFixed(1)}%`
          ),
        ],
        value: UI.money(i.current_amount),
        valueClass: isPositive ? "value--positive" : "value--negative",
      };
    },
  });
}

Router.register("/investments", renderInvestmentsView);

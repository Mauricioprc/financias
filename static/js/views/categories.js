/* Categorias de receita/despesa. */

function renderCategoriesView(container) {
  mountCrudView(container, {
    title: "Categorias",
    icon: "🏷️",
    emptyText: "Nenhuma categoria cadastrada ainda.",
    fields: [
      { name: "name", label: "Nome", required: true },
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
    ],
    editFields: [{ name: "name", label: "Nome", required: true }],
    loadItems: () => Api.categories.list(),
    createItem: (data) => Api.categories.create(data),
    updateItem: (id, data) => Api.categories.update(id, data),
    removeItem: (id) => Api.categories.remove(id),
    renderItem: (c) => ({
      title: c.name,
      subtitle: c.type === "income" ? "Receita" : "Despesa",
      value: null,
    }),
  });
}

Router.register("/categories", renderCategoriesView);

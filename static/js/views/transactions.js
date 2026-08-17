/* Receitas e despesas — filtros, paginação, criação, edição e exclusão. */

function categoryOptionsForType(categories, type) {
  return [{ value: "", label: "(sem categoria)" }].concat(
    categories.filter((c) => c.type === type).map((c) => ({ value: c.id, label: c.name }))
  );
}

/* Modal de criação de transação, reaproveitado pela tela de Transações e pelo
   botão de lançamento rápido da Home. `onCreated` roda após salvar com sucesso. */
function openCreateTransactionModal(accounts, categories, creditCards, onCreated) {
  const accountOptions = accounts.map((a) => ({ value: a.id, label: a.name }));
  const creditCardOptions = [{ value: "", label: "(não é no cartão)" }].concat(
    creditCards.map((c) => ({ value: c.id, label: c.name }))
  );

  const fields = [
    {
      name: "type",
      label: "Tipo",
      type: "select",
      required: true,
      options: [
        { value: "expense", label: "Despesa" },
        { value: "income", label: "Receita" },
      ],
    },
    { name: "account_id", label: "Conta", type: "select", required: true, options: accountOptions },
    {
      name: "credit_card_id",
      label: "Cartão de crédito (opcional)",
      type: "select",
      options: creditCardOptions,
    },
    {
      name: "category_id",
      label: "Categoria",
      type: "select",
      options: categoryOptionsForType(categories, "expense"),
    },
    { name: "description", label: "Descrição", required: true },
    { name: "amount", label: "Valor (R$)", type: "number", step: "0.01", required: true },
    { name: "date", label: "Data", type: "date", required: true },
    { name: "is_paid", label: "Já efetivada", type: "checkbox" },
    { name: "notes", label: "Notas (opcional)", type: "textarea" },
  ];

  const form = UI.buildForm(fields, { date: UI.todayISO(), is_paid: true });
  const errorBox = UI.el("div", { class: "form-error", style: "display:none" });
  form.appendChild(errorBox);
  form.appendChild(
    UI.el("div", { class: "form-actions" }, [
      UI.el(
        "button",
        { type: "button", class: "btn btn--secondary", onclick: () => UI.closeModal() },
        "Cancelar"
      ),
      UI.el("button", { type: "submit", class: "btn btn--primary" }, "Salvar"),
    ])
  );

  const typeSelect = UI.qs('select[name="type"]', form);
  const categorySelect = UI.qs('select[name="category_id"]', form);
  typeSelect.addEventListener("change", () => {
    categorySelect.innerHTML = "";
    categoryOptionsForType(categories, typeSelect.value).forEach((opt) => {
      categorySelect.appendChild(UI.el("option", { value: opt.value }, opt.label));
    });
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const values = UI.formValues(form, fields);
    const data = {
      ...values,
      account_id: Number(values.account_id),
      credit_card_id: values.credit_card_id ? Number(values.credit_card_id) : null,
      category_id: values.category_id ? Number(values.category_id) : null,
    };
    try {
      await Api.transactions.create(data);
      UI.closeModal();
      UI.toast("Transação criada.", "success");
      if (onCreated) onCreated();
    } catch (err) {
      errorBox.textContent = err.message;
      errorBox.style.display = "block";
    }
  });

  UI.openModal("Nova transação", form);
}

async function renderTransactionsView(container) {
  container.appendChild(UI.el("div", { class: "loading" }, "Carregando..."));

  let accounts;
  let categories;
  let creditCards;
  try {
    [accounts, categories, creditCards] = await Promise.all([
      Api.accounts.list(),
      Api.categories.list(),
      Api.creditCards.list(),
    ]);
  } catch (err) {
    container.innerHTML = "";
    UI.showApiError(err);
    return;
  }
  container.innerHTML = "";

  const accountNameById = Object.fromEntries(accounts.map((a) => [String(a.id), a.name]));
  const categoryNameById = Object.fromEntries(categories.map((c) => [String(c.id), c.name]));

  const state = {
    type: "",
    account_id: "",
    page: 1,
    per_page: 20,
  };

  const header = UI.el("div", { class: "page-header" }, [
    UI.el("h1", { class: "page-title" }, "Transações"),
    UI.el(
      "button",
      {
        class: "btn btn--primary btn--sm",
        onclick: () =>
          openCreateTransactionModal(accounts, categories, creditCards, loadList),
      },
      "+ Nova"
    ),
  ]);
  container.appendChild(header);

  const filtersBar = UI.el("div", { class: "filters-bar" }, [
    UI.el("div", { class: "form-field" }, [
      UI.el("label", {}, "Tipo"),
      selectFilter(
        "type",
        [
          { value: "", label: "Todos" },
          { value: "income", label: "Receitas" },
          { value: "expense", label: "Despesas" },
        ],
      ),
    ]),
    UI.el("div", { class: "form-field" }, [
      UI.el("label", {}, "Conta"),
      selectFilter(
        "account_id",
        [{ value: "", label: "Todas" }].concat(
          accounts.map((a) => ({ value: a.id, label: a.name }))
        ),
      ),
    ]),
  ]);
  container.appendChild(filtersBar);

  function selectFilter(name, options) {
    const select = UI.el(
      "select",
      { name },
      options.map((opt) => UI.el("option", { value: opt.value }, opt.label))
    );
    select.addEventListener("change", () => {
      state[name] = select.value;
      state.page = 1;
      loadList();
    });
    return select;
  }

  const listContainer = UI.el("div", {});
  container.appendChild(listContainer);

  const pagination = UI.el("div", { class: "form-actions" });
  container.appendChild(pagination);

  async function loadList() {
    listContainer.innerHTML = "";
    listContainer.appendChild(UI.el("div", { class: "loading" }, "Carregando..."));

    let resp;
    try {
      resp = await Api.transactions.list({
        type: state.type || undefined,
        account_id: state.account_id || undefined,
        page: state.page,
        per_page: state.per_page,
      });
    } catch (err) {
      listContainer.innerHTML = "";
      UI.showApiError(err);
      return;
    }

    listContainer.innerHTML = "";
    if (resp.data.length === 0) {
      listContainer.appendChild(
        UI.el("div", { class: "empty-state" }, [
          UI.el("div", { class: "empty-state__icon" }, UI.icon("receipt")),
          UI.el("div", {}, "Nenhuma transação encontrada."),
        ])
      );
    } else {
      const list = UI.el("div", { class: "list" });
      resp.data.forEach((t) => list.appendChild(transactionItem(t)));
      listContainer.appendChild(list);
    }

    renderPagination(resp.meta);
  }

  function renderPagination(meta) {
    pagination.innerHTML = "";
    const totalPages = Math.max(1, Math.ceil(meta.total / meta.per_page));
    if (totalPages <= 1) return;

    pagination.appendChild(
      UI.el(
        "button",
        {
          class: "btn btn--secondary",
          disabled: state.page <= 1,
          onclick: () => {
            state.page -= 1;
            loadList();
          },
        },
        "← Anterior"
      )
    );
    pagination.appendChild(
      UI.el(
        "button",
        {
          class: "btn btn--secondary",
          disabled: state.page >= totalPages,
          onclick: () => {
            state.page += 1;
            loadList();
          },
        },
        "Próxima →"
      )
    );
  }

  function transactionItem(t) {
    const isIncome = t.type === "income";
    const subtitleParts = [
      UI.dateBR(t.date),
      accountNameById[String(t.account_id)] || "",
      t.category_id ? categoryNameById[String(t.category_id)] || "" : null,
      t.credit_card_id ? "no cartão" : null,
      t.is_paid ? null : "pendente",
    ].filter(Boolean);

    const actions = UI.el("div", { class: "list-item__actions" }, [
      UI.el(
        "button",
        { class: "btn btn--secondary btn--sm", onclick: () => openEditModal(t) },
        "Editar"
      ),
      UI.el(
        "button",
        { class: "btn btn--danger btn--sm", onclick: () => handleDelete(t) },
        "Excluir"
      ),
    ]);

    return UI.el("div", { class: "list-item" }, [
      UI.el("div", { class: "list-item__main" }, [
        UI.el("div", { class: "list-item__title" }, t.description),
        UI.el("div", { class: "list-item__subtitle" }, subtitleParts.join(" · ")),
      ]),
      UI.el(
        "div",
        { class: "list-item__value " + (isIncome ? "value--positive" : "value--negative") },
        (isIncome ? "+ " : "- ") + UI.money(t.amount)
      ),
      actions,
    ]);
  }

  async function handleDelete(t) {
    const ok = await UI.confirmAction("Tem certeza que deseja excluir esta transação?");
    if (!ok) return;
    try {
      await Api.transactions.remove(t.id);
      UI.toast("Transação excluída.", "success");
      loadList();
    } catch (err) {
      UI.showApiError(err);
    }
  }

  function openEditModal(t) {
    const isCardTransaction = Boolean(t.credit_card_id);
    const fields = [
      {
        name: "category_id",
        label: "Categoria",
        type: "select",
        options: categoryOptionsForType(categories, t.type),
      },
      { name: "description", label: "Descrição", required: true },
      { name: "amount", label: "Valor (R$)", type: "number", step: "0.01", required: true },
      { name: "is_paid", label: "Já efetivada", type: "checkbox" },
      { name: "notes", label: "Notas (opcional)", type: "textarea" },
    ];
    if (!isCardTransaction) {
      fields.splice(2, 0, { name: "date", label: "Data", type: "date", required: true });
    }

    const form = UI.buildForm(fields, t);
    if (isCardTransaction) {
      form.prepend(
        UI.el(
          "div",
          { class: "list-item__subtitle", style: "margin-bottom:10px" },
          "Transação de cartão: conta e data não podem ser alteradas (definem a fatura)."
        )
      );
    }
    const errorBox = UI.el("div", { class: "form-error", style: "display:none" });
    form.appendChild(errorBox);
    form.appendChild(
      UI.el("div", { class: "form-actions" }, [
        UI.el(
          "button",
          { type: "button", class: "btn btn--secondary", onclick: () => UI.closeModal() },
          "Cancelar"
        ),
        UI.el("button", { type: "submit", class: "btn btn--primary" }, "Salvar"),
      ])
    );

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const values = UI.formValues(form, fields);
      const data = { ...values, category_id: values.category_id ? Number(values.category_id) : null };
      try {
        await Api.transactions.update(t.id, data);
        UI.closeModal();
        UI.toast("Transação atualizada.", "success");
        loadList();
      } catch (err) {
        errorBox.textContent = err.message;
        errorBox.style.display = "block";
      }
    });

    UI.openModal("Editar transação", form);
  }

  loadList();
}

Router.register("/transactions", renderTransactionsView);

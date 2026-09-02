/* Receitas e despesas — filtros, paginação, criação, edição e exclusão. */

const NEW_CATEGORY_OPTION_VALUE = "__new__";

function categoryOptionsForType(categories, type) {
  return [{ value: "", label: "(sem categoria)" }].concat(
    categories.filter((c) => c.type === type).map((c) => ({ value: c.id, label: c.name }))
  );
}

/* Mesmas opções, com "+ Nova categoria" no fim — só pra formulários que
   sabem tratar essa opção (ver openCreateTransactionModal). O modal de
   edição usa categoryOptionsForType puro, sem essa opção. */
function categoryOptionsWithAdd(categories, type) {
  return categoryOptionsForType(categories, type).concat([
    { value: NEW_CATEGORY_OPTION_VALUE, label: "+ Nova categoria" },
  ]);
}

/* Sugestão automática de categoria (GET /transactions/suggest-category) — só
   dispara no blur (não a cada tecla) e só preenche se a categoria ainda
   estiver vazia, nunca sobrescrevendo escolha manual. Best-effort: falha
   silenciosa (console.warn), nunca trava o formulário. Compartilhado entre
   o modal de criação e o de edição — ambos têm os mesmos dois campos. */
function attachCategorySuggestion(form) {
  const descriptionInput = UI.qs('input[name="description"]', form);
  const categorySelect = UI.qs('select[name="category_id"]', form);
  if (!descriptionInput || !categorySelect) return;

  descriptionInput.addEventListener("blur", async () => {
    const description = descriptionInput.value.trim();
    if (!description || categorySelect.value) return;
    try {
      const { category_id } = await Api.categorySuggestion.suggest(description);
      if (category_id && !categorySelect.value) {
        categorySelect.value = String(category_id);
        UI.toast("Categoria sugerida com base em lançamentos anteriores.", "info");
      }
    } catch (err) {
      console.warn("Falha ao buscar sugestão de categoria:", err);
    }
  });
}

/* Modal de criação de transação, reaproveitado pela tela de Transações e pelo
   botão de lançamento rápido da Home. `onCreated` roda após salvar com sucesso. */
function openCreateTransactionModal(accounts, categories, creditCards, onCreated) {
  const accountOptions = accounts.map((a) => ({ value: a.id, label: a.name }));

  // Cartões vinculados àquela conta (Cartões > Conta vinculada) aparecem
  // sozinhos no dropdown; se sobrar só 1, ele já vem pré-selecionado. Sem
  // nenhum cartão vinculado a essa conta, cai de volta pra lista completa —
  // não trava quem ainda não configurou o vínculo.
  function creditCardOptionsForAccount(accountId) {
    const linked = creditCards.filter((c) => c.account_id && String(c.account_id) === String(accountId));
    const list = linked.length > 0 ? linked : creditCards;
    return {
      options: [{ value: "", label: "(não é no cartão)" }].concat(
        list.map((c) => ({ value: c.id, label: c.name }))
      ),
      autoSelectId: linked.length === 1 ? linked[0].id : "",
    };
  }

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
      options: creditCardOptionsForAccount(accounts[0] ? accounts[0].id : "").options,
    },
    { name: "installments", label: "Parcelas", type: "number", min: 1, max: 24 },
    {
      name: "category_id",
      label: "Categoria",
      type: "select",
      options: categoryOptionsWithAdd(categories, "expense"),
    },
    { name: "description", label: "Descrição", required: true },
    { name: "amount", label: "Valor (R$)", type: "number", step: "0.01", required: true },
    { name: "date", label: "Data", type: "date", required: true },
    { name: "is_paid", label: "Já efetivada", type: "checkbox" },
    { name: "notes", label: "Notas (opcional)", type: "textarea" },
  ];

  const form = UI.buildForm(fields, { date: UI.todayISO(), is_paid: true, installments: 1 });
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
  const accountSelect = UI.qs('select[name="account_id"]', form);
  const creditCardSelect = UI.qs('select[name="credit_card_id"]', form);
  const installmentsInput = UI.qs('input[name="installments"]', form);
  const installmentsWrap = installmentsInput.parentElement;
  const categorySelect = UI.qs('select[name="category_id"]', form);

  // "Parcelas" só faz sentido com um cartão selecionado — sem cartão, fica
  // escondido e travado em 1 (compra parcelada exige credit_card_id).
  function updateInstallmentsVisibility() {
    const hasCard = Boolean(creditCardSelect.value);
    installmentsWrap.style.display = hasCard ? "" : "none";
    if (!hasCard) installmentsInput.value = "1";
  }

  function fillCreditCardSelect(accountId) {
    const { options, autoSelectId } = creditCardOptionsForAccount(accountId);
    creditCardSelect.innerHTML = "";
    options.forEach((opt) => {
      creditCardSelect.appendChild(
        UI.el(
          "option",
          { value: opt.value, selected: String(opt.value) === String(autoSelectId) },
          opt.label
        )
      );
    });
    updateInstallmentsVisibility();
  }

  creditCardSelect.addEventListener("change", updateInstallmentsVisibility);
  accountSelect.addEventListener("change", () => fillCreditCardSelect(accountSelect.value));
  fillCreditCardSelect(accountSelect.value); // aplica o auto-select já na abertura do modal

  attachCategorySuggestion(form);

  function fillCategorySelect(selectedValue = "") {
    categorySelect.innerHTML = "";
    categoryOptionsWithAdd(categories, typeSelect.value).forEach((opt) => {
      categorySelect.appendChild(
        UI.el(
          "option",
          { value: opt.value, selected: String(opt.value) === String(selectedValue) },
          opt.label
        )
      );
    });
  }

  typeSelect.addEventListener("change", () => fillCategorySelect());

  // "+ Nova categoria" — cria inline, sem sair do formulário nem abrir outra
  // tela: troca o <select> por um campo de texto na hora, no lugar dele.
  const newCategoryInput = UI.el("input", {
    type: "text",
    placeholder: "Nome da nova categoria",
    style: "display:none",
  });
  const newCategoryGroup = UI.el("div", { class: "inline-add-group", style: "display:none" }, [
    newCategoryInput,
    UI.el(
      "button",
      { type: "button", class: "btn btn--primary btn--sm", onclick: confirmNewCategory },
      "Adicionar"
    ),
    UI.el(
      "button",
      { type: "button", class: "btn btn--secondary btn--sm", onclick: cancelNewCategory },
      "Cancelar"
    ),
  ]);
  categorySelect.insertAdjacentElement("afterend", newCategoryGroup);

  categorySelect.addEventListener("change", () => {
    if (categorySelect.value !== NEW_CATEGORY_OPTION_VALUE) return;
    categorySelect.style.display = "none";
    newCategoryGroup.style.display = "flex";
    newCategoryInput.style.display = "";
    newCategoryInput.value = "";
    newCategoryInput.focus();
  });

  newCategoryInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      confirmNewCategory();
    }
  });

  function showCategorySelect() {
    newCategoryGroup.style.display = "none";
    categorySelect.style.display = "";
  }

  function cancelNewCategory() {
    fillCategorySelect("");
    showCategorySelect();
  }

  async function confirmNewCategory() {
    const name = newCategoryInput.value.trim();
    if (!name) {
      newCategoryInput.focus();
      return;
    }
    try {
      const created = await Api.categories.create({ name, type: typeSelect.value });
      categories.push(created);
      fillCategorySelect(created.id);
      showCategorySelect();
    } catch (err) {
      errorBox.textContent = err.message;
      errorBox.style.display = "block";
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    // Se o usuário abriu "+ Nova categoria" e submeteu sem confirmar nem
    // cancelar, o select ainda está em "__new__" (mas escondido) — trata
    // como "sem categoria" em vez de mandar esse valor pra API.
    if (categorySelect.value === NEW_CATEGORY_OPTION_VALUE) {
      cancelNewCategory();
    }
    const values = UI.formValues(form, fields);
    const creditCardId = values.credit_card_id ? Number(values.credit_card_id) : null;
    const categoryId = values.category_id ? Number(values.category_id) : null;
    const installments = Number(values.installments) || 1;

    try {
      if (creditCardId && installments > 1) {
        await Api.transactions.createInstallmentPurchase({
          account_id: Number(values.account_id),
          credit_card_id: creditCardId,
          category_id: categoryId,
          description: values.description,
          total_amount: values.amount,
          installments,
          date: values.date,
          notes: values.notes,
        });
        UI.toast(`Compra parcelada em ${installments}x criada.`, "success");
      } else {
        const data = {
          ...values,
          account_id: Number(values.account_id),
          credit_card_id: creditCardId,
          category_id: categoryId,
        };
        delete data.installments; // não faz parte de TransactionCreateSchema
        await Api.transactions.create(data);
        UI.toast("Transação criada.", "success");
      }
      UI.closeModal();
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
  let monthSummary;
  let monthCount;
  try {
    const firstDayOfMonth = UI.todayISO().slice(0, 8) + "01";
    [accounts, categories, creditCards, monthSummary, monthCount] = await Promise.all([
      Api.accounts.list(),
      Api.categories.list(),
      Api.creditCards.list(),
      // Resumo do mês corrente — independente dos filtros da tela (esses
      // só controlam a lista abaixo). Enriquecimento, não crítico.
      Api.reports
        .incomeVsExpense(1)
        .then((items) => items[0])
        .catch(() => null),
      Api.transactions
        .list({ date_from: firstDayOfMonth, date_to: UI.todayISO(), per_page: 1 })
        .then((r) => r.meta.total)
        .catch(() => null),
    ]);
  } catch (err) {
    container.innerHTML = "";
    UI.showApiError(err);
    return;
  }
  container.innerHTML = "";

  const accountNameById = Object.fromEntries(accounts.map((a) => [String(a.id), a.name]));
  // Função (não objeto fixo) porque `categories` pode ganhar itens depois —
  // ver "+ Nova categoria" em openCreateTransactionModal, que empurra pro
  // mesmo array recebido aqui por referência.
  const categoryName = (id) => categories.find((c) => String(c.id) === String(id))?.name || "";

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

  if (monthCount != null && monthSummary) {
    container.appendChild(
      UI.el(
        "div",
        { class: "section-title", style: "margin-top:-8px" },
        `${monthCount} lançamento(s) este mês · receitas ${UI.money(monthSummary.income)} · ` +
          `despesas ${UI.money(monthSummary.expense)}`
      )
    );
  }

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
      t.category_id ? categoryName(t.category_id) : null,
      t.credit_card_id
        ? t.installment_total > 1
          ? `no cartão (${t.installment_number}/${t.installment_total})`
          : "no cartão"
        : null,
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
    attachCategorySuggestion(form);
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

/* Transações recorrentes (salário, assinaturas, parcelas fixas). */

const RECURRING_FREQUENCY_LABELS = { monthly: "Mensal", weekly: "Semanal", yearly: "Anual" };

/* Próxima ocorrência de `dayOfMonth` a partir de hoje — nunca uma data já
   passada. Evita que criar a assinatura hoje gere uma "dívida" retroativa
   de meses que já passaram: só conta a partir da primeira vez que o dia
   de vencimento realmente ocorrer dali pra frente (ou hoje mesmo, se hoje
   for o próprio dia). */
function nextOccurrenceISO(dayOfMonth) {
  const now = new Date();
  let year = now.getFullYear();
  let month = now.getMonth(); // 0-indexado
  if (now.getDate() > dayOfMonth) {
    month += 1;
    if (month > 11) {
      month = 0;
      year += 1;
    }
  }
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const day = Math.min(dayOfMonth, daysInMonth);
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

/* Modal enxuto pra assinatura: nome, valor, cartão, dia do vencimento,
   ativa. Por trás, cria uma recorrência mensal no cartão igual a qualquer
   outra — só esconde os campos que não fazem sentido perguntar de novo
   (tipo é sempre despesa, frequência é sempre mensal, conta vem do cartão). */
function openCreateSubscriptionModal(creditCards, onCreated) {
  const eligibleCards = creditCards.filter((c) => c.account_id);
  if (eligibleCards.length === 0) {
    UI.toast(
      "Nenhum cartão com conta vinculada. Vincule uma conta ao cartão em Cartões primeiro.",
      "error"
    );
    return;
  }

  const fields = [
    { name: "description", label: "Nome da assinatura", required: true },
    { name: "amount", label: "Valor (R$)", type: "number", step: "0.01", required: true },
    {
      name: "credit_card_id",
      label: "Cartão",
      type: "select",
      required: true,
      options: eligibleCards.map((c) => ({ value: c.id, label: c.name })),
    },
    {
      name: "day_of_month",
      label: "Dia do vencimento",
      type: "number",
      min: 1,
      max: 31,
      required: true,
    },
    { name: "is_active", label: "Ativa", type: "checkbox" },
  ];

  const form = UI.buildForm(fields, { is_active: true });
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
    const card = eligibleCards.find((c) => String(c.id) === String(values.credit_card_id));
    const dayOfMonth = Number(values.day_of_month);

    try {
      const created = await Api.recurring.create({
        account_id: card.account_id,
        credit_card_id: card.id,
        category_id: null,
        description: values.description,
        type: "expense",
        amount: values.amount,
        frequency: "monthly",
        day_of_month: dayOfMonth,
        start_date: nextOccurrenceISO(dayOfMonth),
        end_date: null,
      });
      if (!values.is_active) {
        await Api.recurring.update(created.id, { is_active: false });
      }
      UI.closeModal();
      UI.toast("Assinatura criada.", "success");
      if (onCreated) onCreated();
    } catch (err) {
      errorBox.textContent = err.message;
      errorBox.style.display = "block";
    }
  });

  UI.openModal("Nova assinatura", form);
}

async function renderRecurringView(container) {
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

  // Lança silenciosamente qualquer assinatura vencida até hoje, sem exigir
  // clique em "Gerar" — nunca gera pra frente (a rota não aceita `until`).
  Api.recurring.autoGenerate().catch(() => {});

  const accountOptions = accounts.map((a) => ({ value: a.id, label: a.name }));
  const categoryOptions = [{ value: "", label: "(sem categoria)" }].concat(
    categories.map((c) => ({ value: c.id, label: c.name }))
  );
  const creditCardOptions = [{ value: "", label: "(débito automático na conta)" }].concat(
    creditCards.map((c) => ({ value: c.id, label: c.name }))
  );
  const creditCardNameById = Object.fromEntries(creditCards.map((c) => [String(c.id), c.name]));

  mountCrudView(container, {
    title: "Recorrências",
    icon: "refresh-cw",
    emptyText: "Nenhuma transação recorrente cadastrada ainda.",
    fields: [
      { name: "account_id", label: "Conta", type: "select", required: true, options: accountOptions },
      { name: "category_id", label: "Categoria", type: "select", options: categoryOptions },
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
      {
        name: "credit_card_id",
        label: "Cartão de crédito (opcional)",
        type: "select",
        options: creditCardOptions,
      },
      { name: "description", label: "Descrição", required: true },
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
    loadItems: async () => {
      const items = await Api.recurring.list();
      const activeMonthlySubscriptions = items.filter(
        (r) => r.is_active && r.credit_card_id && r.frequency === "monthly"
      );
      const monthlyTotal = activeMonthlySubscriptions.reduce((sum, r) => sum + Number(r.amount), 0);
      container.dispatchEvent(new CustomEvent("subscriptions-total", { detail: monthlyTotal }));
      return items;
    },
    createItem: (data) => Api.recurring.create(data),
    updateItem: (id, data) => Api.recurring.update(id, data),
    removeItem: (id) => Api.recurring.remove(id),
    renderItem: (r) => ({
      title: r.description + (r.is_active ? "" : " (inativa)"),
      subtitle: `${RECURRING_FREQUENCY_LABELS[r.frequency]} · desde ${UI.dateBR(r.start_date)}${
        r.credit_card_id ? ` · cartão: ${creditCardNameById[String(r.credit_card_id)] || ""}` : ""
      }${r.last_generated ? ` · última geração ${UI.dateBR(r.last_generated)}` : ""}`,
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
    extraHeaderActions: (refresh) => [
      UI.el(
        "button",
        {
          class: "btn btn--secondary btn--sm",
          onclick: () => openCreateSubscriptionModal(creditCards, refresh),
        },
        "+ Assinatura"
      ),
    ],
    transformSubmit: (v) => ({
      ...v,
      account_id: Number(v.account_id),
      category_id: v.category_id ? Number(v.category_id) : null,
      credit_card_id: v.type === "expense" && v.credit_card_id ? Number(v.credit_card_id) : null,
    }),
  });

  // Resumo do total mensal comprometido em assinaturas — atualizado toda
  // vez que a lista recarrega (mountCrudView refaz o container inteiro, daí
  // o evento em vez de guardar uma referência de nó que seria descartada).
  container.addEventListener("subscriptions-total", (e) => {
    let summary = UI.qs(".subscriptions-summary", container);
    if (!summary) {
      summary = UI.el("div", { class: "subscriptions-summary" });
      const header = UI.qs(".page-header", container);
      if (header) header.insertAdjacentElement("afterend", summary);
    }
    summary.textContent =
      e.detail > 0 ? `Total mensal em assinaturas no cartão: ${UI.money(e.detail)}` : "";
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

/* Início — resumo de saldo, transações recentes, metas em andamento e lançamento rápido. */

async function renderHomeView(container) {
  container.appendChild(UI.el("div", { class: "loading" }, "Carregando..."));

  let categories;
  let creditCards;
  try {
    [categories, creditCards] = await Promise.all([Api.categories.list(), Api.creditCards.list()]);
  } catch (err) {
    container.innerHTML = "";
    UI.showApiError(err);
    return;
  }

  async function refresh() {
    let accounts;
    let txResp;
    let goals;
    try {
      [accounts, txResp, goals] = await Promise.all([
        Api.accounts.list(),
        Api.transactions.list({ per_page: 5 }),
        Api.goals.list(),
      ]);
    } catch (err) {
      container.innerHTML = "";
      UI.showApiError(err);
      return;
    }

    container.innerHTML = "";

    const totalBalance = accounts.reduce((sum, a) => sum + Number(a.current_balance), 0);

    container.appendChild(
      UI.el("div", { class: "page-header" }, [
        UI.el("h1", { class: "page-title" }, "Início"),
        UI.el(
          "button",
          { class: "btn btn--primary btn--sm", onclick: () => openLaunchModal() },
          "+ Lançar"
        ),
      ])
    );

    container.appendChild(
      UI.el("div", { class: "tiles" }, [
        UI.el("div", { class: "tile tile--wide" }, [
          UI.el("div", { class: "tile__label" }, "Saldo total"),
          UI.el("div", { class: "tile__value" }, UI.money(totalBalance)),
        ]),
        UI.el("div", { class: "tile" }, [
          UI.el("div", { class: "tile__label" }, "Contas"),
          UI.el("div", { class: "tile__value" }, String(accounts.length)),
        ]),
        UI.el("div", { class: "tile" }, [
          UI.el("div", { class: "tile__label" }, "Metas ativas"),
          UI.el(
            "div",
            { class: "tile__value" },
            String(goals.filter((g) => g.status === "in_progress").length)
          ),
        ]),
      ])
    );

    container.appendChild(UI.el("div", { class: "section-title" }, "Contas"));
    if (accounts.length === 0) {
      container.appendChild(emptyState(UI.icon("landmark"), "Nenhuma conta cadastrada ainda."));
    } else {
      const list = UI.el("div", { class: "list" });
      accounts.slice(0, 4).forEach((a) => {
        list.appendChild(
          UI.el("div", { class: "list-item" }, [
            UI.el("div", { class: "list-item__main" }, [
              UI.el("div", { class: "list-item__title" }, a.name),
              UI.el("div", { class: "list-item__subtitle" }, a.type),
            ]),
            UI.el(
              "div",
              {
                class:
                  "list-item__value " +
                  (Number(a.current_balance) >= 0 ? "value--positive" : "value--negative"),
              },
              UI.money(a.current_balance)
            ),
          ])
        );
      });
      container.appendChild(list);
    }

    container.appendChild(UI.el("div", { class: "section-title" }, "Últimas transações"));
    const transactions = txResp.data;
    if (transactions.length === 0) {
      container.appendChild(emptyState(UI.icon("receipt"), "Nenhuma transação registrada ainda."));
    } else {
      const list = UI.el("div", { class: "list" });
      transactions.forEach((t) => list.appendChild(transactionRow(t)));
      container.appendChild(list);
    }

    container.appendChild(
      UI.el(
        "button",
        {
          class: "btn btn--primary btn--fab",
          "aria-label": "Lançar receita ou despesa",
          onclick: () => openLaunchModal(),
        },
        "+"
      )
    );

    function openLaunchModal() {
      openCreateTransactionModal(accounts, categories, creditCards, refresh);
    }
  }

  await refresh();
}

function emptyState(icon, text) {
  return UI.el("div", { class: "empty-state" }, [
    UI.el("div", { class: "empty-state__icon" }, icon),
    UI.el("div", {}, text),
  ]);
}

function transactionRow(t) {
  const isIncome = t.type === "income";
  return UI.el("div", { class: "list-item" }, [
    UI.el("div", { class: "list-item__main" }, [
      UI.el("div", { class: "list-item__title" }, t.description),
      UI.el("div", { class: "list-item__subtitle" }, UI.dateBR(t.date)),
    ]),
    UI.el(
      "div",
      { class: "list-item__value " + (isIncome ? "value--positive" : "value--negative") },
      (isIncome ? "+ " : "- ") + UI.money(t.amount)
    ),
  ]);
}

Router.register("/", renderHomeView);

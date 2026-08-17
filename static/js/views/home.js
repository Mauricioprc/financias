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

  let balanceChart = null;
  let categoryChart = null;

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

    if (balanceChart) balanceChart.destroy();
    if (categoryChart) categoryChart.destroy();
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

    await renderCharts(accounts);

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

    /* Gráficos de evolução de saldo (30 dias) e gastos por categoria (mês atual).
       Calculados no client a partir de Api.transactions.list() — ver reportData.js.
       TODO: mover para endpoint /reports quando existir (Fase C). */
    async function renderCharts(currentAccounts) {
      const today = UI.todayISO();
      const monthStart = today.slice(0, 7) + "-01";

      let last30dTx;
      let monthTx;
      try {
        [last30dTx, monthTx] = await Promise.all([
          ReportData.fetchAllTransactions({ date_from: ReportData.lastNDays(30)[0] }),
          ReportData.fetchAllTransactions({ date_from: monthStart, date_to: today, type: "expense" }),
        ]);
      } catch (err) {
        UI.showApiError(err);
        return;
      }

      const grid = UI.el("div", { class: "report-grid" });

      const balanceWrap = UI.el("div", { class: "chart-card__canvas-wrap" }, [
        UI.el("canvas", {}),
      ]);
      grid.appendChild(
        UI.el("div", { class: "card" }, [
          UI.el("div", { class: "chart-card__title" }, "Evolução do saldo (30 dias)"),
          balanceWrap,
        ])
      );

      const categoryWrap = UI.el("div", { class: "chart-card__canvas-wrap chart-card__canvas-wrap--donut" });
      grid.appendChild(
        UI.el("div", { class: "card" }, [
          UI.el("div", { class: "chart-card__title" }, "Gastos por categoria (mês atual)"),
          categoryWrap,
        ])
      );

      container.appendChild(grid);

      const theme = ChartTheme.applyDefaults();

      const history = ReportData.balanceHistory(currentAccounts, last30dTx, 30);
      balanceChart = new Chart(UI.qs("canvas", balanceWrap), {
        type: "line",
        data: {
          labels: history.labels,
          datasets: [
            {
              data: history.values,
              borderColor: theme.accent,
              backgroundColor: theme.accent + "22",
              fill: true,
              tension: 0.3,
              pointRadius: 0,
              borderWidth: 2,
            },
          ],
        },
        options: {
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { maxTicksLimit: 6 }, grid: { display: false } },
            y: { ticks: { callback: (v) => UI.money(v) }, grid: { color: theme.border } },
          },
        },
      });

      const breakdown = ReportData.categoryBreakdown(monthTx, categories, "expense");
      if (breakdown.labels.length === 0) {
        categoryWrap.appendChild(
          UI.el("div", { class: "chart-card__empty" }, "Nenhuma despesa neste mês ainda.")
        );
      } else {
        const canvas = UI.el("canvas", {});
        categoryWrap.appendChild(canvas);
        categoryChart = new Chart(canvas, {
          type: "doughnut",
          data: {
            labels: breakdown.labels,
            datasets: [
              {
                data: breakdown.values,
                backgroundColor: breakdown.labels.map(
                  (_, i) => theme.categorical[i % theme.categorical.length]
                ),
                borderColor: ChartTheme.cssVar("--surface"),
                borderWidth: 2,
              },
            ],
          },
          options: {
            maintainAspectRatio: false,
            plugins: {
              legend: {
                position: "bottom",
                labels: { boxWidth: 10, padding: 12, font: { size: 11 } },
              },
              tooltip: {
                callbacks: { label: (ctx) => `${ctx.label}: ${UI.money(ctx.parsed)}` },
              },
            },
          },
        });
      }
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

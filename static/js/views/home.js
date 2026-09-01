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

  // Mesmo gatilho silencioso de recurring.js — a Home é a tela que abre
  // primeiro, então é aqui que a maioria das assinaturas vencidas hoje vai
  // ser lançada na prática. Nunca gera pra frente (rota sem `until`).
  Api.recurring.autoGenerate().catch(() => {});

  let balanceChart = null;
  let categoryChart = null;

  async function refresh() {
    let accounts;
    let txResp;
    let goals;
    let insightsSummary;
    try {
      [accounts, txResp, goals, insightsSummary] = await Promise.all([
        Api.accounts.list(),
        Api.transactions.list({ per_page: 5 }),
        Api.goals.list(),
        // Enriquecimento, não crítico — se falhar, o resto da Home continua normal.
        Api.insights.summary().catch(() => null),
      ]);
    } catch (err) {
      container.innerHTML = "";
      UI.showApiError(err);
      return;
    }

    const anomalies = insightsSummary ? insightsSummary.spending_anomalies : [];
    const invoiceTrends = insightsSummary ? insightsSummary.invoice_trends : [];
    const forecastByAccountId = Object.fromEntries(
      (insightsSummary ? insightsSummary.balance_forecasts : []).map((f) => [
        String(f.account_id),
        f,
      ])
    );

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

    if (anomalies.length > 0 || invoiceTrends.length > 0) {
      container.appendChild(UI.el("div", { class: "section-title" }, "Alertas"));
      const alertsList = UI.el("div", { class: "list" });
      anomalies.forEach((a) => alertsList.appendChild(anomalyRow(a)));
      invoiceTrends.forEach((t) => alertsList.appendChild(invoiceTrendRow(t)));
      container.appendChild(alertsList);
    }

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

    await renderCharts();

    container.appendChild(UI.el("div", { class: "section-title" }, "Contas"));
    if (accounts.length === 0) {
      container.appendChild(emptyState(UI.icon("landmark"), "Nenhuma conta cadastrada ainda."));
    } else {
      const list = UI.el("div", { class: "list" });
      accounts.slice(0, 4).forEach((a) => {
        const mainChildren = [
          UI.el("div", { class: "list-item__title" }, a.name),
          UI.el("div", { class: "list-item__subtitle" }, a.type),
        ];

        const forecast = forecastByAccountId[String(a.id)];
        if (forecast && forecast.days_remaining > 0) {
          const diff =
            Number(forecast.projected_end_of_month_balance) - Number(forecast.current_balance);
          // Diferença irrelevante (< R$1) não precisa poluir a lista.
          if (Math.abs(diff) >= 1) {
            mainChildren.push(
              UI.el(
                "div",
                { class: "list-item__subtitle" },
                `projeção fim do mês: ${UI.money(forecast.projected_end_of_month_balance)}`
              )
            );
          }
        }

        list.appendChild(
          UI.el("div", { class: "list-item" }, [
            UI.el("div", { class: "list-item__main" }, mainChildren),
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

    /* Gráficos de evolução de saldo (30 dias) e gastos por categoria (mês atual),
       via app/api/v1/report_routes.py (ver reportData.js). */
    async function renderCharts() {
      const currentMonth = UI.todayISO().slice(0, 7);

      let history;
      let breakdown;
      try {
        [history, breakdown] = await Promise.all([
          ReportData.balanceHistory(30),
          ReportData.categoryBreakdown(currentMonth, "expense"),
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

/* Badge de severidade reaproveitando as cores já existentes pra
   expense/in_progress (vermelho/amarelo) — mesmo padrão de badge usado em
   invoices.js/goals.js, sem componente novo. */
function anomalyRow(a) {
  const badgeClass = a.severity === "alta" ? "badge--expense" : "badge--in_progress";
  const badgeLabel = a.severity === "alta" ? "Alta" : "Moderada";
  return UI.el("div", { class: "list-item" }, [
    UI.el("div", { class: "list-item__main" }, [
      UI.el("div", { class: "list-item__title" }, [
        a.category_name + " ",
        UI.el("span", { class: `badge ${badgeClass}` }, badgeLabel),
      ]),
      UI.el(
        "div",
        { class: "list-item__subtitle" },
        `Projeção: ${UI.money(a.projected_month_total)} · ${Math.round(Number(a.pct_above_avg))}% acima da média`
      ),
    ]),
  ]);
}

function invoiceTrendRow(t) {
  return UI.el(
    "div",
    {
      class: "list-item list-item--clickable",
      onclick: () => Router.navigate(`/credit-cards/${t.card_id}/invoices`),
    },
    [
      UI.el("div", { class: "list-item__main" }, [
        UI.el("div", { class: "list-item__title" }, t.card_name),
        UI.el(
          "div",
          { class: "list-item__subtitle" },
          `Fatura projetada: ${UI.money(t.projected_total)} · ` +
            `${Math.round(Number(t.pct_above_average))}% acima da média de ${UI.money(t.avg_of_last_3)}`
        ),
      ]),
    ]
  );
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

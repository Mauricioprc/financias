/* Relatórios — receitas x despesas por mês, breakdown por categoria, fatura de
   cartão mês a mês e progresso de metas. Agregações client-side (reportData.js);
   TODO: mover para endpoint /reports quando existir (Fase C). */

async function renderReportsView(container) {
  container.appendChild(UI.el("div", { class: "loading" }, "Carregando..."));

  let categories;
  let creditCards;
  let goals;
  try {
    [categories, creditCards, goals] = await Promise.all([
      Api.categories.list(),
      Api.creditCards.list(),
      Api.goals.list(),
    ]);
  } catch (err) {
    container.innerHTML = "";
    UI.showApiError(err);
    return;
  }

  const state = { month: UI.todayISO().slice(0, 7) };
  let incomeExpenseChart = null;
  let breakdownChart = null;

  container.innerHTML = "";
  container.appendChild(UI.el("h1", { class: "page-title" }, "Relatórios"));

  const grid = UI.el("div", { class: "report-grid" });
  container.appendChild(grid);

  const incomeExpenseWrap = UI.el("div", { class: "chart-card__canvas-wrap" });
  grid.appendChild(
    UI.el("div", { class: "card" }, [
      UI.el("div", { class: "chart-card__title" }, "Receitas x despesas (12 meses)"),
      incomeExpenseWrap,
    ])
  );

  const monthSelect = UI.el(
    "select",
    {
      onchange: (e) => {
        state.month = e.target.value;
        renderBreakdown();
      },
    },
    ReportData.lastNMonths(12)
      .reverse()
      .map((m) =>
        UI.el("option", { value: m, selected: m === state.month }, ReportData.monthLabel(m))
      )
  );
  const breakdownWrap = UI.el("div", { class: "chart-card__canvas-wrap chart-card__canvas-wrap--donut" });
  grid.appendChild(
    UI.el("div", { class: "card" }, [
      UI.el("div", { class: "page-header" }, [
        UI.el("div", { class: "chart-card__title", style: "margin-bottom:0" }, "Gastos por categoria"),
        monthSelect,
      ]),
      breakdownWrap,
    ])
  );

  const invoicesCardBody = UI.el("div", { class: "chart-card__canvas-wrap" });
  container.appendChild(
    UI.el("div", { class: "card" }, [
      UI.el("div", { class: "chart-card__title" }, "Faturas por cartão (últimos meses)"),
      invoicesCardBody,
    ])
  );

  const goalsCard = UI.el("div", { class: "list" });
  container.appendChild(UI.el("div", { class: "section-title" }, "Progresso das metas"));
  container.appendChild(goalsCard);

  const theme = ChartTheme.applyDefaults();

  let allTx;
  try {
    allTx = await ReportData.fetchAllTransactions({ date_from: ReportData.lastNMonths(12)[0] + "-01" });
  } catch (err) {
    UI.showApiError(err);
    return;
  }

  const summary = ReportData.incomeVsExpenseByMonth(allTx, 12);
  const ieCanvas = UI.el("canvas", {});
  incomeExpenseWrap.appendChild(ieCanvas);
  incomeExpenseChart = new Chart(ieCanvas, {
    type: "bar",
    data: {
      labels: summary.labels,
      datasets: [
        { label: "Receitas", data: summary.income, backgroundColor: theme.success },
        { label: "Despesas", data: summary.expense, backgroundColor: theme.danger },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 11 } } } },
      scales: {
        x: { grid: { display: false } },
        y: { ticks: { callback: (v) => UI.money(v) }, grid: { color: theme.border } },
      },
    },
  });

  function renderBreakdown() {
    if (breakdownChart) breakdownChart.destroy();
    breakdownWrap.innerHTML = "";
    const monthTx = allTx.filter((t) => String(t.date).slice(0, 7) === state.month && t.type === "expense");
    const breakdown = ReportData.categoryBreakdown(monthTx, categories, "expense");
    if (breakdown.labels.length === 0) {
      breakdownWrap.appendChild(
        UI.el("div", { class: "chart-card__empty" }, "Nenhuma despesa neste mês.")
      );
      return;
    }
    const canvas = UI.el("canvas", {});
    breakdownWrap.appendChild(canvas);
    breakdownChart = new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: breakdown.labels,
        datasets: [
          {
            data: breakdown.values,
            backgroundColor: breakdown.labels.map((_, i) => theme.categorical[i % theme.categorical.length]),
            borderColor: ChartTheme.cssVar("--surface"),
            borderWidth: 2,
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 10, padding: 10, font: { size: 11 } } },
          tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${UI.money(ctx.parsed)}` } },
        },
      },
    });
  }
  renderBreakdown();

  /* Comparativo de fatura por cartão — soma das transações no cartão, por mês, últimos 6 meses. */
  invoicesCardBody.innerHTML = "";
  if (creditCards.length === 0) {
    invoicesCardBody.appendChild(
      UI.el("div", { class: "chart-card__empty" }, "Nenhum cartão de crédito cadastrado.")
    );
  } else {
    const months6 = ReportData.lastNMonths(6);
    const byCard = creditCards.map((card) => {
      const totals = months6.map((m) =>
        allTx
          .filter(
            (t) =>
              t.credit_card_id === card.id &&
              t.type === "expense" &&
              String(t.date).slice(0, 7) === m
          )
          .reduce((sum, t) => sum + Number(t.amount), 0)
      );
      return { label: card.name, data: totals };
    });
    const invCanvas = UI.el("canvas", {});
    invoicesCardBody.appendChild(invCanvas);
    const invoicesChart = new Chart(invCanvas, {
      type: "bar",
      data: {
        labels: months6.map(ReportData.monthLabel),
        datasets: byCard.map((c, i) => ({
          label: c.label,
          data: c.data,
          backgroundColor: theme.categorical[i % theme.categorical.length],
        })),
      },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 11 } } } },
        scales: {
          x: { grid: { display: false } },
          y: { ticks: { callback: (v) => UI.money(v) }, grid: { color: theme.border } },
        },
      },
    });
  }

  /* Progresso das metas */
  goalsCard.innerHTML = "";
  const activeGoals = goals.filter((g) => g.status === "in_progress");
  if (activeGoals.length === 0) {
    goalsCard.appendChild(UI.el("div", { class: "empty-state" }, [
      UI.el("div", { class: "empty-state__icon" }, UI.icon("target")),
      UI.el("div", {}, "Nenhuma meta em andamento."),
    ]));
  } else {
    activeGoals.forEach((g) => {
      const current = Number(g.current_amount);
      const target = Number(g.target_amount) || 1;
      const pct = Math.min(100, Math.round((current / target) * 100));
      goalsCard.appendChild(
        UI.el("div", { class: "list-item", style: "flex-direction:column;align-items:stretch" }, [
          UI.el("div", { class: "list-item__main" }, [
            UI.el("div", { class: "list-item__title" }, g.name),
            UI.el(
              "div",
              { class: "list-item__subtitle" },
              `${UI.money(current)} de ${UI.money(target)} (${pct}%)`
            ),
          ]),
          UI.el("div", { class: "progress-bar" }, [
            UI.el("div", { class: "progress-bar__fill", style: `width:${pct}%` }),
          ]),
        ])
      );
    });
  }
}

Router.register("/reports", renderReportsView);

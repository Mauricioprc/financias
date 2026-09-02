/* Relatórios — receitas x despesas por mês, breakdown por categoria, fatura de
   cartão mês a mês e progresso de metas. Receitas/despesas e breakdown vêm de
   app/api/v1/report_routes.py; faturas por cartão usa Api.invoices (totais já
   fechados pelo app) e metas usa Api.goals — nenhum dos dois precisa de
   agregação extra. */

async function renderReportsView(container) {
  container.appendChild(UI.el("div", { class: "loading" }, "Carregando..."));

  let accounts;
  let creditCards;
  let goals;
  let insightsSummary;
  let netWorthToday;
  let netWorthHistory;
  try {
    [accounts, creditCards, goals, insightsSummary, netWorthToday, netWorthHistory] = await Promise.all([
      Api.accounts.list(),
      Api.creditCards.list(),
      Api.goals.list(),
      // Enriquecimento, não crítico — sem isso a tela segue funcionando,
      // só sem a seção de comparação por categoria.
      Api.insights.summary().catch(() => null),
      Api.netWorth.today().catch(() => null),
      Api.netWorth.history(12).catch(() => null),
    ]);
  } catch (err) {
    container.innerHTML = "";
    UI.showApiError(err);
    return;
  }

  const state = { month: UI.todayISO().slice(0, 7), account_id: "" };
  let incomeExpenseChart = null;
  let breakdownChart = null;
  let balanceHistoryChart = null;

  container.innerHTML = "";
  container.appendChild(UI.el("h1", { class: "page-title" }, "Relatórios"));

  const theme = ChartTheme.applyDefaults();
  renderNetWorthSection();

  const summaryLine = UI.el("div", { class: "section-title" });
  container.appendChild(summaryLine);

  // Filtro por conta — controla só os dois gráficos que consultam o backend
  // por account_id (evolução de saldo e gastos por categoria); receitas x
  // despesas, faturas por cartão e metas continuam sempre "todas as contas"
  // (os endpoints deles não têm esse filtro).
  const accountFilterField = UI.el("div", { class: "form-field" }, [
    UI.el("label", {}, "Conta"),
    UI.el(
      "select",
      {
        onchange: (e) => {
          state.account_id = e.target.value;
          renderBalanceHistory();
          renderBreakdown();
        },
      },
      [{ value: "", label: "(todas as contas)" }]
        .concat(accounts.map((a) => ({ value: a.id, label: a.name })))
        .map((opt) => UI.el("option", { value: opt.value }, opt.label))
    ),
  ]);
  container.appendChild(UI.el("div", { class: "filters-bar" }, [accountFilterField]));

  const grid = UI.el("div", { class: "report-grid" });
  container.appendChild(grid);

  const balanceHistoryWrap = UI.el("div", { class: "chart-card__canvas-wrap" });
  grid.appendChild(
    UI.el("div", { class: "card" }, [
      UI.el("div", { class: "chart-card__title" }, "Evolução do saldo (30 dias)"),
      balanceHistoryWrap,
    ])
  );

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
      UI.el("div", { class: "chart-card__title" }, "Faturas por cartão (últimos 6 meses)"),
      invoicesCardBody,
    ])
  );

  const goalsCard = UI.el("div", { class: "list" });
  container.appendChild(UI.el("div", { class: "section-title" }, "Progresso das metas"));
  container.appendChild(goalsCard);

  let summary;
  try {
    summary = await ReportData.incomeVsExpenseByMonth(12);
  } catch (err) {
    UI.showApiError(err);
    return;
  }

  // Resumo rápido do mês corrente (último ponto dos 12 meses já buscados
  // acima — sem chamada duplicada). Esse endpoint não tem filtro por
  // conta, então esse resumo é sempre "todas as contas", diferente dos
  // dois gráficos abaixo dele.
  const currentMonthIncome = summary.income[summary.income.length - 1] || 0;
  const currentMonthExpense = summary.expense[summary.expense.length - 1] || 0;
  summaryLine.textContent =
    `receitas ${UI.money(currentMonthIncome)} · despesas ${UI.money(currentMonthExpense)} · ` +
    `saldo do mês ${UI.money(currentMonthIncome - currentMonthExpense)}`;

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

  async function renderBalanceHistory() {
    if (balanceHistoryChart) balanceHistoryChart.destroy();
    balanceHistoryWrap.innerHTML = "";
    let history;
    try {
      history = await ReportData.balanceHistory(30, state.account_id || undefined);
    } catch (err) {
      UI.showApiError(err);
      return;
    }
    const canvas = UI.el("canvas", {});
    balanceHistoryWrap.appendChild(canvas);
    balanceHistoryChart = new Chart(canvas, {
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
  }
  await renderBalanceHistory();

  async function renderBreakdown() {
    if (breakdownChart) breakdownChart.destroy();
    breakdownWrap.innerHTML = "";
    let breakdown;
    try {
      breakdown = await ReportData.categoryBreakdown(state.month, "expense", state.account_id || undefined);
    } catch (err) {
      UI.showApiError(err);
      return;
    }
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
  await renderBreakdown();

  /* Comparativo de fatura por cartão — total_amount de cada fatura já fechada
     pelo app (Api.invoices), agrupado por mês de referência. */
  invoicesCardBody.innerHTML = "";
  if (creditCards.length === 0) {
    invoicesCardBody.appendChild(
      UI.el("div", { class: "chart-card__empty" }, "Nenhum cartão de crédito cadastrado.")
    );
  } else {
    const months6 = ReportData.lastNMonths(6);
    let invoicesByCard;
    try {
      invoicesByCard = await Promise.all(creditCards.map((c) => Api.invoices.list({ credit_card_id: c.id })));
    } catch (err) {
      UI.showApiError(err);
      return;
    }
    const byCard = creditCards.map((card, i) => {
      const totalByMonth = {};
      invoicesByCard[i].forEach((inv) => {
        totalByMonth[String(inv.reference_month).slice(0, 7)] = Number(inv.total_amount);
      });
      return { label: card.name, data: months6.map((m) => totalByMonth[m] || 0) };
    });
    const invCanvas = UI.el("canvas", {});
    invoicesCardBody.appendChild(invCanvas);
    new Chart(invCanvas, {
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

  /* Comparação de gastos por categoria (mês corrente x mesmo recorte de dia
     do mês anterior x média trailing de 3 meses) — GET /insights/summary. */
  const categoryComparison = insightsSummary ? insightsSummary.category_comparison : [];
  container.appendChild(
    UI.el("div", { class: "section-title" }, "Comparação de gastos por categoria")
  );
  if (categoryComparison.length === 0) {
    container.appendChild(
      UI.el("div", { class: "empty-state" }, [
        UI.el("div", { class: "empty-state__icon" }, UI.icon("bar-chart-3")),
        UI.el("div", {}, "Sem dado suficiente pra comparar categorias ainda."),
      ])
    );
  } else {
    const comparisonList = UI.el("div", { class: "list" });
    categoryComparison.forEach((item) => comparisonList.appendChild(categoryComparisonRow(item)));
    container.appendChild(comparisonList);
  }

  /* Patrimônio líquido — GET /net-worth/today (contas + investimentos -
     faturas em aberto, hoje) e /net-worth/history (só contas, últimos 12
     meses). São métricas DIFERENTES de propósito: o histórico mensal é só
     contas (dado confiável ao longo do tempo — ver net_worth_service.py),
     "hoje" inclui investimento. O gráfico abaixo deixa isso explícito no
     título pra não confundir com o tile "Patrimônio líquido" (que é o
     total de hoje) nem com "Evolução do saldo (30 dias)" da Home — essa
     é uma janela curta de dias, não um histórico mensal de 12 meses. */
  function renderNetWorthSection() {
    if (!netWorthToday && !netWorthHistory) return; // enriquecimento — sem dado, sem seção

    container.appendChild(UI.el("div", { class: "section-title" }, "Patrimônio líquido"));

    if (netWorthToday) {
      container.appendChild(
        UI.el("div", { class: "tiles" }, [
          UI.el("div", { class: "tile tile--wide" }, [
            UI.el("div", { class: "tile__label" }, "Patrimônio líquido (hoje)"),
            UI.el("div", { class: "tile__value" }, UI.money(netWorthToday.net_worth)),
          ]),
          UI.el("div", { class: "tile" }, [
            UI.el("div", { class: "tile__label" }, "Contas"),
            UI.el("div", { class: "tile__value" }, UI.money(netWorthToday.accounts_total)),
          ]),
          UI.el("div", { class: "tile" }, [
            UI.el("div", { class: "tile__label" }, "Investimentos"),
            UI.el("div", { class: "tile__value" }, UI.money(netWorthToday.investments_total)),
          ]),
          UI.el("div", { class: "tile" }, [
            UI.el("div", { class: "tile__label" }, "Faturas em aberto"),
            UI.el(
              "div",
              { class: "tile__value value--negative" },
              "- " + UI.money(netWorthToday.unpaid_invoices_total)
            ),
          ]),
        ])
      );
    }

    if (netWorthHistory && netWorthHistory.length > 0) {
      const canvasWrap = UI.el("div", { class: "chart-card__canvas-wrap" }, [UI.el("canvas", {})]);
      container.appendChild(
        UI.el("div", { class: "card" }, [
          UI.el(
            "div",
            { class: "chart-card__title" },
            "Patrimônio em contas — últimos 12 meses"
          ),
          canvasWrap,
        ])
      );

      new Chart(UI.qs("canvas", canvasWrap), {
        type: "line",
        data: {
          labels: netWorthHistory.map((h) => h.month),
          datasets: [
            {
              data: netWorthHistory.map((h) => Number(h.total_accounts_balance)),
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
            x: { grid: { display: false } },
            y: { ticks: { callback: (v) => UI.money(v) }, grid: { color: theme.border } },
          },
        },
      });
    }
  }
}

/* Despesas: variação negativa (gastou menos que a média) é boa (verde);
   positiva (gastou mais) é ruim (vermelho) — mesmas classes já usadas em
   valores de receita/despesa no resto do app. */
function categoryComparisonRow(item) {
  const pct = item.pct_change_vs_avg;
  let pctLabel;
  let pctClass = "";
  if (pct === null || pct === undefined) {
    pctLabel = "sem histórico";
  } else {
    const rounded = Math.round(Number(pct));
    pctLabel = (rounded > 0 ? "+" : "") + rounded + "%";
    pctClass = rounded > 0 ? "value--negative" : rounded < 0 ? "value--positive" : "";
  }

  return UI.el("div", { class: "list-item" }, [
    UI.el("div", { class: "list-item__main" }, [
      UI.el("div", { class: "list-item__title" }, item.category_name),
      UI.el(
        "div",
        { class: "list-item__subtitle" },
        `${UI.money(item.current_month_total)} este mês`
      ),
    ]),
    UI.el("div", { class: `list-item__value ${pctClass}` }, pctLabel),
  ]);
}

Router.register("/reports", renderReportsView);

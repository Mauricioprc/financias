/* Wrapper fino sobre Api.reports.* — formata a resposta dos endpoints de
   relatório (app/api/v1/report_routes.py) no shape {labels, values} que os
   gráficos (Chart.js) consomem, e concentra os helpers de rótulo de mês/dia. */

const ReportData = (() => {
  function dayLabel(iso) {
    const [, m, d] = iso.split("-");
    return `${d}/${m}`;
  }

  function monthLabel(key) {
    const [y, m] = key.split("-");
    const names = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
    return `${names[Number(m) - 1]}/${y.slice(2)}`;
  }

  function lastNMonths(n) {
    const months = [];
    const today = new Date();
    for (let i = n - 1; i >= 0; i--) {
      const d = new Date(today.getFullYear(), today.getMonth() - i, 1);
      months.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
    }
    return months;
  }

  async function balanceHistory(days, accountId) {
    const points = await Api.reports.balanceHistory(days, accountId);
    return {
      labels: points.map((p) => dayLabel(p.date)),
      values: points.map((p) => Number(p.balance)),
    };
  }

  async function categoryBreakdown(month, type, accountId) {
    const items = await Api.reports.categoryBreakdown(month, type, accountId);
    return {
      labels: items.map((i) => i.category_name),
      values: items.map((i) => Number(i.total)),
    };
  }

  async function incomeVsExpenseByMonth(months) {
    const items = await Api.reports.incomeVsExpense(months);
    return {
      labels: items.map((i) => monthLabel(i.month)),
      income: items.map((i) => Number(i.income)),
      expense: items.map((i) => Number(i.expense)),
    };
  }

  return {
    dayLabel,
    monthLabel,
    lastNMonths,
    balanceHistory,
    categoryBreakdown,
    incomeVsExpenseByMonth,
  };
})();

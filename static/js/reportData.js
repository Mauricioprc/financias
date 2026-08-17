/* Agregações client-side para Home e Relatórios (evolução de saldo, gastos por
   categoria, receita x despesa por mês).

   TODO: mover estes cálculos para endpoints em app/services/report_service.py
   (GET /api/v1/reports/...) quando existirem — Fase C do plano de refatoração
   visual. Por ora tudo é derivado de Api.transactions.list() no client. */

const ReportData = (() => {
  async function fetchAllTransactions(query, maxPages = 20) {
    const perPage = 100;
    let page = 1;
    let all = [];
    while (page <= maxPages) {
      const resp = await Api.transactions.list({ ...query, page, per_page: perPage });
      all = all.concat(resp.data);
      const totalPages = Math.max(1, Math.ceil(resp.meta.total / resp.meta.per_page));
      if (page >= totalPages) break;
      page += 1;
    }
    return all;
  }

  function isoDate(d) {
    return d.toISOString().slice(0, 10);
  }

  function lastNDays(n) {
    const days = [];
    const today = new Date();
    for (let i = n - 1; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      days.push(isoDate(d));
    }
    return days;
  }

  function dayLabel(iso) {
    const [, m, d] = iso.split("-");
    return `${d}/${m}`;
  }

  function signedAmount(t) {
    const amt = Number(t.amount);
    return t.type === "income" ? amt : -amt;
  }

  /* Reconstrói o saldo total ao final de cada um dos últimos `days` dias, partindo
     do saldo atual das contas e "desfazendo" as transações já efetivadas (is_paid)
     de trás para frente. */
  function balanceHistory(accounts, transactions, days) {
    const totalBalance = accounts.reduce((sum, a) => sum + Number(a.current_balance), 0);
    const dayList = lastNDays(days);
    const netByDay = {};
    transactions
      .filter((t) => t.is_paid)
      .forEach((t) => {
        const day = String(t.date).slice(0, 10);
        netByDay[day] = (netByDay[day] || 0) + signedAmount(t);
      });

    const values = new Array(dayList.length);
    values[dayList.length - 1] = totalBalance;
    for (let i = dayList.length - 1; i > 0; i--) {
      values[i - 1] = values[i] - (netByDay[dayList[i]] || 0);
    }
    return { labels: dayList.map(dayLabel), values };
  }

  function categoryBreakdown(transactions, categories, type) {
    const nameById = {};
    categories.forEach((c) => (nameById[c.id] = c.name));
    const totals = {};
    transactions
      .filter((t) => t.type === type)
      .forEach((t) => {
        const key = t.category_id ? nameById[t.category_id] || "Outros" : "Sem categoria";
        totals[key] = (totals[key] || 0) + Number(t.amount);
      });
    const entries = Object.entries(totals).sort((a, b) => b[1] - a[1]);
    return { labels: entries.map((e) => e[0]), values: entries.map((e) => e[1]) };
  }

  function monthKey(dateStr) {
    return String(dateStr).slice(0, 7);
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

  function monthLabel(key) {
    const [y, m] = key.split("-");
    const names = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
    return `${names[Number(m) - 1]}/${y.slice(2)}`;
  }

  function incomeVsExpenseByMonth(transactions, months) {
    const monthList = lastNMonths(months);
    const income = Object.fromEntries(monthList.map((m) => [m, 0]));
    const expense = Object.fromEntries(monthList.map((m) => [m, 0]));
    transactions.forEach((t) => {
      const key = monthKey(t.date);
      if (!(key in income)) return;
      if (t.type === "income") income[key] += Number(t.amount);
      else expense[key] += Number(t.amount);
    });
    return {
      labels: monthList.map(monthLabel),
      income: monthList.map((m) => income[m]),
      expense: monthList.map((m) => expense[m]),
    };
  }

  return {
    fetchAllTransactions,
    lastNDays,
    lastNMonths,
    monthLabel,
    balanceHistory,
    categoryBreakdown,
    incomeVsExpenseByMonth,
  };
})();

/* Calendário de contas a vencer — linha do tempo horizontal (não grade de
   calendário tradicional, que desperdiça espaço com dias sem nada). */

const UPCOMING_BILLS_DAYS = 30;
const UPCOMING_URGENT_DAYS = 3; // vence em até N dias -> ponto vermelho
const UPCOMING_SOON_DAYS = 7; // vence em até N dias -> ponto amarelo

function shortDateBR(isoDate) {
  const [, m, d] = String(isoDate).slice(0, 10).split("-");
  return `${d}/${m}`;
}

function upcomingBillAmountDisplay(bill) {
  if (bill.type === "invoice") {
    // Fatura: sempre saldo devedor, sempre despesa.
    return { text: "- " + UI.money(bill.amount), className: "value--negative" };
  }
  const amount = Number(bill.amount);
  return amount >= 0
    ? { text: "+ " + UI.money(amount), className: "value--positive" }
    : { text: "- " + UI.money(Math.abs(amount)), className: "value--negative" };
}

function upcomingBillDotClass(isoDate) {
  const today = new Date(UI.todayISO());
  const target = new Date(String(isoDate).slice(0, 10));
  const daysUntil = Math.round((target - today) / 86400000);
  if (daysUntil <= UPCOMING_URGENT_DAYS) return "timeline__dot--urgent";
  if (daysUntil <= UPCOMING_SOON_DAYS) return "timeline__dot--soon";
  return "";
}

async function renderUpcomingBillsView(container) {
  container.appendChild(UI.el("div", { class: "loading" }, "Carregando..."));

  let bills;
  try {
    bills = await Api.upcomingBills.list(UPCOMING_BILLS_DAYS);
  } catch (err) {
    container.innerHTML = "";
    UI.showApiError(err);
    return;
  }
  container.innerHTML = "";

  container.appendChild(
    UI.el("div", { class: "page-header" }, [
      UI.el("h1", { class: "page-title" }, "Próximos vencimentos"),
      UI.el(
        "button",
        { class: "btn btn--secondary btn--sm", onclick: () => Router.navigate("/") },
        "Voltar"
      ),
    ])
  );

  if (bills.length === 0) {
    container.appendChild(
      UI.el("div", { class: "empty-state" }, [
        UI.el("div", { class: "empty-state__icon" }, UI.icon("calendar")),
        UI.el("div", {}, `Nenhuma conta prevista para os próximos ${UPCOMING_BILLS_DAYS} dias.`),
      ])
    );
    return;
  }

  // Agrupa por data (mesma abordagem simples de reduce já usada no resto
  // do app — sem lib de datas nova).
  const billsByDate = bills.reduce((acc, bill) => {
    const key = String(bill.date).slice(0, 10);
    (acc[key] = acc[key] || []).push(bill);
    return acc;
  }, {});
  const dates = Object.keys(billsByDate).sort();

  const timeline = UI.el(
    "div",
    { class: "timeline" },
    dates.map((date) => {
      const dayBills = billsByDate[date];
      const cards = dayBills.map((bill) => {
        const { text, className } = upcomingBillAmountDisplay(bill);
        return UI.el("div", { class: "timeline__card" }, [
          UI.el("div", { class: "timeline__card-label" }, bill.label),
          UI.el("div", { class: `timeline__card-amount ${className}` }, text),
        ]);
      });

      return UI.el("div", { class: "timeline__marker" }, [
        UI.el("div", { class: `timeline__dot ${upcomingBillDotClass(date)}` }),
        UI.el("div", { class: "timeline__date" }, shortDateBR(date)),
        UI.el("div", { class: "timeline__cards" }, cards),
      ]);
    })
  );
  container.appendChild(timeline);

  container.appendChild(
    UI.el("div", { class: "list-item__subtitle", style: "margin-top:16px" }, [
      UI.el("span", { class: "timeline__legend-dot timeline__dot--urgent" }),
      ` vence em até ${UPCOMING_URGENT_DAYS} dias   `,
      UI.el("span", { class: "timeline__legend-dot timeline__dot--soon" }),
      ` vence em até ${UPCOMING_SOON_DAYS} dias`,
    ])
  );
}

Router.register("/upcoming-bills", renderUpcomingBillsView);

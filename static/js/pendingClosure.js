/* Aviso não-bloqueante de faturas vencidas aguardando confirmação de
 * fechamento (GET /invoices/pending-closure). Checa uma única vez por
 * sessão de aba (sessionStorage) — chamado a partir de updateChrome() em
 * app.js sempre que o usuário está autenticado e a chrome do app é
 * montada; a própria flag de sessionStorage garante que só dispara de
 * verdade na primeira vez (reload não reabre; fechar e reabrir a aba, ou
 * uma sessionStorage limpa, sim). */

const PendingClosure = (() => {
  const SESSION_KEY = "financias_pending_closure_checked";

  async function checkOnce() {
    if (sessionStorage.getItem(SESSION_KEY)) return;
    sessionStorage.setItem(SESSION_KEY, "1");

    let invoices;
    try {
      invoices = await Api.invoices.pendingClosure();
    } catch (err) {
      // Aviso de conveniência — não pode quebrar o carregamento do app.
      console.warn("Falha ao checar faturas pendentes de fechamento:", err);
      return;
    }

    if (!invoices || invoices.length === 0) return;

    let cardNameById = {};
    try {
      const cards = await Api.creditCards.list();
      cardNameById = Object.fromEntries(cards.map((c) => [String(c.id), c.name]));
    } catch (err) {
      console.warn("Falha ao carregar cartões para o aviso de fatura pendente:", err);
    }

    showModal(invoices, cardNameById);
  }

  function showModal(invoices, cardNameById) {
    const remaining = invoices.slice();
    const rowsById = {};

    const listEl = UI.el("div", { class: "list" });

    function cardLabel(invoice) {
      return cardNameById[String(invoice.credit_card_id)] || `Cartão #${invoice.credit_card_id}`;
    }

    function finishIfEmpty() {
      if (remaining.length === 0) UI.closeModal();
    }

    async function closeOne(invoice, btn) {
      btn.disabled = true;
      try {
        await Api.invoices.close(invoice.id);
        UI.toast(`Fatura de ${cardLabel(invoice)} fechada.`, "success");
        const row = rowsById[invoice.id];
        if (row) row.remove();
        const idx = remaining.findIndex((i) => i.id === invoice.id);
        if (idx !== -1) remaining.splice(idx, 1);
        finishIfEmpty();
      } catch (err) {
        // Ex.: outra aba já fechou essa fatura nesse meio-tempo (ConflictError)
        // — mantém o item na lista pro usuário tentar de novo ou descartar.
        UI.showApiError(err);
        btn.disabled = false;
      }
    }

    function buildRow(invoice) {
      const confirmBtn = UI.el(
        "button",
        { class: "btn btn--primary btn--sm" },
        "Confirmar fechamento"
      );
      confirmBtn.addEventListener("click", () => closeOne(invoice, confirmBtn));

      const row = UI.el("div", { class: "list-item" }, [
        UI.el("div", { class: "list-item__main" }, [
          UI.el("div", { class: "list-item__title" }, cardLabel(invoice)),
          UI.el(
            "div",
            { class: "list-item__subtitle" },
            `Fechou em ${UI.dateBR(invoice.closing_date)}`
          ),
        ]),
        UI.el("div", { class: "list-item__value" }, UI.money(invoice.total_amount)),
        UI.el("div", { class: "list-item__actions" }, [confirmBtn]),
      ]);
      rowsById[invoice.id] = row;
      return row;
    }

    invoices.forEach((invoice) => listEl.appendChild(buildRow(invoice)));

    const actionsRow = UI.el("div", { class: "form-actions" }, [
      UI.el(
        "button",
        { class: "btn btn--secondary btn--sm", onclick: () => UI.closeModal() },
        "Lembrar depois"
      ),
    ]);

    if (invoices.length > 1) {
      const confirmAllBtn = UI.el(
        "button",
        { class: "btn btn--primary btn--sm" },
        "Confirmar todas"
      );
      confirmAllBtn.addEventListener("click", async () => {
        confirmAllBtn.disabled = true;
        // Em sequência (não em paralelo) pra não sobrecarregar o backend
        // nem arriscar race entre fechamentos concorrentes.
        for (const invoice of remaining.slice()) {
          const row = rowsById[invoice.id];
          const btn = row && UI.qs("button.btn--primary", row);
          if (!row || !row.isConnected || !btn) continue;
          await closeOne(invoice, btn);
        }
        if (confirmAllBtn.isConnected) confirmAllBtn.disabled = false;
      });
      actionsRow.prepend(confirmAllBtn);
    }

    const content = UI.el("div", { class: "pending-closure" }, [actionsRow, listEl]);
    UI.openModal("Faturas pendentes de fechamento", content);
  }

  return { checkOnce };
})();

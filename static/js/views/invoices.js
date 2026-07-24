/* Faturas de um cartão específico — fechar e pagar. */

const INVOICE_STATUS_LABELS = { open: "Aberta", closed: "Fechada", paid: "Paga" };

async function renderInvoicesView(container, params) {
  const cardId = Number(params.id);

  container.appendChild(UI.el("div", { class: "loading" }, "Carregando..."));

  let card;
  let invoices;
  try {
    [card, invoices] = await Promise.all([
      Api.creditCards.get(cardId),
      Api.invoices.list({ credit_card_id: cardId }),
    ]);
  } catch (err) {
    container.innerHTML = "";
    UI.showApiError(err);
    return;
  }

  async function refresh() {
    invoices = await Api.invoices.list({ credit_card_id: cardId });
    draw();
  }

  function draw() {
    container.innerHTML = "";
    container.appendChild(
      UI.el("div", { class: "page-header" }, [
        UI.el("h1", { class: "page-title" }, `Faturas — ${card.name}`),
        UI.el(
          "button",
          { class: "btn btn--secondary btn--sm", onclick: () => Router.navigate("/credit-cards") },
          "Voltar"
        ),
      ])
    );

    if (invoices.length === 0) {
      container.appendChild(
        UI.el("div", { class: "empty-state" }, [
          UI.el("div", { class: "empty-state__icon" }, "🧾"),
          UI.el("div", {}, "Nenhuma fatura gerada ainda para este cartão."),
        ])
      );
      return;
    }

    const list = UI.el("div", { class: "list" });
    invoices.forEach((inv) => {
      const actions = UI.el("div", { class: "list-item__actions" });

      if (inv.status === "open") {
        actions.appendChild(
          UI.el(
            "button",
            { class: "btn btn--secondary btn--sm", onclick: () => handleClose(inv) },
            "Fechar"
          )
        );
      } else if (inv.status === "closed") {
        actions.appendChild(
          UI.el(
            "button",
            { class: "btn btn--primary btn--sm", onclick: () => handlePay(inv) },
            "Pagar"
          )
        );
      }

      list.appendChild(
        UI.el("div", { class: "list-item" }, [
          UI.el("div", { class: "list-item__main" }, [
            UI.el("div", { class: "list-item__title" }, [
              `Referência ${UI.dateBR(inv.reference_month)} `,
              UI.el(
                "span",
                { class: `badge badge--${inv.status}` },
                INVOICE_STATUS_LABELS[inv.status]
              ),
            ]),
            UI.el(
              "div",
              { class: "list-item__subtitle" },
              `Fecha ${UI.dateBR(inv.closing_date)} · vence ${UI.dateBR(inv.due_date)}`
            ),
          ]),
          UI.el("div", { class: "list-item__value" }, UI.money(inv.total_amount)),
          actions.childNodes.length ? actions : null,
        ])
      );
    });
    container.appendChild(list);
  }

  async function handleClose(invoice) {
    const ok = await UI.confirmAction("Fechar esta fatura? Não será mais possível adicionar compras a ela.");
    if (!ok) return;
    try {
      await Api.invoices.close(invoice.id);
      UI.toast("Fatura fechada.", "success");
      refresh();
    } catch (err) {
      UI.showApiError(err);
    }
  }

  async function handlePay(invoice) {
    const accounts = await Api.accounts.list();
    if (accounts.length === 0) {
      UI.toast("Cadastre uma conta antes de pagar a fatura.", "error");
      return;
    }

    const form = UI.buildForm(
      [
        {
          name: "account_id",
          label: "Pagar com a conta",
          type: "select",
          required: true,
          options: accounts.map((a) => ({ value: a.id, label: a.name })),
        },
      ],
      {}
    );
    const errorBox = UI.el("div", { class: "form-error", style: "display:none" });
    form.appendChild(errorBox);
    form.appendChild(
      UI.el("div", { class: "form-actions" }, [
        UI.el(
          "button",
          { type: "button", class: "btn btn--secondary", onclick: () => UI.closeModal() },
          "Cancelar"
        ),
        UI.el("button", { type: "submit", class: "btn btn--primary" }, "Confirmar pagamento"),
      ])
    );

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const accountId = Number(UI.qs("select[name=account_id]", form).value);
      try {
        await Api.invoices.pay(invoice.id, accountId);
        UI.closeModal();
        UI.toast("Fatura paga com sucesso.", "success");
        refresh();
      } catch (err) {
        errorBox.textContent = err.message;
        errorBox.style.display = "block";
      }
    });

    UI.openModal(`Pagar fatura de ${UI.dateBR(invoice.reference_month)}`, form);
  }

  draw();
}

Router.register("/credit-cards/:id/invoices", renderInvoicesView);

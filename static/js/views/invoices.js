/* Faturas de um cartão específico — fechar, pagar (integral) e registrar
   pagamentos parciais mesmo com a fatura ainda aberta. */

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
          UI.el("div", { class: "empty-state__icon" }, UI.icon("receipt")),
          UI.el("div", {}, "Nenhuma fatura gerada ainda para este cartão."),
        ])
      );
      return;
    }

    const list = UI.el("div", { class: "list" });
    invoices.forEach((inv) => {
      const remaining = Number(inv.total_amount) - Number(inv.paid_amount);
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
            { class: "btn btn--primary btn--sm", onclick: () => handlePayInFull(inv) },
            "Pagar tudo"
          )
        );
      }

      if (inv.status !== "paid" && remaining > 0) {
        actions.appendChild(
          UI.el(
            "button",
            { class: "btn btn--secondary btn--sm", onclick: () => handleRegisterPayment(inv) },
            "Registrar pagamento"
          )
        );
      }

      const subtitleParts = [`Fecha ${UI.dateBR(inv.closing_date)} · vence ${UI.dateBR(inv.due_date)}`];
      if (Number(inv.paid_amount) > 0) {
        subtitleParts.push(
          `Pago: ${UI.money(inv.paid_amount)} de ${UI.money(inv.total_amount)}` +
            (remaining > 0 ? ` (restam ${UI.money(remaining)})` : "")
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
            UI.el("div", { class: "list-item__subtitle" }, subtitleParts.join(" · ")),
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

  async function handlePayInFull(invoice) {
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

    const remaining = Number(invoice.total_amount) - Number(invoice.paid_amount);
    UI.openModal(
      `Pagar ${UI.money(remaining)} — fatura de ${UI.dateBR(invoice.reference_month)}`,
      form
    );
  }

  async function handleRegisterPayment(invoice) {
    const accounts = await Api.accounts.list();
    if (accounts.length === 0) {
      UI.toast("Cadastre uma conta antes de registrar um pagamento.", "error");
      return;
    }

    const remaining = Number(invoice.total_amount) - Number(invoice.paid_amount);
    const fields = [
      {
        name: "account_id",
        label: "Pagar com a conta",
        type: "select",
        required: true,
        options: accounts.map((a) => ({ value: a.id, label: a.name })),
      },
      {
        name: "amount",
        label: `Valor (R$) — saldo devedor: ${UI.money(remaining)}`,
        type: "number",
        step: "0.01",
        min: "0.01",
        max: String(remaining),
        required: true,
      },
    ];
    const form = UI.buildForm(fields, {});
    const errorBox = UI.el("div", { class: "form-error", style: "display:none" });
    form.appendChild(errorBox);
    form.appendChild(
      UI.el("div", { class: "form-actions" }, [
        UI.el(
          "button",
          { type: "button", class: "btn btn--secondary", onclick: () => UI.closeModal() },
          "Cancelar"
        ),
        UI.el("button", { type: "submit", class: "btn btn--primary" }, "Registrar"),
      ])
    );

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const values = UI.formValues(form, fields);
      try {
        await Api.invoices.registerPayment(invoice.id, Number(values.account_id), values.amount);
        UI.closeModal();
        UI.toast("Pagamento registrado.", "success");
        refresh();
      } catch (err) {
        errorBox.textContent = err.message;
        errorBox.style.display = "block";
      }
    });

    UI.openModal(`Registrar pagamento — fatura de ${UI.dateBR(invoice.reference_month)}`, form);
  }

  draw();
}

Router.register("/credit-cards/:id/invoices", renderInvoicesView);

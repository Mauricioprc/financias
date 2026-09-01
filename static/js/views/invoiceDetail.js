/* Detalhe de uma fatura: dados, resumo por categoria e transações
   (GET /invoices/{id}/detail). Tela de leitura — as ações de
   fechar/pagar/registrar pagamento continuam na lista de faturas
   (invoices.js), não duplicadas aqui. */

function emptyStateInvoiceDetail(text) {
  return UI.el("div", { class: "empty-state" }, [
    UI.el("div", { class: "empty-state__icon" }, UI.icon("receipt")),
    UI.el("div", {}, text),
  ]);
}

function invoiceDetailTile(label, value) {
  return UI.el("div", { class: "tile" }, [
    UI.el("div", { class: "tile__label" }, label),
    UI.el("div", { class: "tile__value" }, UI.money(value)),
  ]);
}

function categorySummaryRow(item, invoiceTotal) {
  const total = Number(invoiceTotal) || 0;
  const pct = total > 0 ? Math.round((Number(item.total_amount) / total) * 100) : 0;
  return UI.el("div", { class: "list-item list-item--stacked" }, [
    UI.el("div", { class: "list-item__row" }, [
      UI.el("div", { class: "list-item__main" }, [
        UI.el("div", { class: "list-item__title" }, item.category_name),
      ]),
      UI.el("div", { class: "list-item__value" }, UI.money(item.total_amount)),
    ]),
    // progressBar já existe em crud.js — reaproveitada aqui em vez de um
    // componente novo (mesma barra usada no limite usado do cartão).
    progressBar({ pct }),
  ]);
}

function invoiceDetailTransactionItem(t, categoryNameById) {
  const subtitleParts = [
    UI.dateBR(t.date),
    t.category_id ? categoryNameById[String(t.category_id)] : null,
    // Mesmo padrão de exibição de parcela usado em transactions.js
    // (t.installment_total > 1 ? "(X/Y)" : ...).
    t.installment_total ? `Parcela ${t.installment_number}/${t.installment_total}` : null,
    t.is_paid ? null : "pendente",
  ].filter(Boolean);

  return UI.el("div", { class: "list-item" }, [
    UI.el("div", { class: "list-item__main" }, [
      UI.el("div", { class: "list-item__title" }, t.description),
      UI.el("div", { class: "list-item__subtitle" }, subtitleParts.join(" · ")),
    ]),
    UI.el("div", { class: "list-item__value value--negative" }, "- " + UI.money(t.amount)),
  ]);
}

async function renderInvoiceDetailView(container, params) {
  const invoiceId = Number(params.id);
  container.appendChild(UI.el("div", { class: "loading" }, "Carregando..."));

  let detail;
  try {
    detail = await Api.invoices.detail(invoiceId);
  } catch (err) {
    container.innerHTML = "";
    UI.showApiError(err);
    return;
  }
  container.innerHTML = "";

  const { invoice, remaining, transactions, category_summary } = detail;

  // Nomes de categoria já vêm no resumo — evita uma chamada extra a
  // Api.categories.list() só pra rotular as transações.
  const categoryNameById = Object.fromEntries(
    category_summary
      .filter((c) => c.category_id !== null)
      .map((c) => [String(c.category_id), c.category_name])
  );

  container.appendChild(
    UI.el("div", { class: "page-header" }, [
      UI.el("h1", { class: "page-title" }, [
        `Fatura de ${UI.dateBR(invoice.reference_month)} `,
        UI.el(
          "span",
          { class: `badge badge--${invoice.status}` },
          INVOICE_STATUS_LABELS[invoice.status]
        ),
      ]),
      UI.el(
        "button",
        {
          class: "btn btn--secondary btn--sm",
          onclick: () => Router.navigate(`/credit-cards/${invoice.credit_card_id}/invoices`),
        },
        "Voltar"
      ),
    ])
  );

  container.appendChild(
    UI.el(
      "div",
      { class: "list-item__subtitle", style: "margin-bottom:12px" },
      `Fecha ${UI.dateBR(invoice.closing_date)} · vence ${UI.dateBR(invoice.due_date)}`
    )
  );

  container.appendChild(
    UI.el("div", { class: "tiles" }, [
      invoiceDetailTile("Total", invoice.total_amount),
      invoiceDetailTile("Pago", invoice.paid_amount),
      invoiceDetailTile("Restante", remaining),
    ])
  );

  container.appendChild(UI.el("div", { class: "section-title" }, "Resumo por categoria"));
  if (category_summary.length === 0) {
    container.appendChild(emptyStateInvoiceDetail("Nenhuma compra nesta fatura ainda."));
  } else {
    const catList = UI.el("div", { class: "list" });
    category_summary.forEach((item) =>
      catList.appendChild(categorySummaryRow(item, invoice.total_amount))
    );
    container.appendChild(catList);
  }

  container.appendChild(UI.el("div", { class: "section-title" }, "Transações"));
  if (transactions.length === 0) {
    container.appendChild(emptyStateInvoiceDetail("Nenhuma transação nesta fatura ainda."));
  } else {
    const txList = UI.el("div", { class: "list" });
    transactions.forEach((t) =>
      txList.appendChild(invoiceDetailTransactionItem(t, categoryNameById))
    );
    container.appendChild(txList);
  }
}

Router.register("/invoices/:id/detail", renderInvoiceDetailView);

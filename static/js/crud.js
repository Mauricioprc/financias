/* Helper genérico para telas de CRUD simples (lista + criar + editar + excluir).
   renderItem devolve {title, subtitle, value, valueClass, progress, extra} —
   `extra` é um nó DOM opcional (ou null) anexado depois da barra de
   progresso, pra conteúdo extra dentro do item que não caiba no layout
   título/subtítulo/valor padrão (ex.: mini-tiles em creditCards.js). */

/* Barra de progresso opcional para um item de lista — info.progress = { pct, className }. */
function progressBar(progress) {
  const pct = Math.max(0, Math.min(100, progress.pct));
  return UI.el("div", { class: "progress-bar" }, [
    UI.el("div", {
      class: `progress-bar__fill ${progress.className || ""}`,
      style: `width:${pct}%`,
    }),
  ]);
}

function mountCrudView(container, config) {
  const {
    title,
    icon = "receipt",
    emptyText = "Nada por aqui ainda.",
    fields,
    editFields,
    loadItems,
    createItem,
    updateItem,
    removeItem,
    renderItem,
    extraRowActions,
    extraHeaderActions,
    transformSubmit = (v) => v,
  } = config;

  async function refresh() {
    container.innerHTML = "";
    const headerActions = [
      createItem
        ? UI.el(
            "button",
            { class: "btn btn--primary btn--sm", onclick: () => openCreateModal() },
            "+ Novo"
          )
        : null,
    ].concat(extraHeaderActions ? extraHeaderActions(refresh) : []);
    container.appendChild(
      UI.el("div", { class: "page-header" }, [
        UI.el("h1", { class: "page-title" }, title),
        UI.el("div", { class: "page-header__actions" }, headerActions),
      ])
    );

    const loadingNode = UI.el("div", { class: "loading" }, "Carregando...");
    container.appendChild(loadingNode);

    let items;
    try {
      items = await loadItems();
    } catch (err) {
      loadingNode.remove();
      UI.showApiError(err);
      return;
    }
    loadingNode.remove();

    if (items.length === 0) {
      container.appendChild(
        UI.el("div", { class: "empty-state" }, [
          UI.el("div", { class: "empty-state__icon" }, UI.icon(icon)),
          UI.el("div", {}, emptyText),
        ])
      );
      return;
    }

    const list = UI.el("div", { class: "list" });
    items.forEach((item) => {
      const info = renderItem(item);
      const actions = UI.el("div", { class: "list-item__actions" });

      if (extraRowActions) {
        extraRowActions(item, refresh).forEach((btn) => actions.appendChild(btn));
      }
      if (updateItem) {
        actions.appendChild(
          UI.el(
            "button",
            {
              class: "btn btn--secondary btn--sm",
              onclick: () => openEditModal(item),
            },
            "Editar"
          )
        );
      }
      if (removeItem) {
        actions.appendChild(
          UI.el(
            "button",
            {
              class: "btn btn--danger btn--sm",
              onclick: () => handleRemove(item),
            },
            "Excluir"
          )
        );
      }

      const row = UI.el("div", { class: "list-item__row" }, [
        UI.el("div", { class: "list-item__main" }, [
          UI.el("div", { class: "list-item__title" }, info.title),
          info.subtitle ? UI.el("div", { class: "list-item__subtitle" }, info.subtitle) : null,
        ]),
        info.value
          ? UI.el("div", { class: `list-item__value ${info.valueClass || ""}` }, info.value)
          : null,
        actions.childNodes.length ? actions : null,
      ]);

      list.appendChild(
        UI.el(
          "div",
          { class: "list-item" + (info.progress || info.extra ? " list-item--stacked" : "") },
          [row, info.progress ? progressBar(info.progress) : null, info.extra || null]
        )
      );
    });
    container.appendChild(list);
  }

  async function handleRemove(item) {
    const ok = await UI.confirmAction("Tem certeza que deseja excluir este item?");
    if (!ok) return;
    try {
      await removeItem(item.id);
      UI.toast("Excluído com sucesso.", "success");
      refresh();
    } catch (err) {
      UI.showApiError(err);
    }
  }

  function openCreateModal() {
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
        UI.el("button", { type: "submit", class: "btn btn--primary" }, "Salvar"),
      ])
    );

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = transformSubmit(UI.formValues(form, fields));
      try {
        await createItem(data);
        UI.closeModal();
        UI.toast("Criado com sucesso.", "success");
        refresh();
      } catch (err) {
        errorBox.textContent = err.message;
        errorBox.style.display = "block";
      }
    });

    UI.openModal(`Novo — ${title}`, form);
  }

  function openEditModal(item) {
    const usedFields = editFields || fields;
    const form = UI.buildForm(usedFields, item);
    const errorBox = UI.el("div", { class: "form-error", style: "display:none" });
    form.appendChild(errorBox);
    form.appendChild(
      UI.el("div", { class: "form-actions" }, [
        UI.el(
          "button",
          { type: "button", class: "btn btn--secondary", onclick: () => UI.closeModal() },
          "Cancelar"
        ),
        UI.el("button", { type: "submit", class: "btn btn--primary" }, "Salvar"),
      ])
    );

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = transformSubmit(UI.formValues(form, usedFields));
      try {
        await updateItem(item.id, data);
        UI.closeModal();
        UI.toast("Atualizado com sucesso.", "success");
        refresh();
      } catch (err) {
        errorBox.textContent = err.message;
        errorBox.style.display = "block";
      }
    });

    UI.openModal(`Editar — ${title}`, form);
  }

  refresh();
}

/* Metas financeiras. */

const GOAL_STATUS_LABELS = { in_progress: "Em andamento", achieved: "Concluída", abandoned: "Abandonada" };

function renderGoalsView(container) {
  mountCrudView(container, {
    title: "Metas",
    icon: "target",
    emptyText: "Cadastre sua primeira meta financeira.",
    fields: [
      { name: "name", label: "Nome", required: true },
      { name: "target_amount", label: "Valor alvo (R$)", type: "number", step: "0.01", required: true },
      { name: "target_date", label: "Data alvo (opcional)", type: "date" },
    ],
    editFields: [
      { name: "name", label: "Nome", required: true },
      { name: "target_amount", label: "Valor alvo (R$)", type: "number", step: "0.01" },
      { name: "target_date", label: "Data alvo (opcional)", type: "date" },
      {
        name: "status",
        label: "Status",
        type: "select",
        options: Object.entries(GOAL_STATUS_LABELS).map(([value, label]) => ({ value, label })),
      },
    ],
    loadItems: async () => {
      const goals = await Api.goals.list();
      const projections = await Promise.all(
        goals.map((g) =>
          g.status === "in_progress" ? Api.insights.goalProjection(g.id).catch(() => null) : null
        )
      );
      return goals.map((g, i) => ({ ...g, projection: projections[i] }));
    },
    createItem: (data) => Api.goals.create(data),
    updateItem: (id, data) => Api.goals.update(id, data),
    removeItem: (id) => Api.goals.remove(id),
    renderItem: (g) => {
      const pct = Math.min(100, Math.round((Number(g.current_amount) / Number(g.target_amount)) * 100));
      const subtitleParts = [
        `${UI.money(g.current_amount)} de ${UI.money(g.target_amount)} (${pct}%)`,
        GOAL_STATUS_LABELS[g.status],
      ];

      const titleChildren = [g.name];
      const projection = g.projection;
      if (projection && projection.projected_completion_date) {
        const [year, month] = projection.projected_completion_date.split("-");
        subtitleParts.push(`previsão: ${month}/${year} (estimativa)`);
        // Mesmo padrão de badge de alerta usado na Home (anomalias de
        // categoria) — vermelho quando a projeção passa da data alvo.
        if (projection.on_track === false) {
          titleChildren.push(" ", UI.el("span", { class: "badge badge--expense" }, "Fora do prazo"));
        }
      }

      return {
        title: titleChildren,
        subtitle: subtitleParts.join(" · "),
        value: null,
        progress: g.status === "in_progress" ? { pct } : null,
      };
    },
    extraRowActions: (item, refresh) =>
      item.status === "in_progress"
        ? [
            UI.el(
              "button",
              {
                class: "btn btn--primary btn--sm",
                onclick: () => handleContribute(item, refresh),
              },
              "Contribuir"
            ),
          ]
        : [],
  });

  async function handleContribute(item, refresh) {
    const form = UI.buildForm(
      [{ name: "amount", label: "Valor da contribuição (R$)", type: "number", step: "0.01", required: true }],
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
        UI.el("button", { type: "submit", class: "btn btn--primary" }, "Contribuir"),
      ])
    );

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const amount = Number(UI.qs("input[name=amount]", form).value);
      try {
        await Api.goals.contribute(item.id, amount);
        UI.closeModal();
        UI.toast("Contribuição registrada.", "success");
        refresh();
      } catch (err) {
        errorBox.textContent = err.message;
        errorBox.style.display = "block";
      }
    });

    UI.openModal(`Contribuir — ${item.name}`, form);
  }
}

Router.register("/goals", renderGoalsView);

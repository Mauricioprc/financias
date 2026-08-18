/* Perfil — dados da conta e vínculo do número de WhatsApp com o bot. */

async function renderProfileView(container) {
  container.appendChild(UI.el("div", { class: "loading" }, "Carregando..."));

  let user;
  try {
    user = await Api.me();
  } catch (err) {
    container.innerHTML = "";
    UI.showApiError(err);
    return;
  }

  container.innerHTML = "";
  container.appendChild(UI.el("h1", { class: "page-title" }, "Perfil"));

  container.appendChild(
    UI.el("div", { class: "card" }, [
      UI.el("div", { class: "section-title", style: "margin-top:0" }, "Conta"),
      UI.el("div", { class: "list" }, [
        UI.el("div", { class: "list-item" }, [
          UI.el("div", { class: "list-item__main" }, [
            UI.el("div", { class: "list-item__title" }, user.name),
            UI.el("div", { class: "list-item__subtitle" }, user.email),
          ]),
        ]),
      ]),
    ])
  );

  const form = UI.buildForm(
    [
      {
        name: "phone_number",
        label: "WhatsApp (formato internacional, ex.: +5511999999999)",
        placeholder: "+5511999999999",
      },
    ],
    { phone_number: user.phone_number || "" }
  );
  const errorBox = UI.el("div", { class: "form-error", style: "display:none" });
  const helpText = UI.el(
    "div",
    { class: "list-item__subtitle", style: "margin: -6px 0 14px" },
    "Vincule seu número para usar o bot do MR Gestão pelo WhatsApp. Deixe em branco para desvincular."
  );
  form.insertBefore(helpText, form.firstChild);
  form.appendChild(errorBox);
  form.appendChild(
    UI.el(
      "button",
      { type: "submit", class: "btn btn--primary" },
      "Salvar"
    )
  );

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorBox.style.display = "none";
    const values = UI.formValues(form, [{ name: "phone_number" }]);
    const phoneNumber = values.phone_number ? values.phone_number.trim() : null;
    try {
      await Api.users.updateProfile({ phone_number: phoneNumber });
      UI.toast("Perfil atualizado.", "success");
    } catch (err) {
      errorBox.textContent = err.message;
      errorBox.style.display = "block";
    }
  });

  container.appendChild(
    UI.el("div", { class: "card" }, [
      UI.el("div", { class: "section-title", style: "margin-top:0" }, "Bot do WhatsApp"),
      form,
    ])
  );
}

Router.register("/profile", renderProfileView);

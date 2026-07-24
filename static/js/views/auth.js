/* Login e registro. */

function renderAuthScreen(container, { mode }) {
  const isLogin = mode === "login";

  const screen = UI.el("div", { class: "auth-screen" }, [
    UI.el("div", { class: "auth-card" }, [
      UI.el("img", { src: "/img/LogoMRrosto.png", class: "auth-card__logo" }),
      UI.el("div", { class: "auth-card__brand" }, "MR Gestão"),
      UI.el(
        "div",
        { class: "auth-card__tagline" },
        "Organização e controle para sua vida financeira"
      ),
      isLogin ? renderLoginForm() : renderRegisterForm(),
      UI.el("div", { class: "auth-card__switch" }, [
        isLogin ? "Ainda não tem conta? " : "Já tem conta? ",
        UI.el(
          "button",
          {
            type: "button",
            onclick: () => Router.navigate(isLogin ? "/register" : "/login"),
          },
          isLogin ? "Criar conta" : "Entrar"
        ),
      ]),
    ]),
  ]);

  container.appendChild(screen);
}

function renderLoginForm() {
  const form = UI.el("form", {}, [
    UI.el("div", { class: "form-field" }, [
      UI.el("label", { for: "login-email" }, "Email"),
      UI.el("input", { type: "email", id: "login-email", name: "email", required: true }),
    ]),
    UI.el("div", { class: "form-field" }, [
      UI.el("label", { for: "login-password" }, "Senha"),
      UI.el("input", {
        type: "password",
        id: "login-password",
        name: "password",
        required: true,
      }),
    ]),
    UI.el("button", { type: "submit", class: "btn btn--primary btn--block" }, "Entrar"),
  ]);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = UI.qs("#login-email", form).value.trim();
    const password = UI.qs("#login-password", form).value;
    const submitBtn = UI.qs("button[type=submit]", form);
    submitBtn.disabled = true;
    try {
      await Api.login(email, password);
      Router.navigate("/");
    } catch (err) {
      UI.showApiError(err);
    } finally {
      submitBtn.disabled = false;
    }
  });

  return form;
}

function renderRegisterForm() {
  const form = UI.el("form", {}, [
    UI.el("div", { class: "form-field" }, [
      UI.el("label", { for: "reg-name" }, "Nome"),
      UI.el("input", { type: "text", id: "reg-name", name: "name", required: true }),
    ]),
    UI.el("div", { class: "form-field" }, [
      UI.el("label", { for: "reg-email" }, "Email"),
      UI.el("input", { type: "email", id: "reg-email", name: "email", required: true }),
    ]),
    UI.el("div", { class: "form-field" }, [
      UI.el("label", { for: "reg-password" }, "Senha"),
      UI.el("input", {
        type: "password",
        id: "reg-password",
        name: "password",
        minlength: 8,
        required: true,
      }),
    ]),
    UI.el("button", { type: "submit", class: "btn btn--primary btn--block" }, "Criar conta"),
  ]);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = UI.qs("#reg-name", form).value.trim();
    const email = UI.qs("#reg-email", form).value.trim();
    const password = UI.qs("#reg-password", form).value;
    const submitBtn = UI.qs("button[type=submit]", form);
    submitBtn.disabled = true;
    try {
      await Api.register(name, email, password);
      Router.navigate("/");
    } catch (err) {
      UI.showApiError(err);
    } finally {
      submitBtn.disabled = false;
    }
  });

  return form;
}

Router.register("/login", (container) => renderAuthScreen(container, { mode: "login" }));
Router.register("/register", (container) => renderAuthScreen(container, { mode: "register" }));

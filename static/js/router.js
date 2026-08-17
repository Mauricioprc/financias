/* Router baseado em hash — cada view registra uma função render(container, params). */

const Router = (() => {
  const routes = [];
  const PUBLIC_ROUTES = ["/login", "/register"];

  function register(pattern, render) {
    const paramNames = [];
    const regex = new RegExp(
      "^" +
        pattern.replace(/:[^/]+/g, (m) => {
          paramNames.push(m.slice(1));
          return "([^/]+)";
        }) +
        "$"
    );
    routes.push({ pattern, regex, paramNames, render });
  }

  function currentPath() {
    const hash = window.location.hash.replace(/^#/, "");
    return hash || "/";
  }

  function navigate(path) {
    if (window.location.hash === `#${path}`) {
      resolve();
    } else {
      window.location.hash = path;
    }
  }

  function matchRoute(path) {
    for (const route of routes) {
      const match = path.match(route.regex);
      if (match) {
        const params = {};
        route.paramNames.forEach((name, idx) => {
          params[name] = match[idx + 1];
        });
        return { route, params };
      }
    }
    return null;
  }

  async function resolve() {
    const path = currentPath();
    const authed = Api.isAuthenticated();
    const isPublic = PUBLIC_ROUTES.includes(path);

    if (!authed && !isPublic) {
      window.location.hash = "#/login";
      return;
    }
    if (authed && isPublic) {
      window.location.hash = "#/";
      return;
    }

    document.dispatchEvent(new CustomEvent("route:change", { detail: { path } }));

    const container = UI.qs("#app");
    const matched = matchRoute(path);

    if (!matched) {
      container.innerHTML = "";
      container.appendChild(
        UI.el("div", { class: "empty-state" }, [
          UI.el("div", { class: "empty-state__icon" }, UI.icon("circle-help")),
          UI.el("div", {}, "Página não encontrada."),
        ])
      );
      return;
    }

    container.innerHTML = "";
    try {
      await matched.route.render(container, matched.params);
    } catch (err) {
      UI.showApiError(err);
    }
  }

  function init() {
    window.addEventListener("hashchange", resolve);
    resolve();
  }

  return { register, navigate, init, currentPath };
})();

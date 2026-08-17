/* Bootstrap do app: monta header, navegação (bottom-nav mobile / sidebar desktop) e router. */

const NAV_ITEMS = [
  { path: "/", icon: "house", label: "Início", primary: true },
  { path: "/transactions", icon: "arrow-left-right", label: "Transações", primary: true },
  { path: "/accounts", icon: "landmark", label: "Contas", primary: true },
  { path: "/credit-cards", icon: "credit-card", label: "Cartões", primary: true },
  { path: "/reports", icon: "bar-chart-3", label: "Relatórios" },
  { path: "/transfers", icon: "arrow-left-right", label: "Transferências" },
  { path: "/categories", icon: "tag", label: "Categorias" },
  { path: "/recurring", icon: "refresh-cw", label: "Recorrências" },
  { path: "/goals", icon: "target", label: "Metas" },
  { path: "/investments", icon: "trending-up", label: "Investimentos" },
];

function isRoutePrefixOf(currentPath, itemPath) {
  if (itemPath === "/") return currentPath === "/";
  return currentPath === itemPath || currentPath.startsWith(itemPath + "/");
}

function buildBottomNav() {
  const nav = UI.qs("#bottom-nav");
  nav.innerHTML = "";

  NAV_ITEMS.filter((i) => i.primary).forEach((item) => {
    nav.appendChild(
      UI.el(
        "button",
        {
          class: "bottom-nav__item",
          "data-path": item.path,
          onclick: () => Router.navigate(item.path),
        },
        [UI.icon(item.icon), item.label]
      )
    );
  });

  nav.appendChild(
    UI.el(
      "button",
      { class: "bottom-nav__item", "data-path": "__more__", onclick: () => openMoreSheet() },
      [UI.icon("more-horizontal"), "Mais"]
    )
  );
}

function buildSidebar() {
  const sidebar = UI.qs("#sidebar");
  sidebar.innerHTML = "";

  NAV_ITEMS.forEach((item) => {
    sidebar.appendChild(
      UI.el(
        "button",
        { class: "sidebar__item", "data-path": item.path, onclick: () => Router.navigate(item.path) },
        [UI.icon(item.icon), item.label]
      )
    );
  });

  sidebar.appendChild(UI.el("div", { class: "sidebar__divider" }));
  sidebar.appendChild(
    UI.el(
      "button",
      { class: "sidebar__item", onclick: () => handleLogout() },
      [UI.icon("log-out"), "Sair"]
    )
  );
}

function openMoreSheet() {
  const overlay = UI.qs("#sheet-overlay");
  const sheet = UI.qs("#sheet");
  sheet.innerHTML = "";
  sheet.appendChild(UI.el("div", { class: "sheet__handle" }));

  NAV_ITEMS.filter((i) => !i.primary).forEach((item) => {
    sheet.appendChild(
      UI.el(
        "button",
        {
          class: "sheet__item",
          onclick: () => {
            closeMoreSheet();
            Router.navigate(item.path);
          },
        },
        [UI.icon(item.icon), item.label]
      )
    );
  });

  sheet.appendChild(
    UI.el(
      "button",
      {
        class: "sheet__item sheet__item--danger",
        onclick: () => {
          closeMoreSheet();
          handleLogout();
        },
      },
      [UI.icon("log-out"), "Sair"]
    )
  );

  overlay.hidden = false;
  sheet.hidden = false;
  overlay.onclick = closeMoreSheet;
}

function closeMoreSheet() {
  UI.qs("#sheet-overlay").hidden = true;
  UI.qs("#sheet").hidden = true;
}

function handleLogout() {
  Api.logout();
  Router.navigate("/login");
}

function updateActiveNav(path) {
  UI.qsa(".bottom-nav__item").forEach((btn) => {
    btn.classList.toggle("is-active", isRoutePrefixOf(path, btn.dataset.path));
  });
  UI.qsa(".sidebar__item").forEach((btn) => {
    if (!btn.dataset.path) return;
    btn.classList.toggle("is-active", isRoutePrefixOf(path, btn.dataset.path));
  });
}

function updateChrome(path) {
  const isAuthScreen = path === "/login" || path === "/register";
  const authed = Api.isAuthenticated();
  const showChrome = authed && !isAuthScreen;

  UI.qs("#app-header").hidden = !showChrome;
  UI.qs("#bottom-nav").hidden = !showChrome;
  UI.qs("#sidebar").hidden = !showChrome;
  closeMoreSheet();

  if (showChrome) updateActiveNav(path);
}

document.addEventListener("route:change", (e) => updateChrome(e.detail.path));

UI.qs("#btn-logout").addEventListener("click", handleLogout);

buildBottomNav();
buildSidebar();
Router.init();

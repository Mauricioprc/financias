/* Tema compartilhado para os gráficos (Chart.js) — lê as cores direto das variáveis
   CSS do tema escuro, então os gráficos acompanham a paleta em style.css sem duplicar cores aqui. */

const ChartTheme = (() => {
  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function palette() {
    return {
      accent: cssVar("--accent"),
      accentDark: cssVar("--accent-dark"),
      navy: cssVar("--navy"),
      navyLight: cssVar("--navy-light"),
      success: cssVar("--success"),
      danger: cssVar("--danger"),
      warning: cssVar("--warning"),
      text: cssVar("--text"),
      textSecondary: cssVar("--text-secondary"),
      border: cssVar("--border"),
      /* Paleta categórica: começa nas cores de marca/acento e completa com tons
         adicionais para telas com muitas categorias. */
      categorical: [
        cssVar("--accent"),
        cssVar("--navy-light"),
        cssVar("--success"),
        cssVar("--warning"),
        cssVar("--danger"),
        "#a78bfa",
        "#f472b6",
        "#818cf8",
      ],
    };
  }

  /* Aplica os defaults globais do Chart.js (fonte, cor de texto) — chamar uma vez
     antes de instanciar qualquer gráfico na tela. */
  function applyDefaults() {
    const p = palette();
    Chart.defaults.font.family = "Inter, -apple-system, sans-serif";
    Chart.defaults.color = p.textSecondary;
    Chart.defaults.borderColor = p.border;
    return p;
  }

  return { cssVar, palette, applyDefaults };
})();

/* Helpers de DOM, formatação e componentes de UI reutilizáveis (toast, modal, confirm). */

const UI = (() => {
  function qs(selector, parent = document) {
    return parent.querySelector(selector);
  }

  function qsa(selector, parent = document) {
    return Array.from(parent.querySelectorAll(selector));
  }

  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([key, value]) => {
      if (key === "class") node.className = value;
      else if (key === "html") node.innerHTML = value;
      else if (key.startsWith("on") && typeof value === "function") {
        node.addEventListener(key.slice(2).toLowerCase(), value);
      } else if (value !== undefined && value !== null && value !== false) {
        node.setAttribute(key, value === true ? "" : value);
      }
    });
    (Array.isArray(children) ? children : [children]).forEach((child) => {
      if (child === null || child === undefined || child === false) return;
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    });
    return node;
  }

  /* Ícone SVG inline (Lucide). `name` deve existir em ICONS (static/js/icons.js). */
  function icon(name, attrs = {}) {
    const markup = (typeof ICONS !== "undefined" && ICONS[name]) || "";
    const svg = el(
      "span",
      { class: ["icon", attrs.class].filter(Boolean).join(" ") },
      []
    );
    svg.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${markup}</svg>`;
    return svg;
  }

  function money(value) {
    const n = Number(value || 0);
    return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  }

  function dateBR(value) {
    if (!value) return "";
    const [y, m, d] = String(value).slice(0, 10).split("-");
    return `${d}/${m}/${y}`;
  }

  function todayISO() {
    return new Date().toISOString().slice(0, 10);
  }

  function toast(message, type = "info") {
    const stack = qs("#toast-stack");
    const node = el("div", { class: `toast ${type === "error" ? "toast--error" : ""} ${type === "success" ? "toast--success" : ""}` }, message);
    stack.appendChild(node);
    setTimeout(() => node.remove(), 3200);
  }

  function showApiError(err) {
    const message = err && err.message ? err.message : "Algo deu errado. Tente novamente.";
    toast(message, "error");
  }

  async function confirmAction(message) {
    return window.confirm(message);
  }

  function openModal(titleText, contentNode) {
    let dialog = qs("#ui-modal");
    if (dialog) dialog.remove();

    dialog = el("dialog", { class: "modal", id: "ui-modal" }, [
      el("div", { class: "modal__inner" }, [
        el("div", { class: "modal__title" }, titleText),
        contentNode,
      ]),
    ]);
    document.body.appendChild(dialog);
    dialog.addEventListener("click", (e) => {
      const rect = dialog.getBoundingClientRect();
      const inside =
        e.clientX >= rect.left &&
        e.clientX <= rect.right &&
        e.clientY >= rect.top &&
        e.clientY <= rect.bottom;
      if (!inside) dialog.close();
    });
    dialog.showModal();
    return dialog;
  }

  function closeModal() {
    const dialog = qs("#ui-modal");
    if (dialog) dialog.close();
  }

  function buildForm(fields, values = {}) {
    const form = el("form", { class: "modal-form" });
    fields.forEach((field) => {
      if (field.type === "checkbox") {
        const wrap = el("div", { class: "checkbox-field" });
        const input = el("input", {
          type: "checkbox",
          name: field.name,
          id: `f-${field.name}`,
          checked: values[field.name] ? true : false,
        });
        wrap.appendChild(input);
        wrap.appendChild(el("label", { for: `f-${field.name}` }, field.label));
        form.appendChild(wrap);
        return;
      }

      const wrap = el("div", { class: "form-field" });
      wrap.appendChild(el("label", { for: `f-${field.name}` }, field.label));

      let input;
      if (field.type === "select") {
        input = el(
          "select",
          { name: field.name, id: `f-${field.name}`, required: field.required },
          field.options.map((opt) =>
            el(
              "option",
              {
                value: opt.value,
                selected: String(values[field.name]) === String(opt.value),
              },
              opt.label
            )
          )
        );
      } else if (field.type === "textarea") {
        input = el("textarea", {
          name: field.name,
          id: `f-${field.name}`,
          rows: 3,
        });
        input.value = values[field.name] || "";
      } else {
        input = el("input", {
          type: field.type || "text",
          name: field.name,
          id: `f-${field.name}`,
          step: field.step,
          min: field.min,
          max: field.max,
          placeholder: field.placeholder || "",
          required: field.required,
        });
        if (values[field.name] !== undefined && values[field.name] !== null) {
          input.value = values[field.name];
        }
      }
      wrap.appendChild(input);
      form.appendChild(wrap);
    });
    return form;
  }

  function formValues(form, fields) {
    const data = {};
    fields.forEach((field) => {
      const input = qs(`[name="${field.name}"]`, form);
      if (!input) return;
      if (field.type === "checkbox") {
        data[field.name] = input.checked;
      } else if (field.type === "number") {
        data[field.name] = input.value === "" ? null : Number(input.value);
      } else {
        data[field.name] = input.value === "" ? null : input.value;
      }
    });
    return data;
  }

  return {
    qs,
    qsa,
    el,
    icon,
    money,
    dateBR,
    todayISO,
    toast,
    showApiError,
    confirmAction,
    openModal,
    closeModal,
    buildForm,
    formValues,
  };
})();

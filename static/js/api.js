/* Cliente HTTP para a API /api/v1 — gerencia JWT (access + refresh) e erros padronizados. */

const Api = (() => {
  const BASE = "/api/v1";
  const ACCESS_KEY = "financias_access_token";
  const REFRESH_KEY = "financias_refresh_token";

  function getAccessToken() {
    return localStorage.getItem(ACCESS_KEY);
  }

  function getRefreshToken() {
    return localStorage.getItem(REFRESH_KEY);
  }

  function setTokens({ access_token, refresh_token }) {
    if (access_token) localStorage.setItem(ACCESS_KEY, access_token);
    if (refresh_token) localStorage.setItem(REFRESH_KEY, refresh_token);
  }

  function clearTokens() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  }

  function isAuthenticated() {
    return Boolean(getAccessToken());
  }

  class ApiError extends Error {
    constructor(message, code, status, details) {
      super(message);
      this.code = code;
      this.status = status;
      this.details = details || {};
    }
  }

  function buildQuery(params) {
    if (!params) return "";
    const usp = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        usp.append(key, value);
      }
    });
    const qs = usp.toString();
    return qs ? `?${qs}` : "";
  }

  async function refreshAccessToken() {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;

    try {
      const res = await fetch(`${BASE}/auth/refresh`, {
        method: "POST",
        headers: { Authorization: `Bearer ${refreshToken}` },
      });
      if (!res.ok) return false;
      const body = await res.json();
      setTokens({ access_token: body.data.access_token });
      return true;
    } catch (err) {
      return false;
    }
  }

  async function request(path, { method = "GET", body, auth = true, query, retry = true } = {}) {
    const headers = { "Content-Type": "application/json" };
    if (auth) {
      const token = getAccessToken();
      if (token) headers.Authorization = `Bearer ${token}`;
    }

    const res = await fetch(`${BASE}${path}${buildQuery(query)}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    if (res.status === 401 && auth && retry) {
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        return request(path, { method, body, auth, query, retry: false });
      }
      clearTokens();
      window.location.hash = "#/login";
      throw new ApiError("Sessão expirada. Faça login novamente.", "UNAUTHORIZED", 401);
    }

    if (res.status === 204) return null;

    let payload = null;
    try {
      payload = await res.json();
    } catch (err) {
      payload = null;
    }

    if (!res.ok) {
      const error = (payload && payload.error) || {};
      throw new ApiError(
        error.message || "Erro inesperado.",
        error.code || "UNKNOWN_ERROR",
        res.status,
        error.details
      );
    }

    return payload;
  }

  const get = (path, query) => request(path, { method: "GET", query });
  const post = (path, body, opts = {}) => request(path, { method: "POST", body, ...opts });
  const patch = (path, body) => request(path, { method: "PATCH", body });
  const del = (path) => request(path, { method: "DELETE" });

  return {
    ApiError,
    isAuthenticated,
    clearTokens,
    setTokens,

    async register(name, email, password) {
      const res = await post("/auth/register", { name, email, password }, { auth: false });
      setTokens(res.data);
      return res.data.user;
    },

    async login(email, password) {
      const res = await post("/auth/login", { email, password }, { auth: false });
      setTokens(res.data);
      return res.data.user;
    },

    logout() {
      clearTokens();
    },

    me: () => get("/auth/me").then((r) => r.data),

    users: {
      updateProfile: (data) => patch("/users/me", data).then((r) => r.data),
    },

    accounts: {
      list: () => get("/accounts").then((r) => r.data),
      get: (id) => get(`/accounts/${id}`).then((r) => r.data),
      create: (data) => post("/accounts", data).then((r) => r.data),
      update: (id, data) => patch(`/accounts/${id}`, data).then((r) => r.data),
      remove: (id) => del(`/accounts/${id}`),
    },

    categories: {
      list: () => get("/categories").then((r) => r.data),
      get: (id) => get(`/categories/${id}`).then((r) => r.data),
      create: (data) => post("/categories", data).then((r) => r.data),
      update: (id, data) => patch(`/categories/${id}`, data).then((r) => r.data),
      remove: (id) => del(`/categories/${id}`),
    },

    transactions: {
      list: (query) => get("/transactions", query).then((r) => r),
      get: (id) => get(`/transactions/${id}`).then((r) => r.data),
      create: (data) => post("/transactions", data).then((r) => r.data),
      createInstallmentPurchase: (data) =>
        post("/transactions/installment-purchases", data).then((r) => r.data),
      update: (id, data) => patch(`/transactions/${id}`, data).then((r) => r.data),
      remove: (id) => del(`/transactions/${id}`),
    },

    creditCards: {
      list: () => get("/credit-cards").then((r) => r.data),
      get: (id) => get(`/credit-cards/${id}`).then((r) => r.data),
      create: (data) => post("/credit-cards", data).then((r) => r.data),
      update: (id, data) => patch(`/credit-cards/${id}`, data).then((r) => r.data),
      remove: (id) => del(`/credit-cards/${id}`),
      currentInvoice: (id) => get(`/credit-cards/${id}/current-invoice`).then((r) => r.data),
    },

    invoices: {
      list: (query) => get("/invoices", query).then((r) => r.data),
      get: (id) => get(`/invoices/${id}`).then((r) => r.data),
      detail: (id) => get(`/invoices/${id}/detail`).then((r) => r.data),
      pendingClosure: () => get("/invoices/pending-closure").then((r) => r.data),
      close: (id) => post(`/invoices/${id}/close`).then((r) => r.data),
      pay: (id, accountId) =>
        post(`/invoices/${id}/pay`, { account_id: accountId }).then((r) => r.data),
      registerPayment: (id, accountId, amount) =>
        post(`/invoices/${id}/payments`, { account_id: accountId, amount }).then((r) => r.data),
    },

    transfers: {
      list: (query) => get("/transfers", query).then((r) => r.data),
      create: (data) => post("/transfers", data).then((r) => r.data),
      remove: (id) => del(`/transfers/${id}`),
    },

    recurring: {
      list: () => get("/recurring-transactions").then((r) => r.data),
      create: (data) => post("/recurring-transactions", data).then((r) => r.data),
      update: (id, data) => patch(`/recurring-transactions/${id}`, data).then((r) => r.data),
      remove: (id) => del(`/recurring-transactions/${id}`),
      generate: (id, until) =>
        post(`/recurring-transactions/${id}/generate${until ? `?until=${until}` : ""}`).then(
          (r) => r
        ),
      autoGenerate: () => post("/recurring-transactions/auto-generate").then((r) => r.data),
    },

    goals: {
      list: () => get("/goals").then((r) => r.data),
      create: (data) => post("/goals", data).then((r) => r.data),
      update: (id, data) => patch(`/goals/${id}`, data).then((r) => r.data),
      remove: (id) => del(`/goals/${id}`),
      contribute: (id, amount) => post(`/goals/${id}/contribute`, { amount }).then((r) => r.data),
    },

    investments: {
      list: () => get("/investments").then((r) => r.data),
      create: (data) => post("/investments", data).then((r) => r.data),
      update: (id, data) => patch(`/investments/${id}`, data).then((r) => r.data),
      remove: (id) => del(`/investments/${id}`),
    },

    insights: {
      summary: () => get("/insights/summary").then((r) => r.data),
      goalProjection: (goalId) => get(`/insights/goal-projection/${goalId}`).then((r) => r.data),
      balanceForecast: (accountId) =>
        get(`/insights/balance-forecast/${accountId}`).then((r) => r.data),
    },

    reports: {
      balanceHistory: (days) => get("/reports/balance-history", { days }).then((r) => r.data),
      categoryBreakdown: (month, type) =>
        get("/reports/category-breakdown", { month, type }).then((r) => r.data),
      incomeVsExpense: (months) =>
        get("/reports/income-vs-expense", { months }).then((r) => r.data),
    },
  };
})();

/* Shared admin helpers: token storage + authenticated fetch wrapper. */
const Admin = (function () {
  const KEY = "evision_admin_token";
  const EMAIL = "evision_admin_email";
  const ROLE = "evision_admin_role";
  const NAME = "evision_admin_name";

  function token() { return localStorage.getItem(KEY); }
  function email() { return localStorage.getItem(EMAIL); }
  function role() { return localStorage.getItem(ROLE) || "author"; }
  function name() { return localStorage.getItem(NAME) || ""; }
  function isAdmin() { return role() === "admin"; }
  function setToken(t, e) { localStorage.setItem(KEY, t); if (e) localStorage.setItem(EMAIL, e); }
  // Store the full session returned by /api/admin/login (token, email, role, name).
  function setSession(d) {
    localStorage.setItem(KEY, d.token);
    localStorage.setItem(EMAIL, d.email || "");
    localStorage.setItem(ROLE, d.role || "author");
    localStorage.setItem(NAME, d.name || "");
  }
  function clear() {
    [KEY, EMAIL, ROLE, NAME].forEach(k => localStorage.removeItem(k));
  }

  // Authenticated JSON fetch. Redirects to login on 401.
  async function api(path, opts = {}) {
    const headers = Object.assign(
      { "Content-Type": "application/json", "Authorization": "Bearer " + (token() || "") },
      opts.headers || {}
    );
    const res = await fetch(path, Object.assign({}, opts, { headers }));
    if (res.status === 401) {
      clear();
      location.replace("login.html");
      throw new Error("Session expired");
    }
    const data = res.status === 204 ? {} : await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || ("Request failed (" + res.status + ")"));
    return data;
  }

  return { token, email, role, name, isAdmin, setToken, setSession, clear, api };
})();

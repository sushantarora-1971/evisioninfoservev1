/* Shared admin helpers: token storage + authenticated fetch wrapper. */
const Admin = (function () {
  const KEY = "evision_admin_token";
  const EMAIL = "evision_admin_email";

  function token() { return localStorage.getItem(KEY); }
  function email() { return localStorage.getItem(EMAIL); }
  function setToken(t, e) { localStorage.setItem(KEY, t); if (e) localStorage.setItem(EMAIL, e); }
  function clear() { localStorage.removeItem(KEY); localStorage.removeItem(EMAIL); }

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

  return { token, email, setToken, clear, api };
})();

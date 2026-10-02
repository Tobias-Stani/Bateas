// Ingreso al admin con contraseña (los dueños con Google entran directo).

// --- ingreso ---
$("login").onsubmit = async e => {
  e.preventDefault();
  const btn = e.submitter, pw = $("password");
  if (!pw.value) { $("login-error").textContent = "Escribí la contraseña."; pw.setAttribute("aria-invalid", "true"); return; }
  setBusy(btn, true, "Entrando…");
  try {
    await api("/api/admin/login", { method: "POST", body: { value: pw.value } });
    pw.value = "";
    await openPanel();
  } catch (err) {
    $("login-error").textContent = err.message;
    pw.setAttribute("aria-invalid", "true");
    pw.select();
  } finally { setBusy(btn, false); }
};
$("password").oninput = () => { $("login-error").textContent = ""; $("password").removeAttribute("aria-invalid"); };
$("logout").onclick = async () => {
  await Promise.all([api("/api/admin/logout", { method: "POST" }), api("/api/cuenta/logout", { method: "POST" }).catch(() => {})]);
  showGate();
};

// Cuenta del dueño: continuar con Google y crear su tienda.

const show = id => { for (const s of ["loading", "signed-out", "new-store", "my-stores"]) $(s).hidden = s !== id; };
const slugify = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
  .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40).replace(/-+$/, "");
let googleReady = null, clientId = "";

function render(me) {
  document.querySelectorAll("[data-me-name]").forEach(el => { el.textContent = me.name || me.email; });
  document.querySelectorAll("[data-me-email]").forEach(el => { el.textContent = me.email; });
  document.querySelectorAll("[data-me-picture]").forEach(el => { el.src = me.picture || "/assets/img/bateas.svg"; });
  if (!me.stores.length) { show("new-store"); $("s-name").focus(); return; }
  $("stores").innerHTML = me.stores.map(t => `<div class="store">
    <b>${esc(t.name)}</b><span class="hint">${esc(location.host)}/${esc(t.slug)}</span>
    <a class="btn" href="/${esc(t.slug)}/admin">Ir a mi admin</a>
    <a class="btn ghost" href="/${esc(t.slug)}" target="_blank" rel="noopener">Ver mi tienda</a></div>`).join("");
  show("my-stores");
}

// --- Google ---
async function onCredential({ credential }) {
  $("google-error").textContent = "";
  try { render(await api("/api/cuenta/google", { method: "POST", body: { value: credential } })); }
  catch (err) { $("google-error").textContent = err.message; }
}
function renderGoogleButton() {
  if (!clientId) { $("google-error").textContent = "El registro todavía no está habilitado. Escribinos y te armamos la tienda."; return; }
  googleReady.then(() => {
    google.accounts.id.initialize({ client_id: clientId, callback: onCredential, ux_mode: "popup" });
    google.accounts.id.renderButton($("google-button"), { theme: "filled_black", size: "large", text: "continue_with", shape: "pill", locale: "es", width: 300 });
  });
}
// la librería de Google se carga sola; esta promesa avisa cuando está lista
googleReady = new Promise(resolve => { window.onGoogleLibraryLoad = resolve; });

// --- alta de la tienda ---
// plan: viene elegido desde la landing con /cuenta?plan=premium; si no, Gratis
const chosenPlan = () => document.querySelector('input[name="plan"]:checked').value;
if (new URLSearchParams(location.search).get("plan") === "premium") document.querySelector('input[value="premium"]').checked = true;
const syncPlan = () => { $("plan-hint").hidden = chosenPlan() !== "premium"; };
document.querySelectorAll('input[name="plan"]').forEach(r => r.onchange = syncPlan);
syncPlan();
let slugTouched = false;
$("s-origin").textContent = `${location.host}/`;
$("s-name").oninput = () => { $("store-error").textContent = ""; if (!slugTouched) $("s-slug").value = slugify($("s-name").value); };
$("s-slug").oninput = () => { $("store-error").textContent = ""; slugTouched = true; $("s-slug").value = $("s-slug").value.toLowerCase().replace(/[^a-z0-9-]/g, ""); };
$("store-form").onsubmit = async e => {
  e.preventDefault();
  const body = { name: $("s-name").value, slug: $("s-slug").value, plan: chosenPlan() };
  if (body.name.trim().length < 2) return ($("store-error").textContent = "Escribí el nombre de tu disquería.");
  if (body.slug.length < 2) return ($("store-error").textContent = "La dirección tiene que tener al menos 2 caracteres.");
  const btn = e.submitter;
  setBusy(btn, true, "Creando tu tienda…");
  try {
    const t = await api("/api/cuenta/tiendas", { method: "POST", body });
    location.href = `/${t.slug}/admin${t.plan_requested === "premium" ? "?bienvenida=premium" : ""}`;
  } catch (err) {
    setBusy(btn, false);
    if (err.status === 401) return start();
    $("store-error").textContent = err.message;
  }
};

document.querySelectorAll("[data-logout]").forEach(b => b.onclick = async () => {
  await api("/api/cuenta/logout", { method: "POST" }).catch(() => {});
  if (window.google) google.accounts.id.disableAutoSelect();
  start();
});

async function start() {
  show("loading");
  try { return render(await api("/api/cuenta")); }
  catch (err) { if (err.status !== 401) return Swal.fire({ icon: "error", title: "No se pudo cargar tu cuenta", text: err.message }); }
  clientId = (await api("/api/cuenta/config").catch(() => ({}))).google_client_id || "";
  show("signed-out");
  renderGoogleButton();
}
start();

const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = n => Number(n).toLocaleString("es-AR");

// multitenant por ruta: la página /{slug} y /{slug}/admin hablan con /api/t/{slug}/...
const TENANT = location.pathname.split("/")[1];
const apiUrl = url => /^\/api\/(super|cuenta)(\/|$)/.test(url) ? url : url.replace(/^\/api\//, `/api/t/${TENANT}/`);

// fetch que devuelve JSON o tira Error con el mensaje del backend
async function api(url, { method = "GET", body } = {}) {
  const r = await fetch(apiUrl(url), {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const err = new Error(data.detail || "No se pudo conectar con el servidor. Probá de nuevo.");
    err.status = r.status;
    throw err;
  }
  return data;
}

const toast = Swal.mixin({ toast: true, position: "bottom", timer: 2200, showConfirmButton: false, timerProgressBar: true });

function confirmAction({ title, text, confirm, danger = false }) {
  return Swal.fire({
    title, text, icon: danger ? "warning" : "question", showCancelButton: true, confirmButtonText: confirm,
    cancelButtonText: "Cancelar", reverseButtons: true, focusCancel: danger, customClass: danger ? { confirmButton: "swal-danger" } : {},
  }).then(r => r.isConfirmed);
}

// fechas: el backend guarda UTC, se muestran en la hora del navegador
const fmtDate = iso => new Date(iso).toLocaleString("es-AR", { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
function fromNow(iso) {
  const ms = new Date(iso) - Date.now(), rtf = new Intl.RelativeTimeFormat("es", { numeric: "auto" });
  const days = Math.round(ms / 864e5);
  return Math.abs(days) >= 1 ? rtf.format(days, "day") : rtf.format(Math.round(ms / 36e5), "hour");
}

function setBusy(btn, busy, label) {
  btn.disabled = busy;
  if (busy) { btn.dataset.label = btn.textContent; btn.textContent = label; }
  else if (btn.dataset.label) btn.textContent = btn.dataset.label;
}

// buscador: "/" enfoca (atajo para usuarios frecuentes)
document.addEventListener("keydown", e => {
  const q = $("q");
  if (e.key === "/" && q && document.activeElement.tagName !== "INPUT") { e.preventDefault(); q.focus(); }
});

// mensaje de pedido a partir de las plantillas del admin; lo usan la tienda y la vista previa
const fill = (tpl, vars) => tpl.replace(/\{(\w+)\}/g, (m, k) => k in vars ? String(vars[k] ?? "") : m);
// un campo vacío no deja "()", "[]" ni espacios dobles
const tidy = s => s.replace(/([(\[])\s+|\s+([)\]])/g, "$1$2").replace(/\(\)|\[\]/g, "")
  .replace(/\s[-–]\s*(?=[-–(\[]|$)/g, " ")  // guion que quedó sin nada a un lado (un dato vacío): "#2 - – Título" -> "#2 – Título"
  .replace(/[ \t]{2,}/g, " ").trim();
// "75000" -> "$ 75.000"; si el Excel ya trae texto ("USD 40") se deja como está
const fmtPrice = p => /^\d+(\.\d+)?$/.test(p || "") ? `$ ${Number(p).toLocaleString("es-AR")}` : (p || "");
// columnas propias de la disquería como variables: {insert} -> d.extra["Insert"]
const ownVars = (d, columns) => Object.fromEntries(columns.map(c => [c.key, d.extra?.[c.name] ?? ""]));
function buildMessage({ message, message_line, custom_columns = [] }, discs, store = "") {
  const list = discs.map(d => tidy(fill(message_line, { ...ownVars(d, custom_columns), ...d, price: fmtPrice(d.price) }))).join("\n");
  return fill(message, { discos: list, cantidad: discs.length, tienda: store });
}

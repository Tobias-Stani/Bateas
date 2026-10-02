// Admin de la disquería: estado compartido del panel, tabla del catálogo y apertura del panel.
// Se carga primero; los demás archivos usan `status`, `openPanel` y `showGate`.

let status = {}, file = null, page = 1, pages = 1;

function showGate() { $("panel").hidden = true; $("gate").hidden = false; $("password").focus(); }

// "2026-09-30T23:00+00:00" -> "2026-09-30T20:00" (valor para el input en hora local)
function toLocalInput(iso) {
  const d = new Date(iso);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

function renderClose() {
  const s = status, el = $("close-status");
  el.classList.toggle("closed", s.closed);
  el.textContent = !s.closes_at ? "Sin fecha de cierre. La tienda queda abierta."
    : s.closed ? `Cerrada desde el ${fmtDate(s.closes_at)}. Los clientes no pueden entrar.`
    : `Abierta hasta el ${fmtDate(s.closes_at)} (cierra ${fromNow(s.closes_at)}).`;
  $("close-at").value = s.closes_at ? toLocalInput(s.closes_at) : "";
  $("clear-close").hidden = !s.closes_at;
}

function renderStatus() {
  const s = status;
  $("code-now").textContent = s.client_code;
  renderCodeRequired();
  $("wa-now").textContent = s.whatsapp ? `+${s.whatsapp}` : "Sin configurar";
  renderClose();
  $("delete-catalog").hidden = !s.total;
  if (!s.total) {
    $("summary").innerHTML = `<strong>Sin catálogo</strong><span class="hint">Todavía no se cargó ninguna lista. Los clientes ven la tienda vacía.</span>`;
    $("bars").innerHTML = "";
    $("media").innerHTML = $("media").options[0].outerHTML;
    return;
  }
  const when = s.uploaded_at ? new Date(s.uploaded_at).toLocaleString("es-AR", { dateStyle: "long", timeStyle: "short", hourCycle: "h23" }) : "";
  $("summary").innerHTML = `<strong>${num(s.total)} discos</strong>
    <span class="hint">${num(s.genres)} géneros${s.filename ? `, de <b>${esc(s.filename)}</b>, cargado el ${esc(when)}` : ""}</span>`;
  // los 5 formatos principales y el resto junto: los Excel traen valores sueltos que no aportan
  const top = s.media.slice(0, 5), rest = s.media.slice(5).reduce((n, m) => n + m.n, 0);
  $("bars").innerHTML = [...top, ...(rest ? [{ media: `Otros (${s.media.length - 5})`, n: rest }] : [])].map(m => `
    <div class="bar"><span>${esc(m.media || "Sin formato")}</span>
    <div><span style="width:${(m.n / s.total * 100).toFixed(1)}%"></span></div><em>${num(m.n)}</em></div>`).join("");
  $("media").innerHTML = $("media").options[0].outerHTML + s.media.filter(m => m.media).map(m => `<option>${esc(m.media)}</option>`).join("");
}

async function loadTable() {
  const params = new URLSearchParams({ q: $("q").value, media: $("media").value, page });
  $("table-status").textContent = "Buscando…";
  const data = await api("/api/discos?" + params);
  pages = Math.max(1, Math.ceil(data.total / data.page_size));
  $("table-status").textContent = `${num(data.total)} resultados`;
  $("pageinfo").textContent = `Página ${page} de ${num(pages)}`;
  $("prev").disabled = page <= 1;
  $("next").disabled = page >= pages;
  const own = status.custom_columns;
  $("table-head").innerHTML = ["N.º", "Artista", "Título", "Sello", "Formato", "Descripción", "Género", "Origen", "Precio", ...own.map(c => c.name)]
    .map(h => `<th>${esc(h)}</th>`).join("");
  $("rows").innerHTML = data.items.length ? data.items.map(d => `<tr>
    <td><span class="sticker">#${d.id}</span></td><td class="wrap">${esc(d.artist)}</td><td class="wrap">${esc(d.title)}</td>
    <td>${esc(d.label)}</td><td>${esc(d.media)}</td><td>${esc(d.description)}</td><td>${esc(d.genre)}</td><td>${esc(d.origin)}</td><td>${esc(fmtPrice(d.price))}</td>
    ${own.map(c => `<td>${esc(d.extra?.[c.name])}</td>`).join("")}</tr>`).join("")
    : `<tr><td colspan="${9 + own.length}" class="hint" style="padding:24px;text-align:center">${status.total ? "Nada coincide con la búsqueda." : "Cargá un Excel para ver los discos acá."}</td></tr>`;
}

async function openPanel() {
  status = await api("/api/admin/status");
  $("gate").hidden = true;
  $("panel").hidden = false;
  renderStatus();
  if (!msgDirty) renderMessage();
  renderContact();
  renderDiscogs();
  renderMp();
  renderPlan();
  loadTable();
  loadSections().then(loadHome);  // el formulario del banner lista las secciones
}

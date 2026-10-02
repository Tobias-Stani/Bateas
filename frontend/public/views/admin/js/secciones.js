// Secciones de la tienda: carruseles armados a mano.

// --- secciones ---
let sections = [], secId = null, secSearch = [], secQuery = "", secSeq = 0;
const current = () => sections.find(x => x.id === secId);
// con la descripción: el mismo disco suele venir en varias ediciones ("CD + poster", "CD in stickered case")
const discLine = d => {
  const ed = d.disc || d;  // en la sección, la edición actual del catálogo
  const more = [ed.media, ed.description].filter(Boolean).map(esc).join(" · ");
  return `<b>${esc(d.artist)}</b> – ${esc(d.title)}${more ? ` <small>· ${more}</small>` : ""}`;
};

async function loadSections(keep = true) {
  sections = await api("/api/admin/secciones");
  if (!keep || !current()) secId = sections[0]?.id ?? null;
  renderSections();
}
let secShown = null;  // sección que estaba en pantalla: si es la misma, se conserva el scroll de los resultados
function renderSections() {
  const keepScroll = secShown === secId ? document.getElementById("sec-results")?.scrollTop || 0 : 0;
  secShown = secId;
  $("sec-list").innerHTML = sections.map((x, i) => `
    <li class="${x.id === secId ? "on" : ""}" data-sec="${x.id}">
      <span class="sec-name">${esc(x.name)}<small>${x.items.length} ${x.items.length === 1 ? "disco" : "discos"}${x.visible ? "" : " · oculta"}</small></span>
    </li>`).join("");
  const x = current();
  if (!x) {
    $("sec-editor").innerHTML = `<div class="sec-empty">${sections.length ? "Elegí una sección." : "Todavía no hay secciones. Creá la primera con <b>+ Nueva sección</b>."}</div>`;
    return;
  }
  $("sec-editor").innerHTML = `
    <div class="sec-head">
      <input id="sec-name" class="field" maxlength="60" value="${esc(x.name)}" aria-label="Nombre de la sección">
      <button id="sec-rename" class="btn btn-sm">Guardar nombre</button>
      <label class="switch"><input id="sec-visible" type="checkbox" ${x.visible ? "checked" : ""}> Mostrar en la tienda</label>
      <button id="sec-delete" class="btn-text danger">Eliminar</button>
    </div>
    <label for="sec-q">Agregar discos</label>
    <input id="sec-q" class="field" type="search" placeholder="Buscá por artista, título o sello" autocomplete="off" value="${esc(secQuery)}">
    <ul id="sec-results" class="results" aria-live="polite">${resultsHtml()}</ul>
    <p class="hint" style="margin:18px 0 6px"><b>${x.items.length} ${x.items.length === 1 ? "disco" : "discos"} en la sección</b>${x.items.length ? " · el orden es el del carrusel" : ""}</p>
    ${x.items.length ? `<ul class="picks">${x.items.map((it, i) => `
      <li class="${it.disc ? "" : "gone"}">
        <span class="what">${it.disc ? `<span class="sticker">#${it.disc.id}</span> ` : ""}${discLine(it)}</span>
        ${it.disc ? "" : `<span class="tag-gone">No está en la lista actual</span>`}
        <button class="icon-btn" data-item-move="-1" data-i="${i}" aria-label="Subir" ${i ? "" : "disabled"}>▲</button>
        <button class="icon-btn" data-item-move="1" data-i="${i}" aria-label="Bajar" ${i < x.items.length - 1 ? "" : "disabled"}>▼</button>
        <button class="btn-text danger" data-remove="${it.item_id}">Quitar</button>
      </li>`).join("")}</ul>` : `<div class="sec-empty">Buscá discos arriba y tocá <b>Agregar</b>.</div>`}`;
  $("sec-results").scrollTop = keepScroll;  // agregar uno de abajo no te devuelve al principio
}
// solo la lista de resultados: el input no se toca mientras se escribe
function resultsHtml() {
  const inSec = new Set((current()?.items || []).filter(i => i.disc).map(i => i.disc.id));
  return secSearch.map(d => `
      <li><span class="what"><span class="sticker">#${d.id}</span> ${discLine(d)}</span>
      ${inSec.has(d.id) ? `<span class="hint">Agregado ✓</span>` : `<button class="btn btn-sm" data-pick="${d.id}">Agregar</button>`}</li>`).join("");
}
async function secCall(fn) {
  try { await fn(); await loadSections(); loadHome(); }
  catch (err) { if (err.status === 401) return showGate(); if (planBlocked(err)) return; Swal.fire({ icon: "error", title: "No se pudo guardar", text: err.message }); }
}
$("sec-new").onclick = async () => {
  const r = await Swal.fire({ title: "Nueva sección", input: "text", inputPlaceholder: "Más vendidos", inputAttributes: { maxlength: 60 },
    showCancelButton: true, confirmButtonText: "Crear", cancelButtonText: "Cancelar", reverseButtons: true,
    preConfirm: v => v.trim() || Swal.showValidationMessage("Escribí un nombre.") });
  if (!r.isConfirmed) return;
  secCall(async () => { secId = (await api("/api/admin/secciones", { method: "POST", body: { name: r.value } })).id; secSearch = []; secQuery = ""; });
};
$("sec-list").onclick = e => {
  const li = e.target.closest("[data-sec]");
  if (li) { secId = +li.dataset.sec; secSearch = []; secQuery = ""; renderSections(); }
};
let secTimer;
$("sec-editor").oninput = e => {
  if (e.target.id !== "sec-q") return;
  secQuery = e.target.value;  // tal cual, con espacios: se recorta solo para buscar
  clearTimeout(secTimer);
  secTimer = setTimeout(async () => {
    const q = secQuery.trim(), seq = ++secSeq;
    const found = q ? (await api("/api/discos?" + new URLSearchParams({ q, page: 1 }))).items.slice(0, 20) : [];
    if (seq !== secSeq) return;  // llegó tarde: ya hay una búsqueda más nueva
    secSearch = found;
    $("sec-results").innerHTML = resultsHtml();
  }, 250);
};
$("sec-editor").onchange = e => {
  if (e.target.id === "sec-visible") secCall(() => api(`/api/admin/secciones/${secId}`, { method: "PATCH", body: { visible: e.target.checked } }));
};
$("sec-editor").onclick = async e => {
  const d = e.target.dataset, x = current();
  if (e.target.id === "sec-rename") return secCall(() => api(`/api/admin/secciones/${secId}`, { method: "PATCH", body: { name: $("sec-name").value } }));
  if (e.target.id === "sec-delete") {
    if (await confirmAction({ title: `¿Eliminar "${x.name}"?`, text: "Se borra la sección. Los discos siguen en el catálogo.", confirm: "Eliminar sección", danger: true }))
      secCall(async () => { await api(`/api/admin/secciones/${secId}`, { method: "DELETE" }); secId = null; secSearch = []; secQuery = ""; });
    return;
  }
  if (d.pick) return secCall(() => api(`/api/admin/secciones/${secId}/discos`, { method: "POST", body: { disc_id: +d.pick } }));
  if (d.remove) return secCall(() => api(`/api/admin/secciones/${secId}/discos/${d.remove}`, { method: "DELETE" }));
  if (d.itemMove) {
    const i = +d.i, ids = x.items.map(it => it.item_id);
    [ids[i], ids[i + +d.itemMove]] = [ids[i + +d.itemMove], ids[i]];
    secCall(() => api(`/api/admin/secciones/${secId}/orden`, { method: "PUT", body: { ids } }));
  }
};
$("sec-editor").onkeydown = e => { if (e.target.id === "sec-name" && e.key === "Enter") $("sec-rename").click(); };

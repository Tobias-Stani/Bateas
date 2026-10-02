// Portada: orden de los bloques y banners.

// --- portada ---
let home = { blocks: [], banners: [], groups: [] }, groupId = null, bannerId = null;
const currentGroup = () => home.groups.find(g => g.id === groupId);
const groupBanners = () => home.banners.filter(b => b.group_id === groupId);
const currentBanner = () => groupBanners().find(b => b.id === bannerId);

async function loadHome() {
  home = await api("/api/admin/portada");
  if (!currentGroup()) groupId = home.groups[0]?.id ?? null;
  if (!currentBanner()) bannerId = groupBanners()[0]?.id ?? null;
  renderBlocks(); renderBanners();
}
function renderBlocks() {
  const kind = { banners: "Banners", section: "Sección", catalog: "Catálogo" };
  $("blocks").innerHTML = home.blocks.map((b, i) => `
    <li class="${b.visible ? "" : "off"}">
      <span class="b-name"><span class="b-kind">${kind[b.type]}</span><br>${esc(b.name)}
        <small>${b.type === "catalog" ? "Siempre visible" : b.type === "banners" ? `${b.count} ${b.count === 1 ? "imagen" : "imágenes"}` : `${b.count} ${b.count === 1 ? "disco" : "discos"}`}</small></span>
      ${b.type === "catalog" ? "" : `<input class="ios-switch" type="checkbox" role="switch" data-show="${i}" ${b.visible ? "checked" : ""} aria-label="Mostrar ${esc(b.name)}">`}
      <button class="icon-btn" data-block-move="-1" data-i="${i}" aria-label="Subir ${esc(b.name)}" ${i ? "" : "disabled"}>▲</button>
      <button class="icon-btn" data-block-move="1" data-i="${i}" aria-label="Bajar ${esc(b.name)}" ${i < home.blocks.length - 1 ? "" : "disabled"}>▼</button>
    </li>`).join("");
}
async function homeCall(fn) {
  try { await fn(); await loadHome(); }
  catch (err) { if (err.status === 401) return showGate(); if (!planBlocked(err)) Swal.fire({ icon: "error", title: "No se pudo guardar", text: err.message }); loadHome(); }
}
$("blocks").onclick = e => {
  const move = e.target.dataset.blockMove;
  if (!move) return;
  const i = +e.target.dataset.i, tokens = home.blocks.map(b => b.token);
  [tokens[i], tokens[i + +move]] = [tokens[i + +move], tokens[i]];
  homeCall(() => api("/api/admin/portada/orden", { method: "PUT", body: { tokens } }));
};
$("blocks").onchange = e => {
  const b = home.blocks[e.target.dataset.show];
  if (!b) return;
  const value = e.target.checked;
  homeCall(async () => {
    if (b.type === "banners") await api(`/api/admin/banner-bloques/${b.id}`, { method: "PATCH", body: { visible: value } });
    else { await api(`/api/admin/secciones/${b.id}`, { method: "PATCH", body: { visible: value } }); await loadSections(); }
  });
};

// el navegador achica la foto antes de subirla: una de 8 MB del celular queda en ~300 KB
async function shrink(file) {
  const img = await createImageBitmap(file);
  const scale = Math.min(1, 1920 / img.width), canvas = document.createElement("canvas");
  canvas.width = Math.round(img.width * scale); canvas.height = Math.round(img.height * scale);
  canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
  const blob = type => new Promise(r => canvas.toBlob(r, type, 0.85));
  const webp = await blob("image/webp");
  return webp?.type === "image/webp" ? webp : blob("image/jpeg");  // navegadores sin WebP
}
async function sendImage(url, method, file, fields = {}) {
  let small;
  try { small = await shrink(file); }
  catch { throw new Error("No pudimos leer esa imagen. Probá con un JPG o PNG."); }
  const form = new FormData();
  form.append("file", small, small.type === "image/webp" ? "banner.webp" : "banner.jpg");
  for (const [k, v] of Object.entries(fields)) form.append(k, v);
  const r = await fetch(apiUrl(url), { method, body: form });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(data.detail || "No se pudo subir la imagen."), { status: r.status });
  return data;
}
let bannerFileFor = null;  // null = banner nuevo; id = reemplazar la imagen de ese banner
// bloques de banners: pestañas arriba, el elegido abajo
$("group-bar").onclick = async e => {
  const g = e.target.closest("[data-group]");
  if (g) { groupId = +g.dataset.group; bannerId = groupBanners()[0]?.id ?? null; return renderBanners(); }
  if (!e.target.closest("#group-new")) return;
  const r = await Swal.fire({ title: "Nuevo bloque de banners", input: "text", inputPlaceholder: "Promo del mes", inputAttributes: { maxlength: 60 },
    text: "Va a aparecer arriba de la portada; después lo ubicás donde quieras.",
    showCancelButton: true, confirmButtonText: "Crear", cancelButtonText: "Cancelar", reverseButtons: true,
    preConfirm: v => v.trim() || Swal.showValidationMessage("Escribí un nombre.") });
  if (r.isConfirmed) homeCall(async () => { groupId = (await api("/api/admin/banner-bloques", { method: "POST", body: { name: r.value } })).id; bannerId = null; });
};
$("banner-file").onchange = async e => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  Swal.fire({ title: "Subiendo imagen", allowOutsideClick: false, didOpen: () => Swal.showLoading() });
  try {
    if (bannerFileFor) await sendImage(`/api/admin/banners/${bannerFileFor}/imagen`, "PUT", file);
    else bannerId = (await sendImage("/api/admin/banners", "POST", file, { group_id: groupId })).id;
    Swal.close();
    await loadHome();
    toast.fire({ icon: "success", title: bannerFileFor ? "Imagen cambiada" : "Imagen agregada: sumale un título si querés" });
  } catch (err) {
    if (err.status === 401) { Swal.close(); return showGate(); }
    if (planBlocked(err)) return;
    Swal.fire({ icon: "error", title: "No se subió la imagen", text: err.message });
  }
};
function renderBanners() {
  $("group-bar").innerHTML = home.groups.map(g => `<button class="${g.id === groupId ? "on" : ""}" data-group="${g.id}">${esc(g.name)}${g.visible ? "" : " · oculto"}</button>`).join("")
    + `<button id="group-new" class="add">+ Nuevo bloque de banners</button>`;
  const g = currentGroup();
  if (!g) { $("group-editor").innerHTML = `<div class="sec-empty">Todavía no hay banners. Creá el primer bloque con <b>+ Nuevo bloque de banners</b>.</div>`; return; }
  $("group-editor").innerHTML = `
    <div class="group-head">
      <input id="group-name" class="field" maxlength="60" value="${esc(g.name)}" aria-label="Nombre del bloque">
      <button id="group-rename" class="btn btn-sm">Guardar nombre</button>
      <button id="group-delete" class="btn-text danger">Eliminar bloque</button>
    </div>
    <div id="banner-list" class="banner-list"></div>
    <button id="banner-new" class="btn btn-outline btn-sm">+ Agregar imagen</button>
    <div id="banner-form"></div>`;
  const list = groupBanners();
  $("banner-list").innerHTML = list.map((b, i) => `
    <button class="banner-thumb ${b.id === bannerId ? "on" : ""} ${b.visible ? "" : "hidden-b"}" data-banner="${b.id}">
      <img src="${esc(b.url)}" alt=""><span>${i + 1}. ${esc(b.title || "Sin título")}${b.visible ? "" : " · oculto"}</span>
    </button>`).join("");
  const b = currentBanner();
  if (!b) { $("banner-form").innerHTML = list.length ? "" : `<div class="sec-empty" style="margin-top:12px">Este bloque no tiene imágenes. Agregá la primera con <b>+ Agregar imagen</b>.</div>`; return; }
  const i = list.indexOf(b), link = b.button_link || "";
  const target = !link ? "" : link.startsWith("https://") ? "url" : link;
  const options = [["", "Sin botón"], ["catalog", "Al catálogo"], ...sections.map(x => [`section:${x.id}`, `A la sección "${x.name}"`]), ["url", "A un link (https://…)"]];
  $("banner-form").innerHTML = `
    <form id="banner-edit" class="banner-form" novalidate>
      <img class="preview-img" src="${esc(b.url)}" alt="Imagen del banner">
      <div class="banner-tools" style="margin-top:0">
        <button type="button" id="banner-image" class="btn btn-outline btn-sm">Cambiar imagen</button>
        <button type="button" class="icon-btn" data-banner-move="-1" aria-label="Mover antes" ${i ? "" : "disabled"}>◀</button>
        <button type="button" class="icon-btn" data-banner-move="1" aria-label="Mover después" ${i < list.length - 1 ? "" : "disabled"}>▶</button>
        <label class="switch" style="margin:0 0 0 auto"><input id="b-visible" type="checkbox" ${b.visible ? "checked" : ""}> Mostrar este banner</label>
      </div>
      <div class="row2">
        <div><label for="b-title">Título <span class="hint">(opcional)</span></label><input id="b-title" class="field" maxlength="80" value="${esc(b.title)}" placeholder="Preventa de octubre"></div>
        <div><label for="b-text">Texto <span class="hint">(opcional)</span></label><input id="b-text" class="field" maxlength="200" value="${esc(b.text)}" placeholder="Llegan los importados del mes"></div>
      </div>
      <div class="row2">
        <div><label for="b-target">El botón lleva…</label><select id="b-target" class="field">${options.map(([v, l]) => `<option value="${esc(v)}" ${v === target ? "selected" : ""}>${esc(l)}</option>`).join("")}</select></div>
        <div id="b-label-wrap"><label for="b-label">Texto del botón</label><input id="b-label" class="field" maxlength="30" value="${esc(b.button_label)}" placeholder="Ver preventa"></div>
      </div>
      <div id="b-url-wrap"><label for="b-url">Link</label><input id="b-url" class="field" maxlength="500" value="${target === "url" ? esc(link) : ""}" placeholder="https://…" spellcheck="false"></div>
      <p id="b-error" class="error" role="alert"></p>
      <div class="banner-tools">
        <button class="btn">Guardar banner</button>
        <button type="button" id="banner-delete" class="btn-text danger">Eliminar imagen</button>
      </div>
    </form>`;
  syncBannerTarget();
}
function syncBannerTarget() {
  const t = $("b-target").value;
  $("b-url-wrap").hidden = t !== "url";
  $("b-label-wrap").style.visibility = t ? "visible" : "hidden";
}
// el editor del bloque se re-pinta entero: los eventos se escuchan en el contenedor
$("group-editor").onclick = async e => {
  const thumb = e.target.closest("[data-banner]");
  if (thumb) { bannerId = +thumb.dataset.banner; return renderBanners(); }
  if (e.target.id === "banner-new") { bannerFileFor = null; return $("banner-file").click(); }
  if (e.target.id === "group-rename") return homeCall(() => api(`/api/admin/banner-bloques/${groupId}`, { method: "PATCH", body: { name: $("group-name").value } }));
  if (e.target.id === "group-delete") {
    const g = currentGroup(), n = groupBanners().length;
    if (await confirmAction({ title: `¿Eliminar "${g.name}"?`, text: n ? `Se borran sus ${n} ${n === 1 ? "imagen" : "imágenes"} y sus textos.` : "El bloque está vacío.", confirm: "Eliminar bloque", danger: true }))
      homeCall(async () => { await api(`/api/admin/banner-bloques/${groupId}`, { method: "DELETE" }); groupId = null; bannerId = null; });
    return;
  }
  if (e.target.id === "banner-image") { bannerFileFor = bannerId; return $("banner-file").click(); }
  const move = e.target.dataset.bannerMove;
  if (move) {
    const ids = groupBanners().map(b => b.id), i = ids.indexOf(bannerId);
    [ids[i], ids[i + +move]] = [ids[i + +move], ids[i]];
    return homeCall(() => api("/api/admin/banners-orden", { method: "PUT", body: { ids } }));
  }
  if (e.target.id === "banner-delete" && await confirmAction({ title: "¿Eliminar esta imagen?", text: "Se borra la imagen y sus textos.", confirm: "Eliminar imagen", danger: true }))
    homeCall(async () => { await api(`/api/admin/banners/${bannerId}`, { method: "DELETE" }); bannerId = null; });
};
$("group-editor").onchange = e => {
  if (e.target.id === "b-target") syncBannerTarget();
  if (e.target.id === "b-visible") homeCall(() => api(`/api/admin/banners/${bannerId}`, { method: "PATCH", body: { visible: e.target.checked } }));
};
$("group-editor").oninput = () => { const err = document.getElementById("b-error"); if (err) err.textContent = ""; };
$("group-editor").onkeydown = e => { if (e.target.id === "group-name" && e.key === "Enter") $("group-rename").click(); };
$("group-editor").onsubmit = async e => {
  e.preventDefault();
  if (e.target.id !== "banner-edit") return;
  const target = $("b-target").value, url = $("b-url").value.trim();
  if (target === "url" && !url.startsWith("https://")) return ($("b-error").textContent = "El link tiene que empezar con https://");
  if (target && !$("b-label").value.trim()) return ($("b-error").textContent = "Escribí el texto del botón, por ejemplo \"Ver preventa\".");
  const body = { title: $("b-title").value, text: $("b-text").value, button_label: target ? $("b-label").value : "",
                 button_link: target === "url" ? url : target };
  try {
    await api(`/api/admin/banners/${bannerId}`, { method: "PATCH", body });
    await loadHome();
    toast.fire({ icon: "success", title: "Banner guardado" });
  } catch (err) {
    if (err.status === 401) return showGate();
    $("b-error").textContent = err.message;
  }
};

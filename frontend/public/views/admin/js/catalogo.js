// Carga del catálogo desde Excel: vista previa de columnas, confirmación y borrado.

// --- carga del Excel: vista previa de columnas -> confirmación ---
const FIELD_LABELS = {
  artist: "Artista", title: "Título / álbum", artist_title: "Artista y título juntos", label: "Sello", media: "Formato", description: "Descripción",
  genre: "Género", price: "Precio", origin: "Origen", barcode: "Código de barras",
  custom: "Columna propia (con su nombre)", extra: "Agregar a la descripción", ignore: "No usar",
};
let plan = null;  // { filename, header_row, columns: [{ index, letter, header, field, samples }] }

async function pick(f) {
  if (!f) return;
  if (!f.name.toLowerCase().endsWith(".xlsx")) {
    Swal.fire({ icon: "error", title: "Ese archivo no sirve", text: `"${f.name}" no es un Excel .xlsx. Si es .xls, abrilo en Excel y guardalo como .xlsx.` });
    return;
  }
  Swal.fire({ title: "Leyendo el Excel", text: "Subiendo archivo…", allowOutsideClick: false, allowEscapeKey: false, didOpen: () => Swal.showLoading() });
  try {
    plan = await uploadWithProgress(f);
    Swal.close();
  } catch (err) {
    if (err.status === 401) { Swal.close(); return showGate(); }
    return Swal.fire({ icon: "error", title: "No se pudo leer el Excel", text: err.message });
  }
  $("drop").classList.add("ready");
  $("drop-title").textContent = f.name;
  $("drop-hint").textContent = `${(f.size / 1024 / 1024).toFixed(1)} MB. Revisá las columnas y cargalo.`;
  $("reset-file").hidden = false;
  renderMapping();
}
function renderMapping() {
  $("mapping").hidden = false;
  $("mapping-hint").textContent = `Los encabezados están en la fila ${plan.header_row}. Las columnas propias se muestran en la tienda con su nombre. Si algo no está bien, cambialo acá: la próxima vez se acuerda.`;
  const options = Object.entries(FIELD_LABELS).map(([v, l]) => `<option value="${v}">${l}</option>`).join("");
  $("mapping-rows").innerHTML = plan.columns.map((c, i) => `
    <tr class="${c.field === "ignore" ? "off" : ""}">
      <td><b>${esc(c.header || "Sin encabezado")}</b><br><small class="hint">Columna ${c.letter}</small></td>
      <td><select class="field" data-col="${i}" aria-label="Uso de la columna ${esc(c.header || c.letter)}">${options}</select></td>
      <td class="samples">${c.samples.map(esc).join("<br>") || "—"}</td>
    </tr>`).join("");
  plan.columns.forEach((c, i) => { document.querySelector(`[data-col="${i}"]`).value = c.field; });
  checkMapping();
}
function checkMapping() {
  const used = plan.columns.map(c => c.field).filter(f => !["custom", "extra", "ignore"].includes(f));
  const dup = used.find((f, i) => used.indexOf(f) !== i);
  const together = used.includes("artist_title");
  const error = dup ? `Hay dos columnas marcadas como "${FIELD_LABELS[dup]}". Dejá una sola.`
    : together && (used.includes("artist") || used.includes("title")) ? "Si artista y título vienen juntos en una columna, no marques otra como artista o título."
    : together ? ""
    : !used.includes("artist") ? "Elegí qué columna es el artista (o, si viene junto con el título, marcala como \"Artista y título juntos\")."
    : !used.includes("title") ? "Elegí qué columna es el título."
    : "";
  $("mapping-error").textContent = error;
  $("upload-btn").disabled = !!error;
}
$("mapping-rows").onchange = e => {
  const i = e.target.dataset.col;
  if (i === undefined) return;
  plan.columns[i].field = e.target.value;
  e.target.closest("tr").classList.toggle("off", e.target.value === "ignore");
  checkMapping();
};
function resetFile() {
  plan = null; $("file").value = "";
  $("drop").classList.remove("ready");
  $("drop-title").textContent = "Arrastrá el Excel acá";
  $("drop-hint").textContent = "o hacé clic para elegirlo. Solo archivos .xlsx.";
  $("upload-btn").disabled = true;
  $("reset-file").hidden = true;
  $("mapping").hidden = true;
}
$("drop").onclick = () => $("file").click();
$("drop").onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("file").click(); } };
$("file").onchange = e => pick(e.target.files[0]);
$("drop").ondragover = e => { e.preventDefault(); $("drop").classList.add("over"); };
$("drop").ondragleave = () => $("drop").classList.remove("over");
$("drop").ondrop = e => { e.preventDefault(); $("drop").classList.remove("over"); pick(e.dataTransfer.files[0]); };
$("reset-file").onclick = resetFile;

function uploadWithProgress(f) {
  // XHR en vez de fetch para poder mostrar el progreso de subida
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest(), form = new FormData();
    form.append("file", f);
    xhr.open("POST", apiUrl("/api/admin/upload/preview"));
    xhr.upload.onprogress = e => {
      if (!e.lengthComputable) return;
      const pct = Math.round(e.loaded / e.total * 100);
      Swal.update({ text: pct < 100 ? `Subiendo archivo… ${pct}%` : "Buscando las columnas…" });
      Swal.showLoading();
    };
    xhr.onload = () => {
      let data = {};
      try { data = JSON.parse(xhr.responseText || "{}"); } catch {}
      xhr.status < 300 ? resolve(data) : reject(Object.assign(new Error(data.detail || "Error al leer el archivo."), { status: xhr.status }));
    };
    xhr.onerror = () => reject(new Error("Se cortó la conexión. Probá de nuevo."));
    xhr.send(form);
  });
}

$("upload").onsubmit = async e => {
  e.preventDefault();
  if (!plan) return;
  const ok = await confirmAction({
    title: "¿Reemplazar el catálogo?",
    text: status.total
      ? `Se borran los ${num(status.total)} discos actuales y se cargan los de "${plan.filename}".`
      : `Se cargan los discos de "${plan.filename}".`,
    confirm: "Cargar catálogo",
  });
  if (!ok) return;
  Swal.fire({ title: "Cargando catálogo", text: "Guardando los discos…", allowOutsideClick: false, allowEscapeKey: false, didOpen: () => Swal.showLoading() });
  try {
    const mapping = Object.fromEntries(plan.columns.map(c => [c.index, c.field]));
    const r = await api("/api/admin/upload/confirm", { method: "POST", body: { header_row: plan.header_row, mapping } });
    await catalogLoaded(r.total, r.sections_missing);
    resetFile();
    page = 1;
    await openPanel();
  } catch (err) {
    if (err.status === 401) { Swal.close(); return showGate(); }
    if (planBlocked(err)) return;
    Swal.fire({ icon: "error", title: "No se cargó el catálogo", text: `${err.message} La lista anterior sigue publicada.` });
  }
};

$("delete-catalog").onclick = async () => {
  const ok = await confirmAction({
    title: "¿Eliminar el catálogo?",
    text: `Se borran los ${num(status.total)} discos. Los clientes van a ver la tienda vacía hasta que cargues otro Excel. No se puede deshacer.`,
    confirm: "Eliminar catálogo", danger: true,
  });
  if (!ok) return;
  try {
    await api("/api/admin/catalog", { method: "DELETE" });
    Swal.fire({ icon: "success", title: "Catálogo eliminado", text: "La tienda quedó vacía. Cuando tengas la lista nueva, cargala desde acá.", confirmButtonText: "Listo" });
    page = 1;
    await openPanel();
  } catch (err) {
    if (err.status === 401) return showGate();
    Swal.fire({ icon: "error", title: "No se eliminó el catálogo", text: err.message });
  }
};

// aviso después de cargar un catálogo (Excel o Discogs): cuántos discos y qué secciones perdieron alguno
function catalogLoaded(total, missing = []) {
  const gone = missing.map(x => `<li><b>${esc(x.name)}</b>: ${x.missing} ${x.missing === 1 ? "disco no está" : "discos no están"} en esta lista</li>`).join("");
  return Swal.fire({ icon: "success", title: "Catálogo cargado", confirmButtonText: "Listo",
    html: `<b>${num(total)} discos</b> ya están disponibles en la tienda.${gone ? `<ul style="text-align:left;margin-top:14px">${gone}</ul><p style="font-size:0.9rem">Se ocultan de la tienda hasta que vuelvan a aparecer. Podés quitarlos desde <b>Secciones</b>.</p>` : ""}` });
}

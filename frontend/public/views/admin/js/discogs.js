// Discogs (Premium): conectar la cuenta e importar el inventario.

// --- Discogs ---
let discogsTimer;
function renderDiscogs() {
  const d = status.discogs, j = d.job, who = `Conectada como <b>@${esc(d.user)}</b>.`;
  $("discogs-panel").hidden = !d.enabled && isPremium();  // en Gratis se muestra igual: es lo que gana con Premium
  lockPanel($("discogs-panel"), isPremium() ? "" : "Importar desde Discogs: disponible con el plan Premium");
  $("discogs-connect").hidden = !!d.user;
  $("discogs-import").hidden = $("discogs-disconnect").hidden = !d.user;
  $("discogs-import").disabled = $("discogs-disconnect").disabled = d.running;
  const failed = !d.running && j.state === "error";
  $("discogs-state").classList.toggle("closed", !d.user || failed);
  $("discogs-state").innerHTML = "<span>" + (!d.user ? "Sin conectar."
    : d.running ? `Importando… ${num(j.done)}${j.total ? ` de ${num(j.total)}` : ""} discos. Podés seguir usando el admin.`
    : failed ? `${who} La última importación falló: ${esc(j.message)}`
    : j.state === "done" ? `${who} Última importación: ${num(j.done)} discos, el ${fmtDate(j.at)}.`
    : who) + "</span>";
  clearTimeout(discogsTimer);
  if (d.running) discogsTimer = setTimeout(pollDiscogs, 2000);
}
async function pollDiscogs() {
  try {
    const d = (await api("/api/admin/status")).discogs;
    status.discogs = d;
    if (d.running) return renderDiscogs();
    page = 1;
    await openPanel();  // el catálogo cambió: se recarga todo el panel
    if (d.job.state === "done") catalogLoaded(d.job.done, d.job.sections_missing);
    else if (d.job.state === "error") Swal.fire({ icon: "error", title: "No se pudo importar", text: d.job.message });
  } catch (err) {
    if (err.status === 401) return showGate();
    discogsTimer = setTimeout(pollDiscogs, 5000);  // corte de red: reintenta
  }
}
$("discogs-connect").onclick = async e => {
  e.target.disabled = true;
  try { location.href = (await api("/api/admin/discogs/connect", { method: "POST" })).url; }
  catch (err) {
    e.target.disabled = false;
    if (err.status === 401) return showGate();
    Swal.fire({ icon: "error", title: "No se pudo conectar", text: err.message });
  }
};
$("discogs-import").onclick = async () => {
  if (!await confirmAction({ title: "¿Importar desde Discogs?", text: `Se reemplaza el catálogo actual por los discos que @${status.discogs.user} tiene a la venta en Discogs. Puede tardar un par de minutos.`, confirm: "Importar" })) return;
  try {
    status.discogs = await api("/api/admin/discogs/import", { method: "POST" });
    renderDiscogs();
  } catch (err) {
    if (err.status === 401) return showGate();
    Swal.fire({ icon: "error", title: "No se pudo importar", text: err.message });
  }
};
$("discogs-disconnect").onclick = async () => {
  if (!await confirmAction({ title: "¿Desconectar Discogs?", text: "El catálogo que ya importaste queda en la tienda. Para volver a importar vas a tener que conectar la cuenta de nuevo.", confirm: "Desconectar" })) return;
  try {
    status.discogs = await api("/api/admin/discogs", { method: "DELETE" });
    renderDiscogs();
  } catch (err) {
    if (err.status === 401) return showGate();
    Swal.fire({ icon: "error", title: "No se pudo desconectar", text: err.message });
  }
};
// vuelta desde Discogs: /{slug}/admin?discogs=ok|denied|error
{
  const p = new URLSearchParams(location.search), result = p.get("discogs");
  if (result) {
    history.replaceState(null, "", location.pathname);
    if (result === "ok") toast.fire({ icon: "success", title: "Discogs conectado" });
    else Swal.fire({ icon: result === "denied" ? "info" : "error", title: result === "denied" ? "No se conectó Discogs" : "No se pudo conectar Discogs",
                     text: result === "denied" ? "Cancelaste la autorización en Discogs." : p.get("msg") || "Probá de nuevo." });
  }
}

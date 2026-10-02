// Mensaje del pedido por WhatsApp, con vista previa.

// --- mensaje del pedido ---
const SAMPLE = [
  { id: 12, artist: "RADIOHEAD", title: "OK Computer", label: "XL Recordings", media: "Vinyl", description: "2LP", genre: "Rock", price: "75000", origin: "UK", barcode: "634904078218" },
  { id: 348, artist: "GIL, Gilberto", title: "Refazenda", label: "Warner", media: "CD", description: "", genre: "MPB", price: "", origin: "", barcode: "" },
];
const msgDraft = () => ({ message: $("msg-template").value, message_line: $("msg-line").value, custom_columns: status.custom_columns });
// aparte de renderStatus: no pisa lo que se está editando cuando cambia otra cosa del panel
let msgDirty = false;
function renderMessage() {
  msgDirty = false;
  // botones para las columnas propias del catálogo, y valores de ejemplo para la vista previa
  $("own-vars").innerHTML = status.custom_columns.map(c => `<button type="button" data-var="${esc(c.key)}">${esc(c.name.toLowerCase())}</button>`).join("");
  SAMPLE.forEach((d, i) => { d.extra = Object.fromEntries(status.custom_columns.map(c => [c.name, i ? "" : `(${c.name})`])); });
  $("msg-template").value = status.message;
  $("msg-line").value = status.message_line;
  renderPreview();
}
function renderPreview() { $("msg-preview").textContent = buildMessage(msgDraft(), SAMPLE, BRAND.name); }
$("msg-template").oninput = $("msg-line").oninput = () => { msgDirty = true; $("msg-error").textContent = ""; renderPreview(); };
document.querySelectorAll(".msg .vars").forEach(group => group.onclick = e => {
  const v = e.target.dataset.var;
  if (!v) return;
  const ta = $(group.dataset.target), at = ta.selectionStart, token = `{${v}}`;
  ta.setRangeText(token, at, ta.selectionEnd, "end");
  ta.focus();
  msgDirty = true;
  renderPreview();
});
$("msg-form").onsubmit = async e => {
  e.preventDefault();
  const { message, message_line } = msgDraft();
  if (!message.includes("{discos}")) return ($("msg-error").textContent = "Agregá la lista de discos al mensaje: sin eso el cliente manda un mensaje vacío.");
  try {
    const r = await api("/api/admin/message", { method: "PUT", body: { template: message, line: message_line } });
    Object.assign(status, { message: r.message, message_line: r.message_line });
    renderMessage();
    toast.fire({ icon: "success", title: "Mensaje guardado" });
  } catch (err) {
    if (err.status === 401) return showGate();
    $("msg-error").textContent = err.message;
  }
};
$("msg-reset").onclick = async () => {
  if (!await confirmAction({ title: "¿Volver al mensaje original?", text: "Se pierde el mensaje que armaste.", confirm: "Restaurar" })) return;
  try {
    const r = await api("/api/admin/message", { method: "DELETE" });
    Object.assign(status, { message: r.message, message_line: r.message_line });
    renderMessage();
    toast.fire({ icon: "success", title: "Mensaje restaurado" });
  } catch (err) {
    if (err.status === 401) return showGate();
    $("msg-error").textContent = err.message;
  }
};

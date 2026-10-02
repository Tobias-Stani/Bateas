// Pagos online con Mercado Pago (por ahora solo el super admin los conecta) y pedidos pagados.

// --- Mercado Pago ---
const MP_STATUS = { approved: "Pagado", pending: "Pendiente", in_process: "En revisión", authorized: "Autorizado",
  rejected: "Rechazado", cancelled: "Cancelado", refunded: "Devuelto", charged_back: "Contracargo", amount_mismatch: "Revisar: monto distinto" };
function renderMp() {
  const m = status.mercadopago;
  // por ahora los pagos online los conecta y prende solo el super admin; el resto lo ve, bloqueado
  if (!m.allowed) {
    $("mp-panel").hidden = false;
    $("mp-hint").textContent = "Tus clientes pagan el pedido con Mercado Pago y la plata va directo a tu cuenta.";
    $("mp-state").innerHTML = "<span>Sin conectar.</span>";
    $("mp-connect").hidden = false;
    $("mp-disconnect").hidden = $("mp-toggle").hidden = true;
    lockPanel($("mp-panel"), isPremium() ? "Pagos online: muy pronto" : "Pagos online: disponible con el plan Premium", !isPremium());
    return;
  }
  lockPanel($("mp-panel"), "");
  $("mp-panel").hidden = !m.enabled;
  if ($("mp-panel").hidden) return;
  $("mp-hint").textContent = `Tus clientes pagan con Mercado Pago y la plata va directo a tu cuenta.${m.fee_percent ? ` Bateas cobra un ${m.fee_percent}% de cada venta.` : ""} Solo se pueden pagar online los discos con precio en pesos; el resto sigue por WhatsApp.`;
  $("mp-state").classList.toggle("closed", !m.connected);
  $("mp-state").innerHTML = `<span>${m.connected ? "Cuenta de Mercado Pago conectada." : "Sin conectar."}</span>`;
  $("mp-connect").hidden = m.connected;
  $("mp-disconnect").hidden = $("mp-toggle").hidden = !m.connected;
  $("mp-payments").checked = m.payments;
  loadOrders();
}
async function loadOrders() {
  const orders = await api("/api/admin/pedidos").catch(() => []);
  $("orders-panel").hidden = !orders.length;
  const money = n => n == null ? "—" : fmtPrice(String(Math.round(n * 100) / 100));
  const paid = orders.filter(o => o.status === "approved"), sum = k => paid.reduce((s, o) => s + (o[k] || 0), 0);
  $("orders-sum").innerHTML = paid.length ? `<strong>${num(paid.length)} ${paid.length === 1 ? "venta" : "ventas"} · ${money(sum("total"))}</strong>
    <span class="hint">Mercado Pago: ${money(sum("mp_fee"))} · Bateas: ${money(sum("fee"))} · Te quedó: ${money(sum("net"))}</span>` : "";
  $("orders").innerHTML = orders.map(o => `<tr>
    <td><span class="sticker">#${o.id}</span></td>
    <td>${esc(fmtDate(o.updated_at || o.created_at))}</td>
    <td class="wrap">${o.items.map(i => `#${i.id} ${esc(i.artist)} – ${esc(i.title)}`).join("<br>")}</td>
    <td>${esc(money(o.total))}</td>
    <td>${esc(money(o.mp_fee))}</td>
    <td>${esc(money(o.fee))}</td>
    <td><b>${esc(money(o.net))}</b></td>
    <td>${esc(MP_STATUS[o.status] || o.status)}</td>
    <td>${esc(o.payer || "")}</td></tr>`).join("");
}
$("mp-connect").onclick = async e => {
  e.target.disabled = true;
  try { location.href = (await api("/api/admin/mercadopago/connect", { method: "POST" })).url; }
  catch (err) {
    e.target.disabled = false;
    if (err.status === 401) return showGate();
    Swal.fire({ icon: "error", title: "No se pudo conectar", text: err.message });
  }
};
$("mp-payments").onchange = async e => {
  const on = e.target.checked;
  e.target.disabled = true;
  try {
    status.mercadopago = await api("/api/admin/mercadopago/payments", { method: "PUT", body: { value: on } });
    renderMp();
    toast.fire({ icon: "success", title: on ? "Ahora tus clientes pueden pagar online" : "Los pedidos vuelven a ir por WhatsApp" });
  } catch (err) {
    e.target.checked = !on;
    if (err.status === 401) return showGate();
    Swal.fire({ icon: "error", title: "No se pudo cambiar", text: err.message });
  } finally { e.target.disabled = false; }
};
$("mp-disconnect").onclick = async () => {
  if (!await confirmAction({ title: "¿Desconectar Mercado Pago?", text: "Tus clientes dejan de poder pagar online y los pedidos vuelven a ir por WhatsApp. Los pedidos pagados quedan en la lista.", confirm: "Desconectar" })) return;
  try {
    status.mercadopago = await api("/api/admin/mercadopago", { method: "DELETE" });
    renderMp();
  } catch (err) {
    if (err.status === 401) return showGate();
    Swal.fire({ icon: "error", title: "No se pudo desconectar", text: err.message });
  }
};
// vuelta desde Mercado Pago: /{slug}/admin?mp=ok|denied|error
{
  const p = new URLSearchParams(location.search), result = p.get("mp");
  if (result) {
    history.replaceState(null, "", location.pathname);
    if (result === "ok") toast.fire({ icon: "success", title: "Mercado Pago conectado. Prendé Cobrar online para empezar." });
    else Swal.fire({ icon: result === "denied" ? "info" : "error", title: result === "denied" ? "No se conectó Mercado Pago" : "No se pudo conectar Mercado Pago",
                     text: result === "denied" ? "Cancelaste la autorización en Mercado Pago." : p.get("msg") || "Probá de nuevo." });
  }
}

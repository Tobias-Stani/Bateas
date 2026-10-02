// Plan Gratis/Premium: barra del plan, paneles bloqueados y pedido de Premium.

// --- plan ---
function renderPlan() {
  const p = status.plan, bar = $("plan-bar");
  bar.hidden = false;
  bar.classList.toggle("premium", p.plan === "premium");
  if (p.plan === "premium") {
    bar.innerHTML = `<b>Plan Premium</b><span class="meter">Sin límites${p.premium_until ? ` · hasta el ${esc(fmtDate(p.premium_until))}` : ""}</span>`;
    return;
  }
  const meter = (k, one, many) => {
    const used = p.usage[k], top = p.limits[k];
    return `<span class="meter ${used >= top ? "full" : ""}">${num(used)} de ${num(top)} ${top === 1 ? one : many}</span>`;
  };
  bar.innerHTML = `<b>Plan Gratis</b>${meter("discs", "disco", "discos")}${meter("banners", "banner", "banners")}${meter("sections", "sección", "secciones")}
    ${p.requested_at ? `<span class="sent">Pediste Premium ✓ Te contactamos</span>` : `<button id="go-premium" class="btn btn-sm btn-premium">Pasate a Premium</button>`}`;
}

// --- pasarse a Premium: por ahora es un pedido que el super admin activa; con la suscripción, va directo a pagar ---
async function showPremium(reason = "") {
  const p = status.plan, row = (what, free, premium) => `<tr><td>${what}</td><td>${free}</td><td>${premium}</td></tr>`;
  const r = await Swal.fire({
    title: "Pasate a Premium",
    html: `${reason ? `<p style="margin-bottom:12px"><b>${esc(reason)}</b></p>` : ""}<p style="margin-bottom:12px">Sin límites para tu catálogo ni tu portada.</p>
      <table class="compare">
        <thead><tr><th></th><th>Gratis (hoy)</th><th>Premium</th></tr></thead>
        <tbody>
          ${row("Discos", `hasta ${p.limits.discs} <small>(usás ${num(p.usage.discs)})</small>`, "Ilimitados")}
          ${row("Banners", `${p.limits.banners} <small>(usás ${num(p.usage.banners)})</small>`, "Ilimitados")}
          ${row("Secciones", `${p.limits.sections} <small>(usás ${num(p.usage.sections)})</small>`, "Ilimitadas")}
          ${row("Importar desde Discogs", "—", "Sí")}
          ${row("Cobro online con Mercado Pago", "—", "Pronto")}
        </tbody>
      </table>
      <p class="premium-price"><strong>$ ${num(p.price)}</strong> por mes</p>`,
    showCancelButton: true, confirmButtonText: "Quiero Premium", cancelButtonText: "Ahora no", reverseButtons: true,
    customClass: { confirmButton: "btn-premium" },
  });
  if (!r.isConfirmed) return;
  if (status.plan.requested_at) return Swal.fire({ icon: "info", title: "Ya recibimos tu pedido", text: "Te contactamos en las próximas horas para activar Premium." });
  try {
    status.plan = await api("/api/admin/premium", { method: "POST" });
    renderPlan();
    Swal.fire({ icon: "success", title: "¡Listo! Recibimos tu pedido", text: "Te contactamos en las próximas horas para activar Premium. Mientras tanto, seguí usando tu tienda como siempre." });
  } catch (err) {
    if (err.status === 401) return showGate();
    Swal.fire({ icon: "error", title: "No se pudo enviar el pedido", text: err.message });
  }
}
$("plan-bar").onclick = e => { if (e.target.id === "go-premium") showPremium(); };
// botones "Pasate a Premium" de los paneles bloqueados
document.addEventListener("click", e => { if (e.target.closest("[data-premium]")) showPremium(); });

const isPremium = () => status.plan.plan === "premium";
// bloquea (o desbloquea) un panel: queda visible pero borroso, sin poder tocarlo, con el mensaje y el botón encima
function lockPanel(panel, text, cta = true) {
  panel.querySelector(":scope > .lock")?.remove();
  panel.classList.toggle("locked", !!text);
  for (const child of panel.children) if (child.tagName !== "H2") child.inert = !!text;
  if (!text) return;
  panel.insertAdjacentHTML("beforeend", `<div class="lock"><b>${esc(text)}</b>
    ${cta ? `<span class="hint">Pasate a Premium por $ ${num(status.plan.price)} por mes y usalo sin límites.</span>
    <button class="btn btn-sm btn-premium" data-premium>Pasate a Premium</button>` : ""}</div>`);
}
// un límite del plan Gratis (403 del servidor): en vez de un error, la invitación a Premium con el motivo
function planBlocked(err) {
  if (err.status !== 403 || !/plan (Gratis|Premium)/.test(err.message)) return false;
  showPremium(err.message);
  return true;
}

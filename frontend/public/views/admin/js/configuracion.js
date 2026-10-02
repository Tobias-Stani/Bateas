// Configuración de la tienda: cierre de la lista, código de acceso, tienda pública y WhatsApp.

// --- cierre de la lista ---
$("close-at").oninput = () => { $("close-error").textContent = ""; $("close-at").removeAttribute("aria-invalid"); };
async function saveClose(value, message) {
  try {
    const r = await api("/api/admin/closes_at", { method: "PUT", body: { value } });
    Object.assign(status, { closes_at: r.closes_at, closed: r.closed });
    renderClose();
    toast.fire({ icon: "success", title: message });
  } catch (err) {
    if (err.status === 401) return showGate();
    $("close-error").textContent = err.message;
  }
}
$("close-form").onsubmit = async e => {
  e.preventDefault();
  const input = $("close-at");
  if (!input.value) { $("close-error").textContent = "Elegí una fecha y hora."; input.setAttribute("aria-invalid", "true"); input.focus(); return; }
  const when = new Date(input.value);
  if (when <= new Date() && !await confirmAction({
    title: "¿Cerrar la tienda ahora?", text: "Esa fecha ya pasó: los clientes no van a poder entrar desde este momento.", confirm: "Cerrar ahora", danger: true,
  })) return;
  saveClose(when.toISOString(), when <= new Date() ? "Tienda cerrada" : "Cierre guardado");
};
$("clear-close").onclick = () => saveClose("", "Fecha de cierre quitada: la tienda queda abierta");

// --- código de acceso ---
$("copy-code").onclick = async () => {
  try { await navigator.clipboard.writeText(status.client_code); toast.fire({ icon: "success", title: "Código copiado" }); }
  catch { toast.fire({ icon: "error", title: "No se pudo copiar" }); }
};
$("new-code").oninput = () => { $("code-error").textContent = ""; $("new-code").removeAttribute("aria-invalid"); };
$("code-form").onsubmit = async e => {
  e.preventDefault();
  const input = $("new-code"), code = input.value.trim();
  const fail = msg => { $("code-error").textContent = msg; input.setAttribute("aria-invalid", "true"); input.focus(); };
  if (code.length < 4) return fail("El código tiene que tener al menos 4 caracteres.");
  if (code === status.client_code) return fail("Ese ya es el código actual.");
  const ok = await confirmAction({ title: "¿Cambiar el código?", text: `El nuevo código va a ser "${code}". Los clientes que ya entraron van a tener que ingresarlo de nuevo.`, confirm: "Cambiar código" });
  if (!ok) return;
  try {
    const r = await api("/api/admin/code", { method: "PUT", body: { value: code } });
    status.client_code = r.client_code;
    input.value = "";
    renderStatus();
    Swal.fire({ icon: "success", title: "Código cambiado", html: `Pasales a tus clientes el código nuevo: <span class="sticker">${esc(r.client_code)}</span>`, confirmButtonText: "Listo" });
  } catch (err) {
    if (err.status === 401) return showGate();
    fail(err.message);
  }
};

// --- tienda pública o con código ---
function renderCodeRequired() {
  const on = status.code_required;
  $("code-required").checked = on;
  $("code-required").setAttribute("aria-checked", on);
  $("code-required-hint").textContent = on ? "Solo entran los clientes que tienen el código." : "Apagado: la tienda es pública.";
  $("public-note").hidden = on;
  $("code-box").classList.toggle("code-off", !on);  // el código queda guardado para cuando lo vuelvas a prender
  $("code-box").inert = !on;
}
$("code-required").onchange = async e => {
  const on = e.target.checked;
  if (!on && !await confirmAction({ title: "¿Hacer pública la tienda?", text: "Cualquiera con el link va a poder ver el catálogo y armar pedidos, sin código. Podés volver a pedirlo cuando quieras.", confirm: "Hacer pública" })) {
    e.target.checked = true;
    return;
  }
  e.target.disabled = true;
  try {
    status.code_required = (await api("/api/admin/code_required", { method: "PUT", body: { value: on } })).code_required;
    renderCodeRequired();
    toast.fire({ icon: "success", title: on ? "Ahora se pide el código" : "La tienda es pública" });
  } catch (err) {
    e.target.checked = !on;
    if (err.status === 401) return showGate();
    Swal.fire({ icon: "error", title: "No se pudo cambiar", text: err.message });
  } finally { e.target.disabled = false; }
};

// --- whatsapp ---
$("new-wa").oninput = () => { $("wa-error").textContent = ""; $("new-wa").removeAttribute("aria-invalid"); };
$("wa-form").onsubmit = async e => {
  e.preventDefault();
  const input = $("new-wa"), number = input.value.replace(/\D/g, "");
  const fail = msg => { $("wa-error").textContent = msg; input.setAttribute("aria-invalid", "true"); input.focus(); };
  if (number.length < 8 || number.length > 15) return fail("Escribí el número completo, con código de país y de área.");
  if (number === status.whatsapp) return fail("Ese ya es el número actual.");
  try {
    const r = await api("/api/admin/whatsapp", { method: "PUT", body: { value: number } });
    status.whatsapp = r.whatsapp;
    input.value = "";
    renderStatus();
    toast.fire({ icon: "success", title: `Los pedidos llegan a +${r.whatsapp}` });
  } catch (err) {
    if (err.status === 401) return showGate();
    fail(err.message);
  }
};


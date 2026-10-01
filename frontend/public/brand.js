// marca blanca: nombre, logo, colores, WhatsApp y mensaje de cada disquería vienen de /api/t/{slug}/brand
const BRAND = { name: "", logo: "/logo.svg", whatsapp: "", accent: "", highlight: "", message: "{discos}", message_line: "#{id} - {artist} – {title}", custom_columns: [] };

document.querySelectorAll("a[data-link]").forEach(a => { a.href = `/${TENANT}${a.dataset.link}`; });

function blockPage(message) {
  document.title = "Tienda no disponible";
  document.body.innerHTML = `<section class="gate"><div class="gate-box">
    <img class="logo" src="/logo.svg" alt=""><h1>Tienda no disponible</h1><p class="lead">${message}</p></div></section>`;
  return false;
}

// resuelve false si la disquería no existe, está suspendida o cancelada: la página no sigue cargando
const brandReady = api("/api/brand").then(b => {
  Object.assign(BRAND, b);
  // el super admin pasa el bloqueo en la API, pero la tienda tiene que mostrarle lo mismo que ven los clientes
  const isAdmin = location.pathname.split("/")[2] === "admin";
  if (!isAdmin && BRAND.status !== "active") {
    const state = BRAND.status === "suspended" ? "suspendida" : "cancelada";
    return blockPage(`Esta tienda está ${state}; así la ven los clientes.<br><br>Como super admin podés entrar a su <a href="/${esc(TENANT)}/admin">admin</a>.`);
  }
  const root = document.documentElement.style;
  if (BRAND.accent) root.setProperty("--accent", BRAND.accent);
  if (BRAND.highlight) root.setProperty("--highlight", BRAND.highlight);
  document.title = document.title.replace("Tienda de discos", BRAND.name);
  document.querySelectorAll("[data-brand]").forEach(el => { el.textContent = BRAND.name; });
  document.querySelectorAll("img[data-brand-logo]").forEach(img => {
    img.src = BRAND.logo;
    if (img.alt) img.alt = BRAND.name;
  });
  document.querySelector("link[rel=icon]").href = BRAND.logo;
  return true;
}).catch(e => {
  if (![404, 410, 423].includes(e.status)) return true;  // error de red: la página igual intenta cargar
  return blockPage(esc(e.message));
});

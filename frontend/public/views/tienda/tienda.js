// Tienda pública de una disquería: portada, catálogo, pedido y pago.

let page = 1, pages = 1, items = [], cart = [];
const CART = `cart:${TENANT}`;  // un pedido por disquería
try { cart = JSON.parse(localStorage.getItem(CART)) || []; } catch {}

const fmt = d => [d.media, d.description].filter(Boolean).join(" ");
const inCart = d => cart.some(c => c.id === d.id);

function renderCart() {
  try { localStorage.setItem(CART, JSON.stringify(cart)); } catch {}
  $("count").textContent = $("count-bar").textContent = cart.length;
  $("cart-empty").hidden = cart.length > 0;
  $("wa").disabled = $("copy").disabled = !cart.length;
  // pago online: solo si la disquería lo prendió y todos los discos tienen precio en pesos
  const unpriced = cart.filter(d => !/^\d+(\.\d+)?$/.test(d.price || ""));
  $("pay").hidden = !BRAND.payments;
  $("pay").disabled = !cart.length || unpriced.length > 0;
  $("pay-note").hidden = !BRAND.payments || !unpriced.length;
  $("pay-note").textContent = unpriced.length === 1 ? `#${unpriced[0].id} no tiene precio: quitalo para pagar online, o consultá por WhatsApp.`
    : `${unpriced.length} discos no tienen precio: quitalos para pagar online, o consultá por WhatsApp.`;
  $("wa").textContent = BRAND.payments ? "Consultar por WhatsApp" : "Consultar cotización";
  $("empty").hidden = !cart.length;
  remember(cart);
  $("cart-items").innerHTML = cart.map((d, i) => `
    <li><button class="cart-disc" data-disc="${d.id}" aria-label="Ver ficha de ${esc(d.title)}"><span class="sticker">#${d.id}</span> <b>${esc(d.artist)}</b><small>${esc(d.title)}, ${esc(fmt(d))}${d.price ? ` · ${esc(fmtPrice(d.price))}` : ""}</small></button>
    <button class="btn-text danger" data-rm="${i}" aria-label="Quitar ${esc(d.title)}">Quitar</button></li>`).join("");
}

function renderList() {
  if (!items.length) {
    const filtered = $("q").value || $("media").value || $("genre").value;
    $("list").innerHTML = `<div class="empty">${filtered
      ? `<h3>No encontramos discos con esa búsqueda</h3><p class="hint">Probá con menos palabras o quitá los filtros.</p>`
      : `<h3>Todavía no hay catálogo cargado</h3><p class="hint">La disquería lo sube cuando llega la lista del mes.</p>`}</div>`;
    return;
  }
  $("list").innerHTML = items.map((d, i) => card(d, `data-add="${i}"`)).join("");
  loadCovers([...(homeHidden ? [] : shelves.flatMap(sh => sh.items)), ...items]);
}

// --- portada ---
let homeBlocks = [{ type: "catalog" }], shelves = [], heroes = [], homeHidden = false;
async function loadHome() {
  try { homeBlocks = (await api("/api/portada")).blocks; } catch { homeBlocks = [{ type: "catalog" }]; }
  shelves = homeBlocks.filter(b => b.type === "section");
  heroes.forEach(h => clearInterval(h.timer));
  heroes = homeBlocks.filter(b => b.type === "banners").map(b => ({ banners: b.banners, at: 0, timer: null }));
  // un lugar por bloque, en el orden de la disquería; el catálogo es el mismo nodo de siempre, se mueve
  let hi = 0;
  $("home").innerHTML = homeBlocks.map(b => b.type === "section"
    ? `<div class="home-block" data-block="section" data-shelf-slot="${shelves.indexOf(b)}"></div>`
    : b.type === "banners" ? `<div class="home-block" data-block="banners" data-hero-slot="${hi++}"></div>`
    : `<div class="home-block" data-block="${b.type}"></div>`).join("");
  $("home").querySelector('[data-block="catalog"]').append($("catalog"));
  renderBanners();
  renderSections();
}

// --- banners: cada bloque es un slider independiente ---
function renderBanners() {
  heroes.forEach((h, hi) => {
    const slot = $("home").querySelector(`[data-hero-slot="${hi}"]`), many = h.banners.length > 1;
    slot.innerHTML = `<div class="hero" data-hero-i="${hi}" aria-roledescription="carrusel" aria-label="Destacados">
      <div class="hero-track">${h.banners.map((b, i) => `
        <div class="hero-slide" aria-roledescription="diapositiva" aria-label="${i + 1} de ${h.banners.length}" ${i ? 'aria-hidden="true"' : ""}>
          <img src="${esc(b.url)}" alt="${esc(b.title)}" ${i || hi ? 'loading="lazy"' : ""}>
          ${b.title || b.text || b.button_link ? `<div class="hero-copy">
            ${b.title ? `<h2>${esc(b.title)}</h2>` : ""}${b.text ? `<p>${esc(b.text)}</p>` : ""}
            ${b.button_link ? (b.button_link.startsWith("https://")
              ? `<a class="btn hero-btn" href="${esc(b.button_link)}" target="_blank" rel="noopener">${esc(b.button_label)}</a>`
              : `<button class="btn hero-btn" data-go="${esc(b.button_link)}">${esc(b.button_label)}</button>`) : ""}
          </div>` : ""}
        </div>`).join("")}</div>
      ${many ? `<button class="hero-nav prev" data-hero="-1" aria-label="Anterior">‹</button><button class="hero-nav next" data-hero="1" aria-label="Siguiente">›</button>
        <div class="hero-dots">${h.banners.map((_, i) => `<button data-hero-to="${i}" aria-label="Ir al ${i + 1}"></button>`).join("")}</div>` : ""}
    </div>`;
    const hero = slot.querySelector(".hero");
    hero.onmouseenter = hero.onfocusin = () => clearInterval(h.timer);
    hero.onmouseleave = hero.onfocusout = () => startHero(hi);
    showHero(hi, 0);
    startHero(hi);
  });
}
function showHero(hi, i) {
  const h = heroes[hi], el = $("home").querySelector(`[data-hero-i="${hi}"]`);
  if (!h || !el) return;
  h.at = (i + h.banners.length) % h.banners.length;
  el.querySelector(".hero-track").style.transform = `translateX(-${h.at * 100}%)`;
  el.querySelectorAll(".hero-slide").forEach((s, j) => s.setAttribute("aria-hidden", j !== h.at));
  el.querySelectorAll("[data-hero-to]").forEach((d, j) => d.setAttribute("aria-current", j === h.at));
}
function startHero(hi) {
  const h = heroes[hi];
  clearInterval(h.timer);
  if (h.banners.length > 1 && !matchMedia("(prefers-reduced-motion: reduce)").matches)
    h.timer = setInterval(() => showHero(hi, h.at + 1), 6000);
}

// tarjeta de un disco: la usan las secciones y el catálogo; addAttr dice a qué lista pertenece el botón
function card(d, addAttr) {
  known.set(d.id, d);
  const on = inCart(d);
  const meta = [fmt(d), [d.label, d.genre].filter(Boolean).join(" — "), d.origin, ...Object.entries(d.extra || {}).map(([k, v]) => `${k}: ${v}`)].filter(Boolean);
  return `<article class="card ${on ? "in" : ""}">
    <div class="sleeve" data-sleeve="${d.id}"><img alt=""><span class="sticker">#${d.id}</span>
      <button class="card-play" data-listen="${d.id}" data-artist="${esc(d.artist)}" data-title="${esc(d.title)}" aria-label="Escuchar ${esc(d.title)}" ${albums.has(d.id) ? "" : "hidden"}>▶</button></div>
    <button class="c-open" data-disc="${d.id}"><span class="c-artist">${esc(d.artist)}</span><span class="c-title">${esc(d.title)}</span></button>
    ${d.price ? `<span class="price">${esc(fmtPrice(d.price))}</span>` : ""}
    <div class="c-meta">${meta.map(esc).join("<br>")}</div>
    <a class="c-yt" href="https://www.youtube.com/results?search_query=${encodeURIComponent(cleanArtist(d.artist) + " " + cleanTitle(d.title))}" target="_blank" rel="noopener">Buscar en YouTube</a>
    <button class="btn btn-sm" ${addAttr} aria-pressed="${on}">${on ? "Agregado ✓" : "Agregar"}</button>
  </article>`;
}
function renderSections() {
  // re-pintar no tiene que mover el carrusel que el cliente estaba mirando
  const scroll = shelves.map((_, si) => document.getElementById(`shelf-${si}`)?.scrollLeft || 0);
  shelves.forEach((sh, si) => {
    const slot = $("home").querySelector(`[data-shelf-slot="${si}"]`);
    if (slot) slot.innerHTML = shelfHtml(sh, si);
  });
  document.querySelectorAll(".shelf-track").forEach(el => {
    const si = +el.id.split("-")[1];
    el.style.scrollBehavior = "auto"; el.scrollLeft = scroll[si] || 0; el.style.scrollBehavior = "";
  });
  syncShelfNav();
  shelves.forEach(sh => sh.items.forEach(d => applyCover(d.id)));
}
function shelfHtml(sh, si) {
  return `
    <section class="shelf" aria-labelledby="shelf-h-${si}">
      <div class="shelf-head">
        <h2 id="shelf-h-${si}">${esc(sh.name)}</h2>
        <button class="shelf-nav" data-scroll="-1" data-shelf="${si}" aria-label="Ver anteriores de ${esc(sh.name)}">‹</button>
        <button class="shelf-nav" data-scroll="1" data-shelf="${si}" aria-label="Ver más de ${esc(sh.name)}">›</button>
      </div>
      <div class="shelf-track" id="shelf-${si}">${sh.items.map((d, i) => card(d, `data-shelf-add="${si}:${i}"`)).join("")}</div>
    </section>`;
}
// las flechas solo si hay más tarjetas de las que entran
function syncShelfNav() {
  document.querySelectorAll(".shelf").forEach(el => {
    const track = el.querySelector(".shelf-track"), fits = track.scrollWidth <= track.clientWidth + 2;
    el.querySelectorAll(".shelf-nav").forEach(b => { b.hidden = fits; });
  });
}
addEventListener("resize", syncShelfNav);
$("home").onclick = e => {
  const hero = e.target.closest("[data-hero]"), dot = e.target.closest("[data-hero-to]"), go = e.target.closest("[data-go]");
  const hi = +e.target.closest("[data-hero-i]")?.dataset.heroI;
  if (hero) return (showHero(hi, heroes[hi].at + +hero.dataset.hero), startHero(hi));
  if (dot) return (showHero(hi, +dot.dataset.heroTo), startHero(hi));
  if (go) {
    // botón del banner: a una sección de la portada o al catálogo
    const link = go.dataset.go, i = shelves.findIndex(sh => `section:${sh.id}` === link);
    const target = link === "catalog" ? $("catalog") : $("home").querySelector(`[data-shelf-slot="${i}"]`);
    return target?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  }
  const nav = e.target.closest("[data-scroll]");
  if (nav) {
    const track = $(`shelf-${nav.dataset.shelf}`);
    return track.scrollBy({ left: +nav.dataset.scroll * track.clientWidth * 0.8 });
  }
  const add = e.target.dataset.shelfAdd;
  if (!add) return;
  const [si, i] = add.split(":").map(Number), d = shelves[si].items[i], at = cart.findIndex(c => c.id === d.id);
  at >= 0 ? cart.splice(at, 1) : cart.push(d);
  renderCart(); renderList(); renderSections();
};

async function search() {
  const params = new URLSearchParams({ q: $("q").value, media: $("media").value, genre: $("genre").value, page, per_page: $("per-page").value });
  $("list").classList.add("loading");
  $("status").textContent = "Buscando…";
  try {
    const data = await api("/api/discos?" + params);
    items = data.items;
    pages = Math.max(1, Math.ceil(data.total / data.page_size));
    const from = data.total ? (page - 1) * data.page_size + 1 : 0;
    $("status").textContent = `Mostrando ${num(from)}–${num(from + items.length - 1 || 0)} de ${num(data.total)} discos`;
    $("pageinfo").textContent = `Página ${page} de ${num(pages)}`;
    $("prev").disabled = page <= 1;
    $("next").disabled = page >= pages;
    const filtered = $("q").value || $("media").value || $("genre").value;
    $("clear").hidden = !filtered;
    // buscando o en otra página: solo el catálogo
    homeHidden = !!filtered || page > 1;
    document.querySelectorAll('.home-block:not([data-block="catalog"])').forEach(el => { el.hidden = homeHidden; });
    renderList();
    renderCart();
  } catch (e) {
    if (e.status === 401 || e.status === 403) return lockOut(e);
    $("status").textContent = e.message;
  } finally {
    $("list").classList.remove("loading");
  }
}

const message = () => buildMessage(BRAND, cart, BRAND.name);

let estado = {};  // { closes_at, closed }

function showGate() { $("store").hidden = true; $("gate").hidden = false; $("code").focus(); }

function showClosed() {
  $("store").hidden = true;
  $("gate").hidden = false;
  $("login").hidden = $("deadline").hidden = true;
  $("gate-title").textContent = "La lista de este mes ya cerró";
  $("gate-lead").textContent = estado.closes_at
    ? `Cerró el ${fmtDate(estado.closes_at)}. Cuando llegue la lista nueva vas a poder entrar de nuevo.`
    : "Cuando llegue la lista nueva vas a poder entrar de nuevo.";
}

function renderDeadline() {
  const open = estado.closes_at && !estado.closed;
  $("deadline").hidden = $("cart-deadline").hidden = !open;
  if (open) {
    $("deadline").textContent = `Pedidos abiertos hasta el ${fmtDate(estado.closes_at)}.`;
    $("cart-deadline").textContent = `Podés consultar hasta el ${fmtDate(estado.closes_at)}.`;
  }
}

async function loadEstado() {
  try { estado = await api("/api/estado"); } catch { estado = {}; }
  $("logout").hidden = estado.code_required === false;  // tienda pública: no hay de dónde salir
  renderDeadline();
}

// 401 = falta el código, 403 = la lista cerró
async function lockOut(err) {
  if (err.status === 403) { await loadEstado(); return showClosed(); }
  estado.closed ? showClosed() : showGate();
}

async function openStore() {
  const f = await api("/api/filtros");
  for (const k of ["media", "genre"])
    $(k).innerHTML = $(k).options[0].outerHTML + f[k].map(v => `<option>${esc(v)}</option>`).join("");
  $("gate").hidden = true;
  $("store").hidden = false;
  renderCart();
  await loadHome();
  search();
  paymentReturn();
}

$("login").onsubmit = async e => {
  e.preventDefault();
  const btn = e.submitter, code = $("code");
  if (!code.value.trim()) { $("login-error").textContent = "Escribí el código que te pasó la disquería."; code.setAttribute("aria-invalid", "true"); return; }
  setBusy(btn, true, "Entrando…");
  try {
    await api("/api/login", { method: "POST", body: { value: code.value } });
    code.value = "";
    await openStore();
  } catch (err) {
    if (err.status === 403) return lockOut(err);
    $("login-error").textContent = err.message;
    code.setAttribute("aria-invalid", "true");
    code.select();
  } finally { setBusy(btn, false); }
};
$("code").oninput = () => { $("login-error").textContent = ""; $("code").removeAttribute("aria-invalid"); };

$("logout").onclick = async () => { await api("/api/logout", { method: "POST" }); showGate(); };

let t;
$("q").oninput = () => { clearTimeout(t); t = setTimeout(() => { page = 1; search(); }, 300); };
$("media").onchange = $("genre").onchange = $("per-page").onchange = () => { page = 1; search(); };
$("clear").onclick = () => { $("q").value = $("media").value = $("genre").value = ""; page = 1; search(); };
$("prev").onclick = () => { page--; search(); scrollTo({ top: 0 }); };
$("next").onclick = () => { page++; search(); scrollTo({ top: 0 }); };

$("list").onclick = e => {
  const i = e.target.dataset.add;
  if (i === undefined) return;
  const d = items[i], at = cart.findIndex(c => c.id === d.id);
  at >= 0 ? cart.splice(at, 1) : cart.push(d);
  renderCart(); renderList(); renderSections();
};
$("cart-items").onclick = e => {
  const i = e.target.dataset.rm;
  if (i === undefined) return;
  const [removed] = cart.splice(i, 1);
  renderCart(); renderList(); renderSections();
  // deshacer en lugar de confirmar: quitar es barato de revertir
  Swal.fire({ toast: true, position: "bottom", timer: 4000, showConfirmButton: true, confirmButtonText: "Deshacer", text: `Quitaste ${removed.title}` })
    .then(r => { if (r.isConfirmed) { cart.splice(i, 0, removed); renderCart(); renderList(); renderSections(); } });
};
$("empty").onclick = async () => {
  if (await confirmAction({ title: "¿Vaciar el pedido?", text: `Se quitan los ${cart.length} discos que agregaste.`, confirm: "Vaciar pedido" })) {
    cart = []; renderCart(); renderList(); renderSections();
  }
};
$("wa").onclick = () => BRAND.whatsapp
  ? window.open(`https://wa.me/${BRAND.whatsapp}?text=${encodeURIComponent(message())}`, "_blank")
  : Swal.fire({ icon: "info", title: "Falta el WhatsApp de la disquería", text: "Usá Copiar lista y mandásela a la disquería." });
$("pay").onclick = async e => {
  setBusy(e.target, true, "Abriendo Mercado Pago…");
  try { location.href = (await api("/api/pagar", { method: "POST", body: { ids: cart.map(d => d.id) } })).url; }
  catch (err) {
    setBusy(e.target, false);
    if (err.status === 401 || err.status === 403) return lockOut(err);
    Swal.fire({ icon: "error", title: "No se pudo iniciar el pago", text: err.message });
  }
};
// vuelta desde Mercado Pago: /{slug}?pago=success|pending|failure&pedido=N&payment_id=...
async function paymentReturn() {
  const p = new URLSearchParams(location.search), result = p.get("pago"), order = p.get("pedido");
  if (!result || !/^\d+$/.test(order || "")) return;
  history.replaceState(null, "", location.pathname);
  try {
    const o = await api(`/api/pedidos/${order}?payment_id=${encodeURIComponent(p.get("payment_id") || "")}`);
    if (o.status === "approved") {
      cart = []; renderCart(); renderList(); renderSections();
      Swal.fire({ icon: "success", title: `¡Pago aprobado! Pedido #${o.id}`, text: `Pagaste ${fmtPrice(String(o.total))} por ${o.items.length} ${o.items.length === 1 ? "disco" : "discos"}. La disquería ya tiene tu pedido.` });
    } else if (["pending", "in_process", "authorized"].includes(o.status)) {
      Swal.fire({ icon: "info", title: `Pedido #${o.id}: pago pendiente`, text: "Mercado Pago todavía está procesando el pago. Te avisa por mail cuando se acredite." });
    } else {
      Swal.fire({ icon: "error", title: "El pago no se completó", text: "Tu pedido sigue armado: podés intentar de nuevo o consultar por WhatsApp." });
    }
  } catch {
    Swal.fire({ icon: "info", title: "No pudimos confirmar el pago", text: "Si Mercado Pago te lo cobró, la disquería lo va a ver igual. Ante cualquier duda, escribile." });
  }
}

$("copy").onclick = async () => {
  try { await navigator.clipboard.writeText(message()); toast.fire({ icon: "success", title: "Lista copiada" }); }
  catch { toast.fire({ icon: "error", title: "No se pudo copiar. Usá el botón de WhatsApp." }); }
};
$("cart-bar").onclick = () => $("cart").classList.add("open");
$("close-cart").onclick = () => $("cart").classList.remove("open");

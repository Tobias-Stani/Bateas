// Ficha de un disco: se abre tocando el disco en el pedido, el catálogo o una sección.
// Tapa, todos sus datos, escuchar, YouTube y agregar o quitar del pedido. Usa covers.js y player.js.

const known = new Map();  // id -> disco: todos los que se pintaron (catálogo, secciones, pedido)
const remember = list => list.forEach(d => known.set(d.id, d));

document.body.insertAdjacentHTML("beforeend", `
  <dialog id="disc" class="disc" aria-labelledby="disc-title"><div class="disc-box">
    <button id="disc-close" class="disc-x" aria-label="Cerrar">✕</button>
    <div id="disc-body"></div>
  </div></dialog>`);

let discOpen = null;  // el disco que se está mostrando
function renderDisc() {
  const d = discOpen, on = inCart(d), cover = covers.get(d.id);
  const facts = [["Formato", fmt(d)], ["Sello", d.label], ["Género", d.genre], ["Origen", d.origin], ["Código de barras", d.barcode],
                 ...Object.entries(d.extra || {})].filter(([, v]) => v);
  $("disc-body").innerHTML = `
    <div class="disc-cover ${cover ? "has-cover" : ""}">${cover ? `<img src="${esc(cover)}" alt="Tapa de ${esc(d.title)}">` : ""}<span class="sticker">#${d.id}</span></div>
    <div class="disc-info">
      <h2 id="disc-title">${esc(d.title)}</h2>
      <p class="disc-artist">${esc(d.artist)}</p>
      ${d.price ? `<p class="price disc-price">${esc(fmtPrice(d.price))}</p>` : `<p class="hint">Precio a consultar con la disquería.</p>`}
      ${facts.length ? `<dl class="disc-facts">${facts.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>` : ""}
      <div class="disc-actions">
        <button class="btn ${on ? "btn-outline" : ""}" data-disc-toggle>${on ? "Quitar del pedido" : "Agregar al pedido"}</button>
        ${albums.has(d.id) ? `<button class="btn btn-outline" data-disc-listen>▶ Escuchar</button>` : ""}
        <a class="btn-text" href="https://www.youtube.com/results?search_query=${encodeURIComponent(cleanArtist(d.artist) + " " + cleanTitle(d.title))}" target="_blank" rel="noopener">Buscar en YouTube</a>
      </div>
    </div>`;
}

function openDisc(d) {
  if (!d) return;
  discOpen = d;
  renderDisc();
  $("disc").showModal();
  // un disco del pedido puede no estar en pantalla: su tapa todavía no se buscó
  if (!covers.has(d.id)) findCover(d).then(album => {
    covers.set(d.id, album?.cover_medium || null);
    if (album) albums.set(d.id, album.id);
    if (discOpen?.id === d.id) renderDisc();
  }).catch(() => {});
}

$("disc-body").onclick = e => {
  const d = discOpen;
  if (e.target.closest("[data-disc-toggle]")) {
    const at = cart.findIndex(c => c.id === d.id);
    at >= 0 ? cart.splice(at, 1) : cart.push(d);
    renderCart(); renderList(); renderSections(); renderDisc();
    toast.fire({ icon: "success", title: at >= 0 ? "Lo quitaste del pedido" : "Agregado al pedido" });
  }
  if (e.target.closest("[data-disc-listen]")) { $("disc").close(); openPlayer(d.id, d.artist, d.title); }
};
$("disc-close").onclick = () => $("disc").close();
$("disc").onclick = e => { if (e.target === $("disc")) $("disc").close(); };  // clic en el fondo oscuro
document.addEventListener("click", e => {
  const el = e.target.closest("[data-disc]");
  if (el) { e.preventDefault(); openDisc(known.get(+el.dataset.disc)); }
});

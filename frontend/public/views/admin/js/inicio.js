// Buscador de la tabla, bloques desplegables y arranque del panel. Se carga último.

// --- tabla ---
let t;
$("q").oninput = () => { clearTimeout(t); t = setTimeout(() => { page = 1; loadTable(); }, 300); };
$("media").onchange = () => { page = 1; loadTable(); };
$("prev").onclick = () => { page--; loadTable(); };
$("next").onclick = () => { page++; loadTable(); };

// --- bloques desplegables: el estado de cada uno queda en este navegador ---
(() => {
  const KEY = `folded:${TENANT}`, OPEN_BY_DEFAULT = new Set(["h-catalog"]);  // la primera vez, solo el catálogo abierto
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(KEY)); } catch {}
  const save = () => {
    const folded = [...document.querySelectorAll(".panel.folded > h2")].map(h => h.id);
    try { localStorage.setItem(KEY, JSON.stringify(folded)); } catch {}
  };
  document.querySelectorAll("#panel section.panel > h2[id]").forEach(h2 => {
    const panel = h2.parentElement;
    h2.innerHTML = `<button type="button" class="fold" aria-controls="${panel.id || ""}">${h2.innerHTML}</button>`;
    const fold = h2.firstElementChild;
    const set = folded => { panel.classList.toggle("folded", folded); fold.setAttribute("aria-expanded", !folded); };
    set(saved ? saved.includes(h2.id) : !OPEN_BY_DEFAULT.has(h2.id));
    fold.onclick = () => { set(!panel.classList.contains("folded")); save(); };
  });
})();

brandReady.then(ok => ok && openPanel().catch(e => e.status === 401 ? showGate() : Swal.fire({ icon: "error", title: "No se pudo abrir el panel", text: e.message })));

// Tapas desde Deezer, buscadas por el navegador del cliente solo para los discos en pantalla.
// Nada se guarda en el servidor; el caché vive en memoria mientras la pestaña esté abierta.
// Con código de barras se busca primero el disco exacto; si no, por artista y título.
// ponytail: Deezer cubre lo que salió en digital; vinilos raros quedan sin tapa (Discogs si hiciera falta)

const covers = new Map();   // id -> url | null (null = buscado y no encontrado)
const albums = new Map();   // id -> id del álbum en Deezer, para escuchar los temas (player.js)
let coverQueue = [];
const WORKERS = 3;          // Deezer permite ~50 consultas cada 5 s por IP

const norm = s => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
  .replace(/\(.*?\)|\[.*?\]/g, "").replace(/[^a-z0-9]+/g, " ").trim();

// "MURPHY, Peter" -> "Peter Murphy", "MURDER CAPITAL, The" -> "The Murder Capital",
// "X feat Y" -> "X", "MURO/VARIOUS" -> "MURO"
function cleanArtist(a) {
  a = a.split(/\s+(?:feat\.?|ft\.?|featuring)\s+/i)[0].split("/")[0].trim();
  const m = a.match(/^([^,]+),\s*([^,]+)$/);
  return m ? `${m[2]} ${m[1]}` : a;
}
const cleanTitle = t => t.replace(/\(.*?\)|\[.*?\]/g, "").split("/")[0].trim();

// una tapa equivocada es peor que ninguna: artista y título tienen que coincidir
function matches(artist, title, album) {
  const a = norm(artist), t = norm(title), da = norm(album.artist?.name), dt = norm(album.title);
  if (!a || !t || !da || !dt) return false;
  return (a.includes(da) || da.includes(a)) && (t.includes(dt) || dt.includes(t));
}

function jsonp(url) {
  return new Promise((resolve, reject) => {
    const cb = "dz" + Math.random().toString(36).slice(2);
    const s = document.createElement("script");
    const done = () => { window[cb] = () => {}; s.remove(); clearTimeout(timer); };
    const timer = setTimeout(() => { done(); reject(new Error("timeout")); }, 8000);
    window[cb] = data => { done(); resolve(data); };
    s.onerror = () => { done(); reject(new Error("network")); };
    s.src = `${url}${url.includes("?") ? "&" : "?"}output=jsonp&callback=${cb}`;
    document.head.append(s);
  });
}

// "2 Minutos 20 Años No Es Nada (2LP)": sin artista aparte, el texto tiene que contener al artista y al álbum de Deezer
function matchesTogether(text, album) {
  const t = norm(text), da = norm(album.artist?.name), dt = norm(album.title);
  return !!(t && da && dt && t.includes(da) && t.includes(dt));
}

// lo que describe la edición y no el disco: confunde a la búsqueda de Deezer
const EDITION = /\b(limitad[oa]|edici[oó]n|reedici[oó]n|remaster(izado)?|deluxe|vinilo|vinyl|lp|2lp|cd|color|blanco|negro|rojo|azul|transparente|importado|nacional)\b/gi;

async function findCover(d) {
  if (!d.artist) {
    // de lo más completo a lo más corto: el texto, lo que va antes del guion, y sin palabras de edición
    const text = cleanTitle(d.title), main = text.split(/\s[-–]\s/)[0];
    const queries = [...new Set([text, main, main.replace(EDITION, " ").replace(/\s+/g, " ").trim()])].filter(Boolean);
    for (const q of queries) {
      const res = await jsonp(`https://api.deezer.com/search/album?limit=5&q=${encodeURIComponent(q)}`);
      if (res.error) throw new Error(res.error.message);
      const hit = (res.data || []).find(album => matchesTogether(q, album));
      if (hit) return hit;
    }
    // último intento: la búsqueda general (temas) encuentra álbumes que la de álbumes se pierde ("Soda Stereo Signos")
    const q = queries[queries.length - 1];
    const res = await jsonp(`https://api.deezer.com/search?limit=15&q=${encodeURIComponent(q)}`);
    if (res.error) throw new Error(res.error.message);
    const track = (res.data || []).find(t => t.album && matchesTogether(q, { ...t.album, artist: t.artist }));
    return track ? { ...track.album, artist: track.artist } : null;
  }
  const artist = cleanArtist(d.artist), title = cleanTitle(d.title);
  const upc = String(d.barcode || "").replace(/\D/g, "");
  if (upc.length >= 8 && !/^(\d)\1+$/.test(upc)) {  // "000000000000" es relleno, no un código
    const album = await jsonp(`https://api.deezer.com/album/upc:${upc}`);
    if (album.error?.code === 4) throw new Error(album.error.message);  // límite de consultas
    // hay códigos repetidos o mal cargados: el artista tiene que coincidir igual
    const a = norm(artist), da = norm(album.artist?.name);
    if (album.cover_medium && a && da && (a.includes(da) || da.includes(a))) return album;
  }
  const queries = [`artist:"${artist}" album:"${title}"`, `${artist} ${title}`];
  for (const q of queries) {
    const res = await jsonp(`https://api.deezer.com/search/album?limit=5&q=${encodeURIComponent(q)}`);
    if (res.error) throw new Error(res.error.message);  // límite de consultas: no cachear, se reintenta después
    const hit = (res.data || []).find(album => matches(artist, title, album));
    if (hit) return hit;
  }
  return null;
}

function applyCover(id) {
  const url = covers.get(id);
  if (!url) return;
  if (albums.has(id)) document.querySelectorAll(`[data-listen="${id}"]`).forEach(b => { b.hidden = false; });
  document.querySelectorAll(`[data-sleeve="${id}"]`).forEach(el => {
    const img = el.querySelector("img");
    if (img.src === url) return;
    img.onload = () => el.classList.add("has-cover");
    img.src = url;
  });
}

async function coverWorker() {
  while (coverQueue.length) {
    const d = coverQueue.shift();
    if (covers.has(d.id)) { applyCover(d.id); continue; }
    try {
      const album = await findCover(d);
      covers.set(d.id, album?.cover_medium || null);
      if (album) albums.set(d.id, album.id);
      applyCover(d.id);
    }
    catch { /* sin tapa esta vez */ }
  }
}

let coverWorkers = 0;
// llamar después de pintar la lista: reemplaza la cola con los discos en pantalla
function loadCovers(list) {
  list.forEach(d => applyCover(d.id));
  coverQueue = list.filter(d => !covers.has(d.id));
  while (coverWorkers < WORKERS && coverQueue.length) {
    coverWorkers++;
    coverWorker().finally(() => coverWorkers--);
  }
}

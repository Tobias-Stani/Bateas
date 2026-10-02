// Previews de 30 s de Deezer: los temas se piden recién al abrir el reproductor,
// así los links (que Deezer firma con vencimiento) siempre están frescos.
// Necesita covers.js: el álbum es el mismo que se encontró para la tapa.

const audio = new Audio();
const tracksCache = new Map();  // id del álbum en Deezer -> temas
let playerTracks = [], playing = -1;

document.body.insertAdjacentHTML("beforeend", `
  <dialog id="player" class="player" aria-labelledby="player-title"><div class="player-box">
    <header>
      <img id="player-cover" alt="">
      <div><b id="player-title"></b><span id="player-artist"></span></div>
      <button id="player-close" class="player-x" aria-label="Cerrar">✕</button>
    </header>
    <ol id="player-tracks" class="player-tracks"></ol>
    <footer><span>Fragmentos de 30 s · Deezer</span><a id="player-yt" target="_blank" rel="noopener">Completo en YouTube</a></footer>
  </div></dialog>`);

const mmss = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

function renderTracks() {
  $("player-tracks").innerHTML = playerTracks.map((t, i) => `
    <li><button class="${i === playing ? "on" : ""}" data-track="${i}" ${t.preview ? "" : "disabled"}
         aria-label="${i === playing && !audio.paused ? "Pausar" : "Escuchar"} ${esc(t.title)}">
      <span class="ico" aria-hidden="true">${i === playing && !audio.paused ? "❚❚" : "▶"}</span>
      <span class="name">${esc(t.title)}</span><span class="dur">${mmss(t.duration)}</span>
      ${i === playing ? `<span class="bar"><span id="player-progress"></span></span>` : ""}
    </button></li>`).join("");
}

function play(i) {
  if (i === playing) { audio.paused ? audio.play() : audio.pause(); return renderTracks(); }
  playing = i;
  audio.src = playerTracks[i].preview;
  audio.play().catch(() => {});
  renderTracks();
}

async function openPlayer(id, artist, title) {
  const albumId = albums.get(id);
  if (!albumId) return;
  playing = -1; audio.pause();
  $("player-cover").src = covers.get(id) || "/assets/img/logo.svg";
  $("player-title").textContent = title;
  $("player-artist").textContent = artist;
  $("player-yt").href = `https://www.youtube.com/results?search_query=${encodeURIComponent(cleanArtist(artist) + " " + cleanTitle(title))}`;
  $("player-tracks").innerHTML = `<li class="player-msg">Buscando los temas…</li>`;
  $("player").showModal();
  try {
    if (!tracksCache.has(albumId)) {
      const res = await jsonp(`https://api.deezer.com/album/${albumId}/tracks?limit=60`);
      if (res.error) throw new Error(res.error.message);
      tracksCache.set(albumId, res.data || []);
    }
    playerTracks = tracksCache.get(albumId);
    if (!playerTracks.some(t => t.preview)) throw new Error("sin previews");
    renderTracks();
  } catch {
    $("player-tracks").innerHTML = `<li class="player-msg">No pudimos traer los temas. Probá en YouTube.</li>`;
  }
}

audio.ontimeupdate = () => {
  const bar = document.getElementById("player-progress");
  if (bar && audio.duration) bar.style.width = `${(audio.currentTime / audio.duration) * 100}%`;
};
audio.onended = () => {
  const next = playerTracks.findIndex((t, i) => i > playing && t.preview);
  next >= 0 ? play(next) : (playing = -1, renderTracks());
};
$("player-tracks").onclick = e => {
  const b = e.target.closest("[data-track]");
  if (b) play(+b.dataset.track);
};
$("player-close").onclick = () => $("player").close();
$("player").onclose = () => { audio.pause(); playing = -1; };
// clic en el fondo oscuro también cierra
$("player").onclick = e => { if (e.target === $("player")) $("player").close(); };

document.addEventListener("click", e => {
  const b = e.target.closest("[data-listen]");
  if (b) openPlayer(+b.dataset.listen, b.dataset.artist, b.dataset.title);
});

/* ============================================================
   GlassPin — aplikasi frontend (vanilla JS, tanpa emoji)
   ============================================================ */
"use strict";

/* ---------------- utilitas ---------------- */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

const state = {
  mode: "home",           // home | search | explore | saved
  query: "",
  type: "all",
  page: 1,
  items: [],
  loading: false,
  hasMore: true,
  modalIndex: -1,
  saved: JSON.parse(localStorage.getItem("gp_saved") || "[]"),
  liked: JSON.parse(localStorage.getItem("gp_liked") || "[]"),
  history: JSON.parse(localStorage.getItem("gp_history") || "[]"),
};

const TRENDING = [
  "wallpaper keren", "alam indah", "laut biru", "gunung", "seni abstrak",
  "arsitektur modern", "makanan lezat", "kucing", "bunga", "ruang angkasa",
  "mobil keren", "pantai sunset", "hewan lucu", "desain interior", "pemandangan",
];

const keys = {
  get pexels() { return localStorage.getItem("gp_key_pexels") || ""; },
  get pixabay() { return localStorage.getItem("gp_key_pixabay") || ""; },
};

function apiHeaders() {
  const h = {};
  if (keys.pexels) h["X-Pexels-Key"] = keys.pexels;
  if (keys.pixabay) h["X-Pixabay-Key"] = keys.pixabay;
  return h;
}

function toast(msg, icon = "i-check") {
  const box = $("#toasts");
  const t = document.createElement("div");
  t.className = "toast";
  t.innerHTML = `<svg class="ic"><use href="#${icon}"/></svg><span></span>`;
  t.querySelector("span").textContent = msg;
  box.appendChild(t);
  setTimeout(() => { t.classList.add("hide"); setTimeout(() => t.remove(), 450); }, 2800);
}

function saveLocal() {
  localStorage.setItem("gp_saved", JSON.stringify(state.saved));
  localStorage.setItem("gp_liked", JSON.stringify(state.liked));
  localStorage.setItem("gp_history", JSON.stringify(state.history.slice(0, 12)));
}

const isSaved = (id) => state.saved.some((x) => x.id === id);
const isLiked = (id) => state.liked.includes(id);

/* ---------------- data ---------------- */
async function fetchFeed() {
  const url = state.mode === "search"
    ? `/api/search?q=${encodeURIComponent(state.query)}&page=${state.page}&type=${state.type}`
    : `/api/feed?page=${state.page}&type=${state.type}`;
  const r = await fetch(url, { headers: apiHeaders() });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

function uniqueAppend(items) {
  const seen = new Set(state.items.map((x) => x.id));
  for (const it of items) {
    if (it.id && !seen.has(it.id)) {
      seen.add(it.id);
      state.items.push(it);
    }
  }
}

/* ---------------- render kartu ---------------- */
function initials(name) {
  return (name || "?").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
}

function pinCard(item, i) {
  const card = document.createElement("article");
  card.className = "pin-card";
  card.style.animationDelay = `${Math.min(i * 55, 700)}ms`;
  card.dataset.id = item.id;

  const isVid = item.media_type === "video";
  const saved = isSaved(item.id);

  card.innerHTML = `
    <div class="pin-media">
      ${isVid ? `<span class="badge-type"><svg class="ic"><use href="#i-video"/></svg>Video</span>` : ""}
      <img loading="lazy" alt="" src="">
      ${isVid ? `<div class="play-fab"><svg class="ic"><use href="#i-play"/></svg></div>` : ""}
      <div class="pin-veil">
        <div class="pin-top">
          <button class="act-btn js-save ${saved ? "saved" : ""}" data-id="${item.id}">
            <svg class="ic"><use href="#i-bookmark"/></svg>${saved ? "Tersimpan" : "Simpan"}
          </button>
          <button class="act-btn js-download" data-id="${item.id}">
            <svg class="ic"><use href="#i-download"/></svg>Unduh
          </button>
        </div>
        <div class="pin-bottom">
          <div class="pin-title"></div>
          <div class="pin-by">
            <span class="pin-avatar">${initials(item.creator?.name)}</span>
            <span class="by-name"></span>
          </div>
        </div>
      </div>
    </div>`;

  const img = $("img", card);
  img.decoding = "async";
  img.src = item.thumbnail || item.full;
  img.alt = item.title || "Gambar";
  const showImg = () => img.classList.add("loaded");
  img.addEventListener("load", showImg, { once: true });
  img.addEventListener("error", () => {
    showImg();
    img.style.minHeight = "140px"; img.style.opacity = "0.35";
    if (img.src !== item.full && item.full) img.src = item.full;
  });
  if (img.complete && img.naturalWidth > 0) showImg();
  $(".pin-title", card).textContent = item.title || "Tanpa judul";
  $(".by-name", card).textContent = item.creator?.name || "Tidak diketahui";

  card.addEventListener("click", (e) => {
    if (e.target.closest(".js-save")) {
      toggleSave(item, e.target.closest(".js-save"));
      return;
    }
    if (e.target.closest(".js-download")) {
      downloadItem(item);
      return;
    }
    openModal(item.id);
  });

  return card;
}

function renderFeed({ append = false } = {}) {
  const feed = $("#feed");
  if (!append) feed.innerHTML = "";

  const pool = state.mode === "saved" ? state.saved : state.items;
  const frag = document.createDocumentFragment();
  pool.forEach((item, i) => frag.appendChild(pinCard(item, append ? 0 : i)));
  feed.appendChild(frag);

  const empty = $("#emptyState");
  if (pool.length === 0 && !state.loading) {
    empty.hidden = false;
    if (state.mode === "saved") {
      empty.querySelector("h3").textContent = "Belum ada yang tersimpan";
      empty.querySelector("p").innerHTML = "Tekan <em>Simpan</em> pada gambar favoritmu.";
    }
  } else {
    empty.hidden = true;
  }
}

function setSkeleton(on) {
  const box = $("#skeletons");
  if (on && !box.hasChildNodes()) {
    for (let i = 0; i < 10; i++) {
      const s = document.createElement("div");
      s.className = "skel";
      s.style.height = `${180 + Math.round(Math.random() * 190)}px`;
      box.appendChild(s);
    }
  }
  box.hidden = !on;
  $("#loadMore").hidden = on || !state.hasMore || state.mode === "saved";
  $("#endNote").hidden = on || state.hasMore || state.mode === "saved" || state.items.length === 0;
}

async function load({ append = false } = {}) {
  if (state.loading || (state.mode === "saved")) return;
  state.loading = true;
  $("#errorState").hidden = true;
  if (!append) {
    state.page = 1;
    state.hasMore = true;
  }
  setSkeleton(true);
  try {
    const data = await fetchFeed();
    if (!append) state.items = [];
    uniqueAppend(data.items || []);
    if ((data.items || []).length === 0) state.hasMore = false;
    state.loading = false;
    setSkeleton(false);
    renderFeed({ append });
  } catch (err) {
    state.loading = false;
    setSkeleton(false);
    if (state.items.length === 0) {
      $("#errorText").textContent = `Sumber data tidak dapat dihubungi (${err.message}). Coba lagi.`;
      $("#errorState").hidden = false;
    } else {
      toast("Gagal memuat halaman berikutnya", "i-info");
    }
  }
}

/* ---------------- aksi item ---------------- */
function toggleSave(item, btn) {
  const idx = state.saved.findIndex((x) => x.id === item.id);
  if (idx >= 0) {
    state.saved.splice(idx, 1);
    toast("Dihapus dari tersimpan", "i-trash");
  } else {
    state.saved.unshift(item);
    toast("Disimpan ke koleksimu", "i-bookmark");
  }
  saveLocal();
  if (btn) {
    const now = isSaved(item.id);
    btn.classList.toggle("saved", now);
    btn.innerHTML = `<svg class="ic"><use href="#i-bookmark"/></svg>${now ? "Tersimpan" : "Simpan"}`;
  }
  if (state.mode === "saved") renderFeed();
  syncModalButtons();
}

function downloadItem(item) {
  const src = item.full || item.thumbnail;
  if (!src) { toast("Media tidak tersedia", "i-info"); return; }
  const name = (item.title || "glasspin-media").replace(/\s+/g, "_").slice(0, 60);
  const a = document.createElement("a");
  a.href = `/api/download?url=${encodeURIComponent(src)}&filename=${encodeURIComponent(name)}`;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  toast("Pengunduhan dimulai", "i-download");
}

/* ---------------- modal detail ---------------- */
function currentItems() {
  return state.mode === "saved" ? state.saved : state.items;
}

function openModal(id) {
  const items = currentItems();
  const idx = items.findIndex((x) => x.id === id);
  if (idx < 0) return;
  state.modalIndex = idx;
  $("#modalRoot").hidden = false;
  document.body.style.overflow = "hidden";
  renderModal();
}

function closeModal() {
  $("#modalRoot").hidden = true;
  document.body.style.overflow = "";
  state.modalIndex = -1;
  const vid = $("#modalMedia video");
  if (vid) vid.pause();
}

function syncModalButtons() {
  const items = currentItems();
  const item = items[state.modalIndex];
  if (!item) return;
  $("#modalLike").classList.toggle("liked", isLiked(item.id));
  $("#modalSave").classList.toggle("liked", isSaved(item.id));
}

function renderModal() {
  const items = currentItems();
  const item = items[state.modalIndex];
  if (!item) return closeModal();

  const media = $("#modalMedia");
  media.innerHTML = "";
  if (item.media_type === "video") {
    const v = document.createElement("video");
    v.src = item.full;
    v.controls = true; v.autoplay = true; v.playsInline = true;
    v.poster = item.thumbnail || "";
    media.appendChild(v);
  } else {
    const img = document.createElement("img");
    img.src = item.full || item.thumbnail;
    img.alt = item.title || "";
    media.appendChild(img);
  }

  $("#modalTitle").textContent = item.title || "Tanpa judul";
  $("#modalDesc").textContent = item.description || "Tidak ada deskripsi.";
  $("#modalSource").href = item.source?.url || "#";
  $("#modalLike").classList.toggle("liked", isLiked(item.id));
  $("#modalSave").classList.toggle("liked", isSaved(item.id));

  const meta = $("#modalMeta");
  meta.innerHTML = "";
  const rows = [
    ["Jenis", item.media_type === "video" ? "Video" : "Foto"],
    ["Ukuran", item.width && item.height ? `${item.width} x ${item.height} px` : "—"],
    ["Lisensi", item.license || "Lihat sumber"],
    ["Sumber", item.source?.name || "—"],
  ];
  if (item.duration) rows.push(["Durasi", `${item.duration} detik`]);
  if (item.tags?.length) rows.push(["Tag", item.tags.join(", ")]);
  for (const [k, v] of rows) {
    const d = document.createElement("div");
    d.className = "meta-row";
    d.innerHTML = `<span></span><span></span>`;
    d.children[0].textContent = k;
    d.children[1].textContent = v;
    meta.appendChild(d);
  }

  const cr = $("#modalCreator");
  cr.innerHTML = `
    <div class="creator-av">${initials(item.creator?.name)}</div>
    <div>
      <strong></strong>
      <small></small>
    </div>`;
  cr.querySelector("strong").textContent = item.creator?.name || "Tidak diketahui";
  cr.querySelector("small").textContent = "Kreator konten";

  loadComments(item.id);
  $("#modalPrev").hidden = state.modalIndex <= 0;
  $("#modalNext").hidden = state.modalIndex >= items.length - 1;
}

async function loadComments(pinId) {
  const list = $("#commentList");
  list.innerHTML = `<p class="cmt-empty">Memuat komentar...</p>`;
  try {
    const r = await fetch(`/api/comments?pin_id=${encodeURIComponent(pinId)}`);
    const d = await r.json();
    const comments = d.comments || [];
    $("#commentCount").textContent = comments.length;
    if (!comments.length) {
      list.innerHTML = `<p class="cmt-empty">Belum ada komentar. Jadilah yang pertama.</p>`;
      return;
    }
    list.innerHTML = "";
    for (const c of comments) {
      const el = document.createElement("div");
      el.className = "cmt";
      el.innerHTML = `
        <div class="cmt-av">${initials(c.author)}</div>
        <div>
          <strong></strong><time></time>
          <p></p>
        </div>`;
      el.querySelector("strong").textContent = c.author;
      el.querySelector("time").textContent = new Date(c.ts).toLocaleString("id-ID", {
        day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
      });
      el.querySelector("p").textContent = c.text;
      list.appendChild(el);
    }
    list.scrollTop = 0;
  } catch {
    list.innerHTML = `<p class="cmt-empty">Komentar tidak dapat dimuat.</p>`;
  }
}

/* ---------------- navigasi & pencarian ---------------- */
function setMode(mode, query = "") {
  state.mode = mode;
  state.query = query;
  state.page = 1;
  state.hasMore = true;

  $$(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.nav === mode));
  const head = { home: ["Inspirasi untukmu", "Kurasi gambar & video elegan dari sumber terbuka — tanpa login."],
                 search: [`Hasil untuk "${query}"`, "Pilih media favoritmu, unduh, atau tinggalkan komentar."],
                 explore: ["Jelajahi tren", "Koleksi populer yang sedang digemari."],
                 saved: ["Koleksi tersimpan", "Semua yang kamu simpan tersimpan di perangkat ini."] };
  $("#pageTitle").textContent = head[mode][0];
  $("#pageSub").textContent = head[mode][1];

  if (mode === "saved") {
    setSkeleton(false);
    $("#loadMore").hidden = true;
    $("#endNote").hidden = true;
    renderFeed();
    window.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
  load();
}

function doSearch(q) {
  q = (q || "").trim();
  if (!q) return setMode("home");
  $("#searchInput").value = q;
  $("#searchClear").hidden = false;
  state.history = [q, ...state.history.filter((x) => x !== q)].slice(0, 12);
  saveLocal();
  setMode("search", q);
}

/* ---------------- saran pencarian ---------------- */
function renderSuggest(filter = "") {
  const box = $("#suggestBox");
  const f = filter.trim().toLowerCase();
  const pool = [...new Set([...state.history, ...TRENDING])]
    .filter((x) => !f || x.toLowerCase().includes(f))
    .slice(0, 8);
  if (!pool.length) { box.hidden = true; return; }
  box.innerHTML = "";
  for (const s of pool) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "suggest-item";
    const isHist = state.history.includes(s);
    b.innerHTML = `<svg class="ic"><use href="#${isHist ? "i-search" : "i-flame"}"/></svg><span></span>`;
    b.querySelector("span").textContent = s;
    b.addEventListener("click", () => { box.hidden = true; doSearch(s); });
    box.appendChild(b);
  }
  box.hidden = false;
}

/* ---------------- event binding ---------------- */
function bind() {
  // navigasi
  $$(".nav-btn").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.nav)));
  $("#brandHome").addEventListener("click", (e) => { e.preventDefault(); setMode("home"); });

  // pencarian
  $("#searchForm").addEventListener("submit", (e) => {
    e.preventDefault();
    $("#suggestBox").hidden = true;
    doSearch($("#searchInput").value);
  });
  $("#searchInput").addEventListener("input", (e) => {
    $("#searchClear").hidden = !e.target.value;
    renderSuggest(e.target.value);
  });
  $("#searchInput").addEventListener("focus", (e) => renderSuggest(e.target.value));
  $("#searchClear").addEventListener("click", () => {
    $("#searchInput").value = "";
    $("#searchClear").hidden = true;
    $("#suggestBox").hidden = true;
    setMode("home");
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-wrap")) $("#suggestBox").hidden = true;
  });

  // chip jenis
  $$("#typeChips .chip").forEach((c) => c.addEventListener("click", () => {
    $$("#typeChips .chip").forEach((x) => x.classList.remove("active"));
    c.classList.add("active");
    state.type = c.dataset.type;
    if (state.mode === "saved") { renderFeed(); return; }
    load();
  }));

  // chip tren
  const tc = $("#trendChips");
  TRENDING.forEach((t) => {
    const b = document.createElement("button");
    b.className = "chip-soft";
    b.innerHTML = `<svg class="ic"><use href="#i-flame"/></svg><span></span>`;
    b.querySelector("span").textContent = t;
    b.addEventListener("click", () => doSearch(t));
    tc.appendChild(b);
  });

  // load more + infinite scroll
  $("#loadMore").addEventListener("click", () => { state.page += 1; load({ append: true }); });
  $("#retryBtn").addEventListener("click", () => load());
  const io = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && state.hasMore && !state.loading && state.mode !== "saved" && state.items.length) {
      state.page += 1;
      load({ append: true });
    }
  }, { rootMargin: "600px" });
  io.observe($("#sentinel"));

  // modal detail
  $("#modalClose").addEventListener("click", closeModal);
  $("#modalBackdrop").addEventListener("click", closeModal);
  $("#modalPrev").addEventListener("click", () => {
    if (state.modalIndex > 0) { state.modalIndex -= 1; renderModal(); }
  });
  $("#modalNext").addEventListener("click", () => {
    if (state.modalIndex < currentItems().length - 1) { state.modalIndex += 1; renderModal(); }
  });
  $("#modalDownload").addEventListener("click", () => downloadItem(currentItems()[state.modalIndex]));
  $("#modalSave").addEventListener("click", () => {
    const item = currentItems()[state.modalIndex];
    if (item) toggleSave(item);
  });
  $("#modalLike").addEventListener("click", () => {
    const item = currentItems()[state.modalIndex];
    if (!item) return;
    const i = state.liked.indexOf(item.id);
    if (i >= 0) { state.liked.splice(i, 1); toast("Batal menyukai", "i-heart"); }
    else { state.liked.push(item.id); toast("Kamu menyukai ini", "i-heart"); }
    saveLocal();
    syncModalButtons();
  });

  // komentar
  $("#commentForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const item = currentItems()[state.modalIndex];
    if (!item) return;
    const text = $("#commentText").value.trim();
    const author = $("#commentName").value.trim() || "Anonim";
    if (!text) return;
    $("#commentText").value = "";
    try {
      const r = await fetch("/api/comments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin_id: item.id, author, text }),
      });
      if (!r.ok) throw new Error();
      toast("Komentar terkirim", "i-send");
      loadComments(item.id);
    } catch {
      toast("Gagal mengirim komentar", "i-info");
    }
  });

  // keyboard
  document.addEventListener("keydown", (e) => {
    if ($("#modalRoot").hidden) return;
    if (e.key === "Escape") closeModal();
    if (e.key === "ArrowLeft") $("#modalPrev").click();
    if (e.key === "ArrowRight") $("#modalNext").click();
  });

  // pengaturan
  const openSettings = () => {
    $("#keyPexels").value = keys.pexels;
    $("#keyPixabay").value = keys.pixabay;
    const st = $("#apiStatus");
    const n = [keys.pexels && "Pexels", keys.pixabay && "Pixabay"].filter(Boolean).length;
    st.innerHTML = `<svg class="ic"><use href="#i-check"/></svg><span></span>`;
    st.querySelector("span").textContent = n
      ? `${n} API key aktif — hasil pencarian lebih kaya.`
      : "Mode default aktif (Openverse + Wikimedia) tanpa key.";
    $("#settingsRoot").hidden = false;
    document.body.style.overflow = "hidden";
  };
  $("#btnSettings").addEventListener("click", openSettings);
  $$("[data-close-settings]").forEach((b) => b.addEventListener("click", () => {
    $("#settingsRoot").hidden = true;
    document.body.style.overflow = "";
  }));
  $("#saveKeys").addEventListener("click", () => {
    localStorage.setItem("gp_key_pexels", $("#keyPexels").value.trim());
    localStorage.setItem("gp_key_pixabay", $("#keyPixabay").value.trim());
    toast("Pengaturan disimpan", "i-check");
    $("#settingsRoot").hidden = true;
    document.body.style.overflow = "";
    if (state.mode !== "saved") load();
  });
  $("#clearKeys").addEventListener("click", () => {
    localStorage.removeItem("gp_key_pexels");
    localStorage.removeItem("gp_key_pixabay");
    $("#keyPexels").value = "";
    $("#keyPixabay").value = "";
    toast("Key dihapus", "i-trash");
  });
}

/* ---------------- mulai ---------------- */
bind();
load();

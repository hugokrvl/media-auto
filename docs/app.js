// Config Supabase — remplacer par vos vraies valeurs après création du projet
const SUPABASE_URL = "https://knjmhjecrmpummsqiosw.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtuam1oamVjcm1wdW1tc3Fpb3N3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE3MTY0MTQsImV4cCI6MjA5NzI5MjQxNH0.kzcKUb06wgMIV55gtVPzJxyGVKZWjJUDNCU_3JXmmBU";

// ── State ──────────────────────────────────────────────────────────────────
let currentView = "pending";
let allPosts = [];
let filterCat = "";
let filterNetwork = "";

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentView = btn.dataset.view;
      renderPosts();
    });
  });

  document.getElementById("filter-cat").addEventListener("change", e => {
    filterCat = e.target.value;
    renderPosts();
  });
  document.getElementById("filter-network").addEventListener("change", e => {
    filterNetwork = e.target.value;
    renderPosts();
  });

  loadPosts();
});

// ── Data ───────────────────────────────────────────────────────────────────
async function loadPosts() {
  document.getElementById("loading").style.display = "block";
  document.getElementById("posts-grid").innerHTML = "";

  try {
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/posts?select=*&order=relevance_score.desc,created_at.desc`,
      {
        headers: {
          "apikey": SUPABASE_ANON_KEY,
          "Authorization": `Bearer ${SUPABASE_ANON_KEY}`,
        }
      }
    );
    allPosts = await res.json();
    updateStats();
    renderPosts();
  } catch (err) {
    console.error(err);
    document.getElementById("loading").textContent = "Erreur de chargement. Vérifiez la config Supabase.";
  }
}

function updateStats() {
  document.getElementById("count-pending").textContent = allPosts.filter(p => p.status === "pending").length;
  document.getElementById("count-approved").textContent = allPosts.filter(p => p.status === "approved").length;
  document.getElementById("count-posted").textContent = allPosts.filter(p => p.status === "posted").length;
}

// ── Render ─────────────────────────────────────────────────────────────────
function renderPosts() {
  const grid = document.getElementById("posts-grid");
  const empty = document.getElementById("empty-state");
  document.getElementById("loading").style.display = "none";

  let posts = allPosts;

  // Filtre par vue ("pending" regroupe aussi les transcriptions manquantes / en cours)
  if (currentView !== "history") {
    if (currentView === "pending") {
      posts = posts.filter(p => ["pending", "needs_transcript", "to_regenerate"].includes(p.status));
    } else {
      posts = posts.filter(p => p.status === currentView);
    }
  }

  // Filtres supplémentaires
  if (filterCat) posts = posts.filter(p => p.category === filterCat);
  if (filterNetwork) posts = posts.filter(p => p.network === filterNetwork || !p.network);

  grid.innerHTML = "";
  if (!posts.length) {
    empty.style.display = "block";
    return;
  }
  empty.style.display = "none";
  posts.forEach(post => grid.appendChild(makeCard(post)));
}

function makeCard(post) {
  const card = document.createElement("div");
  card.className = `post-card ${post.status}`;
  card.dataset.id = post.id;

  const scoreClass = post.relevance_score >= 8 ? "score-high" : post.relevance_score >= 6 ? "score-mid" : "";
  const catClass = `badge-cat-${post.category || "general"}`;
  const defaultNet = post.network || "instagram";
  const captionKey = `caption_${defaultNet}`;
  const imageKey = `image_${defaultNet}`;

  card.innerHTML = `
    <img class="card-image"
         src="${post[imageKey] || 'https://placehold.co/600x600/141414/FFD700?text=MediaAuto'}"
         alt="${esc(post.article_title)}"
         onclick="openModal('${post.id}')" />
    <div class="card-body">
      <div class="card-meta">
        <span class="badge ${catClass}">${post.category || "—"}</span>
        ${post.is_update ? `<span class="badge badge-update" title="Sujet déjà traité, mais un chiffre/fait a changé">↻ Mise à jour</span>` : ""}
        <span class="badge badge-score ${scoreClass}">${post.relevance_score}/10</span>
        ${post.status !== "pending" ? `<span class="status-badge status-${post.status}">${statusLabel(post.status)}</span>` : ""}
      </div>
      <p class="card-title">${esc(post.article_title)}</p>
      <p class="card-source">📰 ${esc(post.source)}</p>
      <p class="card-caption">${esc((post[captionKey] || "").substring(0, 200))}</p>

      ${post.status === "to_regenerate" ? `
        <div class="regen-pending">⏳ Génération en cours… (≤ 15 min, ou « Run workflow » sur GitHub)</div>
      ` : (post.status === "pending" || post.status === "needs_transcript") ? `
        ${post.status === "needs_transcript" ? transcriptBox(post) : ""}
        <div class="network-select" data-post="${post.id}">
          <button class="net-btn ${defaultNet === "instagram" ? "selected" : ""}" data-net="instagram" onclick="selectNet(this)">Instagram</button>
          <button class="net-btn ${defaultNet === "twitter" ? "selected" : ""}" data-net="twitter" onclick="selectNet(this)">X / Twitter</button>
          <button class="net-btn ${defaultNet === "linkedin" ? "selected" : ""}" data-net="linkedin" onclick="selectNet(this)">LinkedIn</button>
        </div>
        <div class="card-actions">
          <button class="btn-approve" onclick="approvePost('${post.id}', this)">✓ Approuver</button>
          <button class="btn-preview" onclick="openModal('${post.id}')">👁 Voir</button>
          <button class="btn-delete" title="Supprimer définitivement ce post" onclick="deletePost('${post.id}', this)">🗑 Supprimer</button>
        </div>
      ` : `
        <div class="card-actions">
          <button class="btn-preview" style="flex:1" onclick="openModal('${post.id}')">👁 Voir le post</button>
          ${post.status === "approved" ? `<button class="btn-approve" onclick="markPosted('${post.id}', this)">📤 Marquer publié</button>` : ""}
          <button class="btn-delete" title="Supprimer définitivement ce post" onclick="deletePost('${post.id}', this)">🗑</button>
        </div>
      `}
    </div>
  `;
  return card;
}

function statusLabel(s) {
  return {
    pending: "⏳ En attente", approved: "✅ Approuvé", posted: "📤 Publié",
    needs_transcript: "📝 Transcription manquante", to_regenerate: "⏳ Génération…",
  }[s] || s;
}

// Zone de collage de la transcription (vidéo YouTube sans script auto)
function transcriptBox(post) {
  return `
    <div class="transcript-box">
      <p class="tb-label">📝 Transcription manquante — colle le script YouTube pour un post de meilleure qualité (sinon « Approuver » garde la version description).</p>
      ${post.article_url ? `<a class="tb-link" href="${esc(post.article_url)}" target="_blank" rel="noopener">▶ Ouvrir la vidéo sur YouTube</a>` : ""}
      <textarea class="tb-input" id="tb-${post.id}" placeholder="Colle ici la transcription copiée depuis YouTube…"></textarea>
      <button class="btn-generate" onclick="submitTranscript('${post.id}', this)">⚙️ Générer le post</button>
    </div>`;
}

async function submitTranscript(postId, btn) {
  const ta = document.getElementById("tb-" + postId);
  const text = (ta && ta.value || "").trim();
  if (text.length < 50) {
    alert("Colle d'abord la transcription (au moins quelques phrases).");
    return;
  }
  btn.disabled = true;
  btn.textContent = "Envoi…";
  try {
    await supabaseUpdate(postId, { pending_transcript: text, status: "to_regenerate" });
    const post = allPosts.find(p => p.id === postId);
    if (post) { post.status = "to_regenerate"; post.pending_transcript = text; }
    renderPosts();
  } catch (err) {
    btn.disabled = false;
    btn.textContent = "⚙️ Générer le post";
    alert("Erreur : " + err.message);
  }
}

function esc(str) {
  return (str || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

// ── Network selector ────────────────────────────────────────────────────────
function selectNet(btn) {
  const group = btn.closest(".network-select");
  group.querySelectorAll(".net-btn").forEach(b => b.classList.remove("selected"));
  btn.classList.add("selected");

  // Màj caption preview
  const postId = group.dataset.post;
  const net = btn.dataset.net;
  const post = allPosts.find(p => p.id === postId);
  if (!post) return;
  const card = group.closest(".post-card");
  card.querySelector(".card-caption").textContent = (post[`caption_${net}`] || "").substring(0, 200);
  const img = card.querySelector(".card-image");
  img.src = post[`image_${net}`] || img.src;
}

// ── Actions ─────────────────────────────────────────────────────────────────
async function approvePost(postId, btn) {
  const card = btn.closest(".post-card");
  const selectedNet = card.querySelector(".net-btn.selected")?.dataset.net || "instagram";

  btn.disabled = true;
  btn.textContent = "Envoi…";

  try {
    await supabaseUpdate(postId, { status: "approved", network: selectedNet });
    card.classList.remove("pending");
    card.classList.add("approved");
    btn.textContent = "✅ Approuvé";
    const post = allPosts.find(p => p.id === postId);
    if (post) { post.status = "approved"; post.network = selectedNet; }
    updateStats();
  } catch (err) {
    btn.disabled = false;
    btn.textContent = "✓ Approuver";
    alert("Erreur : " + err.message);
  }
}

async function markPosted(postId, btn) {
  btn.disabled = true;
  try {
    await supabaseUpdate(postId, { status: "posted", posted_at: new Date().toISOString() });
    const post = allPosts.find(p => p.id === postId);
    if (post) post.status = "posted";
    updateStats();
    renderPosts();
  } catch (err) {
    btn.disabled = false;
    alert("Erreur : " + err.message);
  }
}

async function supabaseUpdate(id, data) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/posts?id=eq.${id}`, {
    method: "PATCH",
    headers: {
      "apikey": SUPABASE_ANON_KEY,
      "Authorization": `Bearer ${SUPABASE_ANON_KEY}`,
      "Content-Type": "application/json",
      "Prefer": "return=minimal",
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

// Suppression manuelle d'un post (irréversible — confirmation obligatoire)
async function deletePost(postId, btn) {
  const post = allPosts.find(p => p.id === postId);
  const titre = (post && post.article_title) ? post.article_title : "ce post";
  if (!confirm(`Supprimer définitivement ce post ?\n\n« ${titre} »\n\nCette action est irréversible.`)) return;

  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = "…";
  try {
    await supabaseDelete(postId);
    allPosts = allPosts.filter(p => p.id !== postId);
    const card = btn.closest(".post-card");
    if (card) card.remove();
    updateStats();
    // Plus aucune carte affichée → réafficher l'état vide
    if (!document.querySelectorAll("#posts-grid .post-card").length) {
      document.getElementById("empty-state").style.display = "block";
    }
  } catch (err) {
    btn.disabled = false;
    btn.textContent = label;
    alert("Erreur lors de la suppression : " + err.message);
  }
}

async function supabaseDelete(id) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/posts?id=eq.${id}`, {
    method: "DELETE",
    headers: {
      "apikey": SUPABASE_ANON_KEY,
      "Authorization": `Bearer ${SUPABASE_ANON_KEY}`,
      "Prefer": "return=minimal",
    },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

// ── Modal ───────────────────────────────────────────────────────────────────
function openModal(postId) {
  const post = allPosts.find(p => p.id === postId);
  if (!post) return;

  const networks = ["instagram", "twitter", "linkedin"];
  let activeNet = post.network || "instagram";

  function renderModal(net) {
    return `
      <h3 style="font-size:14px;font-weight:700;margin-bottom:12px;line-height:1.4">${esc(post.article_title)}</h3>
      <img src="${post[`image_${net}`] || 'https://placehold.co/600x600/141414/FFD700?text=MediaAuto'}" alt="" />
      <div class="modal-tabs">
        ${networks.map(n => `<button class="modal-tab ${n === net ? "active" : ""}" onclick="switchTab('${postId}','${n}')">${n === "twitter" ? "X / Twitter" : n[0].toUpperCase() + n.slice(1)}</button>`).join("")}
      </div>
      <p class="modal-caption">${esc(post[`caption_${net}`] || "")}</p>
      <p style="font-size:11px;color:var(--text-dim);margin-top:12px">Source : ${esc(post.source)} · Score : ${post.relevance_score}/10</p>
    `;
  }

  document.getElementById("modal-content").innerHTML = renderModal(activeNet);
  document.getElementById("modal").style.display = "flex";

  window._modalPostId = postId;
  window._modalNet = activeNet;
}

function switchTab(postId, net) {
  const post = allPosts.find(p => p.id === postId);
  if (!post) return;
  const mc = document.getElementById("modal-content");
  mc.querySelector("img").src = post[`image_${net}`] || mc.querySelector("img").src;
  mc.querySelector(".modal-caption").textContent = post[`caption_${net}`] || "";
  mc.querySelectorAll(".modal-tab").forEach(t => t.classList.toggle("active", t.textContent.toLowerCase().includes(net) || (net === "twitter" && t.textContent.includes("X"))));
}

function closeModal() {
  document.getElementById("modal").style.display = "none";
}
document.getElementById("modal").addEventListener("click", e => {
  if (e.target === document.getElementById("modal")) closeModal();
});

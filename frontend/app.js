const state = {
  feedId: null,
  minScore: 0.5,
  offset: 0,
  limit: 200,
  total: 0,
};

let currentFetchController = null;

const API_BASE = "http://127.0.0.1:8000";

const DEFAULT_FALLBACK_IMAGE = "/images/fallback-default.jpg";

const FEED_FALLBACKS = {
  "nme.com": "/images/fallback-music.jpg",
  "www.nme.com": "/images/fallback-music.jpg",
  "audiochuck.com": "/images/fallback-podcast.jpg",
  "www.audiochuck.com": "/images/fallback-podcast.jpg",
};

function getHostFromUrl(url) {
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return "";
  }
}

function resolveImageUrl(item) {
  if (item.image_url) return item.image_url;

  const host = getHostFromUrl(item.url || "");
  return FEED_FALLBACKS[host] || DEFAULT_FALLBACK_IMAGE;
}

function applyImageFallback(img, item) {
  img.addEventListener("error", () => {
    img.onerror = null;
    const host = getHostFromUrl(item.url || "");
    img.src = FEED_FALLBACKS[host] || DEFAULT_FALLBACK_IMAGE;
  }, { once: true });
}

async function fetchFeeds() {
  const res = await fetch(`${API_BASE}/api/feeds`);
  if (!res.ok) throw new Error(`Failed to load feeds: HTTP ${res.status}`);
  return res.json();
}

async function populateFeedSelect() {
  const select = document.getElementById("feedSelect");
  try {
    const feeds = await fetchFeeds();
    select.innerHTML = '<option value="">All feeds</option>';

    for (const feed of feeds) {
      const opt = document.createElement("option");
      opt.value = String(feed.id);
      opt.textContent = feed.title || feed.url || `Feed ${feed.id}`;
      select.appendChild(opt);
    }
  } catch (err) {
    console.error(err);
  }
}

function initStateFromUrl() {
  const params = new URLSearchParams(window.location.search);
  state.feedId = params.get("feed_id") || null;
  state.minScore = params.get("min_score") !== null ? parseFloat(params.get("min_score")) : 0.5;
  state.offset = params.get("offset") !== null ? parseInt(params.get("offset"), 10) || 0 : 0;
  state.limit = params.get("limit") !== null ? parseInt(params.get("limit"), 10) || 50 : 50;
}

function updateUrlFromState() {
  const params = new URLSearchParams();

  if (state.feedId) params.set("feed_id", state.feedId);
  if (state.minScore !== null && !Number.isNaN(state.minScore)) params.set("min_score", state.minScore);
  if (state.offset > 0) params.set("offset", state.offset);
  if (state.limit !== 50) params.set("limit", state.limit);

  const newQuery = params.toString();
  const newUrl = newQuery ? `?${newQuery}` : window.location.pathname;
  window.history.replaceState(null, "", newUrl);
}

async function fetchItems() {
  const params = new URLSearchParams();

  if (state.feedId !== null && state.feedId !== "") {
    params.append("feed_id", state.feedId);
  }
  if (state.minScore !== null && !Number.isNaN(state.minScore)) {
    params.append("min_score", state.minScore);
  }

  params.append("offset", state.offset);
  params.append("limit", state.limit);

  const url = `${API_BASE}/api/items?${params.toString()}`;
  const statusEl = document.getElementById("status");

  if (currentFetchController) {
    currentFetchController.abort();
  }

  currentFetchController = new AbortController();
  const { signal } = currentFetchController;

  statusEl.textContent = "Loading...";

  try {
    const res = await fetch(url, { signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const data = await res.json();

    state.total = data.total;
    state.offset = data.offset;
    state.limit = data.limit;

    const itemsWithImages = data.items.filter(item => item.image_url != null);

    renderGallery(data.items);
    renderPaginationInfo();
    statusEl.textContent = `Loaded ${data.items.length} items on this page`;
      } catch (err) {
        if (err.name === "AbortError") {
          return;
        }
        console.error(err);
        statusEl.textContent = `Error loading items: ${err.message}`;
      }
    }

function estimateHeightFromTitle(title = "") {
  const len = title.length;
  if (len < 35) return 220;
  if (len < 70) return 280;
  if (len < 110) return 340;
  return 420;
}

function createPlaceholder(item) {
  const wrapper = document.createElement("div");
  wrapper.className = "tile-placeholder";
  wrapper.style.minHeight = `${estimateHeightFromTitle(item.title)}px`;

  const badge = document.createElement("span");
  badge.textContent = "RSS";
  wrapper.appendChild(badge);

  return wrapper;
}

function renderGallery(items) {
  const gallery = document.getElementById("gallery");
  gallery.innerHTML = "";

  if (!items.length) {
    gallery.innerHTML = `<div class="empty">No items found for the current filters.</div>`;
    return;
  }

  const fragment = document.createDocumentFragment();

  for (const item of items) {
    const tile = document.createElement(item.url ? "a" : "article");
    tile.className = "tile";

    if (item.url) {
      tile.href = item.url;
      tile.target = "_blank";
      tile.rel = "noopener noreferrer";
    }

    const media = document.createElement("div");
    media.className = "tile-media";

    if (item.image_url) {
      const img = document.createElement("img");
      img.src = item.image_url;
      img.alt = item.title || "RSS item image";
      img.loading = "eager";
      img.width = 640;
      img.height = 360;
      img.style.width = "100%";
      img.style.height = "100%";
      img.style.objectFit = "cover";
      media.appendChild(img);
    } else {
      media.appendChild(createPlaceholder(item));
    }

    const body = document.createElement("div");
    body.className = "tile-body";

    const title = document.createElement("h2");
    title.className = "tile-title";
    title.textContent = item.title || "(no title)";
    body.appendChild(title);

    if (item.summary) {
      const summary = document.createElement("p");
      summary.className = "tile-summary";
      summary.textContent = item.summary.length > 160
        ? item.summary.slice(0, 160) + "..."
        : item.summary;
      body.appendChild(summary);
    }

    const footer = document.createElement("div");
    footer.className = "tile-footer";

    const score = document.createElement("span");
    score.textContent =
      item.relevance_score !== null && item.relevance_score !== undefined
        ? `Score ${Number(item.relevance_score).toFixed(2)}`
        : "Unscored";

    const pub = document.createElement("span");
    pub.textContent = item.published_at
      ? new Date(item.published_at).toLocaleDateString()
      : "-";

    footer.appendChild(score);
    footer.appendChild(pub);
    body.appendChild(footer);

    tile.appendChild(media);
    tile.appendChild(body);
    fragment.appendChild(tile);
  }

  gallery.appendChild(fragment);
}

function renderPaginationInfo() {
  const pageInfo = document.getElementById("pageInfo");
  const prevBtn = document.getElementById("prevBtn");
  const nextBtn = document.getElementById("nextBtn");

  const start = state.total === 0 ? 0 : state.offset + 1;
  const end = Math.min(state.offset + state.limit, state.total);
  const page = Math.floor(state.offset / state.limit) + 1;
  const totalPages = Math.max(1, Math.ceil(state.total / state.limit));

  pageInfo.textContent = `Showing ${start}-${end} of ${state.total} (page ${page}/${totalPages})`;
  prevBtn.disabled = state.offset <= 0;
  nextBtn.disabled = state.offset + state.limit >= state.total;
}

function goToPage(offset) {
  state.offset = offset;
  fetchItems();
}

document.addEventListener("DOMContentLoaded", async () => {
  const minScoreInput = document.getElementById("minScoreInput");
  const feedSelect = document.getElementById("feedSelect");
  const refreshBtn = document.getElementById("refreshBtn");
  const prevBtn = document.getElementById("prevBtn");
  const nextBtn = document.getElementById("nextBtn");

  initStateFromUrl();
  await populateFeedSelect();

  if (state.feedId) feedSelect.value = state.feedId;
  if (state.minScore !== null) minScoreInput.value = state.minScore;

  const reloadWithFilters = () => {
    state.feedId = feedSelect.value || null;
    state.minScore = minScoreInput.value === "" ? null : parseFloat(minScoreInput.value);
    state.offset = 0;
    fetchItems();
  };

  refreshBtn.addEventListener("click", reloadWithFilters);
  feedSelect.addEventListener("change", reloadWithFilters);
  minScoreInput.addEventListener("change", reloadWithFilters);

  prevBtn.addEventListener("click", () => {
    goToPage(Math.max(0, state.offset - state.limit));
  });

  nextBtn.addEventListener("click", () => {
    const newOffset = state.offset + state.limit;
    if (newOffset < state.total) goToPage(newOffset);
  });

  fetchItems();
});
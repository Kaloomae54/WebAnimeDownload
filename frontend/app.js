const state = {
  animes: [],
  currentAnime: null,
  currentSeason: null,
  pendingEpisode: null,
};

const animeGrid = document.getElementById('animeGrid');
const searchInput = document.getElementById('searchInput');
const viewTitle = document.getElementById('viewTitle');
const breadcrumb = document.getElementById('breadcrumb');
const downloadsContainer = document.getElementById('downloads');

const modal = document.getElementById('languageModal');
const modalInfo = document.getElementById('modalInfo');

function cardTemplate(title, image) {
  const card = document.createElement('article');
  card.className = 'card';
  card.innerHTML = `<img src="${image}" alt="${title}"><div class="body">${title}</div>`;
  return card;
}

function renderBreadcrumb() {
  const parts = ['Accueil'];
  if (state.currentAnime) parts.push(state.currentAnime);
  if (state.currentSeason) parts.push(state.currentSeason);
  breadcrumb.textContent = parts.join(' > ');
}

function renderAnimes(items) {
  animeGrid.innerHTML = '';
  items.forEach((anime) => {
    const card = cardTemplate(anime.title, anime.image);
    card.addEventListener('click', () => loadSeasons(anime.title));
    animeGrid.appendChild(card);
  });
}

async function loadAnimes() {
  viewTitle.textContent = 'Accueil';
  state.currentAnime = null;
  state.currentSeason = null;
  renderBreadcrumb();
  const response = await fetch('/api/animes');
  const payload = await response.json();
  state.animes = payload.data || [];
  renderAnimes(state.animes);
}

async function loadSeasons(animeTitle) {
  state.currentAnime = animeTitle;
  state.currentSeason = null;
  renderBreadcrumb();
  viewTitle.textContent = `Saisons - ${animeTitle}`;
  const response = await fetch(`/api/seasons?anime=${encodeURIComponent(animeTitle)}`);
  const payload = await response.json();

  animeGrid.innerHTML = '';
  (payload.data || []).forEach((season) => {
    const title = season.name || 'Season';
    const card = cardTemplate(title, 'https://placehold.co/400x600/111827/f59e0b?text=Season');
    card.addEventListener('click', () => loadEpisodes(animeTitle, title));
    animeGrid.appendChild(card);
  });
}

async function loadEpisodes(animeTitle, seasonName) {
  state.currentAnime = animeTitle;
  state.currentSeason = seasonName;
  renderBreadcrumb();
  viewTitle.textContent = `${animeTitle} - ${seasonName}`;

  const response = await fetch(
    `/api/episodes?anime=${encodeURIComponent(animeTitle)}&season=${encodeURIComponent(seasonName)}`,
  );
  const payload = await response.json();

  animeGrid.innerHTML = '';
  (payload.data || []).forEach((episode) => {
    const number = String(episode);
    const card = cardTemplate(`Épisode ${number}`, 'https://placehold.co/400x600/111827/f59e0b?text=Episode');
    card.addEventListener('click', () => openLanguageModal(number));
    animeGrid.appendChild(card);
  });
}

function openLanguageModal(episode) {
  state.pendingEpisode = episode;
  modalInfo.textContent = `${state.currentAnime} - Épisode ${episode}`;
  modal.classList.remove('hidden');
}

async function startDownload(language) {
  modal.classList.add('hidden');
  const payload = {
    anime: state.currentAnime,
    episode: state.pendingEpisode,
    language,
  };

  const response = await fetch('/api/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    alert('Erreur lors du lancement du téléchargement');
  }
}

function renderDownloads(jobs) {
  downloadsContainer.innerHTML = '';
  jobs
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
    .forEach((job) => {
      const el = document.createElement('article');
      el.className = 'job';
      const logs = (job.logs || []).slice(-4).join('\n');
      el.innerHTML = `
        <strong>${job.anime} - Épisode ${job.episode}</strong>
        <div class="status">${job.status} (${job.progress || 0}%)</div>
        <div class="logs">${logs}</div>
      `;
      downloadsContainer.appendChild(el);
    });
}

async function refreshDownloads() {
  const response = await fetch('/api/download-status');
  const payload = await response.json();
  renderDownloads(payload.data || []);
}

searchInput.addEventListener('input', () => {
  const query = searchInput.value.trim().toLowerCase();
  if (!state.currentAnime) {
    const filtered = state.animes.filter((a) => a.title.toLowerCase().includes(query));
    renderAnimes(filtered);
  }
});

Array.from(document.querySelectorAll('[data-lang]')).forEach((btn) => {
  btn.addEventListener('click', () => startDownload(btn.dataset.lang));
});
document.getElementById('closeModal').addEventListener('click', () => modal.classList.add('hidden'));

loadAnimes();
setInterval(refreshDownloads, 2500);
refreshDownloads();

# AnimeSama Crunchyroll-like Web UI

Interface web full-stack (Flask + frontend vanilla JS) pour parcourir des animés, explorer saisons/épisodes, puis déclencher le script de téléchargement Python existant.

## Architecture

- **Backend Flask** (`backend/app.py`)
  - Proxy vers l'API locale AnimeSama (`/api/loadBaseAnimeData`, `/api/getSerchAnime`)
  - Expose les routes demandées:
    - `GET /api/animes`
    - `GET /api/search?q=...`
    - `GET /api/seasons?anime=...`
    - `GET /api/episodes?anime=...&season=...`
    - `POST /api/download`
    - `GET /api/download-status`
  - Lance `python main.py --url ... --episodes ... --fast --no-mal --player sibnet` côté serveur.
  - Suit les jobs de téléchargement (statut/progression/logs) en mémoire.

- **Frontend** (`frontend/`)
  - UI sombre inspirée streaming (cartes, hover, transitions, responsive).
  - Navigation: Accueil -> Saisons -> Épisodes -> modal choix langue VF/VO.
  - Filtre de recherche instantanée insensible à la casse sur la liste locale.
  - Section **Téléchargements** mise à jour en polling toutes les 2.5s.

## Lancement

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python backend/app.py
```

Application: `http://127.0.0.1:8000`

## Variables d'environnement

- `ANIMESAMA_API_BASE` (défaut: `http://127.0.0.1:5000/api`)
- `DOWNLOADER_SCRIPT` (défaut: `main.py`)
- `REQUEST_TIMEOUT` (défaut: `15`)

## Exemples de réponses JSON

### `GET /api/animes`

```json
{
  "data": [
    {
      "id": 1,
      "title": "One Piece",
      "image": "https://cdn.myanimelist.net/...jpg"
    }
  ]
}
```

### `POST /api/download`

Entrée:

```json
{
  "anime": "One Piece",
  "episode": "12",
  "language": "VF"
}
```

Sortie:

```json
{
  "message": "Download started",
  "job_id": "bfcde8f0-2c7f-4454-8ac4-d879f2e8ca81"
}
```

### `GET /api/download-status`

```json
{
  "data": [
    {
      "id": "...",
      "anime": "One Piece",
      "episode": "12",
      "language": "VF",
      "status": "running",
      "progress": 48,
      "logs": ["..."],
      "created_at": "2026-01-01T12:00:00",
      "finished_at": null,
      "command": "python main.py --url ..."
    }
  ]
}
```

## Notes

- Le backend valide les entrées (`anime`, `episode`, `language`) et remonte les erreurs proprement.
- Les structures JSON AnimeSama pouvant varier selon les versions, le parsing est défensif.

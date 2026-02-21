import os
import threading
import uuid
from datetime import datetime
from subprocess import PIPE, STDOUT, Popen
from typing import Any

import requests
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="../frontend", static_url_path="")

ANIMESAMA_API_BASE = os.getenv("ANIMESAMA_API_BASE", "http://127.0.0.1:5000/api")
DOWNLOADER_SCRIPT = os.getenv("DOWNLOADER_SCRIPT", "main.py")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "15"))

jobs_lock = threading.Lock()
download_jobs: dict[str, dict[str, Any]] = {}


def _safe_get(url: str, params: dict[str, Any] | None = None) -> Any:
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _extract_titles(payload: Any) -> list[str]:
    if isinstance(payload, list):
        titles = []
        for item in payload:
            if isinstance(item, dict) and item.get("title"):
                titles.append(str(item["title"]).strip())
            elif isinstance(item, str):
                titles.append(item.strip())
        return [t for t in titles if t]

    if isinstance(payload, dict):
        candidate_lists = [
            payload.get("data"),
            payload.get("results"),
            payload.get("animes"),
            payload.get("items"),
        ]
        for values in candidate_lists:
            if isinstance(values, list):
                return _extract_titles(values)
    return []


def _normalize_episode_value(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("episode", "number", "id", "title"):
            if key in value and value[key] is not None:
                return str(value[key])
        return str(value)
    return str(value)


def _extract_anime_url(payload: Any) -> str | None:
    if isinstance(payload, dict):
        if isinstance(payload.get("url"), str):
            return payload["url"]
        for key in ("data", "result", "anime", "results"):
            nested = payload.get(key)
            result = _extract_anime_url(nested)
            if result:
                return result
    if isinstance(payload, list):
        for item in payload:
            result = _extract_anime_url(item)
            if result:
                return result
    return None


def _extract_seasons(payload: Any) -> list[dict[str, Any]]:
    seasons: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for key in ("seasons", "saisons", "data", "results"):
            val = payload.get(key)
            if isinstance(val, list):
                for idx, season in enumerate(val, start=1):
                    if isinstance(season, dict):
                        season_name = season.get("name") or season.get("title") or f"Season {idx}"
                        episodes = season.get("episodes") or []
                        seasons.append({"name": season_name, "episodes": episodes})
                    else:
                        seasons.append({"name": str(season), "episodes": []})
                if seasons:
                    return seasons
    return [{"name": "Season 1", "episodes": []}]


def _extract_episodes(payload: Any, season_name: str) -> list[str]:
    seasons = _extract_seasons(payload)
    for season in seasons:
        if str(season.get("name")).lower() == season_name.lower():
            eps = season.get("episodes") or []
            if not eps:
                return [str(i) for i in range(1, 13)]
            return [_normalize_episode_value(ep) for ep in eps]

    return [str(i) for i in range(1, 13)]


def _image_for_title(title: str) -> str:
    try:
        response = requests.get(
            "https://api.jikan.moe/v4/anime",
            params={"q": title, "limit": 1},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        items = data.get("data") if isinstance(data, dict) else None
        if isinstance(items, list) and items:
            first = items[0]
            images = first.get("images", {}) if isinstance(first, dict) else {}
            jpg = images.get("jpg", {}) if isinstance(images, dict) else {}
            image_url = jpg.get("image_url")
            if image_url:
                return image_url
    except Exception:
        pass
    return "https://placehold.co/400x600/111827/f59e0b?text=Anime"


def _run_download_job(job_id: str, anime_title: str, anime_url: str, episode: str) -> None:
    cmd = [
        "python",
        DOWNLOADER_SCRIPT,
        "--url",
        anime_url,
        "--episodes",
        episode,
        "--fast",
        "--no-mal",
        "--player",
        "sibnet",
    ]

    with jobs_lock:
        download_jobs[job_id]["status"] = "running"
        download_jobs[job_id]["command"] = " ".join(cmd)

    try:
        process = Popen(cmd, stdout=PIPE, stderr=STDOUT, text=True)
        for line in iter(process.stdout.readline, ""):
            clean_line = line.strip()
            if not clean_line:
                continue
            with jobs_lock:
                download_jobs[job_id]["logs"].append(clean_line)
                download_jobs[job_id]["progress"] = min(
                    99,
                    download_jobs[job_id]["progress"] + 2,
                )

        return_code = process.wait()
        with jobs_lock:
            if return_code == 0:
                download_jobs[job_id]["status"] = "completed"
                download_jobs[job_id]["progress"] = 100
            else:
                download_jobs[job_id]["status"] = "error"
                download_jobs[job_id]["logs"].append(f"Process failed with exit code {return_code}")

    except Exception as exc:
        with jobs_lock:
            download_jobs[job_id]["status"] = "error"
            download_jobs[job_id]["logs"].append(f"Execution error: {exc}")

    with jobs_lock:
        download_jobs[job_id]["finished_at"] = datetime.utcnow().isoformat()
        download_jobs[job_id]["anime"] = anime_title


@app.get("/")
def index() -> Any:
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/animes")
def animes() -> Any:
    payload = _safe_get(f"{ANIMESAMA_API_BASE}/loadBaseAnimeData")
    titles = _extract_titles(payload)

    data = [
        {
            "id": idx,
            "title": title,
            "image": _image_for_title(title),
        }
        for idx, title in enumerate(titles, start=1)
    ]
    return jsonify({"data": data})


@app.get("/api/search")
def search() -> Any:
    query = request.args.get("q", "").strip().lower()
    payload = _safe_get(f"{ANIMESAMA_API_BASE}/loadBaseAnimeData")
    titles = _extract_titles(payload)
    filtered = [t for t in titles if query in t.lower()]
    return jsonify({"data": filtered})


@app.get("/api/seasons")
def seasons() -> Any:
    anime = request.args.get("anime", "").strip()
    if not anime:
        return jsonify({"error": "anime query parameter is required"}), 400

    payload = _safe_get(f"{ANIMESAMA_API_BASE}/getSerchAnime", params={"q": anime, "l": 1})
    data = _extract_seasons(payload)
    return jsonify({"anime": anime, "data": data})


@app.get("/api/episodes")
def episodes() -> Any:
    anime = request.args.get("anime", "").strip()
    season = request.args.get("season", "Season 1").strip()
    if not anime:
        return jsonify({"error": "anime query parameter is required"}), 400

    payload = _safe_get(f"{ANIMESAMA_API_BASE}/getSerchAnime", params={"q": anime, "l": 1})
    eps = _extract_episodes(payload, season)
    return jsonify({"anime": anime, "season": season, "data": eps})


@app.post("/api/download")
def download() -> Any:
    body = request.get_json(silent=True) or {}
    anime = str(body.get("anime", "")).strip()
    episode = str(body.get("episode", "")).strip()
    language = str(body.get("language", "VF")).strip().upper()

    if not anime or not episode:
        return jsonify({"error": "anime and episode are required"}), 400
    if language not in {"VF", "VO"}:
        return jsonify({"error": "language must be VF or VO"}), 400

    lang_value = 1 if language == "VF" else 2
    payload = _safe_get(f"{ANIMESAMA_API_BASE}/getSerchAnime", params={"q": anime, "l": lang_value})
    anime_url = _extract_anime_url(payload)

    if not anime_url:
        return jsonify({"error": "Unable to extract anime URL from API response"}), 502

    job_id = str(uuid.uuid4())
    with jobs_lock:
        download_jobs[job_id] = {
            "id": job_id,
            "anime": anime,
            "episode": episode,
            "language": language,
            "status": "queued",
            "progress": 0,
            "logs": [f"Queued download for {anime} episode {episode} ({language})"],
            "created_at": datetime.utcnow().isoformat(),
            "finished_at": None,
            "command": None,
        }

    worker = threading.Thread(
        target=_run_download_job,
        args=(job_id, anime, anime_url, episode),
        daemon=True,
    )
    worker.start()

    return jsonify({"message": "Download started", "job_id": job_id})


@app.get("/api/download-status")
def download_status() -> Any:
    job_id = request.args.get("job_id", "").strip()
    with jobs_lock:
        if job_id:
            job = download_jobs.get(job_id)
            if not job:
                return jsonify({"error": "job not found"}), 404
            return jsonify(job)
        return jsonify({"data": list(download_jobs.values())})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

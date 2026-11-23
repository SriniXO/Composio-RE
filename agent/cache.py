"""Disk cache + run log. Every network/LLM call is keyed and stored so runs are resumable and auditable."""
import hashlib, json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
LOGS = ROOT / "logs"
CACHE.mkdir(exist_ok=True)
LOGS.mkdir(exist_ok=True)


def key(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:32]


def get(kind: str, k: str):
    p = CACHE / kind / f"{k}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def put(kind: str, k: str, value) -> None:
    d = CACHE / kind
    d.mkdir(exist_ok=True)
    (d / f"{k}.json").write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def log(run: str, event: dict) -> None:
    event = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), **event}
    with open(LOGS / f"{run}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

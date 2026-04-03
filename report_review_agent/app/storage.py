from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from report_review_agent.app import config


class ReviewStorage:
    def create_workspace(self, original_filename: str) -> tuple[str, Path]:
        review_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:8]
        day_dir = config.OUTPUT_DIR / datetime.now().date().isoformat()
        workspace = day_dir / review_id
        workspace.mkdir(parents=True, exist_ok=True)
        return review_id, workspace

    def save_original(self, workspace: Path, original_filename: str, payload: bytes) -> Path:
        suffix = Path(original_filename).suffix.lower() or ".bin"
        path = workspace / f"source{suffix}"
        path.write_bytes(payload)
        return path

    def resolve_workspace(self, review_id: str) -> Path:
        for day_dir in config.OUTPUT_DIR.iterdir():
            if not day_dir.is_dir():
                continue
            candidate = day_dir / review_id
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Unknown review_id: {review_id}")

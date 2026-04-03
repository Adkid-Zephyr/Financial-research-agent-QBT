from __future__ import annotations

import sys
from pathlib import Path

import uvicorn


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    uvicorn.run(
        "report_review_agent.app.main:create_app",
        factory=True,
        host="127.0.0.1",
        port=8020,
        reload=False,
    )


if __name__ == "__main__":
    main()

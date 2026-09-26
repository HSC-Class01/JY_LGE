"""Sites 배포용 최소 정적 산출물을 dist 폴더에 준비한다."""
from pathlib import Path
from shutil import copy2

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
(DIST / "data").mkdir(parents=True, exist_ok=True)
copy2(ROOT / "index.html", DIST / "index.html")
copy2(ROOT / "dashboard-config.js", DIST / "dashboard-config.js")
copy2(ROOT / "data" / "dashboard.json", DIST / "data" / "dashboard.json")
print(f"Site artifact prepared: {DIST}")

"""Settings from .env, Blender discovery, and where products live."""
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_DIRS = [ROOT / "products", ROOT / "examples"]
BLENDER_CANDIDATES = [
    ROOT / "tools" / "blender" / "blender",
    ROOT / "tools" / "blender" / "Blender.app" / "Contents" / "MacOS" / "Blender",
    Path("/Applications/Blender.app/Contents/MacOS/Blender"),
    Path("/opt/homebrew/bin/blender"),
    Path("/usr/local/bin/blender"),
    Path("/snap/bin/blender"),
]
MIN_BLENDER = (4, 2)


def load_env(path: Path = ROOT / ".env") -> None:
    """Reads KEY=value lines into os.environ without overriding what the shell already set."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def setting(key: str, default: str | None = None) -> str | None:
    load_env()
    return os.environ.get(key) or default


def find_blender() -> Path | None:
    if configured := setting("BLENDER_PATH"):
        return Path(configured) if Path(configured).exists() else None
    for candidate in BLENDER_CANDIDATES:
        if candidate.exists():
            return candidate
    found = shutil.which("blender")
    return Path(found) if found else None


def blender_version(path: Path) -> tuple[int, int, int] | None:
    try:
        out = subprocess.run([str(path), "--version"], capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in out.splitlines():
        if line.startswith("Blender "):
            parts = line.split()[1].split(".")
            return tuple(int(p) for p in (parts + ["0", "0"])[:3])
    return None


def find_product(name_or_path: str, relative_to: Path | None = None) -> Path:
    """A product is a folder with product.json, found by path or by name under products/ then examples/."""
    candidates = [Path(name_or_path)]
    if relative_to:
        candidates.insert(0, relative_to / name_or_path)
    candidates += [d / name_or_path for d in PRODUCT_DIRS]
    for c in candidates:
        if (c / "product.json").exists():
            return c.resolve()
        if c.name == "product.json" and c.exists():
            return c.parent.resolve()
    raise FileNotFoundError(f"no product.json for '{name_or_path}' (looked in products/ and examples/)")

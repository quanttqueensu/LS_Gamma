import argparse
import json
import shutil
from pathlib import Path

from lsgamma.hub.collect import REPO, collect

STATIC = Path(__file__).parent / "static"


def build(out, root=None):
    root, out = Path(root or REPO), Path(out)
    data = collect(root)
    if out.exists():
        if any(out.iterdir()) and not (out / "hub.js").exists():
            raise SystemExit(f"{out} is not empty and not a hub build; pick another --out")
        shutil.rmtree(out)
    shutil.copytree(STATIC, out)
    for name in data.pop("files"):
        dest = out / "files" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, dest)
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    page = out / "index.html"
    page.write_text(page.read_text().replace("{{DATA}}", blob))
    return data["stats"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPO / "_site"))
    out = parser.parse_args().out
    print(f"hub -> {out}: {build(out)}")

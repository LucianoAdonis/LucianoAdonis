"""Rebuild the trophy shelf in README.md from public Credly badges.

Every badge is shown, current ones first. Expired ones keep their color and
say so on hover. Set FADE_EXPIRED = True for the locked-trophy grey look.
Run from the repo root:

    python3 .github/trophies/build.py
"""
import datetime as dt
import io
import json
import pathlib
import re
import time
import urllib.request

from PIL import Image, ImageOps

CREDLY_USER = "luciano-adonis.d4febbaf"
SIZE = 128  # stored size; README shows them at 64px for sharp retina rendering
FADE_EXPIRED = False
EXPIRED_ALPHA = 0.38

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "trophies"
README = ROOT / "README.md"
START, END = "<!-- trophies:start -->", "<!-- trophies:end -->"


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "trophy-shelf"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read()
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]


def render(raw: bytes, expired: bool) -> Image.Image:
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    img.thumbnail((SIZE, SIZE), Image.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(img, ((SIZE - img.width) // 2, (SIZE - img.height) // 2), img)
    if expired and FADE_EXPIRED:
        r, g, b, a = canvas.split()
        grey = ImageOps.grayscale(Image.merge("RGB", (r, g, b)))
        a = a.point(lambda v: int(v * EXPIRED_ALPHA))
        canvas = Image.merge("RGBA", (grey, grey, grey, a))
    return canvas


def main() -> None:
    data = json.loads(fetch(f"https://www.credly.com/users/{CREDLY_USER}/badges.json?per_page=48"))["data"]
    today = dt.date.today().isoformat()
    badges = []
    for b in data:
        if b.get("state") != "accepted":
            continue
        t = b["badge_template"]
        exp = b.get("expires_at_date")
        badges.append({
            "id": b["id"],
            "name": t["name"],
            "issued": b.get("issued_at_date") or "",
            "expires": exp,
            "expired": bool(exp and exp < today),
            "image": b.get("image_url") or t.get("image_url"),
        })
    badges = sorted([x for x in badges if not x["expired"]], key=lambda x: x["issued"], reverse=True) + \
             sorted([x for x in badges if x["expired"]], key=lambda x: x["issued"], reverse=True)

    OUT.mkdir(exist_ok=True)
    keep = set()
    cells = []
    for x in badges:
        fname = f"{slug(x['name'])}.png"
        keep.add(fname)
        render(fetch(x["image"]), x["expired"]).save(OUT / fname, optimize=True)
        year = x["issued"][:4]
        status = f"expired {x['expires'][:4]}" if x["expired"] else f"earned {year}"
        cells.append(
            f'<a href="https://www.credly.com/badges/{x["id"]}/public_url">'
            f'<img src="trophies/{fname}" width="64" height="64" alt="{x["name"]}" title="{x["name"]}, {status}"></a>'
        )
    for f in OUT.glob("*.png"):
        if f.name not in keep:
            f.unlink()

    block = f"{START}\n<p>\n" + "\n".join(cells) + "\n</p>\n" + END
    text = README.read_text()
    if START in text:
        text = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S)
    else:
        text = text.rstrip() + "\n\n**Trophies**\n\n" + block + "\n"
    README.write_text(text)
    print(f"{len(badges)} trophies, {sum(x['expired'] for x in badges)} expired")


if __name__ == "__main__":
    main()

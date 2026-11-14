import hashlib
from pathlib import Path

WIDTH = 340  # px, cards show about 170


def name(rel):
    return "thumbs/" + hashlib.sha1(rel.encode()).hexdigest()[:12] + ".jpg"


def render(pdf, dest):
    # page 1 as JPEG; False if unavailable
    try:
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(str(pdf))
        page = doc[0]
        img = page.render(scale=WIDTH / page.get_width()).to_pil().convert("RGB")
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, "JPEG", quality=78, optimize=True)
        doc.close()
        return True
    except Exception:
        return False


def add(docs, root, out):
    # thumb path per library doc, rendered once
    for d in docs:
        src = d.pop("src", None)
        if src and render(Path(root) / src, Path(out) / name(src)):
            d["thumb"] = name(src)

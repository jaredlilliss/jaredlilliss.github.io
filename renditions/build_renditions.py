# Build the portfolio RENDITIONS.
#
# Jared, 24/08/2026: "do the same renditions for the portfolio and business page".
# Same machinery as the other two sites: ONE content source (../index.html),
# N points of view. Content is never duplicated — edit index.html and every
# rendition picks the change up on the next build.
#
#   <key>.css          REQUIRED  appended after the base <style>, wins by cascade.
#   <key>.scene.html   OPTIONAL  appended before </body>. Additive, never surgical:
#                                a rendition that wants its own hero hides #sky in
#                                CSS and builds its own canvas here, so the base
#                                script (clock, reveals, nav) survives intact.
#
# This machinery lives INSIDE the repo rather than in a private folder on purpose:
# unlike the other two sites the portfolio has no cc-side source of truth, the
# repo IS the source, and `cc` is not a git repo. Keeping the themes here means
# they are versioned with the page they style.
#
# INVARIANT: the verified copy is byte-true in every rendition. The only text a
# rendition may add is its own name tag. Checked after every build.
import io, os, sys, pathlib, tempfile

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent
SRC = ROOT / "index.html"

RENDITIONS = {
    "nightshift": ("theme-nightshift.html", "Night Shift",
                   "The live build. Aurora sky, starfield, an indexed evidence board."),
    "terminal":   ("theme-terminal.html",   "Terminal",
                   "A session that never ended. Phosphor on black, everything monospaced."),
    "fieldnotes": ("theme-fieldnotes.html", "Field Notes",
                   "Graph paper and a pencil. The notebook the work actually starts in."),
    "monolith":   ("theme-monolith.html",   "Monolith",
                   "Type and nothing else. One serif, enormous, almost no chrome."),
}

def atomic_write(path, text):
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)

def build_one(key, html):
    css_path = HERE / (key + ".css")
    if not css_path.is_file():
        sys.exit("MISSING THEME CSS: %s" % css_path)
    css = io.open(css_path, encoding="utf-8").read()

    anchor = "</style>\n</head>"
    if anchor not in html:
        sys.exit("STYLE ANCHOR NOT FOUND")
    out = html.replace(
        anchor,
        '</style>\n<style id="rendition-%s">\n%s\n</style>\n</head>' % (key, css),
        1,
    )

    scene = HERE / (key + ".scene.html")
    if scene.is_file():
        out = out.replace("</body>", io.open(scene, encoding="utf-8").read().strip() + "\n</body>", 1)

    # a rendition must never be mistaken for the live page
    label = RENDITIONS[key][1]
    out = out.replace('<a class="sig" href="/">',
                      '<span class="rendition-tag">%s</span><a class="sig" href="/">' % label, 1)
    # renditions are drafts: keep them out of search and out of social previews
    out = out.replace('<meta name="theme-color"',
                      '<meta name="robots" content="noindex,nofollow">\n<meta name="theme-color"', 1)

    fname = RENDITIONS[key][0]
    atomic_write(ROOT / fname, out)
    return fname, len(out)

def build_chooser(results):
    rows = "\n".join(
        '  <a class="r" href="/%s"><b>%s</b><span>%s</span></a>'
        % (RENDITIONS[k][0], RENDITIONS[k][1], RENDITIONS[k][2])
        for k in RENDITIONS if k in results
    )
    page = """<!doctype html>
<html lang="en-AU"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Portfolio — renditions</title>
<style>
:root{color-scheme:dark}
*{box-sizing:border-box;margin:0;padding:0}
body{background:#05070d;color:#eceff5;font:400 16px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;
  padding:clamp(28px,7vw,80px) clamp(20px,5vw,56px);min-height:100vh}
h1{font-size:clamp(30px,6vw,58px);line-height:1;letter-spacing:-.03em;font-weight:600;margin-bottom:.5rem}
p.lede{color:#8d96aa;max-width:60ch;margin-bottom:2.6rem}
.grid{display:grid;gap:12px;max-width:880px}
a.r{display:block;text-decoration:none;color:inherit;border:1px solid rgba(141,150,170,.22);
  padding:1.1rem 1.25rem;transition:border-color .25s,background .25s}
a.r:hover{border-color:#ff8c4a;background:rgba(255,140,74,.06)}
a.r b{display:block;font-size:1.2rem;font-weight:600;letter-spacing:-.01em}
a.r span{color:#8d96aa;font-size:.94rem}
footer{margin-top:3rem;color:#7b8498;font:400 12.5px/1.7 ui-monospace,Consolas,monospace;max-width:78ch}
</style></head><body>
<h1>Renditions</h1>
<p class="lede">Four takes on the same portfolio. Identical copy, identical projects, identical
receipts &mdash; four different ideas about how the work should look.</p>
<div class="grid">
%s
</div>
<footer>Night Shift is what serves at the root. The other three are drafts and are noindex.
Every rendition carries the verified copy byte for byte &mdash; no percentages, no invented
figures, and the Aussie Health entry keeps its approved phrasing.</footer>
</body></html>
""" % rows
    atomic_write(ROOT / "renditions.html", page)

def verify(html_paths, base):
    """the copy check that matters: only the name tag may differ"""
    import re
    def nodes(p):
        h = io.open(p, encoding="utf-8").read()
        b = re.sub(r'(?is)<(script|style)\b.*?</\1>', ' ', h)
        b = re.sub(r'(?s)<!--.*?-->', ' ', b)
        b = re.sub(r'(?s)<[^>]+>', '\n', b)
        return [re.sub(r'\s+', ' ', x).strip() for x in b.split('\n') if x.strip()]
    ref = nodes(base)
    for p in html_paths:
        got = nodes(p)
        extra = [n for n in got if n not in ref]
        missing = [n for n in ref if n not in got]
        flag = "OK " if (len(extra) <= 1 and not missing) else "!! "
        print("   %s%-26s %d nodes  added=%s  missing=%s"
              % (flag, os.path.basename(p), len(got), extra or "-", missing or "-"))

def main():
    html = io.open(SRC, encoding="utf-8").read()
    only = sys.argv[1:] or list(RENDITIONS)
    results, built = {}, []
    for key in only:
        if key not in RENDITIONS:
            sys.exit("UNKNOWN RENDITION: %s" % key)
        fname, size = build_one(key, html)
        results[key] = size
        built.append(ROOT / fname)
        print("OK %-26s %8s bytes" % (fname, f"{size:,}"))
    if len(results) == len(RENDITIONS):
        build_chooser(results)
        print("OK renditions.html (chooser)")
    print("copy check:")
    verify(built, SRC)

if __name__ == "__main__":
    main()

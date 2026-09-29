# The notes as a website

`build.py` turns the notes in this repo into a static, cross-linked site. Each note gets its own page, each script gets a highlighted page, and each series gets an overview. There is full-text search, and every page has a short reference code.

## Build

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r blog/requirements.txt
python blog/build.py                  # writes blog/site/ (git-ignored)
```

The build fails if any link or `#anchor` in the notes doesn't resolve. It then re-reads its own output and checks every `href` again, so a green build means every cross-reference works.

| Flag | What it does |
|---|---|
| `--share-url URL` | The link the site is published at. Adds **Copy link** buttons that produce `URL#ref` for a page or `URL#ref~section` for a heading or code line |
| `--standalone` | Writes `index.html` as a full HTML document, for hosts other than a Claude artifact (GitHub Pages, `python -m http.server`) |
| `--out DIR` | Output folder (default `blog/site`) |

## What each page has

- **Notes:** the series in the sidebar, an "On this page" contents, previous and next in reading order, and **Linked from**, which lists every other note that cites this one, down to the section.
- **Scripts:** syntax highlighting, line anchors (`#L12`, or a range such as `#L12-L20`; shift-click a line number to select a range), an outline of functions, and **Cited by**.
- **Search** (press `/`): covers every heading, paragraph and code block. Heading and title matches rank first, and results link to the section.
- **Evidence stamps:** CONFIRMED, SUSPECTED and REFUTED render as coloured labels.
- **Reference codes:** each page shows a short code under its title (`p03`, `cs07`, `ex02`, `ev-lazy_snapshot`, …). Adding `#cs04` to the published link opens case study 04, and `#cs04~the-fix` opens its "The fix" section.

## Adding a note

Add the file, then add a row to `SERIES` in `build.py` with the note's reference code, sidebar title and one-line summary. The build refuses notes it doesn't know about. Scripts are picked up automatically; a script without a module docstring needs an entry in `CODE_DESCRIPTIONS`.

## Publishing

The site is published as a private Claude artifact at <https://claude.ai/artifact/W9vGJU3QMTjxBE7Rsj3Fgx> (visible only to its owner until shared from its Share menu). To update it, rebuild with that link so the copy-link buttons keep working:

```bash
python blog/build.py --share-url https://claude.ai/artifact/W9vGJU3QMTjxBE7Rsj3Fgx
```

- **As a Claude artifact:** publish `site/index.html` as the page, with every other file in `site/` alongside it. `index.html` is a page fragment because the artifact host wraps it; `home.html` holds the same content as a full document.
- **Anywhere else:** build with `--standalone` and serve `site/` as static files.

#!/usr/bin/env python3
"""Build the notes into a cross-linked static blog: one page per note, per script and per series.

    pip install -r blog/requirements.txt
    python blog/build.py                    # writes blog/site/
    python blog/build.py --share-url URL    # adds copy-link buttons that produce URL#ref~section
    python blog/build.py --standalone       # index.html as a full HTML document (GitHub Pages etc.)

The build fails on any broken link or anchor, so a green build means every cross-reference resolves.
By default site/index.html is a page fragment (no <html>/<head>), which is what the Claude artifact
host wraps into a page; site/home.html always carries the same content as a full document.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import html
import json
import posixpath
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from pygments.lexers import get_lexer_by_name
from pygments.token import STANDARD_TYPES
from pygments.util import ClassNotFound

REPO = Path(__file__).resolve().parent.parent
SITE = "Lakehouse Casebook"

# ---------------------------------------------------------------------------------------------
# Content map. Series in reading order; each page is (file, ref, nav title, dek). The ref is the
# page's short code (casebook-link#ref opens it); the dek is the one-line summary shown under the
# title and on the contents page. A note that isn't listed here fails the build, so new notes get
# a ref and a dek.
# ---------------------------------------------------------------------------------------------
SERIES = [
    dict(id="playbook", label="Playbook", unit="chapters", dir="playbook", ref="playbook",
         dek="How I work a customer data problem, organised by what the interview assesses.",
         pages=[
             ("00-operating-loop.md", "p00", "00 Operating loop",
              "The nine-step loop from framing a question to shipping code a team can own, with what to say out loud at each step."),
             ("01-computational-thinking.md", "p01", "01 Computational thinking",
              "Grain first, four questions per step, and fifteen transformation patterns that real customer problems decompose into."),
             ("02-code-stewardship.md", "p02", "02 Code stewardship",
              "The method I used to read six unfamiliar repos, the smells that matter in data code, and how to explain execution under the hood."),
             ("03-ai-stewardship.md", "p03", "03 AI stewardship",
              "A prompt skeleton, three levels of checking, red flags, and a catalogue of AI mistakes found in these repos' own guidance."),
             ("04-resilience-and-debugging.md", "p04", "04 Resilience and debugging",
              "The debug loop, the row-count ledger, and a table of Spark and Delta error signatures reproduced on purpose."),
             ("05-execution-and-scaling.md", "p05", "05 Execution and scaling",
              "What actually runs, measured: shuffles, joins, skew, UDF cost, Delta layout, streaming state and hash collisions."),
             ("06-business-translation.md", "p06", "06 Business translation",
              "How to justify logic in business terms, with translations for thirty technical concepts and numbers that land."),
             ("07-null-semantics.md", "p07", "07 NULL semantics",
              "Three-valued logic verified on Spark 4, the patterns that make rules NULL-safe, and how to find NULL bugs."),
         ]),
    dict(id="exercises", label="Exercises", unit="exercises", dir="exercises", ref="exercises",
         dek="Five runnable, customer-shaped problems on PySpark 4 and Delta 4, each with tests and a walkthrough.",
         pages=[
             ("ex01_messy_orders_medallion/WALKTHROUGH.md", "ex01", "01 Messy orders → medallion",
              "Finance and Ops never agree on revenue: a messy order feed turned into bronze, silver and gold you can reconcile."),
             ("ex02_scd2_merge/WALKTHROUGH.md", "ex02", "02 SCD2 with Delta MERGE",
              "Report by segment at the time of sale: SCD2 with Delta MERGE, point-in-time joins, and the lazy-evaluation trap."),
             ("ex03_execution_and_scaling/WALKTHROUGH.md", "ex03", "03 Execution and scaling lab",
              "How does it scale? Shuffles, broadcast versus sort-merge, skew and salting, AQE, UDF cost and pruning, measured."),
             ("ex04_streaming_semantics/WALKTHROUGH.md", "ex04", "04 Streaming semantics",
              "Why the last hour is always missing: checkpoints, watermarks, append mode and stream-static joins."),
             ("ex05_debug_kata/DEBUGGING_LOG.md", "ex05", "05 Debug kata",
              "A green job with wrong numbers: eight planted real-world bugs, how to find each one, and the row-count ledger."),
         ]),
    dict(id="case-studies", label="Case studies", unit="cases", dir="case-studies", ref="cases",
         dek="Real bugs found by reading the repos and proved by running them, with the evidence scripts.",
         pages=[
             ("01-lakeflow-packaging-three-stacked-faults.md", "cs01", "01 Three stacked packaging faults",
              "A build backend that doesn't exist, a bare import, and a test setup that hid both: three faults, three one-line fixes."),
             ("02-null-semantics-in-quarantine-predicates.md", "cs02", "02 NULL slips past the quarantine",
              "Why a quarantine predicate lets rows with missing values through, and the same bug in two other codebases."),
             ("03-fail-open-patterns.md", "cs03", "03 Fail-open patterns",
              "Seven places where an error becomes a success signal, and the fail-closed designs to copy instead."),
             ("04-lazy-evaluation-meets-mutable-tables.md", "cs04", "04 Lazy evaluation meets a mutable table",
              "A DataFrame defined before a write sees the write. Pinning a version fixes it; caching doesn't."),
             ("05-the-worker-python-interpreter.md", "cs05", "05 The workers' Python",
              "Driver and workers can run different Pythons. How I diagnosed it and what it looks like on Databricks."),
             ("06-near-misses-and-false-positives.md", "cs06", "06 Near-misses",
              "Fifteen things I almost got wrong in this study, what caught each one, and the habit it left."),
             ("07-lakeflow-delta-join-alias-parsing.md", "cs07", "07 Join direction from typing order",
              "In lakeflow_framework, `a = b` and `b = a` produce different LEFT joins. Proved with the framework's real classes."),
             ("08-price-join-containment-vs-point-in-time.md", "cs08", "08 Two ways to price usage",
              "A containment price join drops usage that spans a price change. The point-in-time alternative and its coverage columns."),
         ]),
    dict(id="repos", label="Repo notes", unit="repos", dir="repos", ref="repos",
         dek="One page per repo: what it does, how it runs, what to steal, what's broken, and how to explain it.",
         pages=[
             ("lakeflow_framework.md", "repo-lakeflow", "lakeflow_framework",
              "Metadata-driven Spark Declarative Pipelines: the engine traced, packaging and join bugs proved, and when not to use it."),
             ("vibe-coding-workshop-template.md", "repo-vibe", "vibe-coding-workshop-template",
              "Ninety agent skills for AI-assisted data products: the patterns worth stealing and the errors in the skills themselves."),
             ("consort.md", "repo-consort", "consort",
              "A deterministic harness around AI coding agents on Lakebase branches, and a loop bound that can silently reset."),
             ("databricks-waf.md", "repo-waf", "databricks-waf",
              "A Well-Architected assessment on system tables, built on the rule that not measured never becomes pass."),
             ("technical-services-solutions.md", "repo-tss", "technical-services-solutions",
              "The field team's accelerators for platform setup, governance, BI migration and CI/CD, and an LLM repair layer that changes meaning."),
             ("starter-journey.md", "repo-starter", "starter-journey",
              "The field runbook from an empty account to a governed platform: expensive decisions, good prompts, and a trusting freshness check."),
         ]),
    dict(id="cheatsheets", label="Cheatsheets", unit="sheets", dir="cheatsheets", ref="cheatsheets",
         dek="Quick references for the day of an interview or a customer session.",
         pages=[
             ("pyspark-sql-patterns.md", "cheat-patterns", "PySpark / SQL / Delta patterns",
              "Correct-semantics idioms for messy input, DQ, dedupe, MERGE, SDP, joins, windows, Delta and streaming."),
             ("system-tables-best-practice-checks.md", "cheat-systables", "System-table checks",
              "Cost, compute, jobs and governance checks over system tables, with the five traps and honest denominators."),
             ("platform-fundamentals.md", "cheat-platform", "Platform fundamentals",
              "Setting up a customer platform: expensive decisions, identity, Unity Catalog, networking, cost, CI/CD and the first 90 days."),
             ("interview-question-bank.md", "cheat-questions", "Interview question bank",
              "Short spoken answers grouped by the four criteria, each linked to its evidence."),
         ]),
    dict(id="appendix", label="Appendix", unit="reports", dir="appendix/deep-read-reports", ref="appendix",
         dek="The six raw deep-read reports, and exactly which of their claims I re-verified.",
         pages=[
             ("lakeflow_docs_samples.md", "raw-lakeflow", "lakeflow_framework docs and samples",
              "Raw deep-read of lakeflow_framework's docs, samples, ADRs and spec format at `0e8d0ca`, kept verbatim."),
             ("vibe-coding-workshop-template.md", "raw-vibe", "vibe-coding-workshop-template",
              "Raw deep-read of vibe-coding-workshop-template at `a26c6d0`, kept verbatim."),
             ("consort.md", "raw-consort", "consort",
              "Raw deep-read of consort at `61b3a48`, kept verbatim."),
             ("databricks-waf.md", "raw-waf", "databricks-waf",
              "Raw deep-read of databricks-waf at `e765461`, kept verbatim."),
             ("technical-services-solutions.md", "raw-tss", "technical-services-solutions",
              "Raw deep-read of technical-services-solutions at `41fa465`, kept verbatim."),
             ("starter-journey.md", "raw-starter", "starter-journey",
              "Raw deep-read of starter-journey at `ac21559`, kept verbatim."),
         ]),
]
EYEBROW = {"playbook": "Playbook · {num}", "exercises": "Exercise {num}", "case-studies": "Case study {num}",
           "repos": "Repo notes", "cheatsheets": "Cheatsheet", "appendix": "Raw deep-read report"}
SHORT = {"playbook": "Playbook {num}", "exercises": "Exercise {num}", "case-studies": "Case {num}",
         "repos": "{nav} notes", "cheatsheets": "{nav}", "appendix": "Raw report: {nav}"}

# Source files become code pages. Files without a module docstring get their description here.
CODE_LANGS = {".py": ("python", "Python"), ".patch": ("diff", "Diff"), ".ini": ("ini", "INI"), ".txt": ("text", "Text")}
CODE_DESCRIPTIONS = {
    "case-studies/evidence/observe_streaming.py":
        "Runs the Exercise 04 streaming lab end to end (checkpoint replay, watermark with append mode, the "
        "constant-watermark trick, a stream-static join) and prints what each run wrote.",
    "case-studies/evidence/lakeflow_packaging_fix.patch":
        "The three-line fix for case study 01: a build backend that exists, and package-qualified imports in "
        "`cdc_snapshot.py` and `utility.py`.",
    "exercises/pytest.ini":
        "pytest settings for the exercises: collect `test_*.py`, no cache directory, deprecation warnings silenced.",
    "exercises/requirements.txt":
        "The stack the exercises were verified on: PySpark 4.0.1, delta-spark 4.0.0, pytest, pandas below 3, pyarrow.",
}
HARNESS_ORDER = ["exercises/requirements.txt", "exercises/pytest.ini", "exercises/conftest.py",
                 "exercises/common/spark_session.py"]
FENCE_LABELS = {"python": "Python", "py": "Python", "sql": "SQL", "ts": "TypeScript", "typescript": "TypeScript",
                "js": "JavaScript", "javascript": "JavaScript", "yaml": "YAML", "yml": "YAML", "json": "JSON",
                "hcl": "HCL", "terraform": "Terraform", "bash": "Shell", "sh": "Shell", "shell": "Shell",
                "diff": "Diff", "text": "", "ini": "INI", "toml": "TOML"}
STAMP = re.compile(r"\b(CONFIRMED|SUSPECTED|REFUTED)\b")
TITLE_PREFIX = re.compile(r"^(?:Case study \d+|Exercise \d+|\d{2}\.)\s*:?\s*")
EXTERNAL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
WS = re.compile(r"\s+")
SHARE_SAFE = re.compile(r"^[A-Za-z0-9._~-]*$")  # what survives in an artifact link's #fragment


class BuildError(Exception):
    pass


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def github_slug(text: str) -> str:
    """GitHub's heading anchors: lowercase, drop punctuation except '-' and '_', spaces become '-'."""
    return re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")


def rel(src_out: str, dst_out: str) -> str:
    return posixpath.relpath(dst_out, posixpath.dirname(src_out) or ".")


def split_num(nav: str) -> tuple[str, str]:
    m = re.match(r"(\d\d) (.*)", nav)
    return (m[1], m[2]) if m else ("", nav)


def code_spans(text: str) -> str:
    """Plain text with `backtick` spans as <code>; used for docstrings, which aren't markdown."""
    parts = text.split("`")
    if len(parts) % 2 == 0:  # unbalanced backticks: show as typed
        return esc(text)
    return "".join(f"<code>{esc(p)}</code>" if i % 2 else esc(p) for i, p in enumerate(parts))


def fmt_date(iso: str) -> str:
    try:
        d = dt.date.fromisoformat(iso)
        return f"{d.day} {d:%b %Y}"
    except ValueError:
        return iso


# ---------------------------------------------------------------------------------------------
# Syntax highlighting: Pygments tokens folded into a few classes that are coloured from theme
# tokens, emitted line by line so code pages can anchor every line.
# ---------------------------------------------------------------------------------------------
_GROUPS = {}
for _group, _classes in {"kw": "k kc kd kn kp kr kt ow", "st": "s sa sb sc dl sd s2 se sh si sx sr s1 ss",
                         "nu": "m mb mf mh mi il mo", "fn": "nf fm nc", "bi": "nb bp nv vc vg vi vm",
                         "co": "c ch cm cp cpf c1 cs", "at": "nd na nt", "de": "gd", "in": "gi", "he": "gh gu"}.items():
    for _c in _classes.split():
        _GROUPS[_c] = _group


def _group_of(ttype) -> str:
    while ttype not in STANDARD_TYPES:
        ttype = ttype.parent
    return _GROUPS.get(STANDARD_TYPES[ttype], "")


def lexer_for(name: str):
    if not name or name == "text":
        return None
    try:
        return get_lexer_by_name(name, stripnl=False, stripall=False, ensurenl=False)
    except ClassNotFound:
        return None


def highlight_lines(code: str, lexer) -> list[str]:
    """One HTML string per source line (no trailing newline handling needed by callers)."""
    if code.endswith("\n"):
        code = code[:-1]
    if lexer is None:
        return [esc(line) for line in code.split("\n")]
    lines: list[list[tuple[str, str]]] = [[]]
    for ttype, value in lexer.get_tokens(code + "\n"):
        group = _group_of(ttype)
        for j, part in enumerate(value.split("\n")):
            if j:
                lines.append([])
            if part:
                cur = lines[-1]
                if cur and cur[-1][0] == group:
                    cur[-1] = (group, cur[-1][1] + part)
                else:
                    cur.append((group, part))
    if not lines[-1]:
        lines.pop()
    return ["".join(f'<span class="x-{g}">{esc(t)}</span>' if g else esc(t) for g, t in line) for line in lines]


def codeblock_html(code: str, lang: str) -> str:
    lang = lang.lower()
    label = FENCE_LABELS.get(lang, lang.upper())
    body = "\n".join(highlight_lines(code, lexer_for(lang)))
    return (f'<div class="codeblock"><div class="codebar"><span>{esc(label)}</span>'
            f'<button class="copy" type="button">Copy</button></div>'
            f'<pre><code>{body}</code></pre></div>\n')


# ---------------------------------------------------------------------------------------------
# Markdown: CommonMark + GFM tables and task lists, GitHub heading slugs, highlighted fences,
# scrollable tables, evidence-status stamps, and a link on every heading.
# ---------------------------------------------------------------------------------------------
def _fence(self, tokens, idx, options, env):
    tok = tokens[idx]
    info = tok.info.strip().split()
    return codeblock_html(tok.content, info[0] if info else "")


def _code_block(self, tokens, idx, options, env):
    return codeblock_html(tokens[idx].content, "")


def _text(self, tokens, idx, options, env):
    return STAMP.sub(lambda m: f'<span class="stamp s-{m[1].lower()}">{m[1]}</span>', esc(tokens[idx].content))


def _table_open(self, tokens, idx, options, env):
    return '<div class="table-wrap">' + self.renderToken(tokens, idx, options, env)


def _table_close(self, tokens, idx, options, env):
    return self.renderToken(tokens, idx, options, env) + "</div>\n"


def _heading_close(self, tokens, idx, options, env):
    opening = tokens[idx - 2]
    hid = opening.attrGet("id")
    link = (f'<a class="anchor" href="#{esc(hid)}" aria-label="Link to this section"></a>'
            if hid and opening.tag != "h1" else "")
    return f"{link}</{opening.tag}>\n"


def make_markdown() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False, "typographer": False})
    md.enable(["table", "strikethrough"])
    md.options["tasklists"] = True
    md.options["tasklists_editable"] = False
    md.use(anchors_plugin, min_level=1, max_level=6, slug_func=github_slug)
    for name, rule in {"fence": _fence, "code_block": _code_block, "text": _text, "table_open": _table_open,
                       "table_close": _table_close, "heading_close": _heading_close}.items():
        md.add_render_rule(name, rule)
    return md


MD = make_markdown()


def inline_text(tok) -> str:
    out = []
    for c in tok.children or []:
        if c.type in ("text", "code_inline"):
            out.append(c.content)
        elif c.type in ("softbreak", "hardbreak"):
            out.append(" ")
    return "".join(out)


def render_dek(text: str) -> str:
    return MD.renderInline(text)


# ---------------------------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------------------------
@dataclass
class Page:
    out: str                      # output path relative to the site root
    kind: str                     # home | index | note | code | listing
    series: str
    ref: str
    nav: str
    dek: str = ""
    src: str = ""                 # repo-relative source path
    eyebrow: str = ""
    eyebrow_href: str = ""        # repo-relative out path the eyebrow links to
    title_text: str = ""
    title_html: str = ""
    h1_id: str = ""
    tokens: list = field(default_factory=list)
    env: dict = field(default_factory=dict)
    anchors: set = field(default_factory=set)
    toc: list = field(default_factory=list)        # (level, id, text)
    sections: list = field(default_factory=list)   # (anchor, heading, text) for search
    minutes: int = 0
    updated: str = ""
    body_html: str = ""
    # code pages
    code: str = ""
    lang: str = ""
    lang_label: str = ""
    n_lines: int = 0
    outline: list = field(default_factory=list)    # (line, label)
    group: str = ""
    listing_groups: list = field(default_factory=list)  # listing pages: the code groups they list

    @property
    def num(self) -> str:
        return split_num(self.nav)[0]


class Site:
    def __init__(self, share_url: str):
        self.share_url = share_url
        self.pages: list[Page] = []
        self.by_src: dict[str, Page] = {}
        self.by_out: dict[str, Page] = {}
        self.by_ref: dict[str, Page] = {}
        self.by_dir: dict[str, Page] = {}
        self.series: list[dict] = []          # SERIES entries plus the code series, with Page objects
        self.code_groups: list[dict] = []
        self.backlinks: dict[str, dict[str, list[tuple[str, str]]]] = {}
        self.errors: list[str] = []
        self.links = 0
        self.home: Page | None = None
        self.dates: dict[str, str] = {}
        self.reading_order: list[Page] = []   # series overviews and notes, for previous/next
        self.code_order: list[Page] = []

    def add(self, page: Page) -> Page:
        if page.ref in self.by_ref:
            raise BuildError(f"duplicate ref {page.ref!r}: {self.by_ref[page.ref].out} and {page.out}")
        if not SHARE_SAFE.match(page.ref):
            raise BuildError(f"ref {page.ref!r} has characters an artifact link's #fragment drops")
        self.pages.append(page)
        self.by_out[page.out] = page
        self.by_ref[page.ref] = page
        if page.src:
            self.by_src[page.src] = page
        page.updated = self.dates.get(page.src, "")
        return page

    def short(self, page: Page) -> str:
        if page.kind == "home":
            return "Home"
        if page.kind in ("index", "listing"):
            return f"{self.series_label(page.series)} overview" if page.kind == "index" else page.title_text
        if page.kind == "code":
            return page.nav
        return SHORT[page.series].format(num=page.num, nav=page.nav)

    def series_label(self, sid: str) -> str:
        return next((s["label"] for s in self.series if s["id"] == sid), "")

    # -- links -------------------------------------------------------------------------------
    def resolve(self, page: Page, href: str) -> tuple[str, Page | None]:
        if EXTERNAL.match(href):
            return href, None
        path, _, frag = href.partition("#")
        frag = unquote(frag)
        if not path:
            target = page
        else:
            full = posixpath.normpath(posixpath.join(posixpath.dirname(page.src), unquote(path)))
            full = "" if full == "." else full
            target = self.by_src.get(full) or self.by_dir.get(full)
            if target is None:
                self.errors.append(f"{page.src}: link to {href!r} resolves to {full!r}, which isn't a page")
                return href, None
        if frag and frag not in target.anchors:
            self.errors.append(f"{page.src}: link to {href!r} names an anchor that {target.src or target.out} lacks")
        if target is page:
            return (f"#{frag}" if frag else "#"), target
        return rel(page.out, target.out) + (f"#{frag}" if frag else ""), target

    def rewrite_links(self, page: Page) -> None:
        cur = ("", "")
        for i, tok in enumerate(page.tokens):
            if tok.type == "heading_open" and tok.tag in ("h2", "h3"):
                cur = (tok.attrGet("id") or "", inline_text(page.tokens[i + 1]))
            if tok.type != "inline":
                continue
            for child in tok.children or []:
                if child.type != "link_open":
                    continue
                url, target = self.resolve(page, child.attrGet("href") or "")
                child.attrSet("href", url)
                if target is None:
                    if EXTERNAL.match(url):
                        child.attrSet("rel", "noopener noreferrer")
                        child.attrSet("target", "_blank")
                    continue
                self.links += 1
                if target is page or page.kind == "home":
                    continue
                if page.kind == "index" and target.series == page.series:
                    continue  # an overview listing its own pages isn't worth a backlink
                spots = self.backlinks.setdefault(target.out, {}).setdefault(page.out, [])
                if cur not in spots:
                    spots.append(cur)


# ---------------------------------------------------------------------------------------------
# Reading sources
# ---------------------------------------------------------------------------------------------
def source_files() -> list[str]:
    """Tracked and untracked-but-not-ignored files, minus the blog itself."""
    try:
        r = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                           cwd=REPO, capture_output=True, check=True)
        files = [f for f in r.stdout.decode().split("\0") if f]
    except (OSError, subprocess.CalledProcessError):
        files = [p.relative_to(REPO).as_posix() for p in REPO.rglob("*") if p.is_file()]
    skip = ("blog/", ".git/", ".venv/", ".pytest_cache/", "spark-warehouse/", "metastore_db/")
    return sorted({f for f in files if not f.startswith(skip) and "__pycache__" not in f
                   and not f.startswith(".") and (REPO / f).is_file()})


def git_dates() -> dict[str, str]:
    """Last commit date per file (newest first log, so the first date seen wins)."""
    try:
        r = subprocess.run(["git", "log", "--format=@%cs", "--name-only"], cwd=REPO,
                           capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return {}
    dates, current = {}, ""
    for line in r.stdout.splitlines():
        if line.startswith("@"):
            current = line[1:]
        elif line and line not in dates:
            dates[line] = current
    return dates


def parse_note(page: Page) -> None:
    text = (REPO / page.src).read_text(encoding="utf-8")
    env: dict = {}
    tokens = MD.parse(text, env)
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.tag == "h1":
            inline = tokens[i + 1]
            page.h1_id = tok.attrGet("id") or ""
            first = (inline.children or [None])[0]
            if page.kind == "note" and first is not None and first.type == "text":
                m = TITLE_PREFIX.match(first.content)
                if m:  # the eyebrow already says "Case study 07", so the title needn't
                    rest = first.content[m.end():]
                    first.content = rest[:1].upper() + rest[1:]
            page.title_text = inline_text(inline)
            page.title_html = MD.renderer.renderInline(inline.children, MD.options, env)
            del tokens[i:i + 3]
            break
    else:
        raise BuildError(f"{page.src}: no '# ' title")
    page.tokens, page.env = tokens, env
    index_tokens(page)


def index_tokens(page: Page) -> None:
    """Anchors, table of contents, search sections and reading time, from the token stream."""
    anchors = {page.h1_id} if page.h1_id else set()
    toc, sections, buf = [], [], []
    cur_anchor, cur_head = "", page.title_text
    words = code_words = 0
    tokens, i = page.tokens, 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            hid = tok.attrGet("id") or ""
            anchors.add(hid)
            text = inline_text(tokens[i + 1])
            words += len(text.split())
            if tok.tag in ("h2", "h3"):
                toc.append((int(tok.tag[1]), hid, text))
                sections.append((cur_anchor, cur_head, " ".join(buf)))
                cur_anchor, cur_head, buf = hid, text, []
            else:
                buf.append(text)
            i += 3
            continue
        if tok.type == "inline":
            s = inline_text(tok)
            buf.append(s)
            words += len(s.split())
        elif tok.type in ("fence", "code_block"):
            buf.append(tok.content)
            code_words += len(tok.content.split())
        i += 1
    sections.append((cur_anchor, cur_head, " ".join(buf)))
    page.anchors = anchors
    page.toc = toc
    page.sections = [(a, h, WS.sub(" ", x).strip()) for a, h, x in sections if a or x.strip()]
    page.minutes = max(1, round((words + code_words / 2) / 220))


def describe_code(path: str, text: str) -> str:
    if path in CODE_DESCRIPTIONS:
        return CODE_DESCRIPTIONS[path]
    if path.endswith(".py"):
        doc = ast.get_docstring(ast.parse(text)) or ""
        lines = doc.strip().split("\n\n")[0].split("\n")
        # keep the prose; usage lines ("pip install ... && python ...") belong on the code page itself
        lines = [ln for ln in lines if not re.match(r"\s*(\$ |pip |python |pytest|cd )", ln)]
        para = WS.sub(" ", " ".join(lines)).strip()
        if len(para) > 260:
            cut = para.rfind(". ", 0, 260)
            para = para[:cut + 1] if cut > 80 else para[:250].rsplit(" ", 1)[0] + "…"
        if para:
            return para
    raise BuildError(f"{path}: no module docstring; add a description to CODE_DESCRIPTIONS")


def code_outline(path: str, text: str) -> list[tuple[int, str]]:
    if path.endswith(".py"):
        items = []
        for node in ast.parse(text).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = min([node.lineno] + [d.lineno for d in node.decorator_list])
                kind = "class" if isinstance(node, ast.ClassDef) else "def"
                items.append((start, f"{kind} {node.name}"))
        return items
    if path.endswith(".patch"):
        return [(n, line[6:]) for n, line in enumerate(text.split("\n"), 1) if line.startswith("+++ b/")]
    return []


def code_group_id(path: str) -> str:
    parts = path.split("/")
    if parts[0] == "playbook":
        return "pb"
    if parts[:2] == ["case-studies", "evidence"]:
        return "ev"
    if parts[0] == "exercises":
        if len(parts) >= 3 and re.match(r"ex\d\d_", parts[1]):
            return parts[1][:4]
        return "harness"
    raise BuildError(f"{path}: source file outside any code group; add a rule to code_group_id()")


# ---------------------------------------------------------------------------------------------
# Building the site model
# ---------------------------------------------------------------------------------------------
def build_site(share_url: str) -> Site:
    site = Site(share_url)
    site.dates = git_dates()
    files = source_files()
    md_files = [f for f in files if f.endswith(".md")]
    covered = set()

    home = site.add(Page(out="home.html", kind="home", series="home", ref="home", nav="Home", src="README.md"))
    site.home = home
    site.by_dir[""] = home
    covered.add("README.md")

    reading_order: list[Page] = []
    for s in SERIES:
        src = f"{s['dir']}/README.md"
        index = site.add(Page(out=f"{s['dir']}/index.html", kind="index", series=s["id"], ref=s["ref"],
                              nav="Overview", dek=s["dek"], src=src,
                              eyebrow=f"Overview · {len(s['pages'])} {s['unit']}"))
        site.by_dir[s["dir"]] = index
        covered.add(src)
        pages = []
        for file, ref, nav, dek in s["pages"]:
            src = f"{s['dir']}/{file}"
            if src not in md_files:
                raise BuildError(f"SERIES lists {src}, which doesn't exist")
            page = site.add(Page(out=src[:-3] + ".html", kind="note", series=s["id"], ref=ref, nav=nav,
                                 dek=dek, src=src))
            page.eyebrow = EYEBROW[s["id"]].format(num=page.num)
            pages.append(page)
            covered.add(src)
        site.series.append({**s, "index": index, "pages": pages})
        reading_order += [index] + pages

    missing = sorted(set(md_files) - covered)
    if missing:
        raise BuildError("notes missing from SERIES (give each a ref, nav title and dek): " + ", ".join(missing))

    # Code pages, grouped for the sidebar and the listing pages.
    exercises = next(s for s in site.series if s["id"] == "exercises")
    exercise_pages = {p.src.split("/")[1][:4]: p for p in exercises["pages"]}
    groups = {"pb": dict(id="g-pb", key="pb", label="Playbook demos", eyebrow="Playbook demo", pages=[]),
              "ev": dict(id="g-ev", key="ev", label="Case-study evidence", eyebrow="Evidence script", pages=[]),
              "harness": dict(id="g-harness", key="harness", label="Exercise harness", eyebrow="Exercise harness",
                              pages=[])}
    for key, wt in exercise_pages.items():
        num, name = split_num(wt.nav)
        groups[key] = dict(id=f"g-{key}", key=key, label=f"Exercise {num} · {name}",
                           eyebrow=f"Exercise {num} · source", pages=[], walkthrough=wt)
    code_files = [f for f in files if Path(f).suffix in CODE_LANGS and (REPO / f).stat().st_size > 0]

    def order(path: str):
        name = path.rsplit("/", 1)[-1]
        return (HARNESS_ORDER.index(path) if path in HARNESS_ORDER else 99, name.startswith("test_"), name)

    for path in sorted(code_files, key=order):
        key = code_group_id(path)
        g = groups[key]
        text = (REPO / path).read_text(encoding="utf-8")
        lang, label = CODE_LANGS[Path(path).suffix]
        name = path.rsplit("/", 1)[-1]
        page = Page(out=path + ".html", kind="code", series="code", ref=f"{key}-{Path(path).stem}", nav=name,
                    dek=describe_code(path, text), src=path, eyebrow=g["eyebrow"], title_text=name,
                    title_html=f"<code>{esc(name)}</code>", code=text, lang=lang, lang_label=label, group=key)
        page.n_lines = len(text[:-1].split("\n")) if text.endswith("\n") else len(text.split("\n"))
        page.anchors = {f"L{n}" for n in range(1, page.n_lines + 1)}
        page.outline = code_outline(path, text)
        page.toc = [(2, f"L{n}", label_) for n, label_ in page.outline]
        page.sections = code_sections(page)
        g["pages"].append(site.add(page))
    site.code_groups = [g for g in (groups["pb"], groups["ev"], groups["harness"],
                                    *(groups[k] for k in sorted(exercise_pages))) if g["pages"]]

    code_index = site.add(Page(out="code/index.html", kind="listing", series="code", ref="code", nav="Overview",
                               title_text="Every script behind the notes",
                               dek="Every script and exercise file behind the notes, with syntax highlighting and "
                                   "line anchors.",
                               eyebrow=f"Source code · {len(code_files)} files"))
    evidence = site.add(Page(out="case-studies/evidence/index.html", kind="listing", series="code", ref="evidence",
                             nav="Case-study evidence", title_text="Evidence scripts",
                             dek="Every script that backs a case-study claim, what it proves, and where it is cited.",
                             eyebrow="Source code · case-study evidence"))
    site.by_dir["case-studies/evidence"] = evidence
    site.by_dir["code"] = code_index
    for listing, gs in ((code_index, site.code_groups), (evidence, [groups["ev"]])):
        listing.title_html = esc(listing.title_text)
        listing.anchors = {g["id"] for g in gs}
        listing.toc = [(2, g["id"], g["label"]) for g in gs]
        listing.listing_groups = gs
    for g in site.code_groups:
        if g["key"] == "ev":
            g["link"] = evidence
        elif "walkthrough" in g:
            g["link"] = g["walkthrough"]
        for p in g["pages"]:
            p.eyebrow_href = (g["walkthrough"].out if "walkthrough" in g else
                              evidence.out if g["key"] == "ev" else f"{code_index.out}#{g['id']}")
    code_pages = [p for g in site.code_groups for p in g["pages"]]
    site.series.append(dict(id="code", label="Source code", unit="files", ref="code", index=code_index,
                            pages=code_pages, dek="Every script and exercise file behind the notes, with syntax "
                                                  "highlighting and line anchors."))
    site.reading_order = reading_order
    site.code_order = code_pages

    # Parse every note, then rewrite and check links once all anchors are known.
    notes = [home] + reading_order
    for page in notes:
        parse_note(page)
    home.anchors |= {"contents"} | {f"series-{s['id']}" for s in site.series}
    for page in notes:
        site.rewrite_links(page)
    for page in site.pages:
        bad = [a for a in page.anchors if not SHARE_SAFE.match(a)]
        if bad:
            site.errors.append(f"{page.out}: anchors that won't survive in a shared link: {bad}")
    if site.errors:
        raise BuildError("broken references:\n  " + "\n  ".join(site.errors))
    for page in notes:
        page.body_html = MD.renderer.render(page.tokens, MD.options, page.env)
    return site


def code_sections(page: Page) -> list[tuple[str, str, str]]:
    lines = page.code.split("\n")
    starts = [(1, "")] + [(n, label) for n, label in page.outline if n > 1]
    out = []
    for k, (start, label) in enumerate(starts):
        end = starts[k + 1][0] - 1 if k + 1 < len(starts) else len(lines)
        chunk = WS.sub(" ", " ".join(lines[start - 1:end])).strip()
        if chunk:
            out.append(("" if start == 1 else f"L{start}", label or page.nav, chunk))
    return out


# ---------------------------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------------------------
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600'
         '&amp;family=IBM+Plex+Sans:wght@400;500;600&amp;family=Source+Serif+4:ital,opsz,wght@0,8..60,400..700;'
         '1,8..60,400..700&amp;display=swap">')
MARK = ('<svg class="mark" viewBox="0 0 24 24" aria-hidden="true">'
        '<rect x="3" y="3" width="18" height="18" rx="4" fill="none" stroke="currentColor" stroke-width="1.8"/>'
        '<path d="M7.5 9h9M7.5 12.5h6M7.5 16h3" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round"/></svg>')
MENU = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>')
LENS = ('<svg class="lens" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5" fill="none" '
        'stroke="currentColor" stroke-width="1.8"/><path d="M16 16l4.5 4.5" fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round"/></svg>')
THEME_FROM_STORAGE = ('<script>try{var t=localStorage.getItem("cb-theme");if(t&&!document.documentElement'
                      '.hasAttribute("data-theme"))document.documentElement.setAttribute("data-theme",t)}'
                      'catch(e){}</script>')
ROUTER = ('<script>(function(){var r=window.CB&&CB.routes,h="";if(!r)return;try{h=decodeURIComponent('
          'location.hash.slice(1))}catch(e){}if(!h)return;var i=h.indexOf("~"),p=r[i<0?h:h.slice(0,i)],'
          's=i<0?"":h.slice(i+1);if(!p)return;var d=document.documentElement;d.style.visibility="hidden";'
          'setTimeout(function(){d.style.visibility=""},1500);location.replace(CB.root+p+(s?"#"+s:""))})();'
          '</script>')


def root_of(out: str) -> str:
    return "../" * out.count("/")


def document(site: Site, page: Page, main_html: str, *, fragment: bool = False, home: bool = False) -> str:
    cfg = {"root": root_of(page.out), "ref": page.ref, "share": site.share_url}
    if fragment:
        cfg["hostTheme"] = True
    if home:
        cfg["routes"] = {p.ref: p.out for p in site.pages if p.kind != "home"}
    if page.kind == "home":
        title = SITE
    elif page.kind == "index":
        title = f"{site.series_label(page.series)} · {SITE}"
    elif page.kind == "listing":
        title = f"{page.title_text} · {SITE}"
    else:
        title = f"{page.nav} · {SITE}"
    config = f"<script>window.CB={json.dumps(cfg, ensure_ascii=False)};</script>"
    head = (f"<title>{esc(title)}</title>\n{config}\n{ROUTER if home else ''}"
            f"{'' if fragment else THEME_FROM_STORAGE}\n{FONTS}\n<style>{CSS}</style>")
    body = f"{chrome(site, page, main_html, home=home)}\n<script>{JS}</script>"
    if fragment:
        return f"{head}\n{body}\n"
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f"{head}\n</head>\n<body>\n{body}\n</body>\n</html>\n")


def chrome(site: Site, page: Page, main_html: str, *, home: bool) -> str:
    root = root_of(page.out)
    navbtn = ("" if home else
              f'<button class="navbtn" type="button" aria-label="All pages" aria-expanded="false" '
              f'aria-controls="sidenav">{MENU}</button>')
    side = "" if home else sidebar(site, page)
    return f"""<a class="skip" href="#main">Skip to content</a>
<header class="topbar">
{navbtn}<a class="brand" href="{root}home.html">{MARK}<span class="brand-name">{SITE}</span></a>
<div class="search" role="search">{LENS}<input id="q" class="search-input" type="search" placeholder="Search the notes" autocomplete="off" spellcheck="false" aria-label="Search the notes"><kbd class="search-kbd" aria-hidden="true">/</kbd>
<div id="results" class="results" aria-label="Search results" hidden></div></div>
</header>
<div class="shell{' shell-home' if home else ''}">
{side}<main id="main" class="main{' main-home' if home else ''}">
{main_html}
</main>
</div>
<div class="scrim" hidden></div>
<div id="toast" class="toast" role="status" aria-live="polite" hidden></div>"""


def nav_label(page: Page, label: str) -> str:
    num, rest = split_num(label)
    return (f'<span class="n">{num}</span>{esc(rest)}' if num else esc(label))


def sidebar(site: Site, page: Page) -> str:
    def item(p: Page, label: str, cls: str = "") -> str:
        cur = ' aria-current="page"' if p is page else ""
        c = f' class="{cls}"' if cls else ""
        return f'<li><a href="{rel(page.out, p.out)}"{c}{cur}>{nav_label(p, label)}</a></li>'

    out = ['<nav id="sidenav" class="sidenav" aria-label="All pages">',
           f'<a class="sn-home" href="{rel(page.out, site.home.out)}">Home and contents</a>']
    for s in site.series:
        is_open = " open" if s["id"] == page.series else ""
        out.append(f'<details class="sn-group"{is_open}><summary>{esc(s["label"])}'
                   f'<span class="sn-count">{len(s["pages"])}</span></summary><ol>')
        out.append(item(s["index"], "Overview"))
        if s["id"] == "code":
            for g in site.code_groups:
                link = g.get("link")
                head = f'<a href="{rel(page.out, link.out)}">{esc(g["label"])}</a>' if link else esc(g["label"])
                out.append(f'<li class="sn-sub">{head}</li>')
                out += [item(p, p.nav, "code") for p in g["pages"]]
        else:
            out += [item(p, p.nav) for p in s["pages"]]
        out.append("</ol></details>")
    out.append("</nav>")
    return "\n".join(out)


def page_head(site: Site, page: Page, meta: list[str], *, title_cls: str = "") -> str:
    eyebrow = esc(page.eyebrow)
    if page.eyebrow_href:
        eyebrow = f'<a href="{rel(page.out, page.eyebrow_href)}">{eyebrow}</a>'
    bits = [f'<span class="ref" title="Reference code: add #{page.ref} to the casebook link to open this page">'
            f'{page.ref}</span>'] + meta
    if page.updated:
        bits.append(f"<span>Updated {fmt_date(page.updated)}</span>")
    if page.src:
        bits.append(f'<span class="srcpath">{esc(page.src)}</span>')
    if site.share_url:
        bits.append('<button class="btn" type="button" data-share>Copy link</button>')
    dek = ""
    if page.dek:
        dek = f'<p class="dek">{code_spans(page.dek) if page.kind == "code" else render_dek(page.dek)}</p>'
    hid = f' id="{page.h1_id}"' if page.h1_id else ""
    cls = f' class="{title_cls}"' if title_cls else ""
    return (f'<header class="page-head"><p class="eyebrow">{eyebrow}</p><h1{hid}{cls}>{page.title_html}</h1>'
            f'{dek}<div class="meta">{"".join(bits)}</div></header>')


def toc_list(toc: list) -> str:
    return "".join(f'<li class="toc-l{lvl}"><a href="#{esc(hid)}">{esc(text)}</a></li>' for lvl, hid, text in toc)


def toc_inline(toc: list, title: str = "On this page") -> str:
    if len(toc) < 2:
        return ""
    return f'<details class="toc-inline"><summary>{title}</summary><ol class="toc">{toc_list(toc)}</ol></details>'


def rail(toc: list, title: str = "On this page") -> str:
    if len(toc) < 2:
        return ""
    return (f'<aside class="rail" aria-label="{title}"><p class="rail-title">{title}</p>'
            f'<ol class="toc">{toc_list(toc)}</ol></aside>')


def backlinks_html(site: Site, page: Page, *, compact: bool = False) -> str:
    sources = site.backlinks.get(page.out, {})
    if not sources:
        return ""
    if compact:
        links = ", ".join(f'<a href="{rel(page.out, site.by_out[s].out)}">{esc(site.short(site.by_out[s]))}</a>'
                          for s in sources)
        return f'<p class="cited"><span>Cited by</span>{links}</p>'
    items = []
    for src_out, spots in sources.items():
        sp = site.by_out[src_out]
        href = rel(page.out, sp.out)
        same = sp.kind in ("index", "listing") or sp.title_text.lower() == site.short(sp).lower()
        title = "" if same else f' · <span class="bl-title">{esc(sp.title_text)}</span>'
        where = [f'<a href="{href}#{esc(a)}">{esc(h)}</a>' for a, h in spots if a]
        more = ""
        if len(where) > 3:
            more, where = f" and {len(where) - 3} more", where[:3]
        where_html = f'<span class="where"> in {", ".join(where)}{more}</span>' if where else ""
        items.append(f'<li><a href="{href}">{esc(site.short(sp))}</a>{title}{where_html}</li>')
    return (f'<section class="backlinks" aria-labelledby="cb-linked-from"><h2 id="cb-linked-from">Linked from</h2>'
            f'<ul>{"".join(items)}</ul></section>')


def pager(site: Site, page: Page, order: list[Page]) -> str:
    if page not in order:
        return ""
    i = order.index(page)
    prev_p = order[i - 1] if i > 0 else None
    next_p = order[i + 1] if i + 1 < len(order) else None

    def card(p: Page, cls: str, word: str) -> str:
        label = site.short(p) if p.kind != "code" else p.nav
        title = p.title_text if p.kind not in ("index", "code") else ""
        extra = f'<span class="pg-title">{esc(title)}</span>' if title and title != label else ""
        return (f'<a class="{cls}" href="{rel(page.out, p.out)}"><small>{word}</small>'
                f'<span class="pg-label">{esc(label)}</span>{extra}</a>')

    cards = (card(prev_p, "prev", "Previous") if prev_p else "") + (card(next_p, "next", "Next") if next_p else "")
    return f'<nav class="pager" aria-label="Previous and next">{cards}</nav>' if cards else ""


def exercise_files(site: Site, page: Page) -> str:
    if page.series != "exercises" or page.kind != "note":
        return ""
    key = page.src.split("/")[1][:4]
    g = next((g for g in site.code_groups if g["key"] == key), None)
    if not g:
        return ""
    chips = "".join(f'<a class="chip" href="{rel(page.out, p.out)}">{esc(p.nav)}</a>' for p in g["pages"])
    return f'<nav class="files" aria-label="Files in this exercise"><span>Files</span>{chips}</nav>'


def note_main(site: Site, page: Page) -> str:
    meta = [f"<span>{page.minutes} min read</span>"]
    head = page_head(site, page, meta)
    foot = backlinks_html(site, page) + pager(site, page, site.reading_order)
    foot = f'<footer class="page-foot">{foot}</footer>' if foot else ""
    article = (f'<article class="article">{head}{exercise_files(site, page)}{toc_inline(page.toc)}'
               f'<div class="prose">{page.body_html}</div>{foot}</article>')
    return article + rail(page.toc)


def code_main(site: Site, page: Page) -> str:
    lexer = lexer_for(page.lang)
    raw = page.code[:-1].split("\n") if page.code.endswith("\n") else page.code.split("\n")
    rows = []
    for n, line_html in enumerate(highlight_lines(page.code, lexer), 1):
        cls = "line"
        if page.lang == "diff":
            src = raw[n - 1]
            if src.startswith("+") and not src.startswith("+++"):
                cls += " ins"
            elif src.startswith("-") and not src.startswith("---"):
                cls += " del"
        rows.append(f'<span class="{cls}" id="L{n}"><a class="ln" href="#L{n}">{n}</a>'
                    f'<span class="lc">{line_html}</span></span>')
    meta = [f"<span>{page.n_lines} lines</span>", f"<span>{page.lang_label}</span>"]
    head = page_head(site, page, meta, title_cls="code-title")
    codefile = (f'<div class="codefile"><div class="codebar"><span class="codepath">{esc(page.src)}</span>'
                f'<button class="copy" type="button" data-copy-file>Copy file</button></div>'
                f'<pre class="lines"><code>{"".join(rows)}</code></pre></div>')
    foot = pager(site, page, site.code_order)
    foot = f'<footer class="page-foot">{foot}</footer>' if foot else ""
    article = (f'<article class="article article-code">{head}{backlinks_html(site, page, compact=True)}'
               f'{toc_inline(page.toc, "Outline")}{codefile}{foot}</article>')
    return article + rail(page.toc, "Outline")


def listing_main(site: Site, page: Page) -> str:
    parts = []
    for g in page.listing_groups:
        rows = []
        for p in g["pages"]:
            cited = ", ".join(f'<a href="{rel(page.out, site.by_out[s].out)}">{esc(site.short(site.by_out[s]))}</a>'
                              for s in site.backlinks.get(p.out, {})) or '<span class="muted">none</span>'
            rows.append(f'<tr><td><a href="{rel(page.out, p.out)}"><code>{esc(p.nav)}</code></a></td>'
                        f'<td class="num">{p.n_lines}</td><td>{code_spans(p.dek)}</td><td>{cited}</td></tr>')
        intro = ""
        if "walkthrough" in g:
            intro = f'<p>Walkthrough: <a href="{rel(page.out, g["walkthrough"].out)}">{esc(g["walkthrough"].title_text)}</a>.</p>'
        parts.append(f'<h2 id="{g["id"]}">{esc(g["label"])}<a class="anchor" href="#{g["id"]}" '
                     f'aria-label="Link to this section"></a></h2>{intro}'
                     f'<div class="table-wrap"><table class="listing"><thead><tr><th>File</th><th>Lines</th>'
                     f'<th>What it does</th><th>Cited by</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    head = page_head(site, page, [f"<span>{sum(len(g['pages']) for g in page.listing_groups)} files</span>"])
    return (f'<article class="article">{head}{toc_inline(page.toc)}<div class="prose">{"".join(parts)}</div></article>'
            + rail(page.toc))


def split_readme(tokens: list) -> tuple[list, list]:
    """README intro (before its bullet list of sections) and the rest from the first '##' on.
    The bullet list is replaced by the generated contents."""
    first_h2 = next(i for i, t in enumerate(tokens) if t.type == "heading_open" and t.tag == "h2")
    start = next((i for i in range(first_h2) if tokens[i].type == "bullet_list_open" and tokens[i].level == 0), None)
    if start is None:
        return tokens[:first_h2], tokens[first_h2:]
    end = next(i for i in range(start, first_h2) if tokens[i].type == "bullet_list_close" and tokens[i].level == 0)
    return tokens[:start], tokens[end + 1:]


def home_main(site: Site) -> str:
    home = site.home
    intro, rest = split_readme(home.tokens)
    render = lambda toks: MD.renderer.render(toks, MD.options, home.env)  # noqa: E731
    subtitle = re.sub(r":\s*study notes$", "", home.title_text, flags=re.I)
    cards = []
    for s in site.series:
        entries = []
        if s["id"] == "code":
            for g in site.code_groups:
                target = g.get("link") if g["key"] == "ev" else None
                href = rel(home.out, target.out) if target else f'{rel(home.out, s["index"].out)}#{g["id"]}'
                n = len(g["pages"])
                entries.append(f'<li><a href="{href}">{esc(g["label"])}</a>'
                               f'<p>{n} file{"s" if n != 1 else ""}: {esc(", ".join(p.nav for p in g["pages"][:4]))}'
                               f'{", …" if n > 4 else ""}</p></li>')
        else:
            for p in s["pages"]:
                entries.append(f'<li><a href="{rel(home.out, p.out)}">{nav_label(p, p.nav)}</a>'
                               f'<p>{render_dek(p.dek)}</p></li>')
        cards.append(f'<section class="series-card" id="series-{s["id"]}"><h3>'
                     f'<a href="{rel(home.out, s["index"].out)}">{esc(s["label"])}</a>'
                     f'<span class="count">{len(s["pages"])} {s["unit"]}</span></h3>'
                     f'<p class="series-dek">{render_dek(s["dek"])}</p><ol class="entries">{"".join(entries)}</ol>'
                     f'</section>')
    n_notes = sum(1 for p in site.pages if p.kind in ("note", "index"))
    n_code = sum(1 for p in site.pages if p.kind == "code")
    latest = max((p.updated for p in site.pages if p.updated), default="")
    ledger = [f"<span><b>{n_notes}</b> pages of notes</span>", f"<span><b>{n_code}</b> source files</span>",
              f"<span><b>{site.links}</b> cross-links, every one resolved at build time</span>"]
    if latest:
        ledger.append(f"<span>updated <b>{fmt_date(latest)}</b></span>")
    share = ('<button class="btn" type="button" data-share>Copy link</button>' if site.share_url else "")
    return f"""<div class="home">
<section class="cover">
<p class="eyebrow">Study notes · six repositories · PySpark 4.0.1 + Delta 4.0.0</p>
<h1 id="{home.h1_id}">{SITE}</h1>
<p class="subtitle">{esc(subtitle)}</p>
<div class="lede">{render(intro)}</div>
<p class="ledger">{"".join(ledger)}</p>
<p class="hint"><span class="kbd-hint">Press <kbd>/</kbd> to search every page. </span>Every page has a short reference code, shown under its title{", and a Copy link button" if share else ""}.{" " + share if share else ""}</p>
</section>
<section class="contents" aria-labelledby="contents"><h2 id="contents" class="section-label">Contents</h2>
<div class="series-cols">{"".join(cards)}</div></section>
<div class="prose home-prose">{render(rest)}</div>
</div>"""


def search_index(site: Site) -> dict:
    pages, entries = [], []
    for page in site.pages:
        if page.kind == "listing" or not page.sections:
            continue
        pi = len(pages)
        nav = "Home" if page.kind == "home" else page.nav
        series = SITE if page.kind == "home" else site.series_label(page.series)
        pages.append({"u": page.out, "t": page.title_text if page.kind != "home" else SITE, "n": nav, "s": series})
        entries += [[pi, a, h, x] for a, h, x in page.sections]
    return {"pages": pages, "entries": entries}


# ---------------------------------------------------------------------------------------------
# Output and verification
# ---------------------------------------------------------------------------------------------
HREF = re.compile(r'\s(?:href|src)="([^"]*)"')
ID = re.compile(r'\sid="([^"]*)"')
SCRIPT_OR_STYLE = re.compile(r"<(script|style)\b.*?</\1>", re.S)


def verify_output(out_dir: Path, written: list[str], site: Site) -> int:
    """Re-read every written page and check each relative href and #anchor lands on something real."""
    texts = {f: SCRIPT_OR_STYLE.sub("", (out_dir / f).read_text(encoding="utf-8"))
             for f in written if f.endswith(".html")}
    ids = {f: set(ID.findall(t)) for f, t in texts.items()}
    errors, checked = [], 0
    for f, text in texts.items():
        for href in HREF.findall(text):
            href = html.unescape(href)
            if EXTERNAL.match(href):
                continue
            path, _, frag = href.partition("#")
            target = posixpath.normpath(posixpath.join(posixpath.dirname(f), path)) if path else f
            checked += 1
            if target not in ids:
                errors.append(f"{f}: href {href!r} -> missing file {target}")
            elif frag and unquote(frag) not in ids[target]:
                errors.append(f"{f}: href {href!r} -> no id {frag!r} in {target}")
    index = json.loads((out_dir / "search-index.json").read_text(encoding="utf-8"))
    for pi, anchor, _, _ in index["entries"]:
        u = index["pages"][pi]["u"]
        if u not in ids or (anchor and anchor not in ids[u]):
            errors.append(f"search-index.json: {u}#{anchor} doesn't exist")
    for ref, page in site.by_ref.items():
        if page.out not in ids:
            errors.append(f"route {ref} -> {page.out} doesn't exist")
    if errors:
        raise BuildError("output check failed:\n  " + "\n  ".join(errors[:50]))
    return checked


def write_site(site: Site, out_dir: Path, standalone: bool) -> list[str]:
    if out_dir.exists():
        if out_dir.name != "site" or REPO not in out_dir.resolve().parents:
            raise BuildError(f"refusing to clear {out_dir}: expected a 'site' folder inside the repo")
        shutil.rmtree(out_dir)
    written = []

    def put(rel_path: str, text: str) -> None:
        path = out_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(rel_path)

    home_html = home_main(site)
    put("home.html", document(site, site.home, home_html, home=True))
    index_page = Page(out="index.html", kind="home", series="home", ref="home", nav="Home")
    put("index.html", document(site, index_page, home_html, fragment=not standalone, home=True))
    for page in site.pages:
        if page.kind in ("note", "index"):
            put(page.out, document(site, page, note_main(site, page)))
        elif page.kind == "code":
            put(page.out, document(site, page, code_main(site, page)))
        elif page.kind == "listing":
            put(page.out, document(site, page, listing_main(site, page)))
    put("search-index.json", json.dumps(search_index(site), ensure_ascii=False, separators=(",", ":")))
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=str(REPO / "blog" / "site"), help="output folder (default: blog/site)")
    ap.add_argument("--share-url", default="", help="the published link, for copy-link buttons (URL#ref~section)")
    ap.add_argument("--standalone", action="store_true", help="write index.html as a full document, not a fragment")
    args = ap.parse_args(argv)
    if args.share_url and not re.match(r"^https://", args.share_url):
        ap.error("--share-url must be an https:// link")
    try:
        site = build_site(args.share_url.split("#")[0])
        out_dir = Path(args.out).resolve()
        written = write_site(site, out_dir, args.standalone)
        checked = verify_output(out_dir, written, site)
    except BuildError as e:
        print(f"build failed: {e}", file=sys.stderr)
        return 1
    size = sum((out_dir / f).stat().st_size for f in written)
    kinds = {k: sum(1 for p in site.pages if p.kind == k) for k in ("note", "index", "code", "listing")}
    print(f"wrote {len(written)} files ({size / 1e6:.1f} MB) to {out_dir}")
    print(f"  {kinds['note']} notes, {kinds['index']} series overviews, {kinds['code']} code pages, "
          f"{kinds['listing']} listings, home")
    print(f"  {site.links} cross-links in the notes resolved; {checked} hrefs in the output verified")
    return 0


# ---------------------------------------------------------------------------------------------
# Styles and behaviour, inlined into every page.
# ---------------------------------------------------------------------------------------------
CSS = r"""
:root{
  --bg:#f6f4ef;--bg-raised:#fcfbf8;--bg-sunk:#edeae2;--code-bg:#f1eee7;
  --ink:#1b2326;--ink-2:#455156;--ink-3:#69757a;--rule:#d9d5cb;--rule-soft:#e6e2d8;
  --accent:#0a676d;--accent-strong:#064d52;--accent-wash:#d8eae8;
  --mark:#f3dc86;--line-hl:#f9edbd;
  --ok:#1d6b43;--ok-wash:#deede3;--warn:#865400;--warn-wash:#f4e6c9;--neg:#66488a;--neg-wash:#eae2f2;
  --x-kw:#8a3a8e;--x-st:#2c6937;--x-nu:#9d4c12;--x-fn:#1d57a1;--x-bi:#0a676d;--x-co:#747d79;--x-at:#86470f;
  --x-de:#a3312a;--x-in:#22703e;--del-bg:#f6dfdb;--ins-bg:#dbeedd;
  --shadow:0 1px 2px rgb(20 30 32 / .06),0 10px 30px rgb(20 30 32 / .12);
  --serif:"Source Serif 4","Iowan Old Style",Charter,Georgia,serif;
  --sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --top:3.5rem;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#101516;--bg-raised:#151b1d;--bg-sunk:#1b2224;--code-bg:#0c1112;
  --ink:#e2e6e4;--ink-2:#b0bab8;--ink-3:#87928e;--rule:#2b3437;--rule-soft:#21292b;
  --accent:#5fc0ba;--accent-strong:#8fd7d2;--accent-wash:#163a3a;
  --mark:#65531a;--line-hl:#2e2912;
  --ok:#7ccf9e;--ok-wash:#153020;--warn:#e7b562;--warn-wash:#33280f;--neg:#c2a6e6;--neg-wash:#281f38;
  --x-kw:#d69ff0;--x-st:#9dd49a;--x-nu:#efa56b;--x-fn:#89b7f4;--x-bi:#5fc0ba;--x-co:#86918d;--x-at:#e5ae7a;
  --x-de:#f08b82;--x-in:#86d69b;--del-bg:#3d1f1d;--ins-bg:#173321;
  --shadow:0 1px 2px rgb(0 0 0 / .4),0 12px 32px rgb(0 0 0 / .5);
  color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#101516;--bg-raised:#151b1d;--bg-sunk:#1b2224;--code-bg:#0c1112;
  --ink:#e2e6e4;--ink-2:#b0bab8;--ink-3:#87928e;--rule:#2b3437;--rule-soft:#21292b;
  --accent:#5fc0ba;--accent-strong:#8fd7d2;--accent-wash:#163a3a;
  --mark:#65531a;--line-hl:#2e2912;
  --ok:#7ccf9e;--ok-wash:#153020;--warn:#e7b562;--warn-wash:#33280f;--neg:#c2a6e6;--neg-wash:#281f38;
  --x-kw:#d69ff0;--x-st:#9dd49a;--x-nu:#efa56b;--x-fn:#89b7f4;--x-bi:#5fc0ba;--x-co:#86918d;--x-at:#e5ae7a;
  --x-de:#f08b82;--x-in:#86d69b;--del-bg:#3d1f1d;--ins-bg:#173321;
  --shadow:0 1px 2px rgb(0 0 0 / .4),0 12px 32px rgb(0 0 0 / .5);
  color-scheme:dark}
*,*::before,*::after{box-sizing:border-box}
:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px);
  scroll-padding-top:calc(var(--top) + env(safe-area-inset-top,0px) + 1rem);-webkit-text-size-adjust:100%;text-size-adjust:100%}
[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--ink);font:400 1.0625rem/1.65 var(--serif);font-optical-sizing:auto;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;overflow-wrap:break-word}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:.18em}
a:hover{color:var(--accent-strong);text-decoration-thickness:2px}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:2px}
::selection{background:var(--accent-wash)}
code,kbd,pre{font-family:var(--mono)}
img,svg{max-width:100%}
.skip{position:absolute;left:-999px;top:0}
.skip:focus{left:1rem;top:calc(env(safe-area-inset-top,0px) + .5rem);z-index:100;background:var(--bg-raised);padding:.5rem .8rem;border:1px solid var(--rule);font-family:var(--sans)}

/* top bar */
.topbar{position:sticky;top:env(safe-area-inset-top,0px);z-index:40;height:var(--top);display:flex;align-items:center;gap:.75rem;
  padding-inline:1rem;background:var(--bg);border-bottom:1px solid var(--rule-soft);font-family:var(--sans)}
@supports (backdrop-filter:blur(1px)){.topbar{background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(10px)}}
.brand{display:flex;align-items:center;gap:.55rem;color:var(--ink);text-decoration:none;font:600 1rem/1 var(--sans);letter-spacing:-.01em;white-space:nowrap}
.brand:hover{color:var(--ink)}
.brand .mark{width:22px;height:22px;color:var(--accent);flex:none}
.navbtn{display:none;align-items:center;justify-content:center;width:2.25rem;height:2.25rem;border:1px solid var(--rule);border-radius:8px;background:var(--bg-raised);color:var(--ink);cursor:pointer;flex:none;padding:0}
.navbtn svg{width:20px;height:20px}
.search{position:relative;margin-left:auto;flex:0 1 25rem;min-width:0;display:flex;align-items:center}
.search .lens{position:absolute;left:.65rem;width:16px;height:16px;color:var(--ink-3);pointer-events:none}
.search-input{width:100%;min-width:0;height:2.25rem;padding:0 2.2rem 0 2.1rem;border:1px solid var(--rule);border-radius:8px;
  background:var(--bg-raised);color:var(--ink);font:400 .9rem var(--sans);-webkit-appearance:none;appearance:none}
.search-input::placeholder{color:var(--ink-3)}
.search-input:focus{outline:2px solid var(--accent);outline-offset:0;border-color:transparent}
.search-kbd{position:absolute;right:.55rem;font:500 .7rem var(--mono);color:var(--ink-3);border:1px solid var(--rule);border-radius:4px;padding:.05rem .35rem;pointer-events:none}
.search-input:focus + .search-kbd{display:none}
.results{position:absolute;right:0;top:calc(100% + .5rem);width:min(36rem,calc(100vw - 2rem));max-height:min(72vh,36rem);overflow:auto;
  background:var(--bg-raised);border:1px solid var(--rule);border-radius:10px;box-shadow:var(--shadow);padding:.35rem;z-index:50}
.res{display:grid;gap:.15rem;padding:.55rem .7rem;border-radius:7px;color:var(--ink);text-decoration:none}
.res:hover,.res.active{background:var(--accent-wash);color:var(--ink)}
.res-where{font:500 .68rem/1.3 var(--sans);text-transform:uppercase;letter-spacing:.07em;color:var(--ink-3)}
.res-head{font:600 .92rem/1.35 var(--sans)}
.res-snip{font:400 .82rem/1.45 var(--sans);color:var(--ink-2);overflow-wrap:anywhere}
.res-note,.res-count{margin:0;padding:.6rem .7rem;font:400 .82rem var(--sans);color:var(--ink-3)}
.res-count{border-top:1px solid var(--rule-soft);margin-top:.25rem;font-size:.75rem}
mark{background:var(--mark);color:inherit;border-radius:2px;padding:0 .08em}

/* layout */
.shell{display:grid;grid-template-columns:17rem minmax(0,1fr);max-width:94rem;margin-inline:auto}
.shell-home{grid-template-columns:minmax(0,1fr);max-width:none}
.sidenav{position:sticky;top:calc(var(--top) + env(safe-area-inset-top,0px));align-self:start;
  height:calc(100vh - var(--top) - env(safe-area-inset-top,0px));height:calc(100dvh - var(--top) - env(safe-area-inset-top,0px));
  overflow-y:auto;overscroll-behavior:contain;padding-block:1.25rem 3rem;padding-inline:1rem .75rem;border-right:1px solid var(--rule-soft);
  font:400 .875rem/1.4 var(--sans)}
.main{display:grid;grid-template-columns:minmax(0,46rem) 14.5rem;gap:3.5rem;justify-content:center;min-width:0;
  padding-block:2.25rem 5rem;padding-inline:2.5rem}
.main:has(> .article-code){grid-template-columns:minmax(0,62rem) 13rem}
.sn-home{display:block;padding:.4rem .5rem;margin-bottom:.4rem;font-weight:600;color:var(--ink);text-decoration:none;border-radius:6px}
.sn-home:hover{background:var(--bg-sunk);color:var(--ink)}
.sn-group summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:.5rem;padding:.4rem .5rem;border-radius:6px;font-weight:600;color:var(--ink)}
.sn-group summary::-webkit-details-marker{display:none}
.sn-group summary::before{content:"";flex:none;width:.38rem;height:.38rem;border-right:1.5px solid var(--ink-3);border-bottom:1.5px solid var(--ink-3);transform:rotate(-45deg);transition:transform .15s}
.sn-group[open] > summary::before{transform:rotate(45deg)}
.sn-group summary:hover{background:var(--bg-sunk)}
.sn-count{margin-left:auto;font:500 .7rem var(--mono);color:var(--ink-3)}
.sn-group ol{list-style:none;margin:.1rem 0 .7rem;padding:0 0 0 .85rem}
.sn-group li a{display:block;padding:.3rem .5rem;border-radius:5px;color:var(--ink-2);text-decoration:none}
.sn-group li a:hover{background:var(--bg-sunk);color:var(--ink)}
.sn-group li a[aria-current="page"]{background:var(--accent-wash);color:var(--accent-strong);font-weight:600}
.sn-group li a.code{font:400 .78rem/1.4 var(--mono);overflow-wrap:anywhere}
.sn-group .n{font:500 .72rem var(--mono);color:var(--ink-3);margin-right:.4rem}
.sn-sub{margin:.7rem 0 .15rem .5rem;font:600 .68rem/1.3 var(--sans);text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3)}
.sn-sub a{color:inherit;text-decoration:none}
.sn-sub a:hover{color:var(--accent)}

/* article */
.article{min-width:0}
.page-head{margin-bottom:2.25rem;padding-bottom:1.5rem;border-bottom:1px solid var(--rule)}
.eyebrow{margin:0 0 .65rem;font:600 .75rem/1.3 var(--sans);text-transform:uppercase;letter-spacing:.09em;color:var(--accent)}
.eyebrow a{color:inherit;text-decoration:none}
.eyebrow a:hover{text-decoration:underline}
.page-head h1{margin:0;font:600 clamp(1.8rem,1.25rem + 2.1vw,2.55rem)/1.14 var(--serif);letter-spacing:-.015em;text-wrap:balance}
.page-head h1 code{font-size:.9em}
.page-head h1.code-title{font:600 clamp(1.4rem,1.1rem + 1.4vw,1.9rem)/1.2 var(--mono);letter-spacing:-.01em;overflow-wrap:anywhere}
.dek{margin:.85rem 0 0;font:italic 400 1.2rem/1.5 var(--serif);color:var(--ink-2);text-wrap:pretty;max-width:42rem}
.dek code{font-style:normal;font-size:.8em}
.meta{display:flex;flex-wrap:wrap;align-items:center;gap:.4rem 1.1rem;margin-top:1.15rem;font:400 .8rem/1.4 var(--sans);color:var(--ink-3);font-variant-numeric:tabular-nums}
.ref{font:500 .76rem/1.2 var(--mono);color:var(--ink-2);background:var(--bg-sunk);border:1px solid var(--rule);border-radius:4px;padding:.14rem .42rem}
.srcpath{font:400 .74rem/1.3 var(--mono);overflow-wrap:anywhere}
.btn{font:500 .78rem/1.2 var(--sans);color:var(--ink-2);background:var(--bg-raised);border:1px solid var(--rule);border-radius:6px;padding:.32rem .65rem;cursor:pointer}
.btn:hover{color:var(--ink);border-color:var(--ink-3)}
.files{display:flex;flex-wrap:wrap;align-items:center;gap:.45rem;margin:-.75rem 0 2rem;font:600 .72rem var(--sans);text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3)}
.files span{margin-right:.25rem}
.chip{font:500 .76rem/1.2 var(--mono);text-transform:none;letter-spacing:0;padding:.28rem .6rem;border:1px solid var(--rule);border-radius:999px;background:var(--bg-raised);color:var(--ink-2);text-decoration:none}
.chip:hover{border-color:var(--accent);color:var(--accent)}
.cited{margin:-1rem 0 1.75rem;font:400 .85rem/1.6 var(--sans);color:var(--ink-2)}
.cited span{font:600 .7rem var(--sans);text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3);margin-right:.35rem}
.cited a{white-space:nowrap}

/* table of contents */
.rail{position:sticky;top:calc(var(--top) + env(safe-area-inset-top,0px) + 2rem);align-self:start;
  max-height:calc(100vh - var(--top) - env(safe-area-inset-top,0px) - 4rem);overflow:auto;overscroll-behavior:contain;font:400 .8rem/1.35 var(--sans)}
.rail-title{margin:0 0 .6rem;font:600 .7rem var(--sans);text-transform:uppercase;letter-spacing:.09em;color:var(--ink-3)}
.toc{list-style:none;margin:0;padding:0;border-left:1px solid var(--rule)}
.toc a{display:block;padding:.28rem .75rem;margin-left:-1px;border-left:2px solid transparent;color:var(--ink-2);text-decoration:none}
.toc .toc-l3 a{padding-left:1.5rem;color:var(--ink-3)}
.toc a:hover{color:var(--ink)}
.toc a.active{color:var(--accent-strong);border-left-color:var(--accent)}
.toc-inline{display:none;margin:0 0 2rem;border:1px solid var(--rule);border-radius:8px;background:var(--bg-raised);font:400 .875rem/1.4 var(--sans)}
.toc-inline summary{cursor:pointer;padding:.65rem .9rem;font-weight:600;color:var(--ink)}
.toc-inline .toc{border-left:0;padding:0 .4rem .7rem;max-height:60vh;overflow:auto}
.toc-inline .toc a{border-left:0;border-radius:5px}

/* prose */
.prose{min-width:0}
.prose > :first-child{margin-top:0}
.prose p{margin:0 0 1.05rem}
.prose h2{margin:2.9rem 0 1rem;padding-top:1.4rem;border-top:1px solid var(--rule);font:600 1.55rem/1.25 var(--serif);letter-spacing:-.01em;text-wrap:balance}
.prose > h2:first-child,.prose hr + h2{border-top:0;padding-top:0}
.prose hr + h2{margin-top:0}
.prose h3{margin:2.2rem 0 .7rem;font:600 1.22rem/1.3 var(--serif);text-wrap:balance}
.prose h4{margin:1.8rem 0 .55rem;font:600 1rem/1.35 var(--sans)}
.prose h5,.prose h6{margin:1.5rem 0 .45rem;font:600 .82rem/1.35 var(--sans);text-transform:uppercase;letter-spacing:.06em;color:var(--ink-2)}
.prose h2 code,.prose h3 code{font-size:.85em}
.anchor{margin-left:.45rem;color:var(--ink-3);text-decoration:none;font:400 .75em var(--mono);opacity:0;transition:opacity .15s}
.anchor::before{content:"#"}
h2:hover > .anchor,h3:hover > .anchor,h4:hover > .anchor,h5:hover > .anchor,h6:hover > .anchor,.anchor:focus-visible{opacity:1}
@media (hover:none){.anchor{opacity:.5}}
.prose ul,.prose ol{margin:0 0 1.1rem;padding-left:1.5rem}
.prose li{margin:.3rem 0}
.prose li > p{margin:0 0 .45rem}
.prose li::marker{color:var(--ink-3)}
.prose ol > li::marker{font:500 .85em var(--sans)}
.prose .contains-task-list{list-style:none;padding-left:.25rem}
.prose .task-list-item-checkbox{margin:0 .55rem 0 0;vertical-align:-.08em;accent-color:var(--accent)}
.prose blockquote{margin:1.5rem 0;padding:.85rem 1.1rem;background:var(--bg-raised);border:1px solid var(--rule-soft);border-left:3px solid var(--accent);
  border-radius:0 8px 8px 0;color:var(--ink-2);font-size:.97rem}
.prose blockquote > :last-child{margin-bottom:0}
.prose hr{border:0;border-top:1px solid var(--rule);margin:2.5rem 0}
.prose strong{font-weight:650;color:var(--ink)}
.prose :not(pre) > code{font-size:.84em;background:var(--bg-sunk);border-radius:4px;padding:.1em .34em;overflow-wrap:anywhere}
.prose a code{color:inherit}
.muted{color:var(--ink-3)}

/* evidence stamps */
.stamp{display:inline-block;font:600 .7em/1 var(--mono);letter-spacing:.06em;padding:.3em .45em .26em;border-radius:3px;border:1px solid;vertical-align:.1em;white-space:nowrap}
.s-confirmed{color:var(--ok);background:var(--ok-wash);border-color:color-mix(in srgb,var(--ok) 40%,transparent)}
.s-suspected{color:var(--warn);background:var(--warn-wash);border-color:color-mix(in srgb,var(--warn) 40%,transparent)}
.s-refuted{color:var(--neg);background:var(--neg-wash);border-color:color-mix(in srgb,var(--neg) 40%,transparent)}

/* tables */
.table-wrap{overflow-x:auto;margin:1.4rem 0 1.7rem;border:1px solid var(--rule);border-radius:8px;background:var(--bg-raised)}
.table-wrap table{border-collapse:collapse;width:100%;font:400 .86rem/1.5 var(--sans)}
.table-wrap table:has(th:nth-child(3)){min-width:30rem}
.table-wrap table:has(th:nth-child(4)){min-width:36rem}
.table-wrap table:has(th:nth-child(5)){min-width:44rem}
.table-wrap th{background:var(--bg-sunk);text-align:left;font-weight:600;color:var(--ink);vertical-align:bottom}
.table-wrap th,.table-wrap td{padding:.55rem .75rem;border-bottom:1px solid var(--rule-soft);vertical-align:top}
.table-wrap tr:last-child td{border-bottom:0}
.table-wrap td code,.table-wrap th code{font-size:.88em}
.table-wrap td.num{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.listing td:first-child{white-space:nowrap}

/* code */
.codeblock,.codefile{margin:1.4rem 0 1.7rem;border:1px solid var(--rule);border-radius:8px;background:var(--code-bg);overflow:hidden}
.codebar{display:flex;align-items:center;justify-content:space-between;gap:1rem;min-height:2.1rem;padding:.25rem .45rem .25rem .85rem;
  border-bottom:1px solid var(--rule-soft);font:600 .68rem/1 var(--sans);text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3)}
.codepath{font:500 .76rem/1.3 var(--mono);text-transform:none;letter-spacing:0;color:var(--ink-2);overflow-wrap:anywhere}
.copy{flex:none;font:500 .72rem/1 var(--sans);text-transform:none;letter-spacing:0;color:var(--ink-2);background:transparent;border:1px solid var(--rule);border-radius:5px;padding:.32rem .6rem;cursor:pointer}
.copy:hover{color:var(--ink);background:var(--bg-raised)}
.codeblock pre{margin:0;padding:.85rem 1rem 1rem;overflow-x:auto;font:400 .8rem/1.6 var(--mono);tab-size:4}
.codefile{margin-top:0}
.codefile pre{margin:0;padding:.55rem 0 .85rem;overflow-x:auto;font:400 .8rem/1.62 var(--mono);tab-size:4}
.codefile code{display:inline-block;min-width:100%}
.line{display:block;padding-right:1.25rem}
.ln{position:sticky;left:0;display:inline-block;width:3.4rem;padding-right:.9rem;margin-right:1rem;text-align:right;color:var(--ink-3);
  text-decoration:none;background:var(--code-bg);border-right:1px solid var(--rule-soft);-webkit-user-select:none;user-select:none}
.ln:hover{color:var(--accent)}
.line.ins,.line.ins .ln{background:var(--ins-bg)}
.line.del,.line.del .ln{background:var(--del-bg)}
.line:target,.line.hl,.line:target .ln,.line.hl .ln{background:var(--line-hl)}
.x-kw{color:var(--x-kw)}.x-st{color:var(--x-st)}.x-nu{color:var(--x-nu)}.x-fn{color:var(--x-fn)}.x-bi{color:var(--x-bi)}
.x-co{color:var(--x-co);font-style:italic}.x-at{color:var(--x-at)}.x-de{color:var(--x-de)}.x-in{color:var(--x-in)}.x-he{color:var(--x-fn);font-weight:600}

/* footer: backlinks and pager */
.page-foot{margin-top:3.5rem;padding-top:1.5rem;border-top:1px solid var(--rule);display:grid;gap:2rem;font-family:var(--sans)}
.backlinks h2{margin:0 0 .75rem;font:600 .72rem var(--sans);text-transform:uppercase;letter-spacing:.09em;color:var(--ink-3)}
.backlinks ul{list-style:none;margin:0;padding:0;display:grid;gap:.55rem;font-size:.9rem;line-height:1.45}
.backlinks a{font-weight:500}
.bl-title{color:var(--ink-2)}
.where{color:var(--ink-3);font-size:.9em}
.where a{font-weight:400}
.pager{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
.pager a{display:grid;gap:.15rem;padding:.85rem 1rem;border:1px solid var(--rule);border-radius:8px;text-decoration:none;color:var(--ink);background:var(--bg-raised);min-width:0}
.pager a:hover{border-color:var(--accent);color:var(--ink)}
.pager small{font:600 .68rem var(--sans);text-transform:uppercase;letter-spacing:.09em;color:var(--ink-3)}
.pg-label{font-weight:600;font-size:.92rem}
.pg-title{font-size:.8rem;color:var(--ink-2);line-height:1.4}
.pager .next{grid-column:2;text-align:right}

/* home */
.main-home{display:block;width:100%;max-width:72rem;margin-inline:auto;padding-block:3.25rem 5rem;padding-inline:2.5rem}
.cover{max-width:48rem;margin-bottom:3.5rem}
.cover h1{margin:0;font:600 clamp(2.5rem,1.6rem + 3.8vw,3.9rem)/1.02 var(--serif);letter-spacing:-.025em}
.subtitle{margin:.7rem 0 1.6rem;font:italic 400 clamp(1.15rem,1rem + .6vw,1.4rem)/1.4 var(--serif);color:var(--ink-2)}
.lede p{margin:0 0 .9rem;font-size:1.1rem;line-height:1.6}
.ledger{display:flex;flex-wrap:wrap;gap:.35rem 1.5rem;margin:1.6rem 0 0;padding:.7rem 0;border-block:1px solid var(--rule);
  font:400 .78rem/1.4 var(--mono);color:var(--ink-3);font-variant-numeric:tabular-nums}
.ledger b{color:var(--ink);font-weight:600}
.hint{margin:.9rem 0 0;font:400 .82rem/1.5 var(--sans);color:var(--ink-3)}
.hint kbd{font:500 .72rem var(--mono);border:1px solid var(--rule);border-radius:4px;padding:.05rem .35rem;color:var(--ink-2)}
.hint .btn{margin-left:.35rem}
@media (hover:none){.kbd-hint{display:none}}
.section-label{margin:0 0 1.6rem;font:600 .75rem var(--sans);text-transform:uppercase;letter-spacing:.1em;color:var(--ink-3)}
.series-cols{columns:2 24rem;column-gap:3.5rem}
.series-card{break-inside:avoid;margin:0 0 2.75rem}
.series-card h3{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;margin:0;padding-bottom:.55rem;border-bottom:2px solid var(--ink);
  font:600 1.35rem/1.2 var(--serif)}
.series-card h3 a{color:var(--ink);text-decoration:none}
.series-card h3 a:hover{color:var(--accent)}
.count{font:500 .7rem var(--sans);text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3);white-space:nowrap}
.series-dek{margin:.65rem 0 1.1rem;font:italic 400 1rem/1.5 var(--serif);color:var(--ink-2)}
.entries{list-style:none;margin:0;padding:0;display:grid;gap:.95rem}
.entries a{font:600 .97rem/1.35 var(--sans);color:var(--ink);text-decoration:none}
.entries a:hover{color:var(--accent);text-decoration:underline}
.entries .n{font:500 .78rem var(--mono);color:var(--accent);margin-right:.5rem}
.entries p{margin:.2rem 0 0;font:400 .87rem/1.5 var(--sans);color:var(--ink-2)}
.entries p code{font-size:.9em}
.home-prose{max-width:60rem;margin-top:1rem}
.home-prose > h2:first-child{border-top:1px solid var(--rule);padding-top:1.4rem}

/* toast */
.toast{position:fixed;left:50%;bottom:calc(1.25rem + env(safe-area-inset-bottom,0px));transform:translateX(-50%);z-index:80;display:grid;gap:.5rem;
  width:max-content;max-width:calc(100vw - 2rem);padding:.7rem 1rem;background:var(--ink);color:var(--bg);border-radius:8px;box-shadow:var(--shadow);font:500 .85rem/1.4 var(--sans)}
.toast-url{width:min(30rem,calc(100vw - 4rem));font:400 .8rem var(--mono);padding:.35rem .5rem;border-radius:5px;border:1px solid var(--ink-3);background:var(--bg);color:var(--ink)}
.scrim{position:fixed;inset:0;z-index:55;background:rgb(0 0 0 / .4)}

/* responsive */
@media (max-width:1279px){
  .main,.main:has(> .article-code){grid-template-columns:minmax(0,46rem)}
  .main:has(> .article-code){grid-template-columns:minmax(0,62rem)}
  .rail{display:none}
  .toc-inline{display:block}
}
@media (max-width:959px){
  .shell{grid-template-columns:minmax(0,1fr)}
  .navbtn{display:inline-flex}
  .sidenav{position:fixed;z-index:60;top:0;bottom:0;left:0;width:min(20rem,86vw);height:auto;background:var(--bg-raised);
    padding-top:calc(env(safe-area-inset-top,0px) + 1rem);border-right:1px solid var(--rule);box-shadow:var(--shadow);
    transform:translateX(-102%);visibility:hidden;transition:transform .2s ease,visibility .2s}
  body.nav-open .sidenav{transform:none;visibility:visible}
  .main{padding-block:1.75rem 4rem;padding-inline:1.25rem}
  .main-home{padding-block:2.25rem 4rem;padding-inline:1.25rem}
}
@media (max-width:560px){
  .brand-name{display:none}
  .search-kbd{display:none}
  .main,.main-home{padding-inline:1rem}
  .results{position:fixed;left:1rem;right:1rem;top:calc(var(--top) + env(safe-area-inset-top,0px) + .35rem);width:auto}
  .pager{grid-template-columns:1fr}
  .pager .next{grid-column:auto}
  .dek{font-size:1.1rem}
  body{font-size:1.03rem}
}
@media (prefers-reduced-motion:no-preference){:root.smooth{scroll-behavior:smooth}}
"""

JS = r"""
(() => {
  "use strict";
  const CB = window.CB || {root: "", ref: "", share: ""};
  const $ = (s, el) => (el || document).querySelector(s);
  const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
  // Smooth scrolling for in-page jumps only; a deep link on load should land instantly.
  addEventListener("load", () => setTimeout(() => document.documentElement.classList.add("smooth"), 0));

  // The host sets data-theme on the main page only; remember it so the other pages match.
  if (CB.hostTheme) {
    const sync = () => {
      try {
        const t = document.documentElement.getAttribute("data-theme");
        if (t) localStorage.setItem("cb-theme", t); else localStorage.removeItem("cb-theme");
      } catch (e) { /* no storage: other pages follow the OS setting */ }
    };
    sync();
    new MutationObserver(sync).observe(document.documentElement, {attributes: true, attributeFilter: ["data-theme"]});
  }

  // Toast and clipboard
  const toast = $("#toast");
  let toastTimer = 0;
  function say(msg, manual) {
    if (!toast) return;
    toast.replaceChildren();
    const span = document.createElement("span");
    span.textContent = msg;
    toast.append(span);
    if (manual) {
      const input = document.createElement("input");
      input.className = "toast-url";
      input.readOnly = true;
      input.value = manual;
      input.setAttribute("aria-label", "Link to copy");
      toast.append(input);
      requestAnimationFrame(() => { input.focus(); input.select(); });
    }
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, manual ? 9000 : 2200);
  }
  function copyText(text, done, failed) {
    let p = null;
    try { p = navigator.clipboard && navigator.clipboard.writeText(text); } catch (e) { p = null; }
    if (p && p.then) p.then(done, failed); else failed();
  }
  function shareLink(anchor) {
    if (!CB.share) return "";
    if (CB.ref === "home") return anchor ? CB.share + "#" + anchor : CB.share;
    return CB.share + "#" + CB.ref + (anchor ? "~" + anchor : "");
  }
  function copyLink(anchor, what) {
    const url = shareLink(anchor);
    if (url) copyText(url, () => say("Copied link to this " + what), () => say("Copy this link:", url));
  }
  function selectIn(el) {
    const r = document.createRange();
    r.selectNodeContents(el);
    const s = getSelection();
    s.removeAllRanges();
    s.addRange(r);
  }
  function flash(btn, text) {
    const old = btn.textContent;
    btn.textContent = text;
    setTimeout(() => { btn.textContent = old; }, 1400);
  }

  // Code pages: #L12 or #L12-L20 highlights lines; shift-click a line number to extend a range.
  function markLines() {
    $$(".line.hl").forEach((l) => l.classList.remove("hl"));
    const m = /^#L(\d+)(?:-L?(\d+))?$/.exec(location.hash);
    if (!m) return;
    const a = +m[1], b = m[2] ? +m[2] : a;
    let first = null;
    for (let i = Math.min(a, b); i <= Math.max(a, b); i++) {
      const el = document.getElementById("L" + i);
      if (el) { el.classList.add("hl"); first = first || el; }
    }
    if (first && m[2]) first.scrollIntoView({block: "center"});
  }
  function lineClick(ev, ln) {
    const n = +ln.textContent;
    const m = /^#L(\d+)/.exec(location.hash);
    let frag = "L" + n;
    if (ev.shiftKey && m) {
      ev.preventDefault();
      const a = Math.min(+m[1], n), b = Math.max(+m[1], n);
      frag = a === b ? "L" + a : "L" + a + "-L" + b;
      history.replaceState(null, "", "#" + frag);
      markLines();
    }
    const url = shareLink(frag);
    if (url) copyText(url, () => say("Copied link to " + (frag.includes("-") ? "these lines" : "line " + n)),
                      () => say("Copy this link:", url));
  }
  if ($(".codefile")) { addEventListener("hashchange", markLines); markLines(); }

  document.addEventListener("click", (ev) => {
    const t = ev.target;
    if (!(t instanceof Element)) return;
    const anchor = t.closest("a.anchor");
    if (anchor) { copyLink(decodeURIComponent(anchor.hash.slice(1)), "section"); return; }
    const ln = t.closest("a.ln");
    if (ln) { lineClick(ev, ln); return; }
    if (t.closest("[data-share]")) { copyLink("", "page"); return; }
    const btn = t.closest("button.copy");
    if (btn) {
      const box = btn.closest(".codeblock, .codefile");
      const pre = $("pre", box);
      const text = btn.hasAttribute("data-copy-file")
        ? $$(".lc", box).map((l) => l.textContent).join("\n") + "\n"
        : pre.innerText.replace(/\n$/, "");
      copyText(text, () => flash(btn, "Copied"), () => { selectIn(pre); say("Selected. Press Ctrl+C (or ⌘C) to copy."); });
    }
  });

  // Sidebar drawer on narrow screens
  const navBtn = $(".navbtn"), scrim = $(".scrim"), sidenav = $("#sidenav");
  function setNav(open) {
    document.body.classList.toggle("nav-open", open);
    if (navBtn) navBtn.setAttribute("aria-expanded", String(open));
    if (scrim) scrim.hidden = !open;
    if (open && sidenav) {
      const c = $('[aria-current="page"]', sidenav) || $("a", sidenav);
      if (c) c.focus();
    }
  }
  if (navBtn) navBtn.addEventListener("click", () => setNav(!document.body.classList.contains("nav-open")));
  if (scrim) scrim.addEventListener("click", () => setNav(false));
  if (sidenav) {
    const cur = $('[aria-current="page"]', sidenav);
    if (cur) sidenav.scrollTop = Math.max(0, cur.offsetTop - sidenav.clientHeight / 3);
  }

  // Table of contents: highlight the section being read
  const rail = $(".rail"), tocLinks = $$(".rail .toc a");
  if (tocLinks.length) {
    const heads = tocLinks.map((a) => document.getElementById(decodeURIComponent(a.hash.slice(1))));
    let ticking = false, active = -2;
    const spy = () => {
      ticking = false;
      let idx = -1;
      for (let i = 0; i < heads.length; i++) {
        const h = heads[i];
        if (!h) continue;
        if (h.getBoundingClientRect().top < 120) idx = i; else break;
      }
      if (idx === active) return;
      active = idx;
      tocLinks.forEach((a, i) => a.classList.toggle("active", i === idx));
      const link = tocLinks[idx];
      if (link && rail) {
        const top = link.offsetTop, bottom = top + link.offsetHeight;
        if (top < rail.scrollTop || bottom > rail.scrollTop + rail.clientHeight) rail.scrollTop = top - rail.clientHeight / 3;
      }
    };
    addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(spy); } }, {passive: true});
    spy();
  }

  // Search: the index loads on first use; every term must match; headings and titles weigh more.
  const q = $("#q"), box = $("#results");
  if (q && box) {
    let data = null, loading = null, failed = false, sel = -1, timer = 0;
    const load = () => loading || (loading = fetch(CB.root + "search-index.json")
      .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then((d) => {
        data = d.entries.map(([p, a, h, x]) => {
          const pg = d.pages[p];
          return {pg, a, h, x, lt: (pg.t + " " + pg.n).toLowerCase(), lh: h.toLowerCase(), lx: x.toLowerCase()};
        });
      })
      .catch(() => { data = []; failed = true; }));
    const count = (hay, t) => { let n = 0, i = hay.indexOf(t); while (i !== -1 && n < 5) { n++; i = hay.indexOf(t, i + t.length); } return n; };
    const reOf = (terms) => new RegExp(terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"), "gi");
    function mark(s, terms) {
      const re = reOf(terms);
      let out = "", last = 0, m;
      while ((m = re.exec(s))) {
        if (!m[0]) { re.lastIndex++; continue; }
        out += esc(s.slice(last, m.index)) + "<mark>" + esc(m[0]) + "</mark>";
        last = m.index + m[0].length;
      }
      return out + esc(s.slice(last));
    }
    function snippet(e, terms) {
      let i = -1;
      for (const t of terms) { const j = e.lx.indexOf(t); if (j !== -1 && (i === -1 || j < i)) i = j; }
      const from = i < 0 ? 0 : Math.max(0, i - 70);
      const s = e.x.slice(from, from + 210);
      return (from ? "…" : "") + mark(s, terms) + (from + 210 < e.x.length ? "…" : "");
    }
    function show(content) { box.innerHTML = content; box.hidden = false; }
    function close() { box.hidden = true; box.innerHTML = ""; sel = -1; }
    function run() {
      const raw = q.value.trim();
      if (!raw) { close(); return; }
      if (!data) { load().then(run); return; }
      if (failed) { show('<p class="res-note">The search index didn’t load, so search isn’t available here. The contents on the home page list every note.</p>'); return; }
      const terms = [...new Set(raw.toLowerCase().split(/\s+/))].filter(Boolean).slice(0, 8);
      const scored = [];
      for (const e of data) {
        let score = 0, ok = true;
        for (const t of terms) {
          const inT = e.lt.includes(t), inH = e.lh.includes(t), n = count(e.lx, t);
          if (!inT && !inH && !n) { ok = false; break; }
          score += (inH ? 10 : 0) + (inT ? 6 : 0) + n;
        }
        if (ok) scored.push([score, e]);
      }
      scored.sort((x, y) => y[0] - x[0]);
      const perPage = new Map(), list = [];
      for (const [, e] of scored) {
        const c = perPage.get(e.pg.u) || 0;
        if (c >= 3) continue;
        perPage.set(e.pg.u, c + 1);
        list.push(e);
        if (list.length >= 30) break;
      }
      sel = list.length ? 0 : -1;
      if (!list.length) { show('<p class="res-note">No matches for “' + esc(raw) + '”.</p>'); return; }
      show(list.map((e, i) => {
        const href = CB.root + e.pg.u + (e.a ? "#" + e.a : "");
        return '<a class="res' + (i === 0 ? " active" : "") + '" href="' + esc(href) + '">' +
          '<span class="res-where">' + esc(e.pg.s) + " · " + esc(e.pg.n) + "</span>" +
          '<span class="res-head">' + mark(e.h, terms) + "</span>" +
          '<span class="res-snip">' + snippet(e, terms) + "</span></a>";
      }).join("") + '<p class="res-count">' + (list.length === 30 ? "Top 30 matches" : list.length + (list.length === 1 ? " match" : " matches")) + "</p>");
    }
    function move(d) {
      const items = $$(".res", box);
      if (!items.length) return;
      sel = (sel + d + items.length) % items.length;
      items.forEach((a, i) => a.classList.toggle("active", i === sel));
      items[sel].scrollIntoView({block: "nearest"});
    }
    q.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(run, 80); });
    q.addEventListener("focus", () => { load(); if (q.value.trim()) run(); });
    q.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
      else if (e.key === "Enter") { const a = $$(".res", box)[sel]; if (a) { e.preventDefault(); close(); location.href = a.href; } }
      else if (e.key === "Escape") { e.preventDefault(); q.value = ""; close(); q.blur(); }
    });
    box.addEventListener("click", (e) => { if (e.target instanceof Element && e.target.closest(".res")) setTimeout(close, 0); });
    document.addEventListener("click", (e) => { if (!(e.target instanceof Element) || !e.target.closest(".search")) close(); });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && document.body.classList.contains("nav-open")) { setNav(false); if (navBtn) navBtn.focus(); }
    if (e.key === "/" && !e.metaKey && !e.ctrlKey && !e.altKey && q) {
      const a = document.activeElement;
      if (a && (a.tagName === "INPUT" || a.tagName === "TEXTAREA" || a.isContentEditable)) return;
      e.preventDefault();
      q.focus();
      q.select();
    }
  });
})();
"""

if __name__ == "__main__":
    sys.exit(main())

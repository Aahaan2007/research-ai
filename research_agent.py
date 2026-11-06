"""
Speech research agent.

topic -> search queries -> web search -> page text -> per-source facts
      -> speech draft in your voice -> HTML -> Google Doc (or local file)

Usage:
    python research_agent.py "money laundering loopholes in banking"
    python research_agent.py "climate finance" --tone light --angle "emerging economies"
"""

import argparse
import html
import io
import os
import re
import time

import ollama
import trafilatura

try:
    from ddgs import DDGS
except ImportError:  # older package name
    from duckduckgo_search import DDGS

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("RESEARCH_MODEL", "llama3.2:3b")  # or "qwen3:4b"
MAX_SOURCES = 8      # pages to read
PAGE_CHARS = 3500    # characters kept per page (keeps context small for 8GB RAM)

with open(os.path.join(HERE, "style_profile.txt"), encoding="utf-8") as f:
    STYLE = f.read()

LOG = print  # the web app swaps this for its own logger


# ---------------------------------------------------------------- LLM helper
def ask(system, user, temperature=0.3):
    kwargs = dict(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        options={"temperature": temperature, "num_ctx": 4096},
    )
    try:
        r = ollama.chat(think=False, **kwargs)  # turns off Qwen3 "thinking"
    except Exception:
        r = ollama.chat(**kwargs)
    text = r["message"]["content"]
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def clean(text):
    return re.sub(r"[*#]+", "", text).strip()


# ------------------------------------------------------------------- search
def make_queries(topic, angle):
    out = ask(
        "You write web search queries.",
        f"Topic: {topic}\nAngle: {angle or 'none'}\n"
        "Write 5 different short web search queries (3-8 words each) to find: "
        "key statistics, real-world case studies, expert views, criticism or "
        "counterarguments, and recent developments. One query per line. "
        "No numbering, no extra text.",
    )
    qs = [re.sub(r"^[\-\d\.\)\s\"']+|[\"']+$", "", ln).strip() for ln in out.splitlines()]
    qs = [q for q in qs if 3 <= len(q) <= 100][:5]
    if len(qs) < 3:
        qs = [topic, f"{topic} statistics", f"{topic} case study",
              f"{topic} criticism", f"{topic} latest news"]
    return qs


def find_urls(queries):
    ddgs = DDGS()
    seen, found = set(), []
    for q in queries:
        LOG(f"  searching: {q}")
        try:
            hits = ddgs.text(q, max_results=5)
        except Exception as e:
            LOG(f"    search failed ({e}); continuing")
            time.sleep(3)
            continue
        for h in hits:
            url = h.get("href")
            if url and url not in seen:
                seen.add(url)
                found.append({"url": url, "title": h.get("title") or url})
        time.sleep(1.5)  # be polite, avoids rate limits
    return found


def fetch_text(url):
    try:
        raw = trafilatura.fetch_url(url)
        text = trafilatura.extract(raw, include_comments=False, include_tables=False) if raw else None
    except Exception:
        return None
    if not text or len(text) < 400:
        return None
    return text[:PAGE_CHARS]


# ------------------------------------------------------------ per-source facts
def summarize(topic, text):
    return clean(ask(
        "You extract facts. Use ONLY the provided text. Never add outside knowledge.",
        f"Topic: {topic}\n\nTEXT:\n{text}\n\n"
        "List 3-5 key facts, figures, dates, names or short exact quotes from this "
        "text that are relevant to the topic. One per line starting with '- '. "
        "If nothing is relevant, write exactly: NOT RELEVANT",
    ))


def gather_sources(topic, angle):
    LOG("Step 1/4: planning searches")
    queries = make_queries(topic, angle)
    LOG("Step 2/4: searching and reading pages")
    candidates = find_urls(queries)
    sources = []
    for c in candidates:
        if len(sources) >= MAX_SOURCES:
            break
        LOG(f"  reading: {c['url'][:80]}")
        text = fetch_text(c["url"])
        if not text:
            continue
        summary = summarize(topic, text)
        if "NOT RELEVANT" in summary.upper() or len(summary) < 30:
            continue
        sources.append({"id": len(sources) + 1, "url": c["url"],
                        "title": c["title"], "summary": summary})
    return sources


# -------------------------------------------------------------- speech draft
def pick_points(topic, angle, sources):
    digest = "\n".join(f"[{s['id']}] {s['title']}\n{s['summary']}" for s in sources)
    out = ask(
        "You are a speechwriting strategist.",
        f"Topic: {topic}\nAngle: {angle or 'none'}\n\nRESEARCH NOTES:\n{digest}\n\n"
        "Choose the 3 strongest, distinct points for a speech. For each, write a short "
        "title, then '::', then the source numbers that support it, separated by commas. "
        "Example: Banks ignore vendor risk :: 1,4\nExactly 3 lines, nothing else.",
    )
    points = []
    for ln in out.splitlines():
        m = re.match(r"^\W*\d*\W*(.+?)\s*::\s*([\d,\s\[\]]+)", ln)
        if m:
            ids = [int(n) for n in re.findall(r"\d+", m.group(2))]
            ids = [i for i in ids if 1 <= i <= len(sources)]
            if ids:
                points.append({"title": m.group(1).strip(), "ids": ids})
    if len(points) < 3:  # fallback: split sources into three groups
        ids = [s["id"] for s in sources]
        size = max(1, len(ids) // 3)
        points = [{"title": f"Key finding {i + 1}", "ids": ids[i * size:(i + 1) * size] or ids[:1]}
                  for i in range(3)]
    return points[:3]


def notes_for(ids, sources):
    return "\n".join(s["summary"] for s in sources if s["id"] in ids)


def write_speech(topic, angle, audience, tone, sources):
    LOG("Step 3/4: writing the speech draft in your voice")
    points = pick_points(topic, angle, sources)
    pun = ("You may include ONE light pun if it fits naturally."
           if tone == "light" else "Do NOT use any puns. This is a serious speech.")

    first = points[0]
    opening = clean(ask(
        STYLE,
        f"Topic: {topic}\nAudience greeting: 'Greetings {audience},'\n\nRESEARCH NOTES:\n"
        f"{notes_for(first['ids'], sources)}\n\n"
        "Write the opening: 1-2 punchy sentences built on the single most striking fact "
        "in the notes, then the greeting line, then ONE pivot sentence that sets up the "
        f"argument. Use ONLY the notes. {pun}",
        temperature=0.7,
    ))

    body = []
    for i, p in enumerate(points):
        extra = ("Make this paragraph AGGRESSIVE: call out negligence or failure directly. "
                 if i == 1 else "")
        text = clean(ask(
            STYLE,
            f"Topic: {topic}\nWrite ONE speech paragraph (90-130 words) making this point: "
            f"{p['title']}\n\nUse ONLY these research notes:\n{notes_for(p['ids'], sources)}\n\n"
            f"{extra}Put one key word in ALL CAPS. {pun}",
            temperature=0.7,
        ))
        body.append({"text": text, "ids": p["ids"]})

    closing = clean(ask(
        STYLE,
        f"Topic: {topic}\nThe speech made these points:\n"
        + "\n".join(f"- {p['title']}" for p in points)
        + "\n\nWrite a 3-4 sentence closing that lands the central argument and ends on "
        f"one short, hard-hitting line. Add NO new facts or numbers. {pun}",
        temperature=0.7,
    ))
    return {"opening": opening, "opening_ids": first["ids"], "body": body, "closing": closing}


# ---------------------------------------------------------------- build doc
def esc(t):
    return html.escape(t)


def cite_links(ids, sources):
    by_id = {s["id"]: s for s in sources}
    return " ".join(f'<a href="{esc(by_id[i]["url"])}">[{i}]</a>' for i in ids if i in by_id)


def paragraphs(text):
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return "".join(f"<p>{esc(p).replace(chr(10), '<br>')}</p>" for p in parts)


def build_html(topic, sources, speech):
    h = [f"<h1>Research: {esc(topic)}</h1>",
         f"<p><i>Generated {time.strftime('%d %b %Y')}. Verify every figure before using it on stage.</i></p>",
         "<h2>1. Speech draft (in your voice)</h2>",
         "<h3>Opening</h3>", paragraphs(speech["opening"]),
         f"<p>Sources: {cite_links(speech['opening_ids'], sources)}</p>"]
    for i, b in enumerate(speech["body"], 1):
        h += [f"<h3>Point {i}</h3>", paragraphs(b["text"]),
              f"<p>Sources: {cite_links(b['ids'], sources)}</p>"]
    h += ["<h3>Closing</h3>", paragraphs(speech["closing"]),
          "<h2>2. Research digest (facts by source)</h2>"]
    for s in sources:
        items = [ln.lstrip("-* ").strip() for ln in s["summary"].splitlines() if ln.strip()]
        h.append(f"<h3>[{s['id']}] {esc(s['title'])}</h3>")
        h.append(f'<p><a href="{esc(s["url"])}">{esc(s["url"])}</a></p>')
        h.append("<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>")
    h.append("<h2>3. Sources</h2><ol>")
    for s in sources:
        h.append(f'<li><a href="{esc(s["url"])}">{esc(s["title"])}</a></li>')
    h.append("</ol>")
    return "<html><body>" + "\n".join(h) + "</body></html>"


# -------------------------------------------------------------- google drive
def upload_to_drive(title, html_str):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload

    scopes = ["https://www.googleapis.com/auth/drive.file"]
    token_path = os.path.join(HERE, "token.json")
    cred_path = os.path.join(HERE, "credentials.json")

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = InstalledAppFlow.from_client_secrets_file(cred_path, scopes).run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    service = build("drive", "v3", credentials=creds)
    media = MediaIoBaseUpload(io.BytesIO(html_str.encode("utf-8")), mimetype="text/html")
    file = service.files().create(
        body={"name": title, "mimeType": "application/vnd.google-apps.document"},
        media_body=media,
        fields="id,webViewLink",
    ).execute()
    return file["webViewLink"]


# ---------------------------------------------------------------------- main
def run(topic, angle="", audience="Delegates and the EB", tone="serious", log=print):
    """Full pipeline. Returns (local_path, google_doc_link_or_None, html) or (None, None, None)."""
    global LOG
    LOG = log

    sources = gather_sources(topic, angle)
    if len(sources) < 2:
        LOG("Found too few usable sources. Try a broader topic or run again.")
        return None, None, None

    speech = write_speech(topic, angle, audience, tone, sources)

    LOG("Step 4/4: building the document")
    doc = build_html(topic, sources, speech)

    os.makedirs(os.path.join(HERE, "output"), exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:50]
    local_path = os.path.join(HERE, "output", f"{slug}.html")
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(doc)
    LOG(f"Saved local copy: {local_path}")

    link = None
    if os.path.exists(os.path.join(HERE, "credentials.json")):
        link = upload_to_drive(f"Research: {topic}", doc)
        LOG(f"Google Doc ready: {link}")
    else:
        LOG("No credentials.json found, so skipped the Google Doc upload.")
    return local_path, link, doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("topic")
    ap.add_argument("--angle", default="", help="specific angle or stance")
    ap.add_argument("--audience", default="Delegates and the EB", help="used in the greeting line")
    ap.add_argument("--tone", choices=["serious", "light"], default="serious",
                    help="'light' allows one pun")
    args = ap.parse_args()
    run(args.topic, args.angle, args.audience, args.tone)


if __name__ == "__main__":
    main()
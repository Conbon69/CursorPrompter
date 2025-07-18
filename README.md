````markdown
# Reddit → SaaS Idea Finder 🪄🚀

A one‑stop toolkit that:

1. **Scrapes** Reddit posts & comments from subreddits you choose  
2. **Filters** for *real*, *software‑solvable* pain‑points with GPT‑4o‑mini  
3. **Designs** a 1‑to‑3‑feature MVP for each viable problem (no generic CRUD apps!)  
4. **Generates** a step‑by‑step **Cursor playbook** so you can build the MVP at lightning speed  
5. Lets you explore everything via a **Streamlit GUI** or an easy CLI

---

## Key Components

| File | Role |
|------|------|
| **`standalone_reddit_scraper.py`** | Self‑contained CLI & library. Houses the whole scrape → GPT pipeline and writes results to `results.jsonl`. |
| **`gui_reddit_scraper.py`** (or `gui_for_main.py`) | Streamlit front‑end: pick subs, kick off scrapes, browse & download ideas. |
| **`scraper.db`** | SQLite store that remembers which Reddit submissions you’ve already processed—prevents duplicate analysis. |
| **`results.jsonl`** | Append‑only ledger of every viable idea, its solution proposal, and the Cursor playbook. Each line is a complete JSON record. |
| **`.env`** | Holds credentials for Reddit & OpenAI (kept out of Git). |

---

## Features

- **Viability analysis** – GPT decides if a discussion exposes a genuine, paid‑worthy problem.
- **Context‑rich solutions** – target market + post excerpt pushed into the prompt; strong guardrail forbids generic task managers.
- **Cursor playbook** – numbered prompts that you can paste into Cursor’s chat to scaffold the entire project (repo → schema → endpoints → tests → deploy).
- **Duplicate protection** – the scraper won’t spend tokens on a post you’ve handled before.
- **Two launch modes**  
  * **CLI** – great for cron jobs or data batches  
  * **GUI** – tweak subreddits, watch ideas stream in, download JSON right in the browser.

---

## Installation

```bash
git clone <this‑repo>
cd Reddit‑SaaS‑Idea‑Finder
python -m venv venv && source venv/bin/activate   # Windows: .\venv\Scripts\activate
pip install -r requirements.txt                   # or pip install praw openai python-dotenv streamlit pandas
````

Create a **`.env`** at the project root:

```
REDDIT_CLIENT_ID=xxxx
REDDIT_CLIENT_SECRET=yyyy
REDDIT_USER_AGENT=RedditIdeaFinder/0.3
OPENAI_API_KEY=sk-...
OPENAI_ORG=org_...        # optional
```

---

## Quick Start — CLI

```bash
python standalone_reddit_scraper.py \
  --subreddits consulting startups ChatGPT \
  --posts-per-subreddit 5 \
  --comments-per-post 20 \
  --output results.jsonl
```

*New viable ideas append to `results.jsonl`; duplicates are skipped automatically.*

---

## Quick Start — GUI

```bash
streamlit run gui_for_main.py
```

* Open [http://localhost:8501](http://localhost:8501)
* Enter comma‑separated subreddits, tweak sliders, hit **“🚀 Scrape now”**
* Table updates live; click **Download JSONL** any time.

---

## Result Schema

```jsonc
{
  "meta":   { "uuid": "...", "scraped_at": "2025‑07‑13T19:31:17Z" },
  "reddit": { "subreddit": "startups", "url": "...", "title": "Feedback Friday" },
  "analysis": {
    "is_viable": true,
    "problem_description": "...",
    "target_market": "...",
    "confidence_score": 0.83
  },
  "solution": {
    "solution_description": "...",
    "tech_stack": ["Next.js", "Supabase"],
    "mvp_features": ["Feature A", "Feature B"],
    "est_development_time": "10–14 days"
  },
  "cursor_playbook": [
    "Prompt 1 – create repo…",
    "Prompt 2 – design schema…",
    "…"
  ]
}
```

---

## Customising

* **Change model / temperature** – edit `MODEL` or `TEMPERATURE` constants in `standalone_reddit_scraper.py`.
* **Different sorting** – in `scrape_subreddit()` switch `.hot()` to `.new()` or `.top(time_filter="day")`.
* **Longer context** – raise `context` slice length (default 1 200 chars) passed to `SOLUTION_PROMPT`.
* **Different storage** – swap SQLite functions in `gui_reddit_scraper.py` for Postgres, Supabase, etc.

---

## Troubleshooting

| Problem                                                                    | Fix                                                                                                                                                                                  |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `AttributeError: module 'streamlit' has no attribute 'experimental_rerun'` | You’re on an older Streamlit. Keep the fallback block in the GUI or run `pip install --upgrade streamlit`.                                                                           |
| Duplicate ideas still appear                                               | `scraper.db` only de‑dupes by Reddit post ID. If you scrape with *new* sort order, IDs are unique and no dupe should appear; otherwise bump the `post_limit` or adjust the DB logic. |
| Costs creeping up                                                          | Lower `posts-per-subreddit`, shorten `context`, or switch to `gpt‑3.5‑turbo` in the `MODEL` constant.                                                                                |

---

## License

MIT – do whatever you want, just don’t blame us if you ship an MVP that becomes a unicorn. 🦄

---

> Made with ☕, GPT‑4o‑mini, and a little vibe‑coding magic.

### Local dev

```bash
pip install -r requirements.txt
# add secrets in .streamlit/secrets.toml
```

```
```

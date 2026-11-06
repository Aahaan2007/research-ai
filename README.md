# Speech Research Agent

A local, free research assistant for public speakers. Give it a topic and it searches the web, reads the pages, and produces a Google Doc containing a cited research digest and a speech draft written in your own style, ready to copy into a script.

Everything runs on your own machine. The language model is a small local model served by [Ollama](https://ollama.com), so there are no paid API keys.

## What you get

For every topic, one Google Doc with three parts:

1. **Speech draft**: an opening, three points and a closing in your voice, with hyperlinked source markers like [1] [3].
2. **Research digest**: key facts, figures, dates and quotes, grouped by source, each with its link.
3. **Sources**: a numbered list of every page used.

A local HTML copy is also saved in `output/`.

## How it works

```
topic
  -> LLM writes 5 search queries
  -> DuckDuckGo search (no API key)
  -> trafilatura extracts page text
  -> LLM pulls facts from each page, one page at a time
  -> LLM picks 3 strongest points, then writes each in your voice
  -> HTML is built and uploaded to Google Drive as a Google Doc
```

Source attribution is done by the code, not the model. Each page gets a number and a link, and the code attaches them to whatever the model writes from that page. This matters because small local models are unreliable at remembering where a fact came from.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) with at least one small model, for example `llama3.2:3b` or `qwen3:4b` (tested target: a Mac with 8 GB RAM)
- A Google account (only for the Google Doc upload; without it the agent still saves a local HTML file)

## Setup

### 1. Install Ollama and a model

```bash
brew install ollama
brew services start ollama
ollama pull llama3.2:3b
ollama pull qwen3:4b
```

### 2. Install the project

```bash
git clone <your-repo-url>
cd speech-research-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Add your writing style

Edit `style_profile.txt`. It is the prompt that teaches the model how you speak: how you open, how you structure points, how you use emphasis and tone. The included file is an example; replace it with a profile built from your own speeches.

### 4. Set up the Google Doc upload (optional)

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create a project.
2. Enable the **Google Drive API**.
3. Open **Google Auth Platform**, complete the setup wizard, choose **External**, and under **Audience** add your own Gmail address as a **test user**.
4. Under **Clients**, create an **OAuth client ID** of type **Desktop app**.
5. Download the JSON file, rename it `credentials.json`, and put it in the project folder.

On the first run a browser window opens for you to sign in. Google will warn that the app is unverified; this is expected for your own project (Advanced, then continue). A `token.json` file is created so you only sign in once.

The script requests only the `drive.file` scope, so it can only see files it creates.

## Usage

### Web interface

```bash
streamlit run app.py
```

On macOS you can also run `chmod +x start.command` once and then double-click `start.command`.

### Command line

```bash
python research_agent.py "money laundering loopholes in banking"
python research_agent.py "climate finance" --angle "emerging economies" --tone light
```

| Option | Meaning | Default |
|---|---|---|
| `--angle` | A specific angle or stance for the research | none |
| `--audience` | Used in the greeting line | `Delegates and the EB` |
| `--tone` | `serious` (no puns) or `light` (allows one pun) | `serious` |

Choose the model with an environment variable:

```bash
RESEARCH_MODEL=qwen3:4b python research_agent.py "your topic"
```

## Project structure

```
research_agent.py   the pipeline (search, read, summarise, write, upload)
app.py              Streamlit web interface
style_profile.txt   your writing style, loaded into every prompt
requirements.txt    Python dependencies
start.command       double-click launcher for macOS
output/             local HTML copies (created on first run, git-ignored)
```

## Security: keep these files private

`credentials.json` and `token.json` give access to your Google account's Drive permissions for this app. They are listed in `.gitignore` and must never be committed or shared. If you ever push them by mistake, delete the OAuth client in the Google Cloud console and create a new one.

## Limitations

- Small local models sometimes miss your style or write a weak paragraph. Re-running or switching models often helps.
- The model can still misread a source. **Verify every statistic and quote before you use it in a speech.**
- DuckDuckGo may rate-limit you if you run many searches in a row. Wait a minute and retry.
- Pages that block scrapers or need JavaScript will be skipped.
- Runs take a few minutes on a laptop with 8 GB of RAM.

## License

Add a license of your choice (for example MIT) before making the repository public.
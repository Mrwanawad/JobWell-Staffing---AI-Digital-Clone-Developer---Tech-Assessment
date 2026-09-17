# Install, run, deploy

Everything operational lives here. For what the project is and why, see the
[README](../README.md).

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- A Google Gemini API key from https://aistudio.google.com/apikey

## Setup

```bash
cp .env.example .env     # then add your Gemini key and model id
uv sync
```

`uv sync` installs from `pyproject.toml`. If you would rather use plain pip:

```bash
pip install -r src/requirements.txt
```

Both lists describe the same four direct dependencies. `src/requirements.txt`
sits next to the app entrypoint because that is where Streamlit Community Cloud
looks for it.

## Run

Both commands run from the project root.

```bash
uv run python src/demo.py            # the three required tasks, with checks
uv run streamlit run src/app.py      # the UI, at localhost:8501
```

`demo.py` writes `demo_output.md`, a transcript of all three tasks.

To start from a clean slate, delete the queue and the saved corrections:

```bash
rm -f data/pending_questions.json data/corrections.json
```

## Configuration

Settings resolve in one place, `src/services/config.py`, in this order:

1. **Streamlit secrets** (`.streamlit/secrets.toml` locally, the Secrets box on
   Streamlit Community Cloud). There is no `.env` on the cloud, so this comes
   first.
2. **Environment variables**, loaded from `.env`. This is how `demo.py` runs,
   where there is no Streamlit runtime at all.

Placeholder values left over from the example files are treated as unset, so a
half-filled template fails with a clear message instead of sending a fake key
to the API.

Neither `.env` nor `.streamlit/secrets.toml` is committed. The templates
`.env.example` and `.streamlit/secrets.toml.example` are.

| Setting | Meaning |
|---|---|
| `LLM_BACKEND` | Which provider to use. Defaults to `gemini`. |
| `GEMINI_API_KEY` | Your key from Google AI Studio. |
| `GEMINI_MODEL_ID` | The exact model id, for example `gemini-3-flash-preview`. |

## Deploying to Streamlit Community Cloud

1. Push to a public GitHub repository.
2. On share.streamlit.io, point a new app at the repo with main file
   `src/app.py`.
3. Open **Advanced settings, Secrets** and paste the three lines below with
   your real values. This is TOML, not `.env`: the quotes and the spaces around
   the equals sign are required, and copying `.env` lines verbatim will not
   parse.

   ```toml
   LLM_BACKEND = "gemini"
   GEMINI_API_KEY = "your-key"
   GEMINI_MODEL_ID = "your-model-id"
   ```

4. Deploy. The sidebar shows which source the key came from, so a misconfigured
   deploy is visible immediately rather than failing as "invalid key".

Community Cloud installs from `src/requirements.txt`. It looks for the
dependency file either in the repository root or in the same directory as the
entrypoint, and `src/requirements.txt` sits beside `src/app.py`, so it is
found. The file lists direct dependencies only and lets pip resolve the rest,
because pinning the full transitive tree tends to fight the platform's base
image.

## Troubleshooting

**"API key not valid" while `.env` looks correct.** An exported shell variable
was shadowing the file. `config.py` loads `.env` with `override=True` so the
file always wins, but a stale `GEMINI_API_KEY` in your environment will still
affect anything else you run in that shell.

**The UI shows an old prompt after an edit.** Streamlit reruns the script but
keeps imported modules cached. Restart the server rather than pressing Rerun.

**Port 8501 is not available.** Another instance is already running. Either
stop it, or start on another port with `--server.port 8502`.

**The queue is empty after a restart on Community Cloud.** Expected. The files
in `data/` are written to the container's local disk, which resets when the app
restarts, so the queue and the corrections are per-session there. Locally they
persist. For real use this moves to a small database, which is noted in the
strategy.

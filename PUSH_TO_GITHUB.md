# Push to GitHub

## Prerequisites

1. **GitHub Account** — [github.com](https://github.com)
2. **Git Installed** — [git-scm.com/download/win](https://git-scm.com/download/win)
3. **Personal Access Token (PAT)** — needed for password authentication (see step 4)

## Steps

### 1. Create a GitHub repository

Go to [github.com/new](https://github.com/new):
- **Name:** `ohio_voter_registration_parser`
- **Description:** Ohio voter registration analysis pipeline — download, clean, analyse, visualise
- **Visibility:** Your choice
- **Do NOT** initialise with README (we already have one)

Copy the HTTPS URL: `https://github.com/YOUR_USERNAME/ohio_voter_registration_parser.git`

### 2. Open a terminal in the project folder

In VSCode: **View → Terminal** or `Ctrl+``

### 3. Initialise git and push

```bash
git init
git add .
git commit -m "Initial commit: Ohio voter registration analysis pipeline"
git remote add origin https://github.com/YOUR_USERNAME/ohio_voter_registration_parser.git
git branch -M main
git push -u origin main
```

### 4. Authenticate

When prompted for credentials:
- **Username:** Your GitHub username
- **Password:** A Personal Access Token — NOT your account password

**To create a PAT:**
1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Generate new token (classic)
3. Name it (e.g. "VSCode"), check `repo`, generate and copy it
4. Paste it when Git prompts for password

## What gets pushed

```
ohio_voter_registration_parser/
├── ohio_voter_pipeline.py       ← download + orchestration script
├── voter_data_cleaner_v2.py     ← analysis engine
├── voter_analysis.ipynb         ← Jupyter notebook
├── requirements.txt
├── README.md
├── RUN_LOCALLY.md
├── PUSH_TO_GITHUB.md
├── JUPYTER_QUICKSTART.md
├── .gitignore
└── docs/                        ← web dashboard (HTML + JS + sample JSON)
```

## What stays out of git

The `.gitignore` excludes voter data, logs, outputs, and the virtual environment:

- `source/` — downloaded voter files (re-fetchable via `ohio_voter_pipeline.py`)
- `*.xlsx`, `*.csv` — analysis outputs
- `*.txt` — excluded broadly as an extra safeguard against accidentally uploading
  large government data files; documentation uses `.md` instead
- `logs/` — run logs
- `download_manifest.json` — local file paths, machine-specific
- `.venv/` — virtual environment

## Verification

After pushing, visit your repo on GitHub and confirm these files are present and
that `source/`, `*.xlsx`, and `logs/` do **not** appear.

## Troubleshooting

| Error | Solution |
|---|---|
| `fatal: not a git repository` | Run `git init` first |
| `Authentication failed` | Token may have expired — regenerate at github.com/settings/tokens |
| `Permission denied (publickey)` | You're using SSH — switch to HTTPS or configure an SSH key |
| Large file rejected | Check that `source/` and any `.txt` files aren't being tracked: `git ls-files --cached source/` |

# Push to GitHub

## Prerequisites

1. **GitHub Account** — Have an account at https://github.com
2. **Git Installed** — Install from https://git-scm.com/download/win
3. **GitHub Credentials** — Use either:
   - Personal Access Token (PAT) — Recommended
   - SSH Key — For SSH-based auth

## Steps

### 1. Create GitHub Repository

Go to https://github.com/new and create a new public repository:
- **Name:** `ohio_voter_registration_parser`
- **Description:** Parse and clean Ohio voter registration data (Ohio Board of Elections) into analysis-ready Excel workbooks with demographic summaries
- **Public/Private:** Your choice
- **Do NOT initialize with README** (we already have one)

After creating, copy the HTTPS URL: `https://github.com/YOUR_USERNAME/ohio_voter_registration_parser.git`

### 2. Open Terminal in This Folder

In VSCode:
- **View → Terminal** or **Ctrl+`**
- Make sure you're in the folder with the Python files

Or open Command Prompt/PowerShell and navigate to:
```
C:\Users\motorbikematt\AppData\Roaming\Claude\local-agent-mode-sessions\33d1e0e5-9f9d-41cd-aef7-e26adbd88eed\9e83e185-2149-4543-8488-96565b7280f8\local_a7b2990a-65be-45f3-ad17-21e772958e3f\outputs
```

### 3. Initialize Git & Push

Run these commands in order (replace `YOUR_USERNAME` and `YOUR_TOKEN` as needed):

```bash
# Initialize git repo
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: voter data cleaner script"

# Add remote (replace URL with your repo URL)
git remote add origin https://github.com/YOUR_USERNAME/ohio_voter_registration_parser.git

# Push to main branch
git branch -M main
git push -u origin main
```

### 4. Authenticate

When prompted for credentials:
- **Username:** Your GitHub username
- **Password:** Use a Personal Access Token (PAT), NOT your password

**To create a PAT:**
1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Name it (e.g., "VSCode")
4. Check: `repo` (full control of private repositories)
5. Generate & copy the token
6. Paste when Git prompts for password

## Verification

After pushing, verify on GitHub:
1. Go to https://github.com/YOUR_USERNAME/ohio_voter_registration_parser
2. You should see:
   - `voter_data_cleaner.py`
   - `requirements.txt`
   - `README.md`
   - `RUN_LOCALLY.md`
   - `.gitignore`

## Troubleshooting

| Error | Solution |
|-------|----------|
| `fatal: not a git repository` | Make sure you ran `git init` first |
| `fatal: 'origin' does not appear to be a 'git' repository` | Verify the remote URL is correct: `git remote -v` |
| `Permission denied (publickey)` | You're using SSH — switch to HTTPS or set up SSH key |
| `Authentication failed` | Token may have expired or permissions incorrect — regenerate PAT |

## Next Steps

Once pushed, you can:
- Share the repo link with others
- Collaborate on improvements
- Track issues & feature requests via GitHub Issues
- Add CI/CD workflows (GitHub Actions) to auto-test on push

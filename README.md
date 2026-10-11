# Job Scout Agent

Hourly scan of about 135 sources: company career sites (Workday, Greenhouse, Lever, Ashby, SmartRecruiters), the Amazon and AMD career sites, The Muse, and GitHub new-grad job lists. Each posting is checked against your resume with OpenAI, and the results go to Telegram:

- **90+ fit**: you get an alert right away.
- **80–89 fit**: the job goes into a digest sent at 9 AM and 6 PM ET.
- **Other roles that accept a Computer Engineering degree** (for example, software new-grad roles): these go into the digest at **65+** and are labeled "CompE-degree match".
- **Other roles that accept a Computer Engineering degree** (for example, software new-grad roles): these go into the digest at **65+** and are labeled "CompE-degree match".

Settings, thresholds, preferences, and the company list are in `config/companies.yaml`.

## Setup

1. **Telegram bot**: In Telegram, message `@BotFather`, send `/newbot`, and copy the token. Send any message to your new bot, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `message.chat.id`.
2. **Gemini API key (free)**: At aistudio.google.com/apikey, click *Create API key*. No credit card is needed.
3. **Resume text**: Run `python -c "from src.resume_matcher import load_resume; print(load_resume(__import__('pathlib').Path('resume/resume.pdf')))" | pbcopy` to copy your resume text to the clipboard.
4. **Public GitHub repo**: Public repos get unlimited Actions minutes. `resume/` is in `.gitignore`, so the PDF is never pushed. Go to *Settings → Secrets and variables → Actions → Repository secrets* and add:
   - `GEMINI_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `RESUME_TEXT` (paste from step 3)
   - Optional: `OPENAI_API_KEY` with `LLM_PROVIDER=openai` and `LLM_MODEL=gpt-4o-mini` to use paid OpenAI instead of Gemini
   - `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` (optional, free at developer.adzuna.com)
   - `USAJOBS_API_KEY` / `USAJOBS_EMAIL` (optional, free at developer.usajobs.gov)
5. In the *Actions* tab, run **Scan jobs** manually once to seed the database.

## Local use

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY=... TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...
python -m src.main test-notify   # check that Telegram works
python -m src.main scan
python -m src.main digest --force
```

If the Telegram variables aren't set, messages are printed to the terminal instead of sent.

## Notes

- **Where the data lives**: The SQLite database (`data/jobs.db`) is carried between runs with the GitHub Actions cache. If that cache is evicted, already-seen jobs may be scored and sent again. That is limited by `max_age_days` and the cap on instant alerts per run.
- **Cost**: $0. Gemini's free tier allows about 1,000 scoring requests a day, and the agent scores 40 jobs an hour to stay under that. The first backlog of about 1,600 jobs takes roughly 2 days to work through. Public repos get unlimited Actions minutes; a private repo would exceed its 2,000 free minutes a month at this scan rate.
- **Adding companies**: For a Workday site, take the career URL `https://<host>.myworkdayjobs.com/<site>` and look in the browser network tab for the `/wday/cxs/<tenant>/<site>/jobs` request. For Greenhouse, Lever, or Ashby, the board token is the slug in the job board URL.

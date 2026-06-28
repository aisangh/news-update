# AI News Finder

Curates the **top 10 viral AI news stories** for Instagram Reels using free data sources.

## Setup

```bash
pip install -r ai_news_finder/requirements.txt
cp ai_news_finder/.env.example ai_news_finder/.env   # optional API keys
```

## Run

From this folder (`news-update`):

```bash
python run.py --days 2
```

Works on Windows, macOS, and Linux.

### Kaggle Notebook

The cleanest Kaggle setup is the ready-made notebook scaffold in
[`my-kaggle-notebook/`](./my-kaggle-notebook/). It clones this repo, installs
the dependencies, and runs the pipeline inside Kaggle.

If you want to run it manually in a Kaggle notebook cell, use:

```python
import os

os.environ["AI_NEWS_USE_HF"] = "1"
os.environ["AI_NEWS_USE_SUMMARY_MODEL"] = "1"
os.environ["AI_NEWS_SUMMARY_MODEL"] = "Qwen/Qwen2.5-1.5B-Instruct"

!python kaggle/launch.py --days 2 --reports-dir /kaggle/working/reports
```

```bash
python run.py --days 1
python run.py --days 3 --json
python run.py --days 7
python run.py --days 1 --output my_report.html
```

## Output

Reports are saved to **`reports/`**:

- `report_YYYY-MM-DD.html`
- `report_YYYY-MM-DD.txt`

On Kaggle, the default output directory is `/kaggle/working/reports` unless you
set `AI_NEWS_REPORTS_DIR` or pass `--reports-dir`.

If `sentence-transformers` is installed, the notebook will use a stronger
Hugging Face embedding model, `sentence-transformers/all-mpnet-base-v2`, to
rerank the shortlist and label the stories. The terminal output also prints
more stage-by-stage progress so you can see the pipeline moving.

If `transformers` is installed and `AI_NEWS_USE_SUMMARY_MODEL=1`, the notebook
will also use a local Qwen-style summarizer to rewrite the extracted article
text into cleaner newsletter copy. This is the fastest way to get the issue
closer to a polished 10/10 on Kaggle.

### GitHub Actions -> Kaggle Notebook

If you want GitHub Actions to trigger the Kaggle notebook automatically every
day, use the `my-kaggle-notebook/` scaffold plus the workflow in
`.github/workflows/run-kaggle-notebook.yml`.

What to do:

1. Replace `YOUR_KAGGLE_USERNAME` in [my-kaggle-notebook/kernel-metadata.json](./my-kaggle-notebook/kernel-metadata.json) with your Kaggle username.
2. Create Kaggle API credentials at Kaggle Settings -> API and download `kaggle.json`.
3. Add these GitHub repository secrets:
   - `KAGGLE_USERNAME`
   - `KAGGLE_KEY`
4. Make sure the Kaggle notebook accelerator is set to GPU in Kaggle. Kaggle controls the exact GPU flavor in the notebook settings.
5. Let GitHub Actions push the notebook daily at 04:30 UTC, which is 10:00 AM IST.

The notebook itself clones this repo, installs dependencies, and runs the
pipeline on Kaggle with the configured accelerator.

If you use the Kaggle workflow, consider disabling the direct-run schedules in
`.github/workflows/daily-run.yml` and `.github/workflows/weekly-run.yml` to
avoid duplicate runs.

## Layout

```
news-update/
├── run.py              # start here
├── README.md
├── my-kaggle-notebook/
├── reports/
└── ai_news_finder/     # all application code
```

## Optional API keys

Edit `ai_news_finder/.env`:

| Service | Sign up | Variable |
|---------|---------|----------|

RSS and Reddit work without keys.

## Daily cron

```
0 8 * * * cd /path/to/news-update && python run.py --days 1
```

## Requirements

Python 3.9+

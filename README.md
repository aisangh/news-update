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

To run the GitHub code inside a Kaggle notebook and save outputs in Kaggle's
working storage:

```python
!git clone https://github.com/aisangh/news-update.git
%cd news-update
!pip install -r requirements.txt
!pip install sentence-transformers
!pip install transformers accelerate sentencepiece
%env AI_NEWS_USE_SUMMARY_MODEL=1
%env AI_NEWS_SUMMARY_MODEL=Qwen/Qwen2.5-1.5B-Instruct
!python kaggle/launch.py --days 2
```

You can also direct reports somewhere else in Kaggle:

```python
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

## Layout

```
news-update/
├── run.py              # start here
├── README.md
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

HRT/TRT Telehealth Voice-of-Customer Analysis

A read-only Python tool that retrieves publicly available posts and comments
from a small set of subreddits via Reddit's Data API and produces aggregate,
offline summaries of consumer experiences with telehealth hormone replacement
therapy (HRT) and testosterone replacement therapy (TRT) providers.

What it does


Retrieves recent posts and comments (last 90 days) from:
r/trt, r/Testosterone, r/TRT_females, r/Menopause, r/HRT,
r/asktransgender, r/MtF, r/ftm
Produces aggregate summaries: common complaints, praised features,
pricing and insurance discussion frequency, and unmet-need mentions
Outputs local CSV files for personal analysis


What it does not do


Does not post, comment, vote, message, or modify anything on Reddit
Does not attempt to identify or profile individual users
Does not use Reddit content for AI/model training
Does not republish or redistribute Reddit content


Technical details


Language: Python 3, using PRAW
Authentication: read-only OAuth via a registered script-type app,
with a descriptive User-Agent per Reddit's Data API rules
Rate limits: respects PRAW's built-in rate limiting, staying under
100 queries per minute
Volume: periodic manual batch runs (approximately weekly),
roughly 5,000 to 20,000 requests per run
Environment: Google Colab or local Python


Data handling

Retrieved data is stored locally in CSV files, retained only for the
duration of the analysis, and never redistributed. Content deleted from
Reddit is deleted from local copies in accordance with Reddit's Data API
Terms.

Compliance

This project is intended to comply with Reddit's Developer Terms,
Data API Terms, and Responsible Builder Policy.

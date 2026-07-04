# =====================================================================
# HRT / TRT Telehealth VoC Reddit Analysis (Colab)
# =====================================================================
# CELL 1 — run this line alone in its own Colab cell first:
#
#   !pip install praw --quiet
#
# CELL 2 — paste everything below this comment block into a second cell.
#
# You will be prompted for:
#   - Reddit app client ID  (short string under your app's name at reddit.com/prefs/apps)
#   - Reddit app secret
#   - Your Reddit username  (used only in the User-Agent string, per Reddit's rules)
#
# Runs read-only. No password needed.
# Expected runtime: 20-60 min depending on comment volume (API cap: 100 req/min).
# =====================================================================

import praw
import prawcore
import re
import time
import datetime as dt
import pandas as pd
from getpass import getpass

# ---------------------------- CONFIG ---------------------------------

DAYS_BACK = 90

SUBREDDITS = [
    "trt",              # men's TRT, heavy telehealth-provider discussion
    "Testosterone",     # broader TRT community
    "TRT_females",      # women's testosterone therapy
    "Menopause",        # HRT for menopause, telehealth mentions frequent
    "HRT",              # general HRT
    "asktransgender",   # trans HRT, telehealth providers discussed often
    "MtF",
    "ftm",
]
# Edit freely. Removing a subreddit shortens runtime.

# Telehealth providers in the space. Keys are display names, values are
# regex patterns (word-bounded to limit false positives on words like
# "hone" or "alloy").
PROVIDERS = {
    "Hone Health":    r"\bhone( health)?\b",
    "Marek Health":   r"\bmarek\b",
    "Defy Medical":   r"\bdefy( medical)?\b",
    "TRT Nation":     r"\btrt nation\b",
    "Peter MD":       r"\bpeter ?md\b",
    "Matrix Hormones":r"\bmatrix( hormones)?\b",
    "Viking Alternative": r"\bviking( alternative)?\b",
    "Gameday":        r"\bgameday\b",
    "Maximus":        r"\bmaximus\b",
    "Hims/Hers":      r"\bhims\b|\bforhers\b|\bhers\b",
    "Midi Health":    r"\bmidi( health)?\b",
    "Alloy":          r"\balloy\b",
    "Evernow":        r"\bevernow\b",
    "Winona":         r"\bwinona\b",
    "Plume":          r"\bplume\b",
    "FOLX":           r"\bfolx\b",
    "QueerDoc":       r"\bqueerdoc\b",
    "GenderGP":       r"\bgendergp\b",
}

# Payment-method signals (rough, mention-based; see caveat in summary)
INSURANCE_RE = re.compile(
    r"\b(insurance|insured|copay|co-pay|deductible|prior auth\w*|coverage|"
    r"covered by|aetna|cigna|united ?health\w*|blue cross|bcbs|anthem|"
    r"kaiser|medicare|medicaid|tricare)\b", re.I)
OOP_RE = re.compile(
    r"\b(out[- ]of[- ]pocket|cash pay|self[- ]pay|paying cash|pay cash|"
    r"no insurance|without insurance|not covered|hsa|fsa)\b", re.I)

# Unmet-need / wishlist signals
WISH_RE = re.compile(
    r"\b(i wish|wish (there|they|it)|why (isn'?t|doesn'?t) (there|anyone)|"
    r"someone should|no one offers|doesn'?t exist|if only|would be nice if|"
    r"would pay for)\b", re.I)

# Crude sentiment lexicons (first pass only; refine with an LLM later)
POS_RE = re.compile(
    r"\b(love|great|smooth|easy|responsive|recommend|happy with|"
    r"impressed|painless|worth it|best)\b", re.I)
NEG_RE = re.compile(
    r"\b(scam|awful|terrible|horrible|ghosted|hidden fee\w*|upsell\w*|"
    r"waste|canceled on me|never (responded|shipped)|rip[- ]?off|"
    r"avoid|worst|frustrat\w*|nightmare)\b", re.I)

# Only fetch full comment trees for posts that look relevant
# (mention a provider, payment terms, or wishlist language).
# Set to True to fetch comments for every post (much slower).
FETCH_ALL_COMMENTS = False
MAX_COMMENTS_PER_POST = 300

# ---------------------------- AUTH -----------------------------------

client_id = getpass("Reddit app client ID: ").strip()
client_secret = getpass("Reddit app secret: ").strip()
username = input("Your Reddit username (for User-Agent only): ").strip()

reddit = praw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    user_agent=f"python:hrt-trt-voc-research:v0.1 (by /u/{username})",
)
reddit.read_only = True

# ---------------------------- COLLECT --------------------------------

cutoff = time.time() - DAYS_BACK * 86400
posts = {}  # id -> record

def keep(submission):
    if submission.created_utc < cutoff:
        return
    if submission.id in posts:
        return
    text = f"{submission.title}\n{submission.selftext or ''}"
    posts[submission.id] = {
        "id": submission.id,
        "subreddit": str(submission.subreddit),
        "created_utc": dt.datetime.utcfromtimestamp(
            submission.created_utc).isoformat(),
        "title": submission.title,
        "selftext": submission.selftext or "",
        "score": submission.score,
        "num_comments": submission.num_comments,
        "url": f"https://reddit.com{submission.permalink}",
        "_text": text,
    }

def drain(listing, label):
    n = 0
    try:
        for s in listing:
            keep(s)
            n += 1
    except prawcore.exceptions.PrawcoreException as e:
        print(f"    listing '{label}' stopped early: {e}")
    return n

for name in SUBREDDITS:
    sr = reddit.subreddit(name)
    print(f"r/{name}")
    try:
        drain(sr.new(limit=None), "new")
        drain(sr.top(time_filter="year", limit=1000), "top-year")
        # keyword searches extend coverage past the 1000-item listing cap
        for prov, pat in PROVIDERS.items():
            term = prov.split("/")[0]
            drain(sr.search(term, sort="new", time_filter="year",
                            limit=None), f"search:{term}")
    except prawcore.exceptions.PrawcoreException as e:
        print(f"  skipping r/{name}: {e}")
    print(f"  running total: {len(posts)} posts in window")

print(f"\nCollected {len(posts)} unique posts from the last {DAYS_BACK} days.")

# ---------------------------- COMMENTS -------------------------------

def looks_relevant(text):
    if INSURANCE_RE.search(text) or OOP_RE.search(text) or WISH_RE.search(text):
        return True
    return any(re.search(p, text, re.I) for p in PROVIDERS.values())

comments = []
targets = [p for p in posts.values()
           if FETCH_ALL_COMMENTS or looks_relevant(p["_text"])]
print(f"Fetching comment trees for {len(targets)} posts "
      f"(of {len(posts)} total)...")

for i, p in enumerate(targets, 1):
    try:
        sub = reddit.submission(id=p["id"])
        sub.comments.replace_more(limit=0)
        for c in sub.comments.list()[:MAX_COMMENTS_PER_POST]:
            body = c.body or ""
            comments.append({
                "post_id": p["id"],
                "comment_id": c.id,
                "subreddit": p["subreddit"],
                "created_utc": dt.datetime.utcfromtimestamp(
                    c.created_utc).isoformat(),
                "score": c.score,
                "body": body,
            })
    except prawcore.exceptions.PrawcoreException as e:
        print(f"  comment fetch failed for {p['id']}: {e}")
    if i % 50 == 0:
        print(f"  {i}/{len(targets)} posts done, "
              f"{len(comments)} comments so far")

print(f"Collected {len(comments)} comments.")

# ---------------------------- ANALYZE --------------------------------

docs = ([{"kind": "post", "text": p["_text"], "score": p["score"],
          "subreddit": p["subreddit"], "url": p["url"]}
         for p in posts.values()] +
        [{"kind": "comment", "text": c["body"], "score": c["score"],
          "subreddit": c["subreddit"],
          "url": f"https://reddit.com/comments/{c['post_id']}"}
         for c in comments])

# Payment mix
ins = oop = both = 0
for d in docs:
    i_hit = bool(INSURANCE_RE.search(d["text"]))
    o_hit = bool(OOP_RE.search(d["text"]))
    if i_hit and o_hit: both += 1
    elif i_hit: ins += 1
    elif o_hit: oop += 1
pay_total = ins + oop + both

# Per-provider stats
rows = []
for prov, pat in PROVIDERS.items():
    rx = re.compile(pat, re.I)
    hits = [d for d in docs if rx.search(d["text"])]
    rows.append({
        "provider": prov,
        "mentions": len(hits),
        "pos_signal": sum(1 for d in hits if POS_RE.search(d["text"])),
        "neg_signal": sum(1 for d in hits if NEG_RE.search(d["text"])),
        "insurance_mentions": sum(1 for d in hits
                                  if INSURANCE_RE.search(d["text"])),
        "oop_mentions": sum(1 for d in hits if OOP_RE.search(d["text"])),
    })
provider_df = pd.DataFrame(rows).sort_values("mentions", ascending=False)

# Wishlist / unmet needs
wishlist = [{"subreddit": d["subreddit"], "kind": d["kind"],
             "score": d["score"], "url": d["url"],
             "text": d["text"][:1500]}
            for d in docs if WISH_RE.search(d["text"])]

# ---------------------------- EXPORT ---------------------------------

posts_df = pd.DataFrame([{k: v for k, v in p.items() if k != "_text"}
                         for p in posts.values()])
comments_df = pd.DataFrame(comments)
wishlist_df = pd.DataFrame(wishlist)

posts_df.to_csv("posts.csv", index=False)
comments_df.to_csv("comments.csv", index=False)
provider_df.to_csv("provider_summary.csv", index=False)
wishlist_df.to_csv("wishlist_unmet_needs.csv", index=False)

print("\n================ SUMMARY ================")
print(f"Posts: {len(posts_df)}   Comments: {len(comments_df)}")
print(f"\nPayment-method mentions (n={pay_total} documents "
      f"that mention payment at all):")
if pay_total:
    print(f"  insurance-only language:      {ins}  "
          f"({ins/pay_total:.0%})")
    print(f"  out-of-pocket-only language:  {oop}  "
          f"({oop/pay_total:.0%})")
    print(f"  both mentioned:               {both}  "
          f"({both/pay_total:.0%})")
print("\nCaveat: these are mention rates in text, not a consumer survey.")
print("\nTop providers by mention volume:")
print(provider_df.head(12).to_string(index=False))
print(f"\nUnmet-need candidates captured: {len(wishlist_df)} "
      f"(see wishlist_unmet_needs.csv)")
print("\nFiles written: posts.csv, comments.csv, "
      "provider_summary.csv, wishlist_unmet_needs.csv")
print("Download via the Colab file browser (folder icon, left sidebar).")

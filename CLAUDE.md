# YTSPERBOT — Project Context for Claude Code

> **Aggiorna questo file dopo ogni sessione in cui cambi codice, actor, schemi DB o architettura.**
> Leggilo integralmente all'inizio di ogni sessione. Non esplorare il codebase finché non hai letto questo file.

---

## ✅ Checklist di Sessione (seguire in ordine) NEVER IGNORE IT!

- [ ] **1. Leggo CLAUDE.md** integralmente prima di aprire qualsiasi altro file
- [ ] **2. Chiedo contesto** se la richiesta dell'utente è ambigua o mancano info; altrimenti proseguo
- [ ] **3. Esploro la codebase** solo se le info in CLAUDE.md non sono sufficienti
- [ ] **4. Implemento** il fix / la feature
- [ ] **5. Scrivo i test** — unit, integration e/o system per il/i modulo/i toccato/i
- [ ] **6. Bug check** — controllo che il/i modulo/i toccato/i non abbia/abbiano bug non visti in precedenza
- [ ] **7. Test di regressione** — aggiungo test aggiuntivi se il bug check ha trovato qualcosa
- [ ] **8. Copertura test esistente** — controllo se mancano unit/integration/system test per funzionalità già presenti nel/nei modulo/i toccato/i; se sì li aggiungo, altrimenti continuo
- [ ] **9. Build & test** — eseguo la suite completa, verifico che tutto passi
- [ ] **10. Aggiorno CLAUDE.md** — sezione Modifiche Recenti, Gotcha, schema DB/API se cambiati
- [ ] **11. Aggiorno README.md** se la modifica è visibile all'utente o cambia il comportamento del sistema
- [ ] **12. Chiedo il backup del DB** all'utente prima di committare
- [ ] **13. Commit & push** (in inglese) dopo conferma backup ricevuta
- [ ] **14. Ricordo il ripristino del DB** all'utente dopo il push

---

## 1. Cos'è il progetto

Bot Python che monitora la nicchia **paranormale/occulto/horror** su YouTube, TikTok, Instagram, Reddit, Twitter/X, Pinterest, Google Trends e RSS. Invia alert Telegram quando rileva trend o contenuti virali. Ha una WebApp React (dashboard) e un'API FastAPI.

**Stack:** Python 3.14, FastAPI, SQLite, `schedule`, React + Vite, Apify, Render (hosting)

---

## 2. Entry Points

| File | Ruolo |
|---|---|
| `main.py` | Orchestratore: inizializza DB, avvia FastAPI in thread daemon, esegue scheduler loop (`schedule` library) |
| `api/app.py` | Crea l'app FastAPI, monta i router |
| `modules/config_manager.py` | Carica `config.yaml` → DB `bot_config`. Usa `get_config()` ovunque |
| `modules/database.py` | Unico punto di accesso al DB SQLite (`ytsperbot.db`) |

**Avvio produzione:** `python main.py` → scheduler + FastAPI porta `$PORT` (default 8080)
**Modalità test:** `python main.py --test` / `--scraper` / `--reddit` / `--rss` / `--comments` / `--trends` / `--twitter`

---

## 3. Moduli — Registro Completo

```
modules/
  apify_scraper.py      TikTok+Instagram outperformer detection via Apify
  bot_logger.py         Intercetta stdout → salva in DB (bot_logs table)
  competitor_monitor.py Monitora nuovi video e crescita iscritti competitor YouTube
  config_manager.py     Carica/legge config.yaml tramite DB bot_config
  cross_signal.py       Rileva convergenza di keyword su ≥3 piattaforme → alert
  database.py           Tutte le query SQLite (init, read, write)
  dispatcher.py         Router Apify vs nativo per Twitter, Reddit, Pinterest
  news_detector.py      NewsAPI.org — monitora keyword nelle notizie
  pinterest_apify.py    Pinterest trend via Apify (fatihtahta)
  pinterest_detector.py Pinterest trend via API nativa (fallback)
  reddit_apify.py       Reddit trend via Apify (fatihtahta)
  reddit_detector.py    Reddit trend via PRAW (fallback)
  rss_detector.py       Legge feed RSS (news + podcast + TikTok/IG RSS)
  telegram_bot.py       send_message(), send_social_outperformer_alert(), alert_allowed(), score_bar()
  telegram_commands.py  Listener comandi Telegram (/run, /status, /block, ...)
  trends_detector.py    Google Trends velocity + Trending RSS + Rising queries
  twitter_apify.py      Twitter/X trend via Apify (apidojo)
  twitter_detector.py   Twitter/X trend via Bearer Token (fallback)
  utils.py              Utility generiche
  youtube_comments.py   Analisi commenti canali competitor
  youtube_scraper.py    Scoperta + outperformer YouTube channels
  yt_api.py             Wrapper YouTube Data API v3

api/routes/
  config.py    GET /config (legge config.yaml)
  dashboard.py GET /keywords, /alerts, /convergences, /alerts-timeline,
               GET /keyword-sources, /keyword-search?keyword=X&hours=N,
               GET /highlights, /keyword-timeseries?keyword=X&hours=N
  news.py      GET /news/...
  pinterest.py GET /pinterest/...
  social.py    GET /social/outperformer, /social/profiles, ...
  system.py    GET /status, /schedule, /logs, /db-stats, /brief, /weekly
               POST /run-all, /run-services, /restart, /restore
               GET /backup
  trends.py    GET /trends/google?hours=N, /trends/rising?hours=N,
               GET /trends/trending-rss?hours=N,
               GET /trends/keyword-timeseries?keyword=X&hours=N
  youtube.py   GET /youtube/outperformer, /youtube/competitor-videos,
               GET /youtube/competitors, /youtube/comments/intel,
               GET /youtube/subscriber-sparkline, /youtube/comments/keywords,
               GET /youtube/comments/category-stats,
               GET /youtube/transcript/{video_id},
               GET /youtube/competitor-videos/by-keyword
```

---

## 4. Apify Actor Registry

### 4.1 TikTok — `clockworks~free-tiktok-scraper`  ✅ TIENI
- **Prezzo:** $2.00/1k | Apify-maintained | 42K utenti | 4.6★ (57 rec.)
- **Input discovery (hashtag):**
  ```json
  {"hashtags": ["paranormal"], "resultsPerPage": 8}
  ```
- **Input analysis (profilo):**
  ```json
  {"profiles": ["username"], "resultsPerPage": 30}
  ```
- **Output campi usati:**
  ```
  authorMeta.name        (str)  username
  authorMeta.fans        (int)  followers
  authorMeta.nickName    (str)  display name
  playCount              (int)  video views
  diggCount              (int)  likes
  shareCount             (int)
  text                   (str)  caption
  createTime             (int)  unix timestamp
  webVideoUrl            (str)  URL video
  id                     (str)  video ID
  ```

### 4.2 Instagram — `apify~instagram-scraper`  ✅ TIENI
- **Prezzo:** $1.50/1k | Apify-maintained | 213K utenti | 4.7★ (344 rec.)
- **Input hashtag discovery:**
  ```json
  {"directUrls": ["https://www.instagram.com/explore/tags/paranormal/"],
   "resultsType": "posts", "resultsLimit": 8}
  ```
- **Input profilo info (con fallback):**
  ```json
  {"directUrls": ["https://www.instagram.com/username/"],
   "resultsType": "details",   // unico tipo valido per follower count
   "resultsLimit": 1}
  ```
- **Input post analysis:**
  ```json
  {"directUrls": ["https://www.instagram.com/username/"],
   "resultsType": "posts", "resultsLimit": 30}
  ```
- **Output campi usati:**
  ```
  videoViewCount         (int)  views video (solo video, foto=null/0)
  likesCount             (int)  likes (foto e video)
  caption / text         (str)  didascalia
  url                    (str)  URL post
  timestamp              (str)  ISO datetime
  id                     (str)  post ID
  followersCount         (int)  followers (vari nomi — vedi _parse_followers_from_item())
  ownerFollowersCount    (int)  alias
  ownerFullName          (str)
  owner.followersCount   (int)  nested
  owner.edge_followed_by.count (int) nested alternativo
  ```
- **GOTCHA:** `videoViewCount` è solo per video. Foto hanno solo `likesCount`. Usare `get_video_views()` (strict) vs `get_engagement()` (per avg baseline). Outperformer detection usa solo post con `videoViewCount > 0`.

### 4.3 Twitter/X — `apidojo~tweet-scraper`  ✅ ATTIVO (cambiato da altimis/scweet)
- **Prezzo:** $0.40/1k (Starter) | 45K utenti | 4.2★ (155 rec.) | issues: 6.3h
- **Input:**
  ```json
  {"searchTerms": ["keyword"], "maxItems": 50, "sort": "Latest"}
  ```
  Minimo 50 items per query imposto dall'actor.
- **Output campi usati:**
  ```
  id             (str)  tweet ID (top-level)
  text           (str)  testo tweet (top-level)
  url            (str)
  twitterUrl     (str)
  retweetCount   (int)
  replyCount     (int)
  likeCount      (int)
  quoteCount     (int)
  createdAt      (str)
  lang           (str)
  author.userName (str)
  author.followers (int)
  ```

### 4.4 Pinterest — `fatihtahta~pinterest-scraper-search`  ✅ ATTIVO (cambiato da automation-lab)
- **Prezzo:** $3.99/1k | 450 utenti | 5.0★ (2 rec.) | issues: 8.5h
- **Input:**
  ```json
  {"queries": ["keyword"], "limit": 12, "type": "all-pins"}
  ```
  Minimo `limit: 10`. Output misto `type="pin"` e `type="profile"` — filtrare solo `type="pin"`.
- **Output (struttura NESTED — importante!):**
  ```
  type           (str)  "pin" o "profile" — filtrare solo "pin"
  id             (int)  Pinterest pin ID
  url            (str)  URL del pin Pinterest (NON il link esterno)
  title          (str)  titolo (alias top-level di pin.title)
  pin.title               (str)
  pin.description         (str)
  pin.closeup_description (str)  fallback description
  pin.link                (str)  URL ESTERNO destinazione
  pin.repin_count         (int)  ← saves/repins PRIMARIO
  pin.comment_count       (int)
  pin.share_count         (int)
  pin.is_video            (bool)
  pin.created_at          (str)
  pin.domain              (str)
  pin.aggregated_pin_data.aggregated_stats.saves  (int) ← FALLBACK a repin_count
  creator.username        (str)
  creator.full_name       (str)
  creator.follower_count  (int)
  board_ref.name          (str)
  board_ref.url           (str)
  media.images.original.url (str)
  ```
- **Mapping in `_search_pins()`:**
  ```python
  pin_data = item.get("pin") or {}
  agg_stats = ((pin_data.get("aggregated_pin_data") or {}).get("aggregated_stats") or {})
  title = item.get("title") or pin_data.get("title") or ""
  description = pin_data.get("description") or pin_data.get("closeup_description") or ""
  repins = pin_data.get("repin_count") or agg_stats.get("saves") or 0
  link = item.get("url") or pin_data.get("link") or ""
  ```

### 4.5 Reddit — `trudax~reddit-scraper-lite`  ✅ ATTIVO (cambiato da fatihtahta~reddit-scraper-search-fast)
- **Prezzo:** $3.40/1k | 17K utenti | 4.2★ — sostituisce fatihtahta che andava in timeout (>300s) su ogni subreddit
- **Input:**
  ```json
  {"startUrls": [{"url": "https://www.reddit.com/r/paranormal/new/?limit=40"}],
   "maxItems": 40}
  ```
- **Output campi usati:**
  ```
  id / postId    (str)  post ID
  title          (str)
  text / selftext / body  (str)
  ```

---

## 5. Database Schema

Tutte le tabelle sono in `ytsperbot.db` (SQLite). Funzioni in `modules/database.py`.

```
keyword_mentions       keyword, source, count, recorded_at
                       source values: "reddit_apify","twitter","pinterest_apify",
                                       "rss","youtube_comments","google_trends","news"

reddit_seen_posts      post_id, subreddit, seen_at

sent_alerts            identifier, alert_type, sent_at
                       ← usata da was_alert_sent_recently() / mark_alert_sent()

youtube_seen_channels  channel_id, video_id, sent_at

keyword_blacklist      keyword, created_at

channel_id_cache       handle, channel_id, cached_at

channel_subscribers_history  channel_id, channel_name, subscribers, recorded_at

apify_profiles         id, platform, username, display_name, followers,
                       last_analyzed, is_pinned, added_at
                       platform values: "tiktok", "instagram"
                       GOTCHA: profili con followers=0 vengono sempre re-accodati
                               (fix in get_apify_profiles_to_analyze)

apify_seen_videos      platform, video_id, seen_at

apify_outperformer_videos  platform, video_id, username, display_name, video_url,
                            caption, views, avg_views, followers, multiplier, sent_at

alerts_log             id, alert_type, keyword, velocity_pct, source_platform,
                        extra_json, sent_at
                        alert_type values: "google_trends","trending_rss","rising_query",
                                           "twitter_trend","reddit_apify_trend",
                                           "pinterest_apify","cross_signal","rss_velocity","news"

youtube_outperformer_log  channel_id, channel_name, video_id, video_title,
                           video_url, views, avg_views, subscribers, multiplier,
                           video_type, detected_at

competitor_video_log   channel_id, channel_name, video_id, video_title,
                        video_url, published_at, logged_at

youtube_comment_intel  channel_id, video_id, keyword, count, category, recorded_at

bot_logs               level, message, module, logged_at
                        ← stdout intercettato da bot_logger.py

scheduler_runs         job_name, last_run
                        ← usato da mark_job_run() / get_last_job_run()
                        ← CRITICO: startup catchup usa questi per rieseguire job scaduti

bot_config             key, value, updated_at   ← config.yaml serializzato
config_lists           key, value, position, updated_at
```

---

## 6. Config — Valori Chiave Attuali (config.yaml)

```yaml
# Piano attivo: STARTER $29/mese

apify_scraper:
  run_interval_days: 5    # ogni 5gg (~6 run/mese)
  run_time: "04:00"
  max_results_per_hashtag: 8
  new_profiles_per_platform: 8
  results_per_profile: 30
  profile_recheck_days: 30
  min_followers: 1000 / max_followers: 80000
  multiplier_threshold: 3.0
  multiplier_threshold_followers: 1.5   # TikTok
  multiplier_threshold_followers_ig: 2.0 # Instagram
  min_views_tiktok: 10000
  min_views_instagram: 3000  # solo videoViewCount, NON likesCount
  lookback_days: 30
  tiktok_hashtags: [paranormal, haunted, witchcraft, occult, horror, cryptid, ghosthunting, darkmagic]
  instagram_hashtags: [paranormal, haunted, occult, horror, mystery, darkfolklore, witchy, ghosthunting]

twitter:
  use_apify: true         # apidojo/tweet-scraper
  tweets_per_keyword: 50
  check_interval_hours: 8

reddit:
  use_apify: true         # fatihtahta/reddit-scraper-search-fast
  check_interval_hours: 42
  subreddits_per_run: 8
  posts_per_subreddit: 40

pinterest:
  use_apify: true         # fatihtahta/pinterest-scraper-search
  check_interval_hours: 120
  keywords_per_run: 12
  pins_per_keyword: 12
  velocity_threshold: 30

trend_detector:
  check_interval_hours: 4
  velocity_threshold_longform: 300   # % in 48h
  velocity_threshold_shorts: 500     # % in 24h
  min_mentions_to_track: 3

google_trends:
  check_interval_hours: 6
  timeframe: "now 7-d"
  geo: ""   # Worldwide
  velocity_threshold: 50
  top_n_keywords: 20

trending_rss:
  geos: ["IT", "US"]
  check_interval_minutes: 60

rising_queries:
  check_interval_hours: 6
  keywords_per_run: 8
  min_growth: 500
  geo: ""

cross_signal:
  min_sources: 3
  lookback_hours: 6
  cooldown_hours: 12
  ai_titles: true   # richiede ANTHROPIC_API_KEY

news_api:
  check_interval_hours: 6
  keywords_per_run: 10
  velocity_threshold: 200

priority_score:
  min_score: 3

db_cleanup:
  enabled: true
  run_time: "03:30"

daily_brief:  send_time: "08:00"
weekly_report: send_day: "sunday", send_time: "09:00"
```

---

## 7. Environment Variables

```
APIFY_API_KEY           ← obbligatorio per TikTok/IG/Twitter/Reddit/Pinterest
TELEGRAM_BOT_TOKEN      ← obbligatorio per tutti gli alert
TELEGRAM_CHAT_ID        ← obbligatorio per tutti gli alert
YOUTUBE_API_KEY         ← YouTube Data API v3
ANTHROPIC_API_KEY       ← cross_signal AI titles (opzionale)
NEWSAPI_KEY             ← news_detector (opzionale)
TWITTER_BEARER_TOKEN    ← solo se twitter.use_apify: false
REDDIT_CLIENT_ID        ← solo se reddit.use_apify: false
REDDIT_CLIENT_SECRET    ← solo se reddit.use_apify: false
PINTEREST_ACCESS_TOKEN  ← solo se pinterest.use_apify: false
PORT                    ← porta FastAPI (default 8080, Render la imposta automaticamente)
```

---

## 8. Architettura Frontend (React + Vite)

```
webapp/src/
  api/client.js           Tutte le chiamate API (fetchKeywords, fetchAlerts, ecc.)
  modules/
    dashboard/DashboardPage.jsx   ← KeywordExplorer (search+chart unificati)
    youtube/YouTubePage.jsx
    trends/TrendsPage.jsx
    social/SocialPage.jsx
  components/
    Topbar.jsx             ← BriefModal (📋), WeeklyModal (📊), nav buttons
```

**Endpoint client.js → backend:**
- `fetchKeywords(hours)` → `GET /dashboard/keywords`
- `fetchAlerts(hours)` → `GET /dashboard/alerts`
- `fetchKeywordSearch(keyword, hours)` → `GET /dashboard/keyword-search`
- `fetchKeywordTimeseries(keyword, hours)` → `GET /dashboard/keyword-timeseries`  ← param è `hours` NON `days`
- `fetchCompetitorVideos(hours)` → `GET /youtube/competitor-videos`  ← param è `hours` NON `days`
- `fetchBrief()` → `GET /system/brief`
- `fetchWeekly()` → `GET /system/weekly`

**GOTCHA:** `useState(initialProp)` non si aggiorna quando la prop cambia — serve `useEffect([prop])`.

---

## 9. Flusso di Esecuzione

```
main.py
  ├── init_db()
  ├── init_config_from_yaml()  → carica config.yaml in DB
  ├── start_health_server()    → FastAPI thread daemon
  ├── seed_startup_seen_videos()
  ├── run_overdue_jobs_on_startup()  ← IMPORTANTE: riesegue job scaduti dopo restart Render
  └── start_scheduler()
        ├── schedule.every(4h).do(job_trend_detector)
        │     └── run_rss_detector + run_youtube_comments_detector
        │         + run_trends_detector + run_cross_signal_detector
        ├── schedule.every(8h).do(job_twitter)   → apidojo/tweet-scraper
        ├── schedule.every(42h).do(job_reddit)   → fatihtahta/reddit-scraper-search-fast
        ├── schedule.every(120h).do(job_pinterest) → fatihtahta/pinterest-scraper-search
        ├── schedule.every(6h).do(job_rising_queries)
        ├── schedule.every(6h).do(job_news)
        ├── schedule.every(60min).do(job_trending_rss)
        ├── schedule.every(30min).do(job_new_video_monitor)
        ├── schedule.every(5days).do(job_apify_scraper)  ← TikTok + Instagram
        ├── schedule.every().day.at("03:00").do(job_youtube_scraper)
        ├── schedule.every().day.at("08:00").do(job_daily_brief)
        └── ...
```

---

## 10. Pattern e Gotcha Ricorrenti

### Python
- **SQL restore split(";"):** Non usare `split(";")` per spezzare script SQL — i valori quotati (es. HTML entities `&#39;`, `&amp;` nei commenti YouTube) contengono `;` e spezzano gli statement. Usare `_split_sql_statements()` che traccia lo stato in-quote.
- **Operator precedence:** `x or 0 if row else 0` → sbagliato. Corretto: `(x or 0) if row else 0`
- **FastAPI param naming:** FastAPI matcha i parametri query per nome esatto. Inviare `?days=X` a un endpoint che si aspetta `?hours=X` ignora silenziosamente il valore e usa il default.
- **feedparser:** `feedparser.parse()` NON solleva eccezioni su errori HTTP. Controllare sempre `feed.status` e `len(feed.entries)` — altrimenti i fallimenti sono silenziosi.
- **SQLite datetime('now'):** usa il tempo locale del server. Su Render è UTC, in locale può essere diverso.
- **json.dumps() in extra_json:** usare SEMPRE `json.dumps({})`, mai f-string JSON raw — le keyword con apostrofi/virgolette rompono il JSON.
- **`from __future__ import annotations` in tutti i moduli:** Il codebase usa `str | None` (Python 3.10+ syntax). Tutti i file in `modules/` che usano union type hints devono avere `from __future__ import annotations` come prima import dopo il docstring, altrimenti i test falliscono su Python 3.9 locale (macOS system Python). Se aggiungi un nuovo modulo con type hints union, aggiungi questa riga.
- **YouTube API 403 = quota esaurita:** YouTube Data API v3 usa HTTP 403 (non 429) per quota exceeded. `raise_for_status()` da solo non distingue il motivo — bisogna parsare il corpo JSON e cercare `reason: quotaExceeded` o `dailyLimitExceeded`. `YouTubeQuotaExceeded` in `yt_api.py` gestisce questo caso; i loop in `youtube_comments.py` e `competitor_monitor.py` si interrompono subito appena la ricevono. Default quota: 10.000 unità/giorno.

### Apify
- **TikTok video_views vs Instagram:** TikTok usa `playCount` per tutti. Instagram ha `videoViewCount` per video classici e `videoPlayCount` per Reels (foto = null/0 in entrambi). Usare sempre `post.get("videoViewCount") or post.get("videoPlayCount") or 0`. Non mescolare con TikTok.
- **Instagram followers campo:** prova in ordine: `followersCount`, `ownerFollowersCount`, `owner.followersCount`, `owner.edge_followed_by.count`. Usa `_parse_followers_from_item()` in `apify_scraper.py`.
- **Instagram profili followers=0:** vengono sempre re-accodati (fix in `get_apify_profiles_to_analyze` con `OR COALESCE(followers,0)=0`).
- **apidojo/tweet-scraper:** minimum 50 items per query. Usare `max(max_items, 50)`.
- **fatihtahta/pinterest-scraper-search:** filtrare `type=="pin"` — l'actor restituisce anche record `type="profile"`.

### React
- `useState(initialProp)` non si risincronizza se la prop cambia dopo il mount. Usare `useEffect([prop], () => setState(prop))`.

### Git
- **Tutte le commit in inglese** (da commit `3dc66a3` in poi — regola dell'utente).
- Non usare `--no-verify`, non amendare senza motivo esplicito.
- **Hook setup (2026-04-02):** pre-commit = solo `ruff` (~1s, fast). pre-push = `pytest tests/unit/` (~30-60s). Questo evita che il lock file di git venga tenuto aperto per 60s durante il commit, causando race conditions nel Claude Code environment (che spawna ogni Bash call come background task).
- **Pattern sicuro per commit in Claude Code:** usare sempre un singolo Bash call che concatena tutto: `find .git -name "*.lock" -delete 2>/dev/null && git add -A && git commit -m "..."`. Mai chiamare `git add` e `git commit` come tool call separati — rischiano di girare in parallelo e fare racing sul lock.

---

## 11. Recenti Modifiche (ultime 10 sessioni)

```
2026-04-02  Switch Reddit actor: fatihtahta~reddit-scraper-search-fast → trudax~reddit-scraper-lite
            Motivo: timeout sistematici HTTP 408 (run-timeout-exceeded >300s) su ogni subreddit,
            rating 2.9★, inutilizzabile in produzione.
            Nuovo actor: $3.40/1k | 17K utenti | 4.2★ | input identico (startUrls+maxItems).
            File: modules/reddit_apify.py (REDDIT_ACTOR constant + docstring)
            Aggiornati: README.md, CLAUDE.md sezione 4.5

2026-04-02  Test coverage expansion — session 3 (priority order):
            Target: pinterest_apify, twitter_apify, cross_signal (unit) +
                    social, pinterest, dashboard missing endpoints (integration).
            New test files:
              tests/unit/test_pinterest_apify.py (28 tests):
                _search_pins (run_actor input, limit min 10, profile filter,
                items-without-type kept, title/description/repins/link extraction,
                aggregated_stats fallback, empty, all-profiles warning),
                _select_keywords (per_run >= n, per_run count, zero, wrap-around,
                full coverage across slots),
                _send_alert (send_message call, content),
                run_pinterest_apify_detector (disabled, zero pins skip, saves count,
                no-baseline skip, velocity alert, below threshold, cooldown)
              tests/unit/test_twitter_apify.py (26 tests):
                _search_tweets (run_actor input, min 50 enforced, id fallbacks
                tweetId/tweet_id, text fallbacks full_text/Embedded_text/tweet.text,
                skip no-id, skip no-text, empty, result keys only id+text),
                _send_twitter_apify_alert (alert_allowed gate, 🔺 high-velocity,
                🐦 normal velocity, 3 tweet previews cap, return value),
                run_twitter_apify_detector (disabled, skip below min_mentions,
                saves count, no-baseline, velocity spike alert, below threshold,
                cooldown, multi-keyword)
              tests/unit/test_cross_signal.py (15 tests):
                generate_title_suggestions (no key, HTTP 200 success, 429 error,
                exception, empty content),
                run_cross_signal_detector (no convergences, blacklisted, cooldown,
                sends alert, marks sent, logs alert, ai_titles disabled/enabled,
                sources list passed, found count)
              tests/integration/test_api_social.py (15 tests):
                GET /social/profiles (empty, insert, platform filter, field
                normalization, ordered by avg_views),
                GET /social/watchlist (empty, pinned, platform filter, normalization),
                POST /social/watchlist (tiktok ok, instagram ok, invalid platform 400,
                profile appears, username compat),
                DELETE /social/watchlist (ok, profile gone after delete),
                GET /social/outperformer-videos (empty, insert, fields, ordered,
                days filter)
              tests/integration/test_api_pinterest.py (20 tests):
                GET /pinterest/trends (empty, insert, fields, growth_pct, trend_type,
                ordered by saves, excludes non-pinterest, hours filter, zero growth),
                GET /pinterest/alerts (empty, insert, excludes wrong types, fields,
                hours filter, ordered desc),
                GET /pinterest/keyword-counts (empty, insert, excludes non-pinterest,
                fields, total integer, aggregation, ordered desc)
              tests/integration/test_api_dashboard_extra.py (18 tests):
                GET /dashboard/alerts-timeline (empty, items, count int, groups by day,
                days filter, ordered asc),
                GET /dashboard/keyword-search (unknown kw, total, source breakdown,
                source_count, case-insensitive, echo keyword/hours, last_seen string,
                hours filter),
                GET /dashboard/keyword-sources (empty dict, breakdown, multiple keywords,
                entry fields, hours filter)
            PATCH NOTE: cross_signal.generate_title_suggestions uses local `import requests`
              inside try block → must patch "requests.post" not "modules.cross_signal.requests.post".
            PATCH NOTE: twitter_apify._send_twitter_apify_alert uses local
              `from modules.database import get_keyword_source_count` →
              must patch "modules.database.get_keyword_source_count".
            Total: 328 → 397 unit tests (+69). All pass.
            Remaining sessions (ordered):
              session 4: apify_scraper TikTok (discover, analyze, outperformer)
              session 5: youtube_comments, competitor_monitor
              session 6: telegram_bot
              session 7: UI component tests (AuthGate, InlineListManager, page-level)

2026-04-02  Fix Reddit Apify timeout:
            fatihtahta~reddit-scraper-search-fast returned TIMED-OUT (HTTP 400)
            because run_actor default timeout is 120s and the actor is slow.
            Fixed: _fetch_subreddit_posts now passes timeout=300 to run_actor.
            Added tests/unit/test_reddit_apify.py (18 tests).
            Note: YT-COMMENTS running during manual Reddit trigger is NOT a bug —
            it's run_overdue_jobs_on_startup() firing trend_detector at each
            Render restart (by design).

2026-04-02  Fix git hooks — pre-commit/pre-push split:
            pre-commit: ruff only (~1s) — commit is now instant
            pre-push: pytest tests/unit/ -q --tb=short -x (~30-60s)
            Motivation: Claude Code environment spawns every Bash call as a
            background task; holding index.lock for 60s during pytest caused
            persistent race conditions on every commit attempt.
            Also documented "safe commit pattern" in CLAUDE.md section 10 (Git).

2026-04-02  Test coverage expansion — session 2 of N:
            Target: reddit_detector.py + twitter_detector.py unit tests.
            New test files:
              tests/unit/test_reddit_detector.py (24 tests): count_keyword_mentions,
                fetch_subreddit_posts, calculate_velocity (wrapper), run_reddit_detector
                (disabled guard, invalid creds, below threshold, saves count, velocity
                spike → alert, no alert below threshold, no duplicate alert, multi-
                subreddit aggregation, no baseline case)
              tests/unit/test_twitter_detector.py (25 tests): get_twitter_client
                (ValueError on missing/placeholder token), search_recent_tweets
                (data mapping, empty/exception/cap-100/query-filter), send_twitter_alert
                (alert_allowed gate, message content, tweet previews capped at 3,
                high-velocity emoji), run_twitter_detector (disabled/missing-token,
                min_mentions, saves count, velocity spike, no alert below threshold,
                no alert first run, cooldown, sleep per keyword, log_alert call)
            Also installed: praw, tweepy (local test env only; already in requirements.txt)
            Total: 261 → 310 tests (+49). All pass.
            Remaining sessions (ordered):
              session 3: apify_scraper (TikTok + discovery)
              session 4: youtube_comments, competitor_monitor (logic tests)
              session 5: telegram_bot, telegram_commands

2026-04-02  Test coverage expansion — session 1 of N:
            Target: 100% coverage across all modules (long-term goal).
            This session: database.py tracking/config + trends_detector + rss_detector.
            New test files:
              tests/unit/test_db_tracking.py (51 tests): is_post_seen,
                mark_post_seen, is_channel_video_sent, mark_channel_video_sent,
                is_apify_video_sent, mark_apify_video_sent, blacklist CRUD,
                channel_id_cache, subscriber_history, keyword aggregates
                (get_daily_brief_data, get_keyword_source_count,
                get_keyword_all_mentions, get_keyword_timeseries)
              tests/unit/test_db_config.py (36 tests): config_load_defaults,
                config_get/get_all/set, config_list_seed/add/remove/get,
                config_lists_get_all
              tests/unit/test_trends_detector.py (37 tests): _matches_niche,
                _is_429, _trends_is_blocked, run_trends_detector,
                run_trending_rss_monitor, run_rising_queries_detector
              tests/unit/test_rss_detector.py (17 tests): fetch_feed,
                count_keyword_in_articles, run_rss_detector
            conftest.py: added 7 missing tables to clean_db fixture
              (youtube_seen_channels, keyword_blacklist, channel_id_cache,
              apify_seen_videos, bot_config, config_lists, scheduler_runs)
            Total: 117 → 261 tests (+144). All pass.
            Remaining sessions (ordered):
              session 2: reddit_detector, twitter_detector
              session 3: apify_scraper (TikTok + discovery)
              session 4: youtube_comments, competitor_monitor (logic tests)
              session 5: telegram_bot, telegram_commands
              session 6: Frontend (React Testing Library)
              session 7: API integration missing endpoints

2026-04-02  Fix test suite Python 3.9 compatibility:
            Added `from __future__ import annotations` to all 12 modules that
            use `str | None` union type hints (requires Python 3.10+ without it).
            Files: modules/database.py, utils.py, cross_signal.py,
            telegram_commands.py, pinterest_detector.py, competitor_monitor.py,
            youtube_comments.py, telegram_bot.py, apify_scraper.py,
            trends_detector.py, pinterest_apify.py, twitter_apify.py
            Result: 117/117 tests pass on Python 3.9 local (was 0/117).

2026-04-02  Fix YouTube API quota exhaustion — silent 403 loop bug:
            YouTube Data API v3 returns HTTP 403 (not 429) for quotaExceeded.
            raise_for_status() logged "403 Forbidden" but execution continued
            through all 30+ competitors, wasting time and making noise.
            - Added YouTubeQuotaExceeded exception class to yt_api.py
            - yt_get() parses 403 body: raises YouTubeQuotaExceeded on
              reason=quotaExceeded or dailyLimitExceeded; falls through to
              raise_for_status() for other 403s
            - youtube_comments.py: re-raise in resolve_channel_handle,
              get_channel_recent_videos, get_video_comments_rich; early return
              in run_comments_trend_detector and run_competitor_comments
            - competitor_monitor.py: re-raise in resolve_and_cache; early break
              in seed_startup_seen_videos, run_new_video_monitor,
              run_subscriber_growth_monitor
            - Added tests/unit/test_yt_quota.py (12 tests)

2026-04-01  Fix Instagram outperformer detection — 0 results bug (3 bugs):
            Bug 1 (CRITICO): get_video_views() returned 0 for Instagram Reels because
              they use "videoPlayCount" instead of "videoViewCount". Added fallback:
              post.get("videoViewCount") or post.get("videoPlayCount") or 0
              Same fix applied to get_engagement() to delegate to get_video_views().
            Bug 2 (MEDIO): Baseline avg was computed from all_eng (photo likes + video views),
              inflating avg when account posts popular photos. Now uses video-only avg when
              any video data exists; falls back to mixed avg only for photo-only accounts.
              New variable: video_views_all (all dates) used to compute avg_views when non-empty.
            Added tests/unit/test_apify_scraper_instagram.py (18 tests).
            File: modules/apify_scraper.py

2026-04-01  Fix NewsAPI 429 double-error: with languages=["en","it"], a 429 on the
            first language was silently swallowed by except Exception, then retried
            on the second language and all subsequent keywords, wasting daily quota.
            - Added NewsApiQuotaExceeded exception class
            - fetch_news_articles raises it on 429 and re-raises past except Exception
            - run_news_detector breaks both loops immediately on first 429
            - Added tests/unit/test_news_detector.py (6 tests)
            File: modules/news_detector.py

2026-04-01  Fix Trending RSS: Google changed endpoint (404 on old URL)
            - Old: /trends/trendingsearches/daily/rss?geo=XX → 404
            - New: /trending/rss?geo=XX → 200, 10 entries
            - Added _fetch_rss_bytes(): pre-fetch con urllib (User-Agent browser +
              SSL permissivo), poi feedparser.parse(raw_bytes); evita fallimenti
              silenziosi di feedparser su SSL/UA
            File: modules/trends_detector.py

2026-04-01  YouTube Comments Intelligence UX fixes:
            - sanitizeComment(): strips HTML tags + decodes &#39; &amp; &quot; &lt; &gt;
              from comment_text before rendering (no dangerouslySetInnerHTML)
            - Added category filter pills in CommentIntelligenceTab: "Tutti" +
              one pill per category with count; click filters both groups and comments
            - Added .yt-cat-pill / .yt-cat-pill-active CSS in index.css
            Files: webapp/src/modules/youtube/YouTubePage.jsx, webapp/src/index.css

2026-04-01  Pinterest: removed region field (always "Worldwide" with Apify, useless).
            - api/routes/pinterest.py: dropped region from query and aggregation logic
            - PinterestPage.jsx: removed region from card row meta, table column REGIONE,
              replaced KPI "Regioni Monitorate" → "Keywords Tracciate" (count + avg growth)

2026-04-01  Fix /restore: semicolons inside quoted values (HTML entities &#39; &amp; &quot;
            in youtube_comment_intel) broke naive split(";") causing 110 errors + lost rows.
            Replaced with _split_sql_statements() that tracks single-quote state.
            File: api/routes/system.py

2026-04-01  Dashboard SignalFeed filter fix:
            - Filtri Twitter/RSS/Reddit ora includono anche cross_signal che hanno
              quella piattaforma tra le fonti (hasSrc + Set RSS_KEYS/REDDIT_KEYS/TWITTER_KEYS)

2026-04-01  Dashboard bug fixes:
            - Schedule "—": /system/schedule ora include last_run + next_run per ogni job
              (query su scheduler_runs; next_run = last_run + interval_h; _parse_dt usa fromisoformat)
            - Competitor views=0: competitor_video_log non ha colonna views; ContentItem ora
              mostra "📅 X fa" (published_at) se views=null invece di "👁 0"
            - .claude/settings.json: aggiunto UserPromptSubmit hook che inietta checklist
              come additionalContext a ogni prompt

2026-04-01  Dashboard redesign — DashboardPage.jsx completo rewrite:
            - Layout: single-column → two-column (main 1fr + sidebar 280px)
            - Rimosso: KpiCard, AlertItem, ConvergenceItem, KeywordRow, HighlightsSection
            - Aggiunto Pulse Card: segnale con velocity più alta sempre in cima
            - Aggiunto Signal Feed unificato: merge alerts + convergenze con filtri
              (Tutti / Velocity / Convergenza / RSS / Reddit / Twitter)
            - Aggiunto Keyword Heatmap: griglia card con border heat (hot-1/2/3)
              + period filter 24h/7g/30g; click su card → apre Explorer
            - Aggiunto Content Outperformer tabbato (YouTube/TikTok/IG/Competitor)
              usa highlights.youtube_top, highlights.social_top, fetchCompetitorVideos
            - Sidebar: Platform Signals, Timeline mini, KeywordExplorer compatto,
              Schedule mini con timeUntil()
            - index.css: aggiunti ~100 righe CSS nuove (dash-grid, pulse-card,
              feed-*, kw-heatmap-*, content-*, plat-*, sched-mini-*, explorer-sb-*)
            - .claude/launch.json: fix frontend cwd (npm --prefix webapp run dev)
            - CLAUDE.md: aggiunto checklist step 8 (non committato in sessione prec.)

2026-03-31  Switch Twitter: altimis/scweet → apidojo/tweet-scraper
            Switch Pinterest: automation-lab/pinterest-scraper → fatihtahta/pinterest-scraper-search
            Aggiornati prezzi actor in config.yaml e docstring (TikTok $2/1k, IG $1.50/1k)
            Aggiunti schemi input/output completi nei docstring di apify_scraper.py

2026-03-31  Fix trends_detector.py:
            - feedparser: controlla feed.entries + log HTTP status (Trending RSS sempre 0)
            - Sostituito f-string JSON raw con json.dumps() in log_alert() per trending_rss e rising_query

2026-03-31  Fix Instagram video outperformer:
            - get_video_views() strict (solo videoViewCount, foto=0 escluse)
            - get_engagement() per avg baseline (tutti i post incluse foto)
            - recent_videos = solo post con videoViewCount > 0
            - min_views_instagram: 3000 ora applicato solo a veri view video

2026-03-30  Fix Dashboard highlights "Nessun segnale":
            - _best_signal() in dashboard.py: aggiunto fallback a keyword_mentions quando alerts_log è vuoto

2026-03-30  Fix YouTube bugs:
            - fetchCompetitorVideos: rinominato param days→hours (FastAPI silently ignored days)
            - Rimosso fetchCommentKeywords (dead code — never rendered)

2026-03-29  Merge KeywordSearchPanel + KeywordChart → KeywordExplorer
            (erano due sezioni dashboard che mostravano gli stessi dati)

2026-03-29  Fix Instagram followers=0 stuck:
            - get_apify_profiles_to_analyze: aggiunto OR COALESCE(followers,0)=0
            - Multi-level fallback in _get_instagram_profile_info()
            - Discovery: estrae followers direttamente dal post item

2026-03-28  Added Dashboard Brief/Weekly modals:
            - /system/brief e /system/weekly endpoints
            - BriefModal e WeeklyModal in Topbar.jsx
            - fetchBrief(), fetchWeekly() in client.js
```

---

## 12. Come Mantenere Questo File

**Aggiornare dopo ogni sessione di lavoro:**
1. Se cambi un actor Apify: aggiorna sezione 4 (input, output, prezzo, note)
2. Se aggiungi/modifichi tabelle DB: aggiorna sezione 5
3. Se aggiungi endpoint API: aggiorna sezione 3 (api/routes/)
4. Se cambi config.yaml: aggiorna sezione 6
5. Se scopri un gotcha: aggiorna sezione 10
6. Aggiungi sempre la modifica in sezione 11 (formato: `data  descrizione breve`)

**Regola per nuove sessioni:**
- Leggi questo file prima di aprire qualsiasi altro file
- Apri file specifici solo quando devi fare modifiche precise
- Non fare Glob/Grep sull'intero codebase se la risposta è già qui

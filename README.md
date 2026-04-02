# YTSPERBOT

Sistema di **trend intelligence** per canali YouTube nella nicchia paranormale/horror/occulto. Monitora keyword su 10+ piattaforme, individua canali e profili social outperformer, analizza i competitor e invia alert su Telegram prima che i topic esplodano.

---

## Funzionalità

| Modulo | Fonte | Frequenza | Credenziali |
|---|---|---|---|
| RSS Detector | Feed IT + EN + Podcast + Google Alerts | ogni 4h | — |
| TikTok RSS | Feed RSSHub per hashtag di nicchia | ogni 4h | — |
| Instagram RSS | Feed RSSHub per hashtag di nicchia | ogni 4h | — |
| Pinterest RSS | Feed RSSHub per hashtag di nicchia | ogni 4h | — |
| Google Trends Velocity | `pytrends` — interest 0-100 | ogni 4h | — |
| Google Trending RSS | Feed trending IT + US filtrati per nicchia | ogni 60 min | — |
| Rising Queries | Keyword emergenti correlate via pytrends | ogni 6h | — |
| YouTube Comments | Trend commenti + sentiment + intensità emotiva | ogni 4h | `YOUTUBE_API_KEY` |
| YouTube Scraper | Canali 1k–80k iscritti con video outperformer | ogni giorno 03:00 UTC | `YOUTUBE_API_KEY` |
| Competitor Video Monitor | Nuovi video competitor + keyword da titoli | ogni 30 min | `YOUTUBE_API_KEY` |
| Competitor Iscritti | Crescita iscritti +10% in 7 giorni | ogni giorno 09:00 UTC | `YOUTUBE_API_KEY` |
| Twitter / X | Keyword velocity su tweet recenti | ogni 24h (Apify) · configurabile | `APIFY_API_KEY` oppure `TWITTER_BEARER_TOKEN` |
| Reddit | Keyword velocity su subreddit tematici | ogni 84h / 2×sett (Apify) | `APIFY_API_KEY` oppure credenziali PRAW |
| Pinterest | Trend pin growing/emerging + velocity | ogni 360h / 2×mese (Apify) | `APIFY_API_KEY` oppure `PINTEREST_ACCESS_TOKEN` |
| TikTok Scraper | Profili 1k–80k con video outperformer 3× media | ogni 14 giorni 04:00 UTC | `APIFY_API_KEY` |
| Instagram Scraper | Profili 1k–80k con post outperformer 3× media | ogni 14 giorni 04:00 UTC | `APIFY_API_KEY` |
| News Detector | Notizie di nicchia via NewsAPI.org | ogni 6h | `NEWSAPI_KEY` |
| Cross Signal | Convergenza 3+ fonti sulla stessa keyword → alert alta priorità + titoli AI | dopo ogni ciclo 4h | — (AI: `ANTHROPIC_API_KEY`) |
| Daily Brief | Riepilogo top keyword 24h | ogni giorno 08:00 UTC | — |
| Weekly Report | Report top keyword 7 giorni | ogni domenica 09:00 UTC | — |

### Budget Apify (free tier $5/mese)

| Piattaforma | Actor | Costo/1k | Volume stimato | Costo/mese |
|---|---|---|---|---|
| Twitter/X | `altimis~scweet` | $0.18 | ~3.000 tweet/mese | ~$0.54 |
| Reddit | `trudax~reddit-scraper-lite` | $3.40 | ~800 post/mese | ~$2.72 |
| Pinterest | `epctex~pinterest-scraper` | $4.00 | ~100 pin/mese | ~$0.40 |
| TikTok | `clockworks~free-tiktok-scraper` | $5.00 | ~78 risultati/mese | ~$0.39 |
| Instagram | `apify~instagram-scraper` | $2.70 | ~96 risultati/mese | ~$0.26 |
| **Totale** | | | | **~$4.31/mese** |

> Tutti e 5 i servizi restano nel free tier di $5/mese con i default del `config.yaml`. Rotazione automatica di subreddit e keyword Pinterest per distribuire il budget uniformemente.

---

## Dashboard Web

La dashboard è un'applicazione React 19 + Vite + TanStack Query, servita da FastAPI.

**Accesso rapido via Telegram:**
```
/dashboard
```
Il bot risponde con il link completo (token incluso), pronto da aprire o salvare come bookmark.

**URL diretto:**
```
https://<tuo-hostname>/dashboard?token=IL_TUO_DASHBOARD_TOKEN
```

### Sezioni dashboard

| Sezione | Contenuto |
|---|---|
| **Home** | Top keyword 48h, convergenze multi-piattaforma, timeline alert, keyword per fonte |
| **YouTube** | Video outperformer (Long + Shorts), competitor recenti, sparkline iscritti, keyword da commenti |
| **Social** | Profili TikTok/Instagram scoperti, watchlist pinned, video/post outperformer |
| **Trends** | Google Trends velocity, Rising Queries, Trending RSS, timeseries keyword |
| **Pinterest** | Trend growing/emerging, velocity pin, conteggi keyword |
| **News & Reddit & Twitter** | Alert news, menzioni Reddit/Twitter, velocity per keyword |
| **Config & Sistema** | Parametri, Schedule, Liste, Backup & API Keys, **Logs** |

> Se `DASHBOARD_TOKEN` non è configurato, tutti gli endpoint `/api/*` restituiscono 403.

---

## Comandi Telegram

### Esecuzione moduli

| Comando | Descrizione |
|---|---|
| `/run` | Esegui tutti i moduli attivi |
| `/rss` | RSS + TikTok/Instagram/Pinterest RSS |
| `/reddit` | Reddit detector (Apify o PRAW) |
| `/twitter` | Twitter/X detector (Apify o Bearer Token) |
| `/trends` | Google Trends velocity |
| `/comments` | YouTube Comments + sentiment |
| `/scraper` | YouTube Scraper canali outperformer |
| `/pinterest` | Pinterest trends (Apify o API nativa) |
| `/trending` | Google Trending RSS ora |
| `/rising` | Rising Queries ora |
| `/newvideo` | Nuovi video competitor ora |
| `/subscribers` | Crescita iscritti competitor ora |
| `/convergence` | Cross-signal convergenza ora |
| `/news` | News detector ora |
| `/social` | TikTok + Instagram Apify scraper ora |
| `/weekly` | Report settimanale |
| `/brief` | Brief ultime 24h |

### Analisi

| Comando | Descrizione |
|---|---|
| `/transcript <video_id>` | Scarica trascrizione di un video YouTube |
| `/cerca <keyword>` | Cerca una keyword in tutte le fonti (ultimi 7 giorni) |
| `/graph <keyword>` | Grafico trend 7 giorni come immagine |

### Configurazione

| Comando | Descrizione |
|---|---|
| `/config` | Mostra tutti i parametri con valore attuale |
| `/set <chiave>` | Info su una chiave (tipo, range, valore) |
| `/set <chiave> <valore>` | Modifica parametro — effetto immediato, nessun redeploy |
| `/dashboard` | Link alla dashboard web (token incluso) |

### Backup & Restore

| Comando | Descrizione |
|---|---|
| `/backup` | Genera e invia un dump SQL del DB come file `.sql` |
| `/populate` | Arma il bot per ricevere un restore — lock attivo 5 minuti |
| `/dbstats` | Righe per tabella + dimensione file DB |

> **Flusso restore:** `/populate` → bot conferma lock con scadenza → invia il file `.sql` entro 5 minuti → restore eseguito, lock disarmato. Previene restore accidentali.

### Sistema

| Comando | Descrizione |
|---|---|
| `/restart` | Riavvia il servizio Render — ⚠️ il DB viene azzerato su Render free tier |
| `/status` | Stato credenziali e moduli attivi |
| `/help` | Lista completa comandi |

> **Render free tier — disco effimero:** il filesystem è temporaneo. Ogni restart ricrea il container azzerando `data/ytsperbot.db`. Al riavvio il DB viene riseminato da `config.yaml`. Usa `/backup` prima e `/populate` dopo per preservare i dati operativi.

### Watchlist profili social

| Comando | Descrizione |
|---|---|
| `/watch <tiktok\|instagram> @username` | Aggiunge alla watchlist — analizzato ad ogni run, senza filtro follower |
| `/unwatch <tiktok\|instagram> @username` | Rimuove dalla watchlist |
| `/watchlist` | Lista profili monitorati con follower e data ultimo check |

> I profili watchlist **bypassano il filtro 1k–80k follower** e vengono analizzati **ad ogni run** del social scraper. Gli alert watchlist sono marcati con 📌.

### Blacklist

| Comando | Descrizione |
|---|---|
| `/block <keyword>` | Silenzia una keyword rumorosa |
| `/unblock <keyword>` | Rimuovi dalla blacklist |
| `/blocklist` | Lista keyword bloccate |

---

## Struttura del progetto

```
YTSPERBOT/
├── main.py                      # Orchestratore + scheduler + run_service()
├── config.yaml                  # Parametri di default (non modificare in produzione)
├── requirements.txt
├── render.yaml                  # Configurazione deploy Render
├── .python-version              # Pin Python 3.12
├── .env                         # Credenziali (NON caricare su Git)
├── .env.template                # Template credenziali
│
├── modules/
│   ├── database.py              # SQLite: tabelle, query, bot_logs
│   ├── bot_logger.py            # Interceptor stdout → bot_logs
│   ├── config_manager.py        # Gestione config via DB — /set, get_config()
│   ├── dispatcher.py            # Dispatcher dual-mode: Twitter / Reddit / Pinterest
│   ├── telegram_bot.py          # Notifiche + grafici Telegram
│   ├── telegram_commands.py     # Command listener (polling) + backup/restore
│   ├── rss_detector.py          # RSS + Google Alerts + TikTok/Instagram/Pinterest RSS
│   ├── trends_detector.py       # Google Trends + Trending RSS + Rising Queries
│   ├── youtube_comments.py      # Trend commenti + sentiment
│   ├── youtube_scraper.py       # Scraper canali outperformer (Long + Shorts)
│   ├── competitor_monitor.py    # Nuovi video + crescita iscritti competitor
│   ├── cross_signal.py          # Convergenza multi-piattaforma + AI titles
│   ├── news_detector.py         # Monitor notizie via NewsAPI.org
│   ├── twitter_detector.py      # Twitter/X via Bearer Token (nativo)
│   ├── twitter_apify.py         # Twitter/X via Apify (altimis~scweet)
│   ├── reddit_detector.py       # Reddit via PRAW (nativo)
│   ├── reddit_apify.py          # Reddit via Apify (trudax~reddit-scraper-lite)
│   ├── pinterest_detector.py    # Pinterest via API v5 (nativa)
│   ├── pinterest_apify.py       # Pinterest via Apify (epctex~pinterest-scraper)
│   ├── apify_scraper.py         # TikTok + Instagram outperformer via Apify
│   ├── yt_api.py                # Helper YouTube API condiviso
│   └── utils.py                 # Utility generiche
│
├── api/
│   ├── app.py                   # FastAPI factory + autenticazione token
│   └── routes/
│       ├── dashboard.py         # /api/dashboard/*
│       ├── youtube.py           # /api/youtube/*
│       ├── social.py            # /api/social/*
│       ├── trends.py            # /api/trends/*
│       ├── pinterest.py         # /api/pinterest/*
│       ├── news.py              # /api/news/*
│       ├── config.py            # /api/config/*
│       └── system.py            # /api/system/* (status, schedule, logs, run-services)
│
├── webapp/                      # React 19 + Vite + TanStack Query
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api/client.js        # Tutte le chiamate API
│   │   ├── auth.js              # Gestione token dashboard
│   │   ├── components/          # Topbar, EmptyState, Badge, ...
│   │   └── modules/             # Una cartella per ogni sezione dashboard
│   └── dist/                    # Build produzione (servita da FastAPI)
│
└── data/
    └── ytsperbot.db             # Database SQLite (auto-generato)
```

---

## Setup

### Prerequisiti obbligatori

| Servizio | Dove ottenerlo | Variabile `.env` |
|---|---|---|
| Python 3.12 | [python.org](https://www.python.org/downloads/) | — |
| Telegram Bot Token | [@BotFather](https://t.me/BotFather) | `TELEGRAM_BOT_TOKEN` |
| Telegram Chat ID | [@userinfobot](https://t.me/userinfobot) | `TELEGRAM_CHAT_ID` |

### Credenziali opzionali

| Servizio | Variabile `.env` | Moduli abilitati | Note |
|---|---|---|---|
| YouTube Data API v3 | `YOUTUBE_API_KEY` | Scraper, Comments, Competitor Monitor | [Google Cloud Console](https://console.cloud.google.com) |
| Apify API | `APIFY_API_KEY` | Twitter/X · Reddit · Pinterest · TikTok · Instagram | [apify.com](https://apify.com) — free: $5/mese di crediti |
| NewsAPI | `NEWSAPI_KEY` | News Detector | [newsapi.org](https://newsapi.org) — free: 100 req/giorno |
| Anthropic API | `ANTHROPIC_API_KEY` | AI title generator (cross-signal) | [console.anthropic.com](https://console.anthropic.com) |
| Twitter Bearer Token | `TWITTER_BEARER_TOKEN` | Twitter/X (modalità nativa) | Solo se `twitter.use_apify: false` — richiede piano Basic $100/mese |
| Reddit API | `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` | Reddit (modalità nativa) | Solo se `reddit.use_apify: false` |
| Pinterest Access Token | `PINTEREST_ACCESS_TOKEN` | Pinterest (modalità nativa) | Solo se `pinterest.use_apify: false` |
| Render API Key | `RENDER_API_KEY` + `RENDER_SERVICE_ID` | Comando `/restart` | [dashboard.render.com](https://dashboard.render.com) → Account Settings |
| Dashboard Token | `DASHBOARD_TOKEN` | Protegge la dashboard web | Stringa segreta a scelta |

> **Twitter/Reddit/Pinterest — dual mode:** ogni piattaforma supporta due modalità selezionabili in `config.yaml` senza redeploy del codice. Imposta `use_apify: true` per usare Apify (consigliato per chi non ha le API native), oppure `use_apify: false` per usare le credenziali proprietarie.

### Installazione

```bash
git clone https://github.com/Alucard9994/YTSPERBOT.git
cd YTSPERBOT
pip install -r requirements.txt
```

### Configurazione credenziali

```bash
cp .env.template .env
# Apri .env e compila i valori
```

```env
# Obbligatori
TELEGRAM_BOT_TOKEN=il_tuo_token
TELEGRAM_CHAT_ID=il_tuo_chat_id

# YouTube (opzionale — attiva Scraper, Comments, Competitor)
YOUTUBE_API_KEY=la_tua_api_key

# Apify (opzionale — attiva Twitter, Reddit, Pinterest, TikTok, Instagram)
APIFY_API_KEY=la_tua_api_key

# News (opzionale)
NEWSAPI_KEY=la_tua_api_key

# AI (opzionale — suggerimenti titoli nel cross-signal)
ANTHROPIC_API_KEY=la_tua_api_key

# Dashboard (opzionale — protegge l'accesso web)
DASHBOARD_TOKEN=una_stringa_segreta_qualsiasi

# Modalità nativa — solo se use_apify: false per le relative piattaforme
TWITTER_BEARER_TOKEN=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
PINTEREST_ACCESS_TOKEN=

# Render restart (opzionale)
RENDER_API_KEY=
RENDER_SERVICE_ID=
```

### Build dashboard (sviluppo locale)

```bash
cd webapp
npm install
npm run build   # crea webapp/dist/ servita da FastAPI
# oppure
npm run dev     # dev server con HMR su :5173
```

---

## Avvio

```bash
# Produzione — scheduler automatico
python main.py

# Test singoli moduli
python main.py --rss
python main.py --trends
python main.py --twitter
python main.py --comments
python main.py --scraper
python main.py --reddit

# Test completo (tutti i moduli in sequenza)
python main.py --test
```

---

## Parametri configurabili

### Due modi per modificare i parametri

**1. Via dashboard web** (Config & Sistema → Parametri) o **via Telegram** (`/set`) — effetto immediato, senza redeploy:
```
/set scraper.multiplier_threshold 2.5
/set apify.min_views_tiktok 5000
/set priority_score.min_score 2
```

**2. Via `config.yaml`** — per parametri permanenti e per tutto ciò che controlla lo scheduler (intervalli, orari, modalità Apify):
```yaml
twitter:
  use_apify: true
  check_interval_hours: 24
```
Richiede commit + redeploy. I parametri scheduler non sono modificabili via UI perché richiedono il riavvio del processo.

---

### Trend Detector

| Parametro | Default | Descrizione |
|---|---|---|
| `check_interval_hours` | `4` | Frequenza dei check (scheduler) |
| `velocity_threshold_longform` | `300` | % crescita 48h per alert long-form |
| `velocity_threshold_shorts` | `500` | % crescita 24h per alert Shorts |
| `min_mentions_to_track` | `3` | Menzioni minime per tracciare una keyword |

### YouTube Scraper

| Parametro | Default | Descrizione |
|---|---|---|
| `multiplier_threshold` | `3.0` | Soglia outperformer vs media views del canale |
| `multiplier_subs_threshold` | `2.0` | Soglia outperformer vs iscritti (views ≥ 2× iscritti) |
| `min_views` | `5000` | Views minime assolute |
| `min_followers` | `1000` | Iscritti minimi canale |
| `max_followers` | `80000` | Iscritti massimi canale |
| `lookback_days` | `30` | Finestra analisi video |
| `max_channels_per_run` | `400` | Canali max analizzati per run |
| `run_time` | `03:00` | Orario esecuzione giornaliera (UTC) |

> Un video è outperformer se supera **almeno uno** dei due moltiplicatori. L'alert mostra entrambi i valori; 🔥🔥 indica il superamento di entrambi. Video Long e Shorts classificati separatamente (basato su durata reale ISO 8601).

### TikTok + Instagram (Apify Scraper)

| Parametro | Default | Descrizione |
|---|---|---|
| `run_interval_days` | `14` | Ogni quanti giorni eseguire (scheduler) |
| `run_time` | `04:00` | Orario esecuzione (UTC) |
| `new_profiles_per_platform` | `3` | Nuovi profili da scoprire per run |
| `max_results_per_hashtag` | `3` | Risultati per hashtag discovery |
| `results_per_profile` | `10` | Video/post scaricati per profilo |
| `profile_recheck_days` | `60` | Giorni tra rianalisi di un profilo già noto |
| `min_followers` | `1000` | Follower minimi (bypassato per watchlist) |
| `max_followers` | `80000` | Follower massimi (bypassato per watchlist) |
| `multiplier_threshold` | `3.0` | Moltiplicatore outperformer vs media views |
| `multiplier_threshold_followers` | `1.5` | Moltiplicatore TikTok vs follower |
| `multiplier_threshold_followers_ig` | `2.0` | Moltiplicatore Instagram vs follower |
| `min_views_tiktok` | `10000` | Views minime TikTok |
| `min_views_instagram` | `3000` | Views minime Instagram |
| `lookback_days` | `30` | Finestra analisi post/video recenti |

### Twitter / X

| Parametro | Default | Descrizione |
|---|---|---|
| `use_apify` | `true` | `true` = Apify (`altimis~scweet`) · `false` = Bearer Token nativo |
| `tweets_per_keyword` | `20` | Tweet scaricati per keyword per run |
| `check_interval_hours` | `24` | Frequenza check (scheduler) |

### Reddit

| Parametro | Default | Descrizione |
|---|---|---|
| `use_apify` | `true` | `true` = Apify · `false` = PRAW nativo |
| `check_interval_hours` | `84` | Frequenza check (~2×/settimana) |
| `subreddits_per_run` | `5` | Subreddit analizzati per run (rotazione automatica) |
| `posts_per_subreddit` | `20` | Post per subreddit |

> **Rotazione subreddit:** con 17 subreddit configurati e 5 per run, il sistema ruota automaticamente per coprire tutti i subreddit in ~4 run (~2 settimane).

### Pinterest

| Parametro | Default | Descrizione |
|---|---|---|
| `use_apify` | `true` | `true` = Apify · `false` = API nativa |
| `check_interval_hours` | `360` | Frequenza check (~2×/mese) |
| `keywords_per_run` | `5` | Keyword analizzate per run (rotazione automatica) |
| `pins_per_keyword` | `10` | Pin per keyword |
| `velocity_threshold` | `30` | % crescita per alert |

### News

| Parametro | Default | Descrizione |
|---|---|---|
| `check_interval_hours` | `6` | Frequenza check |
| `keywords_per_run` | `10` | Keyword per run (rispetta quota 100 req/giorno free) |
| `velocity_threshold` | `200` | % crescita menzioni per alert |

### Cross Signal

| Parametro | Default | Descrizione |
|---|---|---|
| `min_sources` | `3` | Fonti minime diverse per scattare alert |
| `lookback_hours` | `6` | Finestra temporale analisi |
| `cooldown_hours` | `12` | Cooldown per stessa keyword |
| `ai_titles` | `true` | Genera suggerimenti titoli (richiede `ANTHROPIC_API_KEY`) |

### Competitor Monitor

| Parametro | Default | Descrizione |
|---|---|---|
| `new_video_max_age_hours` | `48` | Ignora video più vecchi di N ore al primo avvio |
| `subscriber_growth_threshold` | `0.10` | % crescita in 7 giorni per alert iscritti |
| `subscriber_check_time` | `09:00` | Orario controllo iscritti (UTC) |

### Priority Score

| Parametro | Default | Descrizione |
|---|---|---|
| `min_score` | `3` | Score minimo 1-10 per ricevere l'alert |

---

## Deploy su Render

### Configurazione

Il file `render.yaml` configura il servizio. Le variabili d'ambiente vanno impostate nel pannello Render → Environment:

```
TELEGRAM_BOT_TOKEN     = ...
TELEGRAM_CHAT_ID       = ...
YOUTUBE_API_KEY        = ...
APIFY_API_KEY          = ...
NEWSAPI_KEY            = ...
ANTHROPIC_API_KEY      = ...
DASHBOARD_TOKEN        = ...
PORT                   = 8080
```

### Disco effimero (free tier)

Su Render free tier il filesystem è temporaneo: ogni restart azzera `data/ytsperbot.db`. Al riavvio il bot:
1. Ricrea il DB con `init_db()`
2. Risemina i parametri di default da `config.yaml`
3. Riprende lo scheduler normalmente

Per preservare i dati operativi (keyword counts, alert history, profili Apify):
```
/backup          ← scarica il dump SQL prima del restart
/restart         ← riavvia il servizio
/populate        ← arma il lock restore
[invia il file .sql entro 5 minuti]
```

---

## Logs di sistema

Il bot cattura automaticamente tutti i `print()` e li salva nella tabella `bot_logs` del DB con classificazione del livello (ERROR / WARNING / INFO).

**Via dashboard:** Config & Sistema → onglet **Logs** — filtri per livello e finestra temporale, aggiornamento automatico ogni 30 secondi.

**Via API:**
```
GET /api/system/logs?minutes=60&level=ERROR&limit=200
```

I log vengono puliti automaticamente ogni avvio (conservati solo gli ultimi 7 giorni).

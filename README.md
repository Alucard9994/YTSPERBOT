# YTSPERBOT

Sistema di **trend intelligence** per canali YouTube nella nicchia paranormale/horror/occulto. Monitora keyword su più piattaforme, individua canali outperformer, analizza i competitor e invia alert su Telegram prima che i topic esplodano.

---

## Funzionalità

| Modulo | Fonte | Frequenza | Stato |
|---|---|---|---|
| RSS Detector | 19 feed (English + Podcast + Italian) + 36 Google Alerts | ogni 4h | ✅ Attivo |
| TikTok RSS | 8 feed RSSHub per hashtag di nicchia (0 quota) | ogni 4h | ✅ Attivo |
| Instagram RSS | 8 feed RSSHub per hashtag di nicchia (0 quota) | ogni 4h | ✅ Attivo |
| Pinterest RSS | 10 feed RSSHub per hashtag di nicchia (0 quota) | ogni 4h | ✅ Attivo |
| Twitter / X | Keyword velocity su tweet recenti | ogni 4h | ✅ Attivo |
| Reddit | Keyword velocity su subreddit tematici | ogni 4h | ⏳ In attesa credenziali |
| Google Trends Velocity | `pytrends` — interest 0-100 sulle keyword monitorate | ogni 4h | ✅ Attivo |
| YouTube Comments | Trend commenti nicchia + sentiment + intensità emotiva | ogni 4h | ✅ Attivo |
| TikTok Scraper | Profili 1k–80k follower con video outperformer 3x media (Apify) | ogni giorno 04:00 UTC | ⚙️ Richiede APIFY_API_KEY |
| Instagram Scraper | Profili 1k–80k follower con post outperformer 3x media (Apify) | ogni giorno 04:00 UTC | ⚙️ Richiede APIFY_API_KEY |
| Cross Signal | Convergenza 3+ fonti sulla stessa keyword → alert alta priorità | dopo ogni ciclo 4h | ✅ Attivo |
| Google Trending RSS | Feed RSS trending IT + US filtrati per nicchia (0 quota) | ogni 60 min | ✅ Attivo |
| Competitor Monitor | Nuovo video competitor via RSS (0 quota) + estrazione keyword titoli | ogni 30 min | ✅ Attivo |
| Rising Queries | Keyword emergenti correlate via pytrends | ogni 6h | ✅ Attivo |
| Pinterest API | Trend growing/emerging + velocity via API v5 | ogni 6h | ⚙️ Richiede token |
| News Detector | Notizie di nicchia via NewsAPI.org (100 req/giorno free) | ogni 6h | ⚙️ Richiede NEWSAPI_KEY |
| YouTube Scraper | Canali 1k–80k iscritti con video outperformer (3x media) | ogni giorno 03:00 UTC | ✅ Attivo |
| Competitor Iscritti | Crescita iscritti +10% in 7 giorni | ogni giorno 09:00 UTC | ✅ Attivo |
| Daily Brief | Riepilogo top keyword 24h | ogni giorno 08:00 UTC | ✅ Attivo |
| Weekly Report | Report top keyword 7 giorni | ogni domenica 09:00 UTC | ✅ Attivo |

---

## Comandi Telegram

| Comando | Descrizione |
|---|---|
| `/run` | Esegui tutti i moduli subito (esclusi scraper e iscritti) |
| `/rss` | Solo RSS + TikTok + Instagram + Pinterest RSS |
| `/reddit` | Solo Reddit detector |
| `/twitter` | Solo Twitter/X detector |
| `/trends` | Solo Google Trends velocity |
| `/comments` | Solo YouTube Comments + sentiment |
| `/scraper` | Solo YouTube Scraper canali outperformer |
| `/pinterest` | Controlla trend Pinterest API ora |
| `/trending` | Controlla trending Google IT + US ora |
| `/rising` | Scopri keyword emergenti correlate ora |
| `/newvideo` | Controlla nuovi video competitor ora |
| `/subscribers` | Controlla crescita iscritti competitor ora |
| `/convergence` | Controlla convergenza multi-piattaforma ora |
| `/news` | Controlla notizie di nicchia ora |
| `/social` | Scraper TikTok + Instagram outperformer ora (richiede APIFY_API_KEY) |
| `/weekly` | Report settimanale top keyword |
| `/brief` | Riepilogo top keyword delle ultime 24h |
| `/transcript <video_id>` | Scarica trascrizione di un video YouTube |
| `/cerca <keyword>` | Cerca una keyword in tutte le fonti (ultimi 7 giorni) |
| `/graph <keyword>` | Grafico trend 7 giorni inviato come immagine |
| `/block <keyword>` | Silenzia una keyword rumorosa |
| `/unblock <keyword>` | Rimuovi dalla blacklist |
| `/blocklist` | Lista keyword bloccate |
| `/status` | Stato del bot e ora server |

---

## Struttura del progetto

```
YTSPERBOT/
├── main.py                      # Orchestratore + scheduler + dashboard web
├── config.yaml                  # Tutti i parametri configurabili
├── requirements.txt
├── render.yaml                  # Configurazione deploy Render
├── .python-version              # Pin Python 3.12
├── .env                         # Credenziali (NON caricare su Git)
├── .env.template                # Template credenziali (sicuro da committare)
├── modules/
│   ├── database.py              # Persistenza SQLite
│   ├── telegram_bot.py          # Notifiche + grafici Telegram
│   ├── telegram_commands.py     # Command listener (polling)
│   ├── rss_detector.py          # Monitor RSS + Google Alerts + TikTok/Instagram/Pinterest RSS
│   ├── trends_detector.py       # Google Trends velocity + Trending RSS + Rising Queries
│   ├── youtube_comments.py      # Trend commenti + sentiment + intensità emotiva
│   ├── youtube_scraper.py       # Scraper canali outperformer
│   ├── competitor_monitor.py    # Nuovi video + crescita iscritti + keyword da titoli
│   ├── cross_signal.py          # Convergenza multi-piattaforma + AI title generator
│   ├── news_detector.py         # Monitor notizie via NewsAPI.org
│   ├── twitter_detector.py      # Monitor X/Twitter
│   ├── reddit_detector.py       # Monitor Reddit
│   ├── pinterest_detector.py    # Monitor Pinterest API v5
│   └── yt_api.py                # Helper YouTube API condiviso
└── data/
    └── ytsperbot.db             # Database SQLite (auto-generato)
```

---

## Setup

### Prerequisiti

#### Obbligatori

| Servizio | Dove ottenerlo | Variabile `.env` |
|---|---|---|
| Python 3.12 | [python.org](https://www.python.org/downloads/) | — |
| Telegram Bot Token | [@BotFather](https://t.me/BotFather) su Telegram | `TELEGRAM_BOT_TOKEN` |
| Telegram Chat ID | [@userinfobot](https://t.me/userinfobot) su Telegram | `TELEGRAM_CHAT_ID` |
| YouTube Data API v3 | [Google Cloud Console](https://console.cloud.google.com) → API & Services → Credentials | `YOUTUBE_API_KEY` |
| Twitter/X Bearer Token | [developer.twitter.com](https://developer.twitter.com) → Projects & Apps → Keys | `TWITTER_BEARER_TOKEN` |

#### Opzionali (ogni chiave attiva un modulo aggiuntivo)

| Servizio | Dove ottenerlo | Variabile `.env` | Modulo abilitato |
|---|---|---|---|
| Reddit API | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) (tipo: script) | `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` | Reddit detector |
| NewsAPI | [newsapi.org](https://newsapi.org) (free: 100 req/giorno) | `NEWSAPI_KEY` | News detector |
| Pinterest Access Token | [developers.pinterest.com](https://developers.pinterest.com) | `PINTEREST_ACCESS_TOKEN` | Pinterest API trends |
| Anthropic API | [console.anthropic.com](https://console.anthropic.com) | `ANTHROPIC_API_KEY` | AI title generator nel cross-signal |
| Apify API | [apify.com](https://apify.com) (free: $5/mese di crediti) | `APIFY_API_KEY` | TikTok + Instagram outperformer scraper |
| Dashboard Token | stringa segreta a scelta | `DASHBOARD_TOKEN` | Protegge `/dashboard` da accessi non autorizzati |

### Installazione

```bash
git clone https://github.com/Alucard9994/YTSPERBOT.git
cd YTSPERBOT
pip install -r requirements.txt
```

### Configurazione credenziali

Copia `.env.template` in `.env` e compila i valori:

```bash
cp .env.template .env
```

```env
# --- TELEGRAM ---
TELEGRAM_BOT_TOKEN=il_tuo_token
TELEGRAM_CHAT_ID=il_tuo_chat_id

# --- YOUTUBE ---
YOUTUBE_API_KEY=la_tua_api_key

# --- TWITTER / X ---
TWITTER_BEARER_TOKEN=il_tuo_bearer_token

# --- REDDIT (opzionale) ---
REDDIT_CLIENT_ID=inserisci_qui
REDDIT_CLIENT_SECRET=inserisci_qui
REDDIT_USER_AGENT=ytsperbot/1.0

# --- NEWSAPI.ORG (opzionale) ---
NEWSAPI_KEY=inserisci_qui

# --- PINTEREST API (opzionale) ---
PINTEREST_ACCESS_TOKEN=inserisci_qui

# --- ANTHROPIC CLAUDE API (opzionale) ---
ANTHROPIC_API_KEY=inserisci_qui

# --- DASHBOARD TOKEN (opzionale) ---
DASHBOARD_TOKEN=una_stringa_segreta_qualsiasi
```

---

## Utilizzo

```bash
# Avvio in produzione (scheduler automatico)
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

## Dashboard Web

Il bot espone una dashboard HTML con le top keyword degli ultimi 7 giorni:

```
https://ytsperbot.onrender.com/dashboard?token=IL_TUO_DASHBOARD_TOKEN
```

Aggiornata ad ogni ricarica della pagina. **Salva l'URL completo come bookmark** per accedervi con un click.

> Se `DASHBOARD_TOKEN` non è configurata, la dashboard restituisce sempre 403. Con il token configurato, l'accesso è consentito solo via `?token=...`.

---

## Parametri configurabili

Tutto si modifica in `config.yaml` senza toccare il codice.

### Trend Detector

| Parametro | Default | Descrizione |
|---|---|---|
| `check_interval_hours` | `4` | Frequenza dei check |
| `velocity_threshold_longform` | `300` | % crescita per alert long-form |
| `velocity_threshold_shorts` | `500` | % crescita per alert Shorts |
| `min_mentions_to_track` | `3` | Menzioni minime per tracciare una keyword |

### Priority Score

| Parametro | Default | Descrizione |
|---|---|---|
| `min_score` | `3` | Score minimo 1-10 per ricevere l'alert |

### YouTube Scraper

| Parametro | Default | Descrizione |
|---|---|---|
| `max_followers` | `80000` | Iscritti massimi canale |
| `min_followers` | `1000` | Iscritti minimi canale |
| `multiplier_threshold` | `3.0` | Soglia outperformer (3x la media del canale) |
| `lookback_days` | `30` | Finestra temporale analisi video |
| `run_time` | `03:00` | Orario esecuzione giornaliera (UTC) |

### Apify Social Scraper

| Parametro | Default | Descrizione |
|---|---|---|
| `run_time` | `04:00` | Orario esecuzione giornaliera (UTC) |
| `new_profiles_per_platform` | `15` | Max nuovi profili scoperti al giorno per piattaforma |
| `profile_recheck_days` | `30` | Giorni prima di rianalizzare un profilo già in DB |
| `min_followers` | `1000` | Follower minimi |
| `max_followers` | `80000` | Follower massimi |
| `multiplier_threshold` | `3.0` | Soglia outperformer (3x la media del profilo) |
| `lookback_days` | `30` | Finestra temporale analisi video |
| `tiktok_hashtags` | `[...]` | Hashtag TikTok da monitorare |
| `instagram_hashtags` | `[...]` | Hashtag Instagram da monitorare |

### Competitor Monitor

| Parametro | Default | Descrizione |
|---|---|---|
| `new_video_max_age_hours` | `48` | Ignora video più vecchi al primo avvio |
| `subscriber_growth_threshold` | `0.10` | % crescita in 7 giorni per scattare alert |
| `subscriber_check_time` | `09:00` | Orario controllo iscritti (UTC) |

### Cross Signal

| Parametro | Default | Descrizione |
|---|---|---|
| `min_sources` | `3` | Numero minimo di fonti diverse per alert |
| `lookback_hours` | `6` | Finestra temporale di analisi |
| `cooldown_hours` | `12` | Cooldown tra alert per la stessa keyword |
| `ai_titles` | `true` | Genera titoli video con AI (richiede `ANTHROPIC_API_KEY`) |

### News API

| Parametro | Default | Descrizione |
|---|---|---|
| `check_interval_hours` | `6` | Frequenza controllo |
| `keywords_per_run` | `10` | Keyword campionate per run (rispetta quota 100 req/giorno) |
| `languages` | `["en", "it"]` | Lingue da monitorare |
| `velocity_threshold` | `200` | % crescita per scattare alert |

### Weekly Report

| Parametro | Default | Descrizione |
|---|---|---|
| `send_day` | `sunday` | Giorno invio (monday–sunday) |
| `send_time` | `09:00` | Orario invio (UTC) |

### Google Trends Velocity

| Parametro | Default | Descrizione |
|---|---|---|
| `timeframe` | `now 7-d` | Finestra dati Trends |
| `geo` | `""` | Geo (`""` = Worldwide, `"IT"` = Italia) |
| `velocity_threshold` | `50` | % aumento interest per scattare alert |
| `top_n_keywords` | `20` | Keyword controllate per run |

### Google Trending RSS

| Parametro | Default | Descrizione |
|---|---|---|
| `geos` | `["IT", "US"]` | Paesi da monitorare |
| `check_interval_minutes` | `60` | Frequenza controllo |
| `extra_filter_words` | `[...]` | Parole aggiuntive oltre a quelle built-in della nicchia |

### Rising Queries

| Parametro | Default | Descrizione |
|---|---|---|
| `check_interval_hours` | `6` | Frequenza controllo |
| `keywords_per_run` | `8` | Keyword sonda per run (rispetta rate limit pytrends) |
| `min_growth` | `500` | % minimo crescita per alertare (`Breakout` = sempre inviato) |
| `geo` | `""` | Geo (`""` = Worldwide, `"IT"` = solo Italia) |

---

## Alert intelligenti

### Priority Score (1–10)
Ogni alert include uno score calcolato su:
- **Velocity** (0–5 punti): quanto velocemente cresce la keyword
- **Multi-source** (0–5 punti): quante fonti diverse la segnalano simultaneamente

```
🎯 Score: 8/10  🟥🟥🟥🟥⬜
```

### 🚨 Convergenza Multi-Piattaforma
Quando la stessa keyword emerge su 3+ fonti diverse in 6 ore, scatta un alert speciale ad alta priorità. Se `ANTHROPIC_API_KEY` è configurata, vengono generati automaticamente 5 titoli video ottimizzati per YouTube sulla base del topic in trend.

### 🧠 Sentiment commenti competitor
Il modulo YouTube Comments classifica le richieste del pubblico:
- 🎬 **Richieste video** — "fai un video su..."
- 🔍 **Domande su fonti** — "qualcuno sa dove trovare..."
- 📖 **Richieste approfondimento** — "puoi spiegare meglio..."
- 💡 **Suggerimenti topic** — "dovresti parlare di..."

E analizza l'**intensità emotiva** con pattern matching locale (no API):
- 😱 Paura · 🤔 Curiosità · 🤯 Shock · ✋ Coinvolgimento personale

---

## Deploy su Render (gratuito)

1. Crea un account su [render.com](https://render.com)
2. **New** → **Blueprint** → connetti il repo GitHub `Alucard9994/YTSPERBOT`
3. Render legge `render.yaml` e configura tutto automaticamente
4. Vai su **Environment** e aggiungi le variabili:

| Key | Obbligatorio | Note |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | |
| `TELEGRAM_CHAT_ID` | ✅ | |
| `YOUTUBE_API_KEY` | ✅ | |
| `TWITTER_BEARER_TOKEN` | ✅ | |
| `REDDIT_USER_AGENT` | ✅ | valore: `ytsperbot/1.0` |
| `REDDIT_CLIENT_ID` | ⚙️ opzionale | attiva Reddit detector |
| `REDDIT_CLIENT_SECRET` | ⚙️ opzionale | attiva Reddit detector |
| `NEWSAPI_KEY` | ⚙️ opzionale | attiva News detector |
| `PINTEREST_ACCESS_TOKEN` | ⚙️ opzionale | attiva Pinterest API trends |
| `ANTHROPIC_API_KEY` | ⚙️ opzionale | attiva AI title generator |
| `APIFY_API_KEY` | ⚙️ opzionale | attiva TikTok + Instagram scraper |
| `DASHBOARD_TOKEN` | ⚙️ opzionale | protegge `/dashboard` da accessi esterni |

5. Configura **UptimeRobot** (gratuito) per pingare `https://ytsperbot.onrender.com/health` ogni 5 minuti — impedisce il sleep del servizio gratuito.

---

## Attivare Apify (TikTok + Instagram Scraper)

1. Registrati su [apify.com](https://apify.com) — piano free, nessuna carta di credito richiesta
2. Vai su **Settings → Integrations** → copia la **Personal API token**
3. Aggiungila al `.env` e alle variabili Render:

```env
APIFY_API_KEY=la_tua_api_key
```

> Il modulo si attiva automaticamente. Gira ogni giorno alle 04:00 UTC (un'ora dopo lo YouTube Scraper). Scopre fino a 15 nuovi profili TikTok + 15 Instagram al giorno, filtra per 1k–80k follower e segnala i contenuti con views 3x+ la media del profilo. I profili già in DB vengono ricontrollati ogni 30 giorni per nuovi video outperformer.

## Attivare Reddit

1. Crea un'app su [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) (tipo: **script**)
2. Inserisci le credenziali nel `.env` / variabili Render
3. In `modules/reddit_detector.py` imposta `REDDIT_ENABLED = True`
4. Riavvia il servizio

## Attivare Pinterest API

1. Vai su [developers.pinterest.com](https://developers.pinterest.com) → **My Apps** → **Create App**
2. Attiva i permessi: `pins:read`, `user_accounts:read`
3. Genera un Access Token e aggiungilo a `.env` / variabili Render

> Senza token il modulo RSS Pinterest (10 feed RSSHub) rimane comunque attivo.

## Attivare NewsAPI

1. Registrati su [newsapi.org](https://newsapi.org) — piano free, nessuna carta di credito
2. Copia la API key e aggiungila a `.env` / variabili Render

## Attivare AI Title Generator

1. Registrati su [console.anthropic.com](https://console.anthropic.com)
2. Crea una API key e aggiungila a `.env` / variabili Render
3. Ogni alert di convergenza multi-piattaforma includerà automaticamente 5 titoli YouTube ottimizzati per la nicchia

---

## Note

- `.env` non va mai committato — è già in `.gitignore`
- Il database SQLite viene creato automaticamente in `data/ytsperbot.db` al primo avvio
- Le quote YouTube API (10.000 unità/giorno) vengono rispettate — il competitor monitor usa RSS (0 quota)
- Tutti i moduli sono **read-only**: nessuna scrittura, post o interazione sulle piattaforme monitorate
- I comandi `/graph` e `/cerca` richiedono almeno un ciclo completo del bot per avere dati in DB
- Gli orari `08:00`, `09:00` ecc. sono in **UTC** → ora italiana +1h (solare) o +2h (legale)

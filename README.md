# YTSPERBOT

Sistema di **trend intelligence** per canali YouTube nella nicchia paranormale/horror/occulto. Monitora keyword su più piattaforme, individua canali outperformer e invia alert su Telegram prima che i topic esplodano.

---

## Funzionalità

| Modulo | Fonte | Stato |
|---|---|---|
| RSS Detector | 19 feed (English + Podcast + Italian) + 36 Google Alerts | ✅ Attivo |
| Google Trends | `pytrends` — interest 0-100 sulle keyword | ✅ Attivo |
| YouTube Comments | Trend nei commenti della nicchia + richieste competitor | ✅ Attivo |
| YouTube Scraper | Canali 1k–80k iscritti con video outperformer (3x media) | ✅ Attivo |
| Twitter / X | Keyword velocity su tweet recenti | ✅ Attivo |
| Reddit | Keyword velocity su subreddit tematici | ⏳ In attesa credenziali |

---

## Struttura del progetto

```
YTSPERBOT/
├── main.py                      # Orchestratore + scheduler
├── config.yaml                  # Tutti i parametri configurabili
├── requirements.txt
├── .env                         # Credenziali (NON caricare su Git)
├── modules/
│   ├── database.py              # Persistenza SQLite
│   ├── telegram_bot.py          # Notifiche Telegram
│   ├── rss_detector.py          # Monitor RSS + Google Alerts
│   ├── trends_detector.py       # Google Trends via pytrends
│   ├── youtube_comments.py      # Trend commenti + competitor intelligence
│   ├── youtube_scraper.py       # Scraper canali outperformer
│   ├── twitter_detector.py      # Monitor X/Twitter
│   ├── reddit_detector.py       # Monitor Reddit
│   └── yt_api.py                # Helper YouTube API condiviso
└── data/
    └── ytsperbot.db               # Database SQLite (auto-generato)
```

---

## Setup

### Prerequisiti

- Python 3.10+
- Un bot Telegram (crea con [@BotFather](https://t.me/BotFather))
- YouTube Data API v3 key ([Google Cloud Console](https://console.cloud.google.com))
- Twitter/X Bearer Token ([developer.twitter.com](https://developer.twitter.com))

### Installazione

```bash
git clone https://github.com/Alucard9994/YTSPERBOT.git
cd YTSPERBOT
pip install -r requirements.txt
```

### Configurazione credenziali

Crea il file `.env` nella root del progetto:

```env
# Telegram
TELEGRAM_BOT_TOKEN=il_tuo_token
TELEGRAM_CHAT_ID=il_tuo_chat_id

# YouTube
YOUTUBE_API_KEY=la_tua_api_key

# Twitter / X
TWITTER_BEARER_TOKEN=il_tuo_bearer_token

# Reddit (attivare quando approvato)
REDDIT_CLIENT_ID=inserisci_qui
REDDIT_CLIENT_SECRET=inserisci_qui
REDDIT_USER_AGENT=ytsperbot/1.0
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

## Parametri configurabili

Tutto si modifica in `config.yaml` senza toccare il codice.

### Trend Detector

| Parametro | Default | Descrizione |
|---|---|---|
| `check_interval_hours` | `4` | Frequenza dei check |
| `velocity_threshold_longform` | `300` | % crescita per alert long-form |
| `velocity_threshold_shorts` | `500` | % crescita per alert Shorts |
| `min_mentions_to_track` | `3` | Menzioni minime per tracciare una keyword |

### YouTube Scraper

| Parametro | Default | Descrizione |
|---|---|---|
| `max_followers` | `80000` | Iscritti massimi canale |
| `min_followers` | `1000` | Iscritti minimi canale |
| `multiplier_threshold` | `3.0` | Soglia outperformer (3x = 3x la media del canale) |
| `lookback_days` | `30` | Finestra temporale analisi video |
| `run_time` | `03:00` | Orario esecuzione giornaliera |

### Google Trends

| Parametro | Default | Descrizione |
|---|---|---|
| `timeframe` | `now 7-d` | Finestra dati Trends |
| `geo` | `""` | Geo (`""` = Worldwide, `"IT"` = Italia) |
| `velocity_threshold` | `50` | % aumento interest per scattare alert |
| `top_n_keywords` | `20` | Keyword controllate per run |

---

## Attivare Reddit

1. Crea un'app su [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) (tipo: **script**)
2. Inserisci le credenziali nel `.env`
3. In `modules/reddit_detector.py` imposta `REDDIT_ENABLED = True`
4. Riavvia il sistema

---

## Deploy su Render (gratuito)

1. Crea un account su [render.com](https://render.com)
2. **New** → **Blueprint** → connetti il tuo repo GitHub
3. Render legge il file `render.yaml` e configura tutto automaticamente
4. Vai su **Environment** e aggiungi le variabili:

| Key | Valore |
|---|---|
| `TELEGRAM_BOT_TOKEN` | il tuo token |
| `TELEGRAM_CHAT_ID` | il tuo chat ID |
| `YOUTUBE_API_KEY` | la tua API key |
| `TWITTER_BEARER_TOKEN` | il tuo bearer token |
| `REDDIT_CLIENT_ID` | quando disponibile |
| `REDDIT_CLIENT_SECRET` | quando disponibile |

5. Click **Deploy** — il bot parte e gira 24/7 sul piano gratuito

> Il servizio è configurato come **background worker**: non va in sleep come i web service gratuiti.

---

## Note

- `.env` non va mai committato — aggiungilo a `.gitignore`
- Il database SQLite viene creato automaticamente in `data/ytsperbot.db`
- Le quote YouTube API (10.000 unità/giorno) vengono rispettate
- Tutti i moduli sono **read-only**: nessuna scrittura, post o interazione sulle piattaforme

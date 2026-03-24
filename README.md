# YTSPERBOT

Sistema di **trend intelligence** per canali YouTube nella nicchia paranormale/horror/occulto. Monitora keyword su più piattaforme, individua canali outperformer, analizza i competitor e invia alert su Telegram prima che i topic esplodano.

---

## Funzionalità

| Modulo | Fonte | Frequenza | Stato |
|---|---|---|---|
| RSS Detector | 19 feed (English + Podcast + Italian) + 36 Google Alerts | ogni 4h | ✅ Attivo |
| Google Trends | `pytrends` — interest 0-100 sulle keyword | ogni 4h | ✅ Attivo |
| YouTube Comments | Trend commenti nicchia + sentiment competitor | ogni 4h | ✅ Attivo |
| YouTube Scraper | Canali 1k–80k iscritti con video outperformer (3x media) | ogni giorno 03:00 | ✅ Attivo |
| Competitor Monitor | Nuovo video (RSS, 0 quota) + crescita iscritti | ogni 30 min / 1x/giorno | ✅ Attivo |
| Twitter / X | Keyword velocity su tweet recenti | ogni 4h | ✅ Attivo |
| Reddit | Keyword velocity su subreddit tematici | ogni 4h | ⏳ In attesa credenziali |

---

## Comandi Telegram

| Comando | Descrizione |
|---|---|
| `/run` | Esegui tutti i moduli subito |
| `/rss` | Solo RSS detector |
| `/reddit` | Solo Reddit detector |
| `/twitter` | Solo Twitter/X detector |
| `/trends` | Solo Google Trends |
| `/comments` | Solo YouTube Comments |
| `/scraper` | Solo YouTube Scraper |
| `/transcript <video_id>` | Scarica trascrizione di un video YouTube |
| `/cerca <keyword>` | Cerca una keyword in tutte le fonti (ultimi 7 giorni) |
| `/graph <keyword>` | Grafico trend 7 giorni inviato come immagine |
| `/brief` | Riepilogo top keyword delle ultime 24h |
| `/block <keyword>` | Silenzia una keyword rumorosa |
| `/unblock <keyword>` | Rimuovi dalla blacklist |
| `/blocklist` | Lista keyword bloccate |
| `/status` | Stato del bot e ora server |

---

## Struttura del progetto

```
YTSPERBOT/
├── main.py                      # Orchestratore + scheduler
├── config.yaml                  # Tutti i parametri configurabili
├── requirements.txt
├── render.yaml                  # Configurazione deploy Render
├── .python-version              # Pin Python 3.12
├── .env                         # Credenziali (NON caricare su Git)
├── modules/
│   ├── database.py              # Persistenza SQLite
│   ├── telegram_bot.py          # Notifiche + grafici Telegram
│   ├── telegram_commands.py     # Command listener (polling)
│   ├── rss_detector.py          # Monitor RSS + Google Alerts
│   ├── trends_detector.py       # Google Trends via pytrends
│   ├── youtube_comments.py      # Trend commenti + sentiment competitor
│   ├── youtube_scraper.py       # Scraper canali outperformer
│   ├── competitor_monitor.py    # Nuovi video + crescita iscritti competitor
│   ├── twitter_detector.py      # Monitor X/Twitter
│   ├── reddit_detector.py       # Monitor Reddit
│   └── yt_api.py                # Helper YouTube API condiviso
└── data/
    └── ytsperbot.db             # Database SQLite (auto-generato)
```

---

## Setup

### Prerequisiti

- Python 3.12
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

### Competitor Monitor

| Parametro | Default | Descrizione |
|---|---|---|
| `new_video_max_age_hours` | `48` | Ignora video più vecchi al primo avvio |
| `subscriber_growth_threshold` | `0.10` | % crescita in 7 giorni per scattare alert |
| `subscriber_check_time` | `09:00` | Orario controllo iscritti (UTC) |

### Google Trends

| Parametro | Default | Descrizione |
|---|---|---|
| `timeframe` | `now 7-d` | Finestra dati Trends |
| `geo` | `""` | Geo (`""` = Worldwide, `"IT"` = Italia) |
| `velocity_threshold` | `50` | % aumento interest per scattare alert |
| `top_n_keywords` | `20` | Keyword controllate per run |

---

## Alert intelligenti

### Priority Score (1–10)
Ogni alert include uno score calcolato su:
- **Velocity** (0–5 punti): quanto velocemente cresce la keyword
- **Multi-source** (0–5 punti): quante fonti diverse la segnalano simultaneamente

```
🎯 Score: 8/10  🟥🟥🟥🟥⬜
```

### Sentiment commenti
Il modulo YouTube Comments classifica le richieste del pubblico in categorie:
- 🎬 **Richieste video** — "fai un video su..."
- 🔍 **Domande su fonti** — "qualcuno sa dove trovare..."
- 📖 **Richieste approfondimento** — "puoi spiegare meglio..."
- 💡 **Suggerimenti topic** — "dovresti parlare di..."

---

## Attivare Reddit

1. Crea un'app su [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) (tipo: **script**)
2. Inserisci le credenziali nel `.env`
3. In `modules/reddit_detector.py` imposta `REDDIT_ENABLED = True`
4. Riavvia il sistema

---

## Deploy su Render (gratuito)

1. Crea un account su [render.com](https://render.com)
2. **New** → **Blueprint** → connetti il tuo repo GitHub `Alucard9994/YTSPERBOT`
3. Render legge `render.yaml` e configura tutto automaticamente
4. Vai su **Environment** e aggiungi le variabili:

| Key | Valore |
|---|---|
| `TELEGRAM_BOT_TOKEN` | il tuo token |
| `TELEGRAM_CHAT_ID` | il tuo chat ID |
| `YOUTUBE_API_KEY` | la tua API key |
| `TWITTER_BEARER_TOKEN` | il tuo bearer token |
| `REDDIT_USER_AGENT` | `ytsperbot/1.0` |

5. Configura **UptimeRobot** (gratuito) per pingare `https://ytsperbot.onrender.com/health` ogni 5 minuti — impedisce il sleep del servizio.

---

## Note

- `.env` non va mai committato — è in `.gitignore`
- Il database SQLite viene creato automaticamente in `data/ytsperbot.db`
- Le quote YouTube API (10.000 unità/giorno) vengono rispettate — il competitor monitor usa RSS (0 quota)
- Tutti i moduli sono **read-only**: nessuna scrittura, post o interazione sulle piattaforme
- I grafici `/graph` richiedono che il bot abbia eseguito almeno un ciclo completo per avere dati in DB

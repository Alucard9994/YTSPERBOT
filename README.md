# YTSPERBOT

Sistema di **trend intelligence** per canali YouTube nella nicchia paranormale/horror/occulto. Monitora keyword su più piattaforme, individua canali outperformer, analizza i competitor e invia alert su Telegram prima che i topic esplodano.

---

## Funzionalità

| Modulo | Fonte | Frequenza | Stato |
|---|---|---|---|
| RSS Detector | 19 feed (English + Podcast + Italian) + 36 Google Alerts | ogni 4h | ✅ Attivo |
| Google Trends Velocity | `pytrends` — interest 0-100 sulle keyword monitorate | ogni 4h | ✅ Attivo |
| Google Trending RSS | Feed RSS trending IT + US filtrati per nicchia (0 quota) | ogni 60 min | ✅ Attivo |
| Rising Queries | Keyword emergenti correlate via pytrends | ogni 6h | ✅ Attivo |
| YouTube Comments | Trend commenti nicchia + sentiment competitor | ogni 4h | ✅ Attivo |
| YouTube Scraper | Canali 1k–80k iscritti con video outperformer (3x media) | ogni giorno 03:00 | ✅ Attivo |
| Competitor Monitor | Nuovo video competitor (RSS, 0 quota) | ogni 30 min | ✅ Attivo |
| Competitor Iscritti | Crescita iscritti +10% in 7 giorni | ogni giorno 09:00 | ✅ Attivo |
| Pinterest RSS | Feed RSSHub per hashtag di nicchia (0 quota) | ogni 4h | ✅ Attivo |
| Pinterest API | Trend growing/emerging + velocity via API v5 | ogni 6h | ⚙️ Richiede token |
| Twitter / X | Keyword velocity su tweet recenti | ogni 4h | ✅ Attivo |
| Reddit | Keyword velocity su subreddit tematici | ogni 4h | ⏳ In attesa credenziali |

---

## Comandi Telegram

| Comando | Descrizione |
|---|---|
| `/run` | Esegui tutti i moduli subito (esclusi scraper e iscritti) |
| `/rss` | Solo RSS detector |
| `/reddit` | Solo Reddit detector |
| `/twitter` | Solo Twitter/X detector |
| `/trends` | Solo Google Trends velocity |
| `/pinterest` | Controlla trend Pinterest ora (richiede token API) |
| `/trending` | Controlla trending Google IT + US ora |
| `/rising` | Scopri keyword emergenti correlate ora |
| `/comments` | Solo YouTube Comments + sentiment |
| `/scraper` | Solo YouTube Scraper canali outperformer |
| `/newvideo` | Controlla nuovi video competitor ora |
| `/subscribers` | Controlla crescita iscritti competitor ora |
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
| `keywords_per_run` | `8` | Keyword sonda per run (rispetta rate limit) |
| `min_growth` | `500` | % minimo crescita per alertare (`Breakout` = sempre) |
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

### Sentiment commenti
Il modulo YouTube Comments classifica le richieste del pubblico in categorie:
- 🎬 **Richieste video** — "fai un video su..."
- 🔍 **Domande su fonti** — "qualcuno sa dove trovare..."
- 📖 **Richieste approfondimento** — "puoi spiegare meglio..."
- 💡 **Suggerimenti topic** — "dovresti parlare di..."

---

## Attivare Pinterest API

1. Vai su [developers.pinterest.com](https://developers.pinterest.com) → **My Apps** → **Create App**
2. Nella sezione **Permissions** attiva: `pins:read`, `user_accounts:read`
3. Vai su **Generate Access Token** e copia il token
4. Aggiungilo al `.env` e alle variabili Render:

```env
PINTEREST_ACCESS_TOKEN=il_tuo_token
```

> Senza token il modulo RSS Pinterest (feed RSSHub) rimane attivo. Il modulo API si attiva automaticamente quando il token è presente.

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

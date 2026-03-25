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
| Twitter / X | Keyword velocity su tweet recenti | ogni 4h | ❌ API a pagamento (piano Basic $100/mese) |
| Reddit | Keyword velocity su subreddit tematici | ogni 4h | ⚙️ Richiede credenziali |
| Google Trends Velocity | `pytrends` — interest 0-100 sulle keyword monitorate | ogni 4h | ✅ Attivo |
| YouTube Comments | Trend commenti nicchia + sentiment + intensità emotiva | ogni 4h | ⚙️ Richiede `YOUTUBE_API_KEY` |
| TikTok Scraper | Profili 1k–80k follower con video outperformer 3x media (Apify) | ogni mercoledì 04:00 UTC | ⚙️ Richiede `APIFY_API_KEY` |
| Instagram Scraper | Profili 1k–80k follower con post outperformer 3x media (Apify) | ogni mercoledì 04:00 UTC | ⚙️ Richiede `APIFY_API_KEY` |
| Cross Signal | Convergenza 3+ fonti sulla stessa keyword → alert alta priorità | dopo ogni ciclo 4h | ✅ Attivo |
| Google Trending RSS | Feed RSS trending IT + US filtrati per nicchia (0 quota) | ogni 60 min | ✅ Attivo |
| Competitor Monitor | Nuovo video competitor via RSS (0 quota) + estrazione keyword titoli | ogni 30 min | ⚙️ Richiede `YOUTUBE_API_KEY` |
| Rising Queries | Keyword emergenti correlate via pytrends | ogni 6h | ✅ Attivo |
| Pinterest API | Trend growing/emerging + velocity via API v5 | ogni 6h | ⚙️ Richiede token |
| News Detector | Notizie di nicchia via NewsAPI.org (100 req/giorno free) | ogni 6h | ⚙️ Richiede `NEWSAPI_KEY` |
| YouTube Scraper | Canali 1k–80k iscritti con video outperformer (3x media) | ogni giorno 03:00 UTC | ⚙️ Richiede `YOUTUBE_API_KEY` |
| Competitor Iscritti | Crescita iscritti +10% in 7 giorni | ogni giorno 09:00 UTC | ⚙️ Richiede `YOUTUBE_API_KEY` |
| Daily Brief | Riepilogo top keyword 24h | ogni giorno 08:00 UTC | ✅ Attivo |
| Weekly Report | Report top keyword 7 giorni | ogni domenica 09:00 UTC | ✅ Attivo |

---

## Comandi Telegram

### Esecuzione moduli

| Comando | Descrizione | Credenziali richieste |
|---|---|---|
| `/run` | Esegui tutti i moduli attivi (salta automaticamente quelli senza credenziali) | — |
| `/rss` | Solo RSS + TikTok + Instagram + Pinterest RSS | — |
| `/reddit` | Solo Reddit detector | `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` |
| `/twitter` | Solo Twitter/X detector | `TWITTER_BEARER_TOKEN` (piano a pagamento) |
| `/trends` | Solo Google Trends velocity | — |
| `/comments` | Solo YouTube Comments + sentiment | `YOUTUBE_API_KEY` |
| `/scraper` | Solo YouTube Scraper canali outperformer | `YOUTUBE_API_KEY` |
| `/pinterest` | Controlla trend Pinterest API ora | — |
| `/trending` | Controlla trending Google IT + US ora | — |
| `/rising` | Scopri keyword emergenti correlate ora | — |
| `/newvideo` | Controlla nuovi video competitor ora | `YOUTUBE_API_KEY` |
| `/subscribers` | Controlla crescita iscritti competitor ora | `YOUTUBE_API_KEY` |
| `/convergence` | Controlla convergenza multi-piattaforma ora | — |
| `/news` | Controlla notizie di nicchia ora | `NEWSAPI_KEY` |
| `/social` | Scraper TikTok + Instagram outperformer ora | `APIFY_API_KEY` |
| `/weekly` | Report settimanale top keyword | — |
| `/brief` | Riepilogo top keyword delle ultime 24h | — |

### Ricerca e analisi

| Comando | Descrizione |
|---|---|
| `/transcript <video_id>` | Scarica trascrizione di un video YouTube |
| `/cerca <keyword>` | Cerca una keyword in tutte le fonti (ultimi 7 giorni) |
| `/graph <keyword>` | Grafico trend 7 giorni inviato come immagine |

### Configurazione via Telegram

| Comando | Descrizione |
|---|---|
| `/config` | Mostra tutti i parametri configurabili con valore attuale |
| `/set <chiave>` | Info su una chiave (tipo, range, valore attuale) |
| `/set <chiave> <valore>` | Modifica un parametro — effetto immediato, nessun redeploy |
| `/dashboard` | Invia il link completo alla dashboard web (include il token) |

### Backup & Restore

| Comando | Descrizione |
|---|---|
| `/backup` | Genera e invia un dump SQL del DB corrente come file `.sql` |
| `/populate` | Arma il bot per ricevere un restore — lock attivo 5 minuti |
| `/dbstats` | Mostra righe per tabella e dimensione del file DB |

> **Flusso restore:** `/populate` → bot conferma il lock con scadenza → invia il file `.sql` entro 5 minuti → bot esegue il restore e disarma automaticamente il lock. Se non invii nulla entro 5 minuti il lock scade senza fare nulla. Questo previene restore accidentali.

### Blacklist e info

| Comando | Descrizione |
|---|---|
| `/block <keyword>` | Silenzia una keyword rumorosa |
| `/unblock <keyword>` | Rimuovi dalla blacklist |
| `/blocklist` | Lista keyword bloccate |
| `/status` | Stato del bot + stato di ogni credenziale configurata |
| `/help` | Lista completa di tutti i comandi disponibili |

> I comandi che richiedono credenziali rispondono con un messaggio di errore esplicito se la variabile d'ambiente non è configurata, invece di crashare.

---

## Struttura del progetto

```
YTSPERBOT/
├── main.py                      # Orchestratore + scheduler + dashboard web
├── config.yaml                  # Parametri di default (valori base, non modificare in produzione)
├── requirements.txt
├── render.yaml                  # Configurazione deploy Render
├── .python-version              # Pin Python 3.12
├── .env                         # Credenziali (NON caricare su Git)
├── .env.template                # Template credenziali (sicuro da committare)
├── modules/
│   ├── database.py              # Persistenza SQLite + tabella bot_config
│   ├── config_manager.py        # Gestione config via DB — /set, /config, get_config()
│   ├── telegram_bot.py          # Notifiche + grafici Telegram
│   ├── telegram_commands.py     # Command listener (polling) + /backup + /populate
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
│   ├── apify_scraper.py         # TikTok + Instagram outperformer via Apify
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

#### Opzionali (ogni chiave attiva uno o più moduli)

| Servizio | Dove ottenerlo | Variabile `.env` | Modulo abilitato |
|---|---|---|---|
| YouTube Data API v3 | [Google Cloud Console](https://console.cloud.google.com) → API & Services → Credentials | `YOUTUBE_API_KEY` | YouTube Scraper, Comments, Competitor Monitor |
| Reddit API | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) (tipo: script) | `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` | Reddit detector |
| Twitter/X Bearer Token | [developer.twitter.com](https://developer.twitter.com) → Projects & Apps | `TWITTER_BEARER_TOKEN` | Twitter/X detector ⚠️ richiede piano Basic ($100/mese) |
| NewsAPI | [newsapi.org](https://newsapi.org) (free: 100 req/giorno) | `NEWSAPI_KEY` | News detector |
| Pinterest Access Token | [developers.pinterest.com](https://developers.pinterest.com) | `PINTEREST_ACCESS_TOKEN` | Pinterest API trends |
| Anthropic API | [console.anthropic.com](https://console.anthropic.com) | `ANTHROPIC_API_KEY` | AI title generator nel cross-signal |
| Apify API | [apify.com](https://apify.com) (free: $5/mese di crediti) | `APIFY_API_KEY` | TikTok + Instagram outperformer scraper |
| Dashboard Token | stringa segreta a scelta | `DASHBOARD_TOKEN` | Protegge `/dashboard` da accessi non autorizzati |

> **Twitter/X**: il piano free di X non include le API di ricerca dal 2023. Il modulo richiede il piano Basic ($100/mese). Senza credenziali valide (o con credenziali senza crediti) il modulo viene saltato automaticamente senza crashare.

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
# --- TELEGRAM (obbligatori) ---
TELEGRAM_BOT_TOKEN=il_tuo_token
TELEGRAM_CHAT_ID=il_tuo_chat_id

# --- YOUTUBE (opzionale) ---
YOUTUBE_API_KEY=la_tua_api_key

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

# --- APIFY (opzionale) ---
APIFY_API_KEY=inserisci_qui

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

Il bot espone una dashboard HTML con le top keyword degli ultimi 7 giorni.

**Modo rapido — via Telegram:**
```
/dashboard
```
Il bot risponde con il link completo (token incluso), pronto da aprire o salvare come bookmark.

**URL diretto:**
```
https://ytsperbot.onrender.com/dashboard?token=IL_TUO_DASHBOARD_TOKEN
```

Aggiornata ad ogni ricarica della pagina.

> Se `DASHBOARD_TOKEN` non è configurata, la dashboard restituisce sempre 403. Con il token configurato, l'accesso è consentito solo via `?token=...`.

---

## Parametri configurabili

### Due modi per modificare i parametri

**1. Via Telegram (consigliato in produzione)** — nessun redeploy, effetto immediato:
```
/set scraper.multiplier_threshold 2.5
/set priority_score.min_score 2
/set apify_scraper.min_views_tiktok 5000
```
Usa `/config` per vedere tutti i valori attuali e `/set <chiave>` (senza valore) per info su una chiave specifica.

**2. Via `config.yaml`** — richiede commit + redeploy (e azzera il DB su Render free tier):
```yaml
scraper:
  multiplier_threshold: 2.5
```

> I valori modificati via `/set` vengono salvati nel DB e sopravvivono ai **restart** del processo. Vengono persi solo in caso di **redeploy** (che azzera il DB). Usa `/backup` prima di ogni redeploy per non perdere i tuoi override.

> Parametri che controllano gli **intervalli dello scheduler** (es. `check_interval_hours`, `run_time`) vengono salvati correttamente ma applicati solo al prossimo riavvio — il bot avverte automaticamente con un messaggio.

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
| `multiplier_threshold` | `3.0` | Soglia outperformer vs **media views** del canale |
| `multiplier_threshold_followers` | `2.0` | Soglia outperformer vs **iscritti** (views ≥ 2x iscritti) |
| `min_views_absolute` | `5000` | Views minime assolute — ignora video sotto questa soglia |
| `lookback_days` | `30` | Finestra temporale analisi video |
| `max_channels_per_run` | `400` | Canali max analizzati per run |
| `run_time` | `03:00` | Orario esecuzione giornaliera (UTC) |

> Un video viene segnalato come outperformer se supera **almeno uno** dei due moltiplicatori. L'alert mostra solo i criteri effettivamente superati (🔥🔥 se entrambi).

### Apify Social Scraper

| Parametro | Default | Descrizione |
|---|---|---|
| `run_day` | `wednesday` | Giorno esecuzione settimanale (monday–sunday) |
| `run_time` | `04:00` | Orario esecuzione (UTC) |
| `max_results_per_hashtag` | `5` | Risultati per hashtag — **attenzione: aumentare fa salire i costi** |
| `new_profiles_per_platform` | `5` | Max nuovi profili scoperti per run per piattaforma |
| `profile_recheck_days` | `30` | Giorni prima di rianalizzare un profilo già in DB |
| `min_followers` | `1000` | Follower minimi |
| `max_followers` | `80000` | Follower massimi |
| `multiplier_threshold` | `3.0` | Soglia outperformer vs **media views** del profilo |
| `multiplier_threshold_followers` | `1.5` | Soglia outperformer vs **follower** TikTok |
| `multiplier_threshold_followers_ig` | `2.0` | Soglia outperformer vs **follower** Instagram |
| `min_views_tiktok` | `10000` | Views minime assolute TikTok |
| `min_views_instagram` | `3000` | Views/engagement minimi Instagram |
| `lookback_days` | `30` | Finestra temporale analisi video |
| `tiktok_hashtags` | `[...]` | Hashtag TikTok da monitorare (top 5 consigliati) |
| `instagram_hashtags` | `[...]` | Hashtag Instagram da monitorare (top 5 consigliati) |

> Stesso criterio OR del YouTube Scraper: outperformer se supera media views **oppure** follower threshold.

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

## Backup & Restore del Database

Su Render free tier il filesystem è **effimero**: ogni redeploy azzera il DB. Il sistema di backup integrato permette di preservare i dati importanti.

### Cosa viene salvato nel backup

| Tabella | Contenuto | Importanza |
|---|---|---|
| `keyword_blacklist` | Keyword silenziate con `/block` | ⭐⭐⭐ Alta |
| `bot_config` | Override parametri via `/set` | ⭐⭐⭐ Alta |
| `youtube_seen_channels` | Video outperformer già notificati | ⭐⭐ Media (evita ri-invii) |
| `apify_seen_videos` | Video TikTok/IG già notificati | ⭐⭐ Media (evita ri-invii) |
| `apify_profiles` | Profili social scoperti | ⭐⭐ Media |
| `channel_id_cache` | Cache ID canali YouTube | ⭐ Bassa (si ricostruisce) |
| `channel_subscribers_history` | Storico iscritti competitor | ⭐ Bassa |
| `keyword_mentions` | Dati trend storici | ⭐ Bassa |
| `sent_alerts` | Alert già inviati (dedup) | ⭐ Bassa |
| `reddit_seen_posts` | Post Reddit già visti | ⭐ Bassa |

### Flusso consigliato prima di un redeploy

```
1. /backup      →  bot invia ytsperbot_backup_YYYYMMDD_HHMM.sql
2. Salva il file
3. Fai il redeploy su Render
4. Aspetta il messaggio di avvio del bot
5. /populate    →  bot conferma il lock (5 min)
6. Invia il file .sql come documento
7. Bot risponde con il riepilogo delle righe inserite
```

### Comportamento con duplicati

Il file usa `INSERT OR IGNORE` — su un DB fresco (dopo redeploy) tutti i dati vengono inseriti. Se il bot ha già girato dopo il redeploy, le righe già esistenti vengono saltate silenziosamente senza errori.

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
| `REDDIT_USER_AGENT` | ✅ | valore fisso: `ytsperbot/1.0` |
| `YOUTUBE_API_KEY` | ⚙️ opzionale | attiva Scraper, Comments, Competitor Monitor |
| `REDDIT_CLIENT_ID` | ⚙️ opzionale | attiva Reddit detector |
| `REDDIT_CLIENT_SECRET` | ⚙️ opzionale | attiva Reddit detector |
| `NEWSAPI_KEY` | ⚙️ opzionale | attiva News detector |
| `PINTEREST_ACCESS_TOKEN` | ⚙️ opzionale | attiva Pinterest API trends |
| `ANTHROPIC_API_KEY` | ⚙️ opzionale | attiva AI title generator |
| `APIFY_API_KEY` | ⚙️ opzionale | attiva TikTok + Instagram scraper |
| `DASHBOARD_TOKEN` | ⚙️ opzionale | protegge `/dashboard` da accessi esterni |

5. Configura **UptimeRobot** (gratuito) per pingare `https://ytsperbot.onrender.com/` ogni 5 minuti — impedisce il sleep del servizio gratuito.
   - URL: `https://ytsperbot.onrender.com/` (root, non `/health`)
   - Intervallo: **5 minuti**
   - Timeout: **60 secondi** (il cold start di Render può richiedere 30–60s)

---

## ⚠️ Limiti, quote e impatto delle modifiche al config

Ogni servizio ha limiti precisi. Questa sezione spiega cosa succede se modifichi i parametri in `config.yaml` e dove si trova il confine tra gratuito e a pagamento.

---

### YouTube Data API v3 — 10.000 unità/giorno gratuite

| Operazione | Costo in unità |
|---|---|
| Ricerca canali (`search`) | 100 unità per chiamata |
| Statistiche canale (`channels`) | 1 unità per chiamata |
| Video playlist (`playlistItems`) | 1 unità per chiamata |
| Dettagli video (`videos`) | 1 unità per chiamata |
| Commenti (`commentThreads`) | 1 unità per chiamata |

**Consumo stimato per run con impostazioni default:**

| Modulo | Unità stimate |
|---|---|
| YouTube Scraper (400 canali) | ~2.000–3.000 unità |
| YouTube Comments (6 query × 5 video × commenti) | ~200–400 unità |
| Competitor Monitor — iscritti (35 canali) | ~35 unità |
| **Totale giornaliero stimato** | **~2.500–3.500 unità** → ampiamente nel limite |

**Cosa succede se modifichi `max_channels_per_run`:**

| Valore | Unità stimate | Rischio |
|---|---|---|
| `400` (default) | ~3.000 | ✅ Sicuro |
| `600` | ~4.500 | ✅ Sicuro |
| `800` | ~6.000 | ✅ Sicuro |
| `1.200` | ~9.000 | ⚠️ Limite quota in vista |
| `1.500+` | ~11.000+ | ❌ Supera quota → errori 403, modulo bloccato per 24h |

> Se la quota viene superata, il bot non crasha ma le chiamate YouTube falliscono silenziosamente e il modulo si ferma per quel run.

---

### Apify — $5/mese di crediti gratuiti (piano free)

Il pricing degli actor usati è **per risultato restituito**, non per tempo di esecuzione:

| Actor | Pricing |
|---|---|
| `clockworks~free-tiktok-scraper` | **$5.00 / 1.000 risultati** |
| `apify~instagram-scraper` | **$2.70 / 1.000 risultati** |

**Stima con impostazioni default (5 risultati × 5 hashtag, 1 run/settimana):**

| Operazione | Costo per run | Costo mensile (4 run) |
|---|---|---|
| Discovery TikTok (5 hashtag × 5 risultati) | ~$0.125 | ~$0.50 |
| Discovery Instagram (5 hashtag × 5 risultati) | ~$0.068 | ~$0.27 |
| Analisi profili TikTok (5 profili × ~20 video) | ~$0.50 | ~$2.00 |
| Analisi profili Instagram (5 profili × ~20 post) | ~$0.27 | ~$1.08 |
| **Totale stimato** | **~$0.96/run** | **~$3.85/mese** ✅ |

**Cosa succede se modifichi i parametri — soglie di rischio:**

| Modifica | Impatto costo |
|---|---|
| `max_results_per_hashtag: 10` (da 5) | +2x costo discovery |
| `new_profiles_per_platform: 10` (da 5) | +2x costo analisi profili |
| Aggiungere 5 hashtag per piattaforma (da 5 a 10) | +2x costo discovery |
| Passare da settimanale a giornaliero (`run_day` rimosso) | +7x costo totale → ~$27/mese ❌ |

> ⚠️ Con la combinazione `max_results: 30` + `10 hashtag` + run giornaliero (configurazione iniziale prima dell'ottimizzazione), il costo era ~$6–8 per run → ~$180/mese. I parametri default sono stati calibrati per restare nel free tier.

**Cosa succede se la quota free viene esaurita:**
- Le chiamate Apify restituiscono `402 Payment Required`
- Il bot logga l'errore e continua senza crashare
- Nessun alert viene inviato per TikTok/Instagram fino al rinnovo dei crediti (1° del mese)

---

### NewsAPI.org — 100 richieste/giorno gratuite

Il piano free consente esattamente 100 richieste al giorno.

**Consumo stimato con impostazioni default:**

```
keywords_per_run: 10
languages: ["en", "it"]  → 2 chiamate per keyword
check_interval_hours: 6  → 4 run al giorno

10 × 2 × 4 = 80 richieste/giorno → ✅ nel limite
```

**Cosa succede se modifichi i parametri:**

| Modifica | Richieste/giorno | Rischio |
|---|---|---|
| `keywords_per_run: 10` + `interval: 6h` (default) | 80 | ✅ Sicuro |
| `keywords_per_run: 12` + `interval: 6h` | 96 | ✅ Limite in vista |
| `keywords_per_run: 13` + `interval: 6h` | 104 | ❌ Supera quota |
| `keywords_per_run: 10` + `interval: 4h` | 120 | ❌ Supera quota |
| Aggiungere una terza lingua (`languages: ["en", "it", "es"]`) | 120 | ❌ Supera quota |

> Se la quota viene superata, NewsAPI restituisce `426 Too Many Requests`. Il bot logga l'errore e salta il run senza crashare. La quota si azzera a mezzanotte UTC.

---

### pytrends (Google Trends) — nessuna quota ufficiale, ma rate limit aggressivo

pytrends usa l'API non ufficiale di Google Trends. Google non ha una quota dichiarata ma blocca temporaneamente gli IP che fanno troppe richieste.

**Rischio di rate limiting:**

| Scenario | Rischio |
|---|---|
| `top_n_keywords: 20` ogni 4h (default) | ✅ Sicuro con i delay già implementati |
| `top_n_keywords: 40+` | ⚠️ Possibile errore 429 — Google blocca l'IP per 1–24h |
| `keywords_per_run: 8` per rising queries (default) | ✅ Sicuro |
| `keywords_per_run: 15+` | ⚠️ Rischio 429 |
| Ridurre `check_interval_hours` sotto 2h | ❌ Quasi certamente 429 |

> Quando pytrends viene bloccato, il modulo lancia un'eccezione catturata, logga l'errore e il run viene saltato. Si riprende automaticamente al ciclo successivo.

---

### Twitter/X API — piano Basic richiesto ($100/mese)

Il piano free di X non include più le API di ricerca (rimosso nel 2023). Il modulo richiede il piano Basic o superiore. Senza credenziali valide o con un account senza crediti API, il bot logga un errore `402 Payment Required` e salta automaticamente tutte le ricerche senza crashare.

---

### RSSHub (TikTok, Instagram, Pinterest RSS) — 0 costo, ma servizio pubblico

I feed TikTok, Instagram e Pinterest usano l'istanza pubblica di RSSHub (`rsshub.app`). È gratuita ma:
- Può andare offline o essere lenta durante picchi di traffico
- L'istanza pubblica può bloccare certi feed se vengono abusati
- Se smette di funzionare: il modulo RSS non crasha, semplicemente non trova articoli per quei feed

> Per maggiore affidabilità puoi self-hostare RSSHub gratuitamente su Render e aggiornare gli URL in `config.yaml`.

---

### Riepilogo: parametri "a rischio" da non toccare alla leggera

Modificabili via `/set` o `config.yaml`. I valori `/set` hanno precedenza.

| Parametro chiave `/set` | Valore safe | Soglia di rischio |
|---|---|---|
| `scraper.max_channels_per_run` | ≤ 800 | > 1.200 → quota YouTube |
| `apify_scraper.max_results_per_hashtag` | ≤ 5 | > 10 → supera Apify free |
| `apify_scraper.new_profiles_per_platform` | ≤ 5 | > 10 → supera Apify free |
| `apify_scraper.run_day` | settimanale | giornaliero → +7x costo |
| `news_api.keywords_per_run` | ≤ 12 | ≥ 13 con 2 lingue e 6h → supera NewsAPI |
| `news_api.check_interval_hours` | ≥ 6 | < 5 → supera NewsAPI |
| `google_trends.top_n_keywords` | ≤ 25 | > 40 → rischio ban IP pytrends |
| `rising_queries.keywords_per_run` | ≤ 10 | > 15 → rischio ban IP pytrends |

---

## Attivare YouTube Data API

1. Vai su [Google Cloud Console](https://console.cloud.google.com) → **API & Services** → **Library**
2. Cerca e abilita **YouTube Data API v3**
3. Vai su **Credentials** → **Create Credentials** → **API Key**
4. Aggiungila a `.env` / variabili Render come `YOUTUBE_API_KEY`

## Attivare Apify (TikTok + Instagram Scraper)

1. Registrati su [apify.com](https://apify.com) — piano free, nessuna carta di credito richiesta
2. Vai su **Settings → Integrations** → copia la **Personal API token**
3. Aggiungila al `.env` e alle variabili Render:

```env
APIFY_API_KEY=la_tua_api_key
```

> Il modulo gira ogni mercoledì alle 04:00 UTC. Scopre fino a 5 nuovi profili TikTok + 5 Instagram per run, filtra per 1k–80k follower e segnala i contenuti con views 3x+ la media del profilo. I profili già in DB vengono ricontrollati ogni 30 giorni. Costo stimato: ~$0.96/run → ~$3.85/mese (nel free tier da $5/mese).

## Attivare Reddit

1. Crea un'app su [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) (tipo: **script**)
2. Inserisci le credenziali nel `.env` / variabili Render
3. Riavvia il servizio — il modulo si attiva automaticamente

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
- **Su Render free tier il DB viene azzerato ad ogni redeploy** — usa `/backup` prima di ogni deploy e `/populate` (inviando il file `.sql`) dopo il riavvio
- I parametri modificati via `/set` vengono salvati nel DB — sopravvivono ai restart ma non ai redeploy; `/backup` li include
- Le trascrizioni YouTube (`/transcript`) funzionano senza cookies per la maggior parte dei video pubblici con sottotitoli disponibili
- Gli orari `08:00`, `09:00` ecc. sono in **UTC** → ora italiana +1h (solare) o +2h (legale)
- Tutti i moduli sono **read-only**: nessuna scrittura, post o interazione sulle piattaforme monitorate
- I comandi `/graph` e `/cerca` richiedono almeno un ciclo completo del bot per avere dati in DB
- Il messaggio di avvio su Telegram mostra ✅/❌ per ogni modulo in base alle credenziali configurate
- `/dashboard` invia il link completo con token direttamente in chat — non condividerlo

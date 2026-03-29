"""
YTSPERBOT - Dispatcher multi-piattaforma
Ogni dispatcher sceglie tra il modulo Apify e quello con API nativa in base a config.X.use_apify.
Iniettabilità delle fn per facilitare i test unitari.
"""


def run_twitter_auto(config: dict, apify_fn=None, bearer_fn=None):
    """Sceglie Twitter Apify o Bearer Token in base a config.twitter.use_apify."""
    if apify_fn is None or bearer_fn is None:
        from modules.twitter_apify import run_twitter_apify_detector
        from modules.twitter_detector import run_twitter_detector
        apify_fn  = run_twitter_apify_detector
        bearer_fn = run_twitter_detector

    if config.get("twitter", {}).get("use_apify", False):
        apify_fn(config)
    else:
        bearer_fn(config)


def run_reddit_auto(config: dict, apify_fn=None, native_fn=None):
    """Sceglie Reddit Apify o PRAW nativo in base a config.reddit.use_apify."""
    if apify_fn is None or native_fn is None:
        from modules.reddit_apify import run_reddit_apify_detector
        from modules.reddit_detector import run_reddit_detector
        apify_fn  = run_reddit_apify_detector
        native_fn = run_reddit_detector

    if config.get("reddit", {}).get("use_apify", False):
        apify_fn(config)
    else:
        native_fn(config)


def run_pinterest_auto(config: dict, apify_fn=None, native_fn=None):
    """Sceglie Pinterest Apify o API nativa in base a config.pinterest.use_apify."""
    if apify_fn is None or native_fn is None:
        from modules.pinterest_apify import run_pinterest_apify_detector
        from modules.pinterest_detector import run_pinterest_detector
        apify_fn  = run_pinterest_apify_detector
        native_fn = run_pinterest_detector

    if config.get("pinterest", {}).get("use_apify", False):
        apify_fn(config)
    else:
        native_fn(config)

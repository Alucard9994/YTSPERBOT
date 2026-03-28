"""
YTSPERBOT - Twitter dispatcher
Estratto da main.py per essere importabile nei test senza le dipendenze pesanti.
"""


def run_twitter_auto(config: dict, apify_fn=None, bearer_fn=None):
    """
    Sceglie il detector Twitter corretto in base a config.twitter.use_apify.

    apify_fn e bearer_fn sono iniettabili per facilitare i test;
    in produzione vengono importati automaticamente se non forniti.
    """
    if apify_fn is None or bearer_fn is None:
        from modules.twitter_apify import run_twitter_apify_detector
        from modules.twitter_detector import run_twitter_detector
        apify_fn = run_twitter_apify_detector
        bearer_fn = run_twitter_detector

    use_apify = config.get("twitter", {}).get("use_apify", False)
    if use_apify:
        apify_fn(config)
    else:
        bearer_fn(config)

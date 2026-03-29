"""
YTSPERBOT - Utility pure functions
Funzioni pure senza side-effect, facili da testare in isolamento.
"""


def calculate_velocity(current: float, previous: float) -> float | None:
    """
    Calcola la variazione percentuale tra due misurazioni consecutive.

    Returns:
        float: variazione percentuale (es. 150.0 = +150%)
        None:  se previous == 0 (divisione per zero non definita)
    """
    if previous == 0:
        return None
    return ((current - previous) / previous) * 100

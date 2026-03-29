"""
Unit tests — calculate_velocity()
La formula è il cuore del sistema: se è sbagliata, tutti gli alert sono sbagliati.
"""

import pytest
from modules.utils import calculate_velocity


class TestCalculateVelocity:
    def test_positive_growth(self):
        """Caso normale: crescita del 50%."""
        assert calculate_velocity(150, 100) == pytest.approx(50.0)

    def test_double(self):
        """Raddoppio esatto → +100%."""
        assert calculate_velocity(200, 100) == pytest.approx(100.0)

    def test_ten_times(self):
        """10x → +900%."""
        assert calculate_velocity(1000, 100) == pytest.approx(900.0)

    def test_no_change(self):
        """Nessuna variazione → 0%."""
        assert calculate_velocity(100, 100) == pytest.approx(0.0)

    def test_decline(self):
        """Calo del 50% → -50%."""
        assert calculate_velocity(50, 100) == pytest.approx(-50.0)

    def test_zero_previous_returns_none(self):
        """Base zero → None (evita ZeroDivisionError)."""
        assert calculate_velocity(10, 0) is None

    def test_zero_both(self):
        """Entrambi zero → None."""
        assert calculate_velocity(0, 0) is None

    def test_fractional(self):
        """Valori frazionari."""
        result = calculate_velocity(1.5, 1.0)
        assert result == pytest.approx(50.0)

    def test_large_numbers(self):
        """Numeri grandi (menzioni reali tipiche)."""
        result = calculate_velocity(5000, 1000)
        assert result == pytest.approx(400.0)

    def test_result_type(self):
        """Il risultato è sempre float quando defined."""
        result = calculate_velocity(200, 100)
        assert isinstance(result, float)

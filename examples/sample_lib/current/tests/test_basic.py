import random

from samplelib.accounts import deposit, withdraw
from samplelib.perf import checksum, find_duplicates
from samplelib.rates import apply_discount, region_tax
from samplelib.stats import clamp, mean


def test_mean_basic():
    assert mean([1, 2, 3]) == 2


def test_mean_basic_again():  # PLANTED duplicate of test_mean_basic (identical coverage)
    assert mean([1, 2, 3]) == 2


def test_clamp():
    assert clamp(5, 0, 3) == 3


def test_withdraw_ok():
    assert withdraw(100, 30)["balance"] == 70


def test_deposit():
    assert deposit(10, 5)["balance"] == 15


def test_tax_and_discount():
    assert region_tax("US") == 0.07
    assert apply_discount(10.0, 50) == 5.0


def test_find_duplicates():
    assert find_duplicates([1, 2, 2, 3]) == [2]


def test_checksum_small():
    assert checksum([1, 2, 3]) == checksum([1, 2, 3])


def test_flaky_planted():
    """PLANTED flaky test: fails ~50% of the time, unseeded."""
    assert random.SystemRandom().random() < 0.5

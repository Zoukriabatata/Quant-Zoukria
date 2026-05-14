"""Tests de pa_rules : constantes PA EOD 50K + tier_for_balance."""
from gauntlet.pa_rules import (
    ACCOUNT_SIZE, EOD_DD, EOD_THRESHOLD_INITIAL, EOD_THRESHOLD_LOCK,
    tier_for_balance,
)


def test_constantes_de_base():
    assert ACCOUNT_SIZE == 50_000.0
    assert EOD_DD == 2_000.0
    assert EOD_THRESHOLD_INITIAL == 48_000.0   # 50_000 - 2_000
    assert EOD_THRESHOLD_LOCK == 50_100.0      # 50_000 + 100


def test_tier_l1_balance_de_depart():
    # balance 50_000 -> Level 1 : 2 contrats std, DLL $1_000
    level, max_ctr, dll = tier_for_balance(50_000.0)
    assert level == 1
    assert max_ctr == 2
    assert dll == 1_000.0


def test_tier_l1_floor_sous_50k():
    # sous 50_000 -> plancher L1 (le tier ne descend jamais sous L1)
    level, max_ctr, dll = tier_for_balance(48_500.0)
    assert (level, max_ctr, dll) == (1, 2, 1_000.0)


def test_tier_l2():
    # balance 51_500 (profit +1_500) -> Level 2 : 3 contrats, DLL $1_000
    assert tier_for_balance(51_500.0) == (2, 3, 1_000.0)


def test_tier_l3():
    # balance 53_000 (profit +3_000) -> Level 3 : 4 contrats, DLL $2_000
    assert tier_for_balance(53_000.0) == (3, 4, 2_000.0)


def test_tier_l4():
    # balance 56_000 (profit +6_000) -> Level 4 : 4 contrats, DLL $3_000
    assert tier_for_balance(56_000.0) == (4, 4, 3_000.0)


def test_tier_frontiere_l1_l2():
    # 51_499 -> encore L1 ; 51_500 -> L2
    assert tier_for_balance(51_499.0)[0] == 1
    assert tier_for_balance(51_500.0)[0] == 2

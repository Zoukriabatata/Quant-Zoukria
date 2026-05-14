"""Tests du simulateur de compte PA EOD."""
from gauntlet.pa_account import PaAccount


def test_etat_initial():
    acc = PaAccount()
    assert acc.balance == 50_000.0
    assert acc.eod_threshold == 48_000.0       # 50_000 - 2_000
    assert acc.status == "alive"
    assert acc.tier == 1
    assert acc.max_contracts_std == 2
    assert acc.dll == 1_000.0
    assert acc.threshold_locked is False


def test_record_trade_met_a_jour_la_balance():
    acc = PaAccount()
    acc.record_trade(150.0)
    acc.record_trade(-50.0)
    assert acc.balance == 50_100.0


def test_end_session_fait_monter_le_seuil_sur_nouveau_plus_haut():
    acc = PaAccount()
    acc.record_trade(1_000.0)                  # balance 51_000
    acc.end_session("2026-01-02")
    # seuil = min(51_000 - 2_000, 50_100) = 49_000
    assert acc.eod_threshold == 49_000.0
    assert acc.highest_eod_close == 51_000.0


def test_end_session_seuil_ne_descend_jamais():
    acc = PaAccount()
    acc.record_trade(1_000.0); acc.end_session("2026-01-02")   # seuil 49_000
    acc.record_trade(-500.0); acc.end_session("2026-01-03")    # balance 50_500, clôture plus basse
    # le seuil reste à 49_000 (ne descend pas)
    assert acc.eod_threshold == 49_000.0
    assert acc.highest_eod_close == 51_000.0


def test_seuil_se_fige_a_50100():
    acc = PaAccount()
    acc.record_trade(2_100.0)                  # balance 52_100
    acc.end_session("2026-01-02")
    # min(52_100 - 2_000, 50_100) = 50_100 -> figé
    assert acc.eod_threshold == 50_100.0
    assert acc.threshold_locked is True
    # même après un gros gain, le seuil reste figé
    acc.record_trade(5_000.0); acc.end_session("2026-01-03")
    assert acc.eod_threshold == 50_100.0


def test_check_intraday_mort_si_equity_touche_le_seuil():
    acc = PaAccount()
    # seuil initial 48_000. equity (balance + PnL non réalisé) tombe à 48_000.
    res = acc.check_intraday(48_000.0)
    assert res == "dead"
    assert acc.status == "dead_eod"


def test_check_intraday_ok_si_equity_au_dessus():
    acc = PaAccount()
    assert acc.check_intraday(49_500.0) == "ok"
    assert acc.status == "alive"


def test_check_intraday_dll_pause_la_journee():
    acc = PaAccount()                          # DLL L1 = 1_000
    acc.start_session("2026-01-02")            # session_start_balance = 50_000
    # perte intraday de 1_000 -> equity 49_000 -> DLL touchée
    res = acc.check_intraday(49_000.0)
    assert res == "day_paused"
    assert acc.day_paused is True
    assert acc.status == "alive"               # le compte SURVIT
    assert acc.can_trade() is False


def test_dll_se_reset_a_la_session_suivante():
    acc = PaAccount()
    acc.start_session("2026-01-02")
    acc.check_intraday(49_000.0)               # DLL touchée
    assert acc.can_trade() is False
    acc.end_session("2026-01-02")
    acc.start_session("2026-01-03")            # nouvelle session
    assert acc.day_paused is False
    assert acc.can_trade() is True


def test_tier_monte_apres_une_bonne_cloture():
    acc = PaAccount()
    acc.record_trade(1_600.0)                  # balance 51_600 -> L2 au prochain tier-update
    acc.end_session("2026-01-02")
    assert acc.tier == 2
    assert acc.max_contracts_std == 3
    assert acc.dll == 1_000.0


def test_daily_history_enregistre_les_clotures():
    acc = PaAccount()
    acc.record_trade(300.0); acc.end_session("2026-01-02")
    acc.record_trade(-100.0); acc.end_session("2026-01-03")
    assert len(acc.daily_history) == 2
    assert acc.daily_history[0] == ("2026-01-02", 50_300.0, 1)
    assert acc.daily_history[1] == ("2026-01-03", 50_200.0, 1)

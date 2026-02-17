"""Unit tests for team Elo calculations."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from elo.team_elo import (
    EloParameters,
    TeamEloCalculator,
    TeamMapResult,
    calculate_expected_score,
)


def test_elo_parameters_defaults_are_expected_constants() -> None:
    params = EloParameters()
    assert params.initial_elo == pytest.approx(1500.0)
    assert params.k_factor == pytest.approx(20.0)
    assert params.scale_factor == pytest.approx(400.0)
    assert params.even_multiplier == pytest.approx(1.0)
    assert params.favored_multiplier == pytest.approx(1.0)
    assert params.unfavored_multiplier == pytest.approx(1.0)
    assert params.opponent_strength_weight == pytest.approx(1.0)
    assert params.lan_multiplier == pytest.approx(1.0)
    assert params.round_domination_multiplier == pytest.approx(1.0)
    assert params.kd_ratio_domination_multiplier == pytest.approx(1.0)
    assert params.recency_min_multiplier == pytest.approx(1.0)
    assert params.inactivity_half_life_days == pytest.approx(0.0)
    assert params.bo1_match_multiplier == pytest.approx(1.0)
    assert params.bo3_match_multiplier == pytest.approx(1.0)
    assert params.bo5_match_multiplier == pytest.approx(1.0)


def test_expected_score_equal_ratings_is_half() -> None:
    expected = calculate_expected_score(1500.0, 1500.0, 400.0)
    assert expected == pytest.approx(0.5)


def test_expected_scores_sum_to_one() -> None:
    expected_a = calculate_expected_score(1600.0, 1500.0, 400.0)
    expected_b = calculate_expected_score(1500.0, 1600.0, 400.0)
    assert expected_a + expected_b == pytest.approx(1.0)


def test_map_update_is_zero_sum() -> None:
    calculator = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    team1_event, team2_event = calculator.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
        )
    )
    assert team1_event.elo_delta + team2_event.elo_delta == pytest.approx(0.0)
    assert team1_event.post_elo + team2_event.post_elo == pytest.approx(3000.0)


def test_even_match_win_uses_default_multiplier() -> None:
    calculator = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    team1_event, _ = calculator.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )
    assert team1_event.elo_delta == pytest.approx(10.0)


def test_even_multiplier_increases_even_match_gain() -> None:
    baseline = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    boosted = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, even_multiplier=1.25)
    )

    baseline_event, _ = baseline.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )
    boosted_event, _ = boosted.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )

    assert boosted_event.elo_delta > baseline_event.elo_delta


def test_initial_elo_changes_starting_pre_elo() -> None:
    baseline = TeamEloCalculator(EloParameters())
    shifted = TeamEloCalculator(EloParameters(initial_elo=1700.0))

    baseline_event, _ = baseline.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )
    shifted_event, _ = shifted.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )

    assert baseline_event.pre_elo == pytest.approx(1500.0)
    assert shifted_event.pre_elo == pytest.approx(1700.0)
    assert shifted_event.elo_delta == pytest.approx(baseline_event.elo_delta)


def test_k_factor_increases_delta_magnitude() -> None:
    baseline = TeamEloCalculator(EloParameters())
    boosted = TeamEloCalculator(EloParameters(k_factor=32.0))

    baseline_event, _ = baseline.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )
    boosted_event, _ = boosted.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )

    assert boosted_event.elo_delta > baseline_event.elo_delta


def test_scale_factor_changes_expected_score_and_delta() -> None:
    baseline = TeamEloCalculator(EloParameters(scale_factor=400.0))
    widened = TeamEloCalculator(EloParameters(scale_factor=800.0))

    baseline._ratings[100] = 1400.0
    baseline._ratings[200] = 1600.0
    widened._ratings[100] = 1400.0
    widened._ratings[200] = 1600.0

    baseline_event, _ = baseline.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )
    widened_event, _ = widened.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )

    assert baseline_event.expected_score < widened_event.expected_score
    assert baseline_event.elo_delta > widened_event.elo_delta


def test_underdog_win_gains_more_than_even_match_win() -> None:
    calculator = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    calculator._ratings[100] = 1400.0
    calculator._ratings[200] = 1600.0

    team1_event, _ = calculator.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )
    assert team1_event.elo_delta > 10.0


def test_unfavored_multiplier_increases_underdog_gain() -> None:
    baseline = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    boosted = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, unfavored_multiplier=1.5)
    )
    baseline._ratings[100] = 1400.0
    baseline._ratings[200] = 1600.0
    boosted._ratings[100] = 1400.0
    boosted._ratings[200] = 1600.0

    baseline_event, _ = baseline.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )
    boosted_event, _ = boosted.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )

    assert boosted_event.elo_delta > baseline_event.elo_delta


def test_favored_multiplier_increases_favorite_gain() -> None:
    baseline = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    boosted = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, favored_multiplier=1.5)
    )
    baseline._ratings[100] = 1600.0
    baseline._ratings[200] = 1400.0
    boosted._ratings[100] = 1600.0
    boosted._ratings[200] = 1400.0

    baseline_event, _ = baseline.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )
    boosted_event, _ = boosted.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )

    assert boosted_event.elo_delta > baseline_event.elo_delta


def test_opponent_strength_weight_scales_win_gain_by_opponent_strength() -> None:
    underdog_baseline = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    underdog_weighted = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, opponent_strength_weight=1.5)
    )
    underdog_baseline._ratings[100] = 1400.0
    underdog_baseline._ratings[200] = 1600.0
    underdog_weighted._ratings[100] = 1400.0
    underdog_weighted._ratings[200] = 1600.0

    underdog_baseline_event, _ = underdog_baseline.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )
    underdog_weighted_event, _ = underdog_weighted.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )

    favorite_baseline = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    favorite_weighted = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, opponent_strength_weight=1.5)
    )
    favorite_baseline._ratings[100] = 1600.0
    favorite_baseline._ratings[200] = 1400.0
    favorite_weighted._ratings[100] = 1600.0
    favorite_weighted._ratings[200] = 1400.0

    favorite_baseline_event, _ = favorite_baseline.process_map(
        TeamMapResult(
            match_id=2,
            map_id=2,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )
    favorite_weighted_event, _ = favorite_weighted.process_map(
        TeamMapResult(
            match_id=2,
            map_id=2,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )

    assert underdog_weighted_event.elo_delta > underdog_baseline_event.elo_delta
    assert favorite_weighted_event.elo_delta < favorite_baseline_event.elo_delta


def test_lan_multiplier_increases_lan_gain() -> None:
    baseline = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    boosted = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, lan_multiplier=1.3)
    )

    baseline_event, _ = baseline.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            is_lan=True,
            match_format="BO1",
        )
    )
    boosted_event, _ = boosted.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            is_lan=True,
            match_format="BO1",
        )
    )

    assert boosted_event.elo_delta > baseline_event.elo_delta


def test_lan_multiplier_does_not_change_online_gain() -> None:
    baseline = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    boosted = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, lan_multiplier=1.3)
    )

    baseline_event, _ = baseline.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            is_lan=False,
            match_format="BO1",
        )
    )
    boosted_event, _ = boosted.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            is_lan=False,
            match_format="BO1",
        )
    )

    assert boosted_event.elo_delta == pytest.approx(baseline_event.elo_delta)


def test_round_domination_multiplier_rewards_blowouts_more_than_close_wins() -> None:
    calculator = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, round_domination_multiplier=1.2)
    )

    blowout_event, _ = calculator.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            team1_score=13,
            team2_score=0,
            match_format="BO1",
        )
    )

    calculator = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, round_domination_multiplier=1.2)
    )
    close_event, _ = calculator.process_map(
        TeamMapResult(
            match_id=2,
            map_id=2,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            team1_score=13,
            team2_score=11,
            match_format="BO1",
        )
    )

    assert blowout_event.elo_delta > close_event.elo_delta


def test_round_domination_multiplier_has_no_effect_when_score_is_missing() -> None:
    baseline = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    boosted = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, round_domination_multiplier=1.2)
    )

    baseline_event, _ = baseline.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )
    boosted_event, _ = boosted.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )

    assert boosted_event.elo_delta == pytest.approx(baseline_event.elo_delta)


def test_kd_ratio_domination_multiplier_rewards_larger_kd_gap() -> None:
    calculator = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, kd_ratio_domination_multiplier=1.2)
    )

    large_gap_event, _ = calculator.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            team1_kd_ratio=2.0,
            team2_kd_ratio=0.7,
            match_format="BO1",
        )
    )

    calculator = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, kd_ratio_domination_multiplier=1.2)
    )
    small_gap_event, _ = calculator.process_map(
        TeamMapResult(
            match_id=2,
            map_id=2,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            team1_kd_ratio=1.1,
            team2_kd_ratio=1.0,
            match_format="BO1",
        )
    )

    assert large_gap_event.elo_delta > small_gap_event.elo_delta


def test_kd_ratio_domination_multiplier_has_no_effect_when_kd_missing() -> None:
    baseline = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    boosted = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, kd_ratio_domination_multiplier=1.2)
    )

    baseline_event, _ = baseline.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )
    boosted_event, _ = boosted.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )

    assert boosted_event.elo_delta == pytest.approx(baseline_event.elo_delta)


def test_recency_min_multiplier_decays_old_maps_linearly() -> None:
    as_of_time = datetime(2026, 1, 2, 0, 0, 0)
    params = EloParameters(initial_elo=1500.0, k_factor=20.0, recency_min_multiplier=0.0)

    today_calc = TeamEloCalculator(params, lookback_days=365, as_of_time=as_of_time)
    old_calc = TeamEloCalculator(params, lookback_days=365, as_of_time=as_of_time)

    today_event, _ = today_calc.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=as_of_time,
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )
    oldest_event, _ = old_calc.process_map(
        TeamMapResult(
            match_id=2,
            map_id=2,
            map_number=1,
            event_time=as_of_time - timedelta(days=365),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )

    assert today_event.elo_delta > oldest_event.elo_delta
    assert oldest_event.elo_delta == pytest.approx(0.0)


def test_recency_min_multiplier_default_keeps_old_maps_weighted() -> None:
    as_of_time = datetime(2026, 1, 2, 0, 0, 0)
    params = EloParameters(initial_elo=1500.0, k_factor=20.0)

    today_calc = TeamEloCalculator(params, lookback_days=365, as_of_time=as_of_time)
    old_calc = TeamEloCalculator(params, lookback_days=365, as_of_time=as_of_time)

    today_event, _ = today_calc.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=as_of_time,
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )
    oldest_event, _ = old_calc.process_map(
        TeamMapResult(
            match_id=2,
            map_id=2,
            map_number=1,
            event_time=as_of_time - timedelta(days=365),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )

    assert oldest_event.elo_delta == pytest.approx(today_event.elo_delta)


def test_inactivity_half_life_days_decays_ratings_toward_initial_between_maps() -> None:
    base_time = datetime(2026, 1, 1, 12, 0, 0)

    baseline = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    decayed = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, inactivity_half_life_days=30.0)
    )

    first_map = TeamMapResult(
        match_id=1,
        map_id=1,
        map_number=1,
        event_time=base_time,
        team1_id=100,
        team2_id=200,
        winner_id=100,
        match_format="BO1",
    )
    baseline.process_map(first_map)
    decayed.process_map(first_map)

    second_map = TeamMapResult(
        match_id=2,
        map_id=2,
        map_number=1,
        event_time=base_time + timedelta(days=60),
        team1_id=100,
        team2_id=200,
        winner_id=100,
        match_format="BO1",
    )

    baseline_event, _ = baseline.process_map(second_map)
    decayed_event, _ = decayed.process_map(second_map)

    assert decayed_event.pre_elo < baseline_event.pre_elo
    assert decayed_event.elo_delta > baseline_event.elo_delta


def test_inactivity_half_life_days_zero_disables_inactivity_decay() -> None:
    base_time = datetime(2026, 1, 1, 12, 0, 0)

    baseline = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    disabled = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, inactivity_half_life_days=0.0)
    )

    first_map = TeamMapResult(
        match_id=1,
        map_id=1,
        map_number=1,
        event_time=base_time,
        team1_id=100,
        team2_id=200,
        winner_id=100,
        match_format="BO1",
    )
    baseline.process_map(first_map)
    disabled.process_map(first_map)

    second_map = TeamMapResult(
        match_id=2,
        map_id=2,
        map_number=1,
        event_time=base_time + timedelta(days=120),
        team1_id=100,
        team2_id=200,
        winner_id=100,
        match_format="BO1",
    )

    baseline_event, _ = baseline.process_map(second_map)
    disabled_event, _ = disabled.process_map(second_map)

    assert disabled_event.pre_elo == pytest.approx(baseline_event.pre_elo)
    assert disabled_event.elo_delta == pytest.approx(baseline_event.elo_delta)


def test_bo1_bo3_and_bo5_default_multipliers_are_neutral() -> None:
    params = EloParameters(initial_elo=1500.0, k_factor=20.0)

    calc_bo1 = TeamEloCalculator(params)
    bo1_event, _ = calc_bo1.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )

    calc_bo3 = TeamEloCalculator(params)
    bo3_event, _ = calc_bo3.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO3",
        )
    )

    calc_bo5 = TeamEloCalculator(params)
    bo5_event, _ = calc_bo5.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO5",
        )
    )

    assert bo3_event.elo_delta == pytest.approx(bo1_event.elo_delta)
    assert bo5_event.elo_delta == pytest.approx(bo1_event.elo_delta)


def test_bo1_multiplier_increases_bo1_gain() -> None:
    baseline = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    boosted = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, bo1_match_multiplier=1.3)
    )

    baseline_event, _ = baseline.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )
    boosted_event, _ = boosted.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO1",
        )
    )

    assert boosted_event.elo_delta > baseline_event.elo_delta


def test_bo3_multiplier_increases_bo3_gain() -> None:
    baseline = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    boosted = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, bo3_match_multiplier=1.25)
    )

    baseline_event, _ = baseline.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO3",
        )
    )
    boosted_event, _ = boosted.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO3",
        )
    )

    assert boosted_event.elo_delta > baseline_event.elo_delta


def test_bo5_multiplier_increases_bo5_gain() -> None:
    baseline = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    boosted = TeamEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, bo5_match_multiplier=1.4)
    )

    baseline_event, _ = baseline.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO5",
        )
    )
    boosted_event, _ = boosted.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            match_format="BO5",
        )
    )

    assert boosted_event.elo_delta > baseline_event.elo_delta

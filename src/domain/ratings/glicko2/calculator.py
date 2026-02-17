"""Team-level Glicko-2 logic."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from math import exp, log, pi, sqrt
from typing import Final

from domain.ratings.common import TeamMapResult

GLICKO2_SCALE: Final[float] = 173.7178
DEFAULT_RATING: Final[float] = 1500.0


@dataclass(frozen=True)
class Glicko2Parameters:
    initial_rating: float = 1500.0
    initial_rd: float = 350.0
    initial_volatility: float = 0.06
    tau: float = 0.5
    rating_period_days: float = 1.0
    min_rd: float = 30.0
    max_rd: float = 350.0
    epsilon: float = 1e-6


@dataclass(frozen=True)
class Glicko2OpponentResult:
    opponent_rating: float
    opponent_rd: float
    score: float


@dataclass(frozen=True)
class TeamGlicko2Event:
    team_id: int
    opponent_team_id: int
    match_id: int
    map_id: int
    map_number: int
    event_time: datetime
    won: bool
    actual_score: float
    expected_score: float
    pre_rating: float
    pre_rd: float
    pre_volatility: float
    rating_delta: float
    rd_delta: float
    volatility_delta: float
    post_rating: float
    post_rd: float
    post_volatility: float
    tau: float
    rating_period_days: float
    initial_rating: float
    initial_rd: float
    initial_volatility: float


@dataclass
class _TeamGlicko2State:
    rating: float
    rd: float
    volatility: float


def _to_mu(rating: float) -> float:
    return (rating - DEFAULT_RATING) / GLICKO2_SCALE


def _to_phi(rd: float) -> float:
    return rd / GLICKO2_SCALE


def _from_mu(mu: float) -> float:
    return (mu * GLICKO2_SCALE) + DEFAULT_RATING


def _from_phi(phi: float) -> float:
    return phi * GLICKO2_SCALE


def _g(phi: float) -> float:
    return 1.0 / sqrt(1.0 + ((3.0 * (phi**2)) / (pi**2)))


def _expected(mu: float, opp_mu: float, opp_phi: float) -> float:
    exponent = -_g(opp_phi) * (mu - opp_mu)
    if exponent >= 0.0:
        exp_term = exp(-exponent)
        return exp_term / (1.0 + exp_term)
    exp_term = exp(exponent)
    return 1.0 / (1.0 + exp_term)


def calculate_expected_score(
    *,
    rating: float,
    rd: float,
    opponent_rating: float,
    opponent_rd: float,
) -> float:
    """Compute expected score for one side under Glicko-2."""
    return _expected(
        _to_mu(rating),
        _to_mu(opponent_rating),
        _to_phi(opponent_rd),
    )


def _solve_volatility(
    *,
    phi: float,
    sigma: float,
    delta: float,
    v: float,
    tau: float,
    epsilon: float,
) -> float:
    a = log(sigma**2)

    def f(x: float) -> float:
        ex = exp(x)
        numerator = ex * ((delta**2) - (phi**2) - v - ex)
        denominator = 2.0 * ((phi**2) + v + ex) ** 2
        return (numerator / denominator) - ((x - a) / (tau**2))

    a_value = a
    if (delta**2) > ((phi**2) + v):
        b_value = log((delta**2) - (phi**2) - v)
    else:
        k = 1
        b_value = a_value - (k * tau)
        while f(b_value) < 0.0:
            k += 1
            if k > 1_000:
                raise RuntimeError("Glicko-2 volatility solve failed to bracket root.")
            b_value = a_value - (k * tau)

    f_a = f(a_value)
    f_b = f(b_value)
    while abs(b_value - a_value) > epsilon:
        if f_b == f_a:
            c_value = (a_value + b_value) / 2.0
        else:
            c_value = a_value + (((a_value - b_value) * f_a) / (f_b - f_a))
        f_c = f(c_value)
        if f_c * f_b < 0.0:
            a_value = b_value
            f_a = f_b
        else:
            f_a /= 2.0
        b_value = c_value
        f_b = f_c

    return exp(a_value / 2.0)


def update_glicko2_player(
    *,
    rating: float,
    rd: float,
    volatility: float,
    results: Sequence[Glicko2OpponentResult],
    tau: float = 0.5,
    epsilon: float = 1e-6,
) -> tuple[float, float, float]:
    """Update one player/team for one Glicko-2 rating period."""
    if not results:
        return rating, rd, volatility

    mu = _to_mu(rating)
    phi = _to_phi(rd)

    g_terms: list[float] = []
    e_terms: list[float] = []
    score_minus_e_terms: list[float] = []
    for result in results:
        opp_mu = _to_mu(result.opponent_rating)
        opp_phi = _to_phi(result.opponent_rd)
        g_term = _g(opp_phi)
        expected = _expected(mu, opp_mu, opp_phi)
        g_terms.append(g_term)
        e_terms.append(expected)
        score_minus_e_terms.append(result.score - expected)

    v_inverse = 0.0
    for g_term, expected in zip(g_terms, e_terms):
        v_inverse += (g_term**2) * expected * (1.0 - expected)
    if v_inverse <= 0.0:
        return rating, rd, volatility

    v = 1.0 / v_inverse
    delta = v * sum(g_term * score_minus_e for g_term, score_minus_e in zip(g_terms, score_minus_e_terms))
    sigma_prime = _solve_volatility(
        phi=phi,
        sigma=volatility,
        delta=delta,
        v=v,
        tau=tau,
        epsilon=epsilon,
    )

    phi_star = sqrt((phi**2) + (sigma_prime**2))
    phi_prime = 1.0 / sqrt((1.0 / (phi_star**2)) + (1.0 / v))
    mu_prime = mu + (phi_prime**2) * sum(
        g_term * score_minus_e for g_term, score_minus_e in zip(g_terms, score_minus_e_terms)
    )

    return _from_mu(mu_prime), _from_phi(phi_prime), sigma_prime


class TeamGlicko2Calculator:
    """Stateful map-by-map team Glicko-2 calculator."""

    def __init__(self, params: Glicko2Parameters) -> None:
        self.params = params
        self._states: dict[int, _TeamGlicko2State] = {}
        self._last_event_times: dict[int, datetime] = {}

    def _clamp_rd(self, rd: float) -> float:
        return max(self.params.min_rd, min(rd, self.params.max_rd))

    def _get_or_create_state(self, team_id: int) -> _TeamGlicko2State:
        existing = self._states.get(team_id)
        if existing is not None:
            return existing
        state = _TeamGlicko2State(
            rating=self.params.initial_rating,
            rd=self._clamp_rd(self.params.initial_rd),
            volatility=self.params.initial_volatility,
        )
        self._states[team_id] = state
        return state

    def get_rating(self, team_id: int) -> float:
        return self._get_or_create_state(team_id).rating

    def get_rd(self, team_id: int) -> float:
        return self._get_or_create_state(team_id).rd

    def get_volatility(self, team_id: int) -> float:
        return self._get_or_create_state(team_id).volatility

    def tracked_team_count(self) -> int:
        return len(self._states)

    def tracked_entity_count(self) -> int:
        """Subject-agnostic alias for protocol compatibility."""
        return self.tracked_team_count()

    def ratings(self) -> dict[int, float]:
        """Return a snapshot of current team ratings."""
        return {team_id: state.rating for team_id, state in self._states.items()}

    def _inflate_rd_for_inactivity(
        self,
        *,
        team_id: int,
        rd: float,
        volatility: float,
        event_time: datetime,
    ) -> float:
        last_event_time = self._last_event_times.get(team_id)
        if last_event_time is None:
            return self._clamp_rd(rd)

        inactive_days = (event_time - last_event_time).total_seconds() / 86_400.0
        if inactive_days <= 0.0:
            return self._clamp_rd(rd)

        inactive_periods = inactive_days / self.params.rating_period_days
        if inactive_periods <= 0.0:
            return self._clamp_rd(rd)

        phi = _to_phi(rd)
        inflated_phi = sqrt((phi**2) + ((volatility**2) * inactive_periods))
        return self._clamp_rd(_from_phi(inflated_phi))

    def process_map(self, map_result: TeamMapResult) -> tuple[TeamGlicko2Event, TeamGlicko2Event]:
        if map_result.team1_id == map_result.team2_id:
            raise ValueError(
                f"map_id={map_result.map_id} has identical teams ({map_result.team1_id})"
            )
        if map_result.winner_id not in (map_result.team1_id, map_result.team2_id):
            raise ValueError(
                f"winner_id={map_result.winner_id} does not belong to map teams "
                f"{map_result.team1_id}/{map_result.team2_id} for map_id={map_result.map_id}"
            )

        team1_state = self._get_or_create_state(map_result.team1_id)
        team2_state = self._get_or_create_state(map_result.team2_id)

        team1_pre_rating = team1_state.rating
        team2_pre_rating = team2_state.rating
        team1_pre_vol = team1_state.volatility
        team2_pre_vol = team2_state.volatility
        team1_pre_rd = self._inflate_rd_for_inactivity(
            team_id=map_result.team1_id,
            rd=team1_state.rd,
            volatility=team1_state.volatility,
            event_time=map_result.event_time,
        )
        team2_pre_rd = self._inflate_rd_for_inactivity(
            team_id=map_result.team2_id,
            rd=team2_state.rd,
            volatility=team2_state.volatility,
            event_time=map_result.event_time,
        )

        team1_actual = 1.0 if map_result.winner_id == map_result.team1_id else 0.0
        team2_actual = 1.0 - team1_actual

        team1_expected = calculate_expected_score(
            rating=team1_pre_rating,
            rd=team1_pre_rd,
            opponent_rating=team2_pre_rating,
            opponent_rd=team2_pre_rd,
        )
        team2_expected = calculate_expected_score(
            rating=team2_pre_rating,
            rd=team2_pre_rd,
            opponent_rating=team1_pre_rating,
            opponent_rd=team1_pre_rd,
        )

        team1_post_rating, team1_post_rd, team1_post_vol = update_glicko2_player(
            rating=team1_pre_rating,
            rd=team1_pre_rd,
            volatility=team1_pre_vol,
            results=[
                Glicko2OpponentResult(
                    opponent_rating=team2_pre_rating,
                    opponent_rd=team2_pre_rd,
                    score=team1_actual,
                )
            ],
            tau=self.params.tau,
            epsilon=self.params.epsilon,
        )
        team2_post_rating, team2_post_rd, team2_post_vol = update_glicko2_player(
            rating=team2_pre_rating,
            rd=team2_pre_rd,
            volatility=team2_pre_vol,
            results=[
                Glicko2OpponentResult(
                    opponent_rating=team1_pre_rating,
                    opponent_rd=team1_pre_rd,
                    score=team2_actual,
                )
            ],
            tau=self.params.tau,
            epsilon=self.params.epsilon,
        )

        team1_post_rd = self._clamp_rd(team1_post_rd)
        team2_post_rd = self._clamp_rd(team2_post_rd)

        self._states[map_result.team1_id] = _TeamGlicko2State(
            rating=team1_post_rating,
            rd=team1_post_rd,
            volatility=team1_post_vol,
        )
        self._states[map_result.team2_id] = _TeamGlicko2State(
            rating=team2_post_rating,
            rd=team2_post_rd,
            volatility=team2_post_vol,
        )
        self._last_event_times[map_result.team1_id] = map_result.event_time
        self._last_event_times[map_result.team2_id] = map_result.event_time

        team1_event = TeamGlicko2Event(
            team_id=map_result.team1_id,
            opponent_team_id=map_result.team2_id,
            match_id=map_result.match_id,
            map_id=map_result.map_id,
            map_number=map_result.map_number,
            event_time=map_result.event_time,
            won=bool(team1_actual),
            actual_score=team1_actual,
            expected_score=team1_expected,
            pre_rating=team1_pre_rating,
            pre_rd=team1_pre_rd,
            pre_volatility=team1_pre_vol,
            rating_delta=team1_post_rating - team1_pre_rating,
            rd_delta=team1_post_rd - team1_pre_rd,
            volatility_delta=team1_post_vol - team1_pre_vol,
            post_rating=team1_post_rating,
            post_rd=team1_post_rd,
            post_volatility=team1_post_vol,
            tau=self.params.tau,
            rating_period_days=self.params.rating_period_days,
            initial_rating=self.params.initial_rating,
            initial_rd=self.params.initial_rd,
            initial_volatility=self.params.initial_volatility,
        )
        team2_event = TeamGlicko2Event(
            team_id=map_result.team2_id,
            opponent_team_id=map_result.team1_id,
            match_id=map_result.match_id,
            map_id=map_result.map_id,
            map_number=map_result.map_number,
            event_time=map_result.event_time,
            won=bool(team2_actual),
            actual_score=team2_actual,
            expected_score=team2_expected,
            pre_rating=team2_pre_rating,
            pre_rd=team2_pre_rd,
            pre_volatility=team2_pre_vol,
            rating_delta=team2_post_rating - team2_pre_rating,
            rd_delta=team2_post_rd - team2_pre_rd,
            volatility_delta=team2_post_vol - team2_pre_vol,
            post_rating=team2_post_rating,
            post_rd=team2_post_rd,
            post_volatility=team2_post_vol,
            tau=self.params.tau,
            rating_period_days=self.params.rating_period_days,
            initial_rating=self.params.initial_rating,
            initial_rd=self.params.initial_rd,
            initial_volatility=self.params.initial_volatility,
        )
        return team1_event, team2_event

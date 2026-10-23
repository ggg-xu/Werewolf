"""Dead players must not receive daytime speak/vote turns or later night actions."""

from backend.base import Role
from backend.game_state import GameState


def new_game() -> GameState:
    game = GameState()
    game.initialize_players()
    return game


def consumed_targets(game: GameState, etype: str) -> list[int]:
    """Return allow-* targets in the order the event stack will process them.

    Day and night queues are built with ``reversed(order)`` and popped from
    the end, so reversing the stored matches restores that order.
    """
    stored = [event.target for event in game.events if event.etype == etype]
    return list(reversed(stored))


def test_players_killed_at_night_are_absent_from_day_speak_and_vote():
    game = new_game()
    game.speak_order = [1, 2, 3, 4, 5, 6]
    game.just_killed = [2, 6]

    game.kill_player()
    game.when_day_event()

    assert game.alive_players == [1, 3, 4, 5]
    assert game.speak_order == [1, 3, 4, 5]
    assert 2 not in game.act_order
    assert 6 not in game.act_order
    assert consumed_targets(game, "ALLOW_SPEAK") == [1, 3, 4, 5]
    assert consumed_targets(game, "ALLOW_VOTE") == [1, 3, 4, 5]


def test_night_kill_preserves_relative_speak_order():
    game = new_game()
    game.speak_order = [6, 5, 4, 3, 2, 1]
    game.act_order = [4, 6, 1, 2]
    game.just_killed = [5, 2]

    game.kill_player()
    game.when_day_event()

    assert game.speak_order == [6, 4, 3, 1]
    assert game.act_order == [4, 6, 1]
    assert consumed_targets(game, "ALLOW_SPEAK") == [6, 4, 3, 1]
    assert consumed_targets(game, "ALLOW_VOTE") == [6, 4, 3, 1]


def test_peaceful_night_keeps_the_full_day_roster():
    game = new_game()
    speak_order = list(game.speak_order)
    act_order = list(game.act_order)
    game.just_killed = []

    game.kill_player()
    game.when_day_event()

    assert game.speak_order == speak_order
    assert game.act_order == act_order
    assert consumed_targets(game, "ALLOW_SPEAK") == speak_order
    assert consumed_targets(game, "ALLOW_VOTE") == speak_order


def test_rescued_player_speaks_and_poisoned_player_does_not():
    game = new_game()
    wolf = next(player for player in game.players if player.role == Role.WEREWOLF)
    witch = next(player for player in game.players if player.role == Role.WITCH)
    villagers = [player.id for player in game.players if player.role == Role.VILLAGER]
    saved, poisoned = villagers[0], villagers[1]

    game.add_just_killed(saved, wolf.id)
    game.resurrection(saved, witch.id)
    game.add_just_killed(poisoned, witch.id)
    game.kill_player()
    game.when_day_event()

    speak = consumed_targets(game, "ALLOW_SPEAK")
    assert saved in speak
    assert poisoned not in speak
    assert speak == [pid for pid in range(1, 7) if pid != poisoned]
    assert consumed_targets(game, "ALLOW_VOTE") == speak
    assert saved in game.alive_players
    assert poisoned not in game.alive_players


def test_when_day_event_drops_dead_players_left_in_a_stale_speak_order():
    game = new_game()
    game.players[2].alive = False

    game.when_day_event()

    assert 3 not in game.alive_players
    assert 3 not in game.speak_order
    assert 3 not in consumed_targets(game, "ALLOW_SPEAK")
    assert 3 not in consumed_targets(game, "ALLOW_VOTE")


def test_exiled_villager_cannot_speak_or_vote_on_later_days():
    game = new_game()
    villager = next(player.id for player in game.players if player.role == Role.VILLAGER)
    act_order = list(game.act_order)
    game.votes = [0] * 6
    game.votes[villager - 1] = 1

    game.set_out()
    assert game.out == villager
    assert villager not in game.alive_players
    assert villager not in game.speak_order
    assert game.act_order == act_order

    game.next_day()
    game.kill_player()
    game.when_day_event()

    expected = [pid for pid in range(1, 7) if pid != villager]
    assert consumed_targets(game, "ALLOW_SPEAK") == expected
    assert consumed_targets(game, "ALLOW_VOTE") == expected


def test_exiled_night_actor_cannot_act_speak_or_vote_afterwards():
    game = new_game()
    exile_id = game.act_order[0]
    game.speak_order = [6, 5, 4, 3, 2, 1]
    game.votes = [0] * 6
    game.votes[exile_id - 1] = 2

    game.set_out()

    assert game.out == exile_id
    assert exile_id not in game.alive_players
    assert exile_id not in game.act_order
    assert game.speak_order == [pid for pid in [6, 5, 4, 3, 2, 1] if pid != exile_id]

    game.when_count_vote_event()
    assert all(event.etype not in {"ALLOW_SPEAK", "ALLOW_VOTE", "ALLOW_ACT"} for event in game.events)

    game.next_day()
    assert exile_id not in consumed_targets(game, "ALLOW_ACT")
    assert consumed_targets(game, "ALLOW_ACT") == game.act_order

    victim = next(pid for pid in game.alive_players)
    game.just_killed = [victim]
    game.kill_player()
    game.when_day_event()

    expected = [pid for pid in range(1, 7) if pid not in {exile_id, victim}]
    assert consumed_targets(game, "ALLOW_SPEAK") == expected
    assert consumed_targets(game, "ALLOW_VOTE") == expected

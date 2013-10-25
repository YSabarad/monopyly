from monopyly import Game
from monopyly import ElectedChairman
from testing_utils import DefaultPlayerAI


def test_elected_chairman():
    '''
    Tests the "You have been elected chairman or the board"
    Chance card.

    This includes testing that money can be taken from a player
    and given to other players.
    '''
    # We set up a game with 4 players...
    game = Game()
    game.add_player(DefaultPlayerAI())
    game.add_player(DefaultPlayerAI())
    game.add_player(DefaultPlayerAI())
    game.add_player(DefaultPlayerAI())

    player1 = game.state.players[0]
    player2 = game.state.players[1]
    player3 = game.state.players[2]
    player4 = game.state.players[3]

    # Player 2 picks up the 'elected chairman' card...
    card = ElectedChairman()
    card.play(game, player2)

    # We check that player2 has paid £50 to each of the
    # other players...
    assert player1.state.cash == 1550
    assert player2.state.cash == 1350
    assert player3.state.cash == 1550
    assert player4.state.cash == 1550

from .dice import Dice
from .player import Player
from .game_state import GameState
from .player_ai_base import PlayerAIBase
from .board import Board
from ..squares import Square
from ..squares import Property
from ..squares import Street


class Game(object):
    '''
    Manages one game of monopoly.

    Holds all the game state: the board, the cards and the players.
    It rolls the dice and moves the players. It calls into the player
    AIs when events occur and when there are decisions to be made.

    It keeps track of players' solvency and decides when a player is
    bankrupt and when the game is over.

    There is a turn limit (as otherwise the game could continue forever).
    When the limit is reached, all assets are liquidated (houses sold,
    properties mortgaged) and the winner is the player with the most money.
    '''

    class Action(object):
        '''
        An 'enum' for actions that can happen during the game.
        '''
        ROLL_AGAIN = 1
        DO_NOT_ROLL_AGAIN = 2
        PROPERTY_BOUGHT = 3
        PROPERTY_NOT_BOUGHT = 4

    def __init__(self):
        '''
        The 'constructor'.
        '''
        self.state = GameState()
        self.dice = Dice()
        self.most_recent_total_dice_roll = 0

    def add_player(self, ai):
        '''
        Adds a player AI.

        Returns the Player object created.
        '''
        # We wrap the AI up into a Player object...
        player_number = len(self.state.players)
        player = Player(ai, player_number)
        self.state.players.append(player)
        return player

    def play_game(self):
        '''
        Plays a game of monopoly.
        '''
        # We tell the players that the game is starting, and which
        # player-number they are...
        for player in self.state.players:
            player.ai.start_of_game(player.number)

        # TODO: Play the game!

    def play_one_round(self):
        '''
        Plays one round of the game, ie one turn for each of
        the players.

        The round can come to an end before all players' turns
        are finished if one of the players wins.
        '''
        for player in self.state.players:
            self.play_one_turn(player)

    def play_one_turn(self, current_player):
        '''
        Plays one turn for one player.
        '''
        # We keep a count of how many turns the player has been in jail for...
        if(current_player.state.is_in_jail):
            current_player.state.number_of_turns_in_jail += 1

        # We notify all players that this player's turn is starting...
        for player in self.state.players:
            player.ai.start_of_turn(self.state.copy(), current_player.state.player_number)

        # TODO: unmortgage properties

        # The player can build houses...
        self._build_houses(current_player)

        # This while loop manages rolling again if the player
        # rolls doubles...
        roll_again = Game.Action.ROLL_AGAIN
        number_of_doubles_rolled = 0
        while roll_again == Game.Action.ROLL_AGAIN:
            roll_again, number_of_doubles_rolled = self.roll_and_move(current_player, number_of_doubles_rolled)

    def roll_and_move(self, current_player, number_of_doubles_rolled):
        '''
        Rolls the dice, moves the player and takes the appropriate
        action for the square landed on.

        Returns whether we should roll again and the number of doubles rolled.
        '''
        # We roll the dice and move the player...
        roll1, roll2 = self.dice.roll()
        self.most_recent_total_dice_roll = roll1 + roll2
        doubles_rolled = (roll1 == roll2)

        # If the player is in jail, we check if they rolled themself out...
        if(current_player.state.is_in_jail):
            if(not doubles_rolled and current_player.state.number_of_turns_in_jail < 3):
                # They have not rolled doubles, so they stay in jail...
                return Game.Action.DO_NOT_ROLL_AGAIN, 0
            elif(not doubles_rolled and current_player.state.number_of_turns_in_jail == 3):
                # It is the third turn in jail, so they must pay their way out...
                self.take_money_from_player(current_player, 50)
                current_player.state.is_in_jail = False
                current_player.state.number_of_turns_in_jail = 0
            else:
                # Doubles were rolled, so the player gets out of jail without paying,
                # but their turn will be over after this move even though doubles
                # were rolled...
                doubles_rolled = False # We 'pretend' that doubles weren't rolled.
                current_player.state.is_in_jail = False
                current_player.state.number_of_turns_in_jail = 0

        # We check if doubles was rolled...
        roll_again = Game.Action.DO_NOT_ROLL_AGAIN
        if(doubles_rolled):
            number_of_doubles_rolled += 1
            if(number_of_doubles_rolled == 3):
                self.send_player_to_jail(current_player)
                return Game.Action.DO_NOT_ROLL_AGAIN, number_of_doubles_rolled
            else:
                roll_again = Game.Action.ROLL_AGAIN

        # We move the player to the new square...
        current_player.state.square += self.most_recent_total_dice_roll
        if(current_player.state.square >= Board.NUMBER_OF_SQUARES):
            current_player.state.square -= Board.NUMBER_OF_SQUARES

            # If the player has passed Go, they get £200.
            # Note that we don't give £200 for landing on Go, as the
            # square itself does this...
            if(current_player.state.square != 0):
                current_player.state.cash += 200

        # We perform any actions appropriate for the new square
        # the player has landed on...
        self.player_has_changed_square(current_player)

        # If the player has ended up in jail, their turn is over
        # (even if doubles were rolled)...
        if(current_player.state.is_in_jail is True):
            roll_again = Game.Action.DO_NOT_ROLL_AGAIN

        return roll_again, number_of_doubles_rolled

    def player_has_changed_square(self, current_player):
        '''
        Called when the player has moved squares.

        We take whatever action is appropriate for the square landed on.
        '''
        square = self.state.board.squares[current_player.state.square]

        # We notify all players that the player has landed
        # on this square...
        for player in self.state.players:
            player.ai.player_landed_on_square(self.state.copy(), square.name, player.state.player_number)

        # We perform the square's landed-on action...
        square.landed_on(self, current_player)

    def take_money_from_player(self, player, amount):
        '''
        Takes some money from the player.

        The player is given the option to make a deal or
        mortgage properties first.

        Returns the money taken. In the case that the player has
        gone bankrupt, this may not be the same as the amount requested.
        '''
        # We tell the player that we need money from them...
        player.ai.money_will_be_taken(player.state.copy(), amount)

        # TODO: We allow the player to make deals...

        # We allow the player to sell houses...
        self._sell_houses(player)

        # We allow the player to mortgage properties...
        self._mortgage_properties(player)

        # We take the money, and tell the player that it was taken...
        cash_before_money_taken = player.state.cash
        player.state.cash -= amount
        player.ai.money_taken(player.state.copy(), amount)

        # We return the amount taken...
        if(player.state.cash >= 0):
            return amount
        else:
            return cash_before_money_taken

    def give_money_to_player(self, player, amount):
        '''
        Gives some money to the player.
        '''
        # We give the money to the player and tell them about it...
        player.state.cash += amount
        player.ai.money_given(player.state.copy(), amount)

    def send_player_to_jail(self, player):
        '''
        Sends the player to jail.
        '''
        player.state.is_in_jail = True
        player.state.number_of_turns_in_jail = 0
        player.state.square = self.state.board.get_index(Square.Name.JAIL)
        self.player_has_changed_square(player)

    def give_property_to_player(self, player, square_name):
        '''
        Gives a named property to a player.

        Returns the property square.
        '''
        # The square on the board is given the player number of its owner,
        # and the player is given the index of the square on the board.
        # So they both know about each other...
        index = self.state.board.get_index(square_name)
        square = self.state.board.get_square_by_index(index)
        square.owner_player_number = player.state.player_number
        player.state.property_indexes.add(index)

        # We update which sets are owned by which players, as this
        # may have changed...
        self._update_sets()

        return square

    def offer_property_for_sale(self, current_player, square):
        '''
        Offers the property for sale, initially to the current player.
        If they do not want it, it is then offered for auction to all
        players.
        '''
        # We first offer the property to the current player...
        action = self._offer_property_to_current_player(current_player, square)
        if(action == Game.Action.PROPERTY_BOUGHT):
            return

        # The current player did not buy the property, so we put it
        # up for auction...
        self._offer_property_for_auction(square)

    def _offer_property_for_auction(self, square):
        '''
        We request bids from each player and sell to the highest bidder.
        If the highest bidder cannot actually pay, it goes to the next
        highest (and so on).
        '''
        # We get bids from each player and store them in a list of
        # tuples of (player, bid)...
        bids = []
        for player in self.state.players:
            # We get a bid from the player and make sure that
            # it's an integer amount...
            bid = player.ai.property_offered_for_auction(
                self.state.copy(),
                player.state.copy(),
                square.name,
                square.price)
            bid = int(bid)

            # A bid of zero is not a bid...
            if(bid != 0):
                bids.append((player, bid))

        # We sort the bids from high to low...
        bids.sort(key=lambda x: x[1], reverse=True)

        # We sell to the highest bidder...
        number_of_bids = len(bids)
        for i in range(number_of_bids):
            player = bids[i][0]

            # We find the next highest bid...
            if(i+1 < number_of_bids):
                next_highest_bid = bids[i+1][1]
            else:
                next_highest_bid = 0
            selling_price = next_highest_bid + 1

            # We sell it to the player...
            self.take_money_from_player(player, selling_price)
            if(player.state.cash < 0):
                # The player did not have enough money, so we refund what we
                # took and sell the property to the next highest bidder...
                self.give_money_to_player(player, selling_price)
            else:
                # The player successfully bought the property...
                self.give_property_to_player(player, square.name)
                break

    def _offer_property_to_current_player(self, player, square):
        '''
        Offers the property to the current player.

        Returns Game.Action.PROPERTY_BOUGHT or PROPERTY_NOT_BOUGHT.
        '''
        # We ask the player if they want to buy the property...
        action = player.ai.landed_on_unowned_property(
            self.state.copy(),
            player.state.copy(),
            square.name,
            square.price)
        if(action == PlayerAIBase.Action.DO_NOT_BUY):
            return Game.Action.PROPERTY_NOT_BOUGHT

        # The player wants to buy the property, so we take the money...
        self.take_money_from_player(player, square.price)

        if(player.state.cash < 0):
            # The player did not have enough money, so we revert the transaction...
            self.give_money_to_player(player, square.price)
            return Game.Action.PROPERTY_NOT_BOUGHT
        else:
            # The purchase was successful...
            self.give_property_to_player(player, square.name)
            return Game.Action.PROPERTY_BOUGHT

    def _update_sets(self):
        '''
        Called after any properties have been bought or otherwise
        changed hands, to keep the information about which players
        own which sets up to date.
        '''
        # We find which players own sets, and put this info
        # into the Player objects...
        player_number_to_owned_sets_map = self.state.board.get_owned_sets()
        for player in self.state.players:
            player_number = player.state.player_number
            if(player_number in player_number_to_owned_sets_map):
                player.state.owned_sets = player_number_to_owned_sets_map[player_number]
            else:
                # The player does not own any sets...
                player.state.owned_sets.clear()

    def _build_houses(self, current_player):
        '''
        We give the current player the option to build houses.
        '''
        # We ask the player if he wants to build any houses.
        # build_instructions is a list of tuples like:
        # (street_name, number_of_houses)
        build_instructions = current_player.ai.build_houses(
            self.state.copy(),
            current_player.state.copy())
        if(not build_instructions):
            return

        # We find the Street objects for the square names provided...
        instructions_with_streets = self._get_instructions_with_streets(build_instructions)

        # There are a number of ways that building can fail. Some are
        # hard to see without doing the transaction first. So we first do
        # the building and take the money then check that everything looks
        # OK. If not, we roll back...
        self._build_houses_and_take_money(current_player, instructions_with_streets)

        # Did the player have enough money?
        if(current_player.state.cash < 0):
            self._roll_back_house_building(current_player, instructions_with_streets)
            return

        # We check each street to see if it looks as we expect...
        for (square_name, number_of_houses, street) in instructions_with_streets:
            # Did the player try to build a -ve number of houses?
            if(number_of_houses < 0):
                self._roll_back_house_building(current_player, instructions_with_streets)
                return

            # Does the street have more than five houses?
            if(street.number_of_houses > 5):
                self._roll_back_house_building(current_player, instructions_with_streets)
                return

            # Is the set that this street is a part of wholly owned by
            # the current player, and unmortgaged?
            if(street.street_set not in current_player.state.owned_sets):
                self._roll_back_house_building(current_player, instructions_with_streets)
                return

            # We check if the set that this street is part of has been
            # built in a balanced way...
            if(not self._set_has_balanced_houses(street.street_set)):
                self._roll_back_house_building(current_player, instructions_with_streets)
                return

    def _set_has_balanced_houses(self, street_set):
        '''
        Returns True if the set has balanced housing, False if not.
        '''
        properties_in_set = self.state.board.get_properties_for_set(street_set)
        houses_for_each_property = [p.number_of_houses for p in properties_in_set]
        if(max(houses_for_each_property) - min(houses_for_each_property) <= 1):
            return True
        else:
            return False

    def _build_houses_and_take_money(self, current_player, build_instructions):
        '''
        Builds the houses passed in and takes the money from the player.

        build_instructions is a list of tuples like:
        (square_name, number_of_houses, Street-object)
        '''
        # We build the houses...
        total_cost = 0
        for (square_name, number_of_houses, street) in build_instructions:
            street.number_of_houses += number_of_houses
            total_cost += (street.house_price * number_of_houses)

        # And take the money...
        self.take_money_from_player(current_player, total_cost)

    def _roll_back_house_building(self, current_player, build_instructions):
        '''
        Removes the houses specified and refunds the money.
        '''
        # We remove the houses...
        total_cost = 0
        for (square_name, number_of_houses, street) in build_instructions:
            street.number_of_houses -= number_of_houses
            total_cost += (street.house_price * number_of_houses)

        # And refund the money...
        self.give_money_to_player(current_player, total_cost)

    def _mortgage_properties(self, current_player):
        '''
        We give the current player the option to mortgage properties.
        '''
        # We ask the player if they want to mortgage anything...
        property_names_to_mortgage = current_player.ai.mortgage_properties(
            self.state.copy(),
            current_player.state.copy())

        # We mortgage them...
        total_mortgage_value = 0
        for property_name in property_names_to_mortgage:
            # We check that the square is a property...
            square = self.state.board.get_square_by_name(property_name)
            if(not isinstance(square, Property)):
                continue

            # We check that the current player owns the property and
            # that they are not sneakily trying to mortgage someone
            # else's property...
            if(square.owner_player_number != current_player.state.player_number):
                continue

            # We check that the property is not already mortgaged...
            if(square.is_mortgaged is True):
                continue

            # We check that there are no houses on the property.
            # (You can't mortgage if a property has houses.)
            if(isinstance(square, Street)):
                if(square.number_of_houses != 0):
                    continue

            # We mortgage the property...
            square.is_mortgaged = True
            total_mortgage_value += square.mortgage_value

        # We give the money to the player and update the owned
        # sets, as they may have changed...
        self.give_money_to_player(current_player, total_mortgage_value)
        self._update_sets()

    def _sell_houses(self, current_player):
        '''
        We offer the player the chance to sell houses.
        '''
        # We ask the player which properties they want to sell...
        sale_instructions = current_player.ai.sell_houses(
            self.state.copy(),
            current_player.state.copy())

        # We convert the street names into Street objects...
        instructions_with_streets = self._get_instructions_with_streets(sale_instructions)

        # We first remove the houses from the board, then check that things
        # look good. We may have to replace them if things don't look OK.
        sale_value = self._remove_houses(instructions_with_streets)

        # A few checks...
        for (square_name, number_of_houses, street) in instructions_with_streets:

            # We check that the player isn't trying to sell a negative
            # number of houses. (As a sneaky way of buying houses cheaply.)
            if(number_of_houses < 0):
                self._replace_houses(instructions_with_streets)
                return

            # We check that the property has been left with between 0 and 5 houses...
            if(street.number_of_houses < 0 or street.number_of_houses > 5):
                self._replace_houses(instructions_with_streets)
                return

            # We check that the street belongs to the current player...
            if(street.owner_player_number != current_player.state.player_number):
                self._replace_houses(instructions_with_streets)
                return

            # Will the sale result in unbalanced housing?
            if(not self._set_has_balanced_houses(street.street_set)):
                self._replace_houses(instructions_with_streets)
                return

        # The sale looks good, so we give the player the money...
        self.give_money_to_player(current_player, sale_value)

    def _remove_houses(self, instructions):
        '''
        Removes houses from the board when they are being sold.

        Returns the total sale value.
        '''
        total_sale_value = 0
        for (square_name, number_of_houses, street) in instructions:
            street.number_of_houses -= number_of_houses
            sale_price = int(street.house_price / 2)
            total_sale_value += (number_of_houses * sale_price)

        return total_sale_value

    def _replace_houses(self, instructions):
        '''
        Replaces houses on the board if a sale of them was unsuccessful.
        '''
        for (square_name, number_of_houses, street) in instructions:
            street.number_of_houses += number_of_houses

    def _get_instructions_with_streets(self, instructions):
        '''
        Takes a list of house-build or house-sale instructions and
        converts it to a list including the Street object.
        In:  [(square_name, number_of_houses), ...]
        Out: [(square_name, number_of_houses, street_object), ...]
        '''
        board = self.state.board
        instructions_with_streets = []

        # We convert each instruction...
        for (square_name, number_of_houses) in instructions:
            square = board.get_square_by_name(square_name)

            # We only include the square if it is a Street...
            if(isinstance(square, Street)):
                instructions_with_streets.append((square_name, number_of_houses, square))

        return instructions_with_streets

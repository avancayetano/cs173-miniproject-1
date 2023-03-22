import smartpy as sp

class Lottery(sp.Contract):
    def __init__(self):
        self.init(
            players = sp.map(l={}, tkey=sp.TNat, tvalue=sp.TAddress),
            ticket_cost = sp.tez(1),
            tickets_available = sp.nat(5),
            max_tickets = sp.nat(5),
            admin = sp.address("tz1i1THJ4MHiqTWsHNcZNU4YT8tPtqZW5NYE")
        )

    @sp.entry_point
    def buy_ticket(self, num_tickets):
        sp.set_type(num_tickets, sp.TNat)
        
        
        sp.verify(self.data.tickets_available > 0, "NO TICKETS AVAILABLE")

        # Here, can_buy is the number of tickets the player can buy.
        # If the player requests for more than the available tickets,
        # the player will only get <tickets_available> number of tickets.
        can_buy = sp.local("can_buy", num_tickets)
        sp.if num_tickets > self.data.tickets_available:
            can_buy.value = self.data.tickets_available

        # cost of the tickets bought by the player
        total_cost = sp.local("total_cost", sp.mul(can_buy.value, self.data.ticket_cost))

        sp.verify(sp.amount >= total_cost.value, "INVALID AMOUNT")

        # Storage updates
        # Here, I modified self.data.players such that players can have multiple entries
        # because they can buy multiple tickets.
        idx = sp.local("idx", sp.nat(0))
        sp.while idx.value < can_buy.value:
            self.data.players[sp.len(self.data.players)] = sp.sender
            idx.value += 1

        self.data.tickets_available = sp.as_nat(self.data.tickets_available - can_buy.value)

        # Return extra tez balance to the sender
        extra_balance = sp.amount - total_cost.value
        sp.if extra_balance > sp.mutez(0):
            sp.send(sp.sender, extra_balance)


    @sp.entry_point
    def change_ticket_cost(self, new_ticket_cost):
        sp.set_type(new_ticket_cost, sp.TMutez)

        sp.verify(sp.sender == self.data.admin, "NOT AUTHORIZED")
        sp.verify(self.data.tickets_available == self.data.max_tickets, "GAME ALREADY STARTED")
        
        self.data.ticket_cost = new_ticket_cost

    
    @sp.entry_point
    def change_max_tickets(self, new_max_tickets):
        sp.set_type(new_max_tickets, sp.TNat)

        sp.verify(sp.sender == self.data.admin, "NOT AUTHORIZED")
        sp.verify(self.data.tickets_available == self.data.max_tickets, "GAME ALREADY STARTED")
        
        self.data.max_tickets = new_max_tickets
        self.data.tickets_available = self.data.max_tickets
    

    @sp.entry_point
    def end_game(self):
        # In the original code, end_game can be called by anyone (not just the admin).
        # I did not change this behavior as it was not specified on the miniproject specs.


        # Sanity checks
        sp.verify(self.data.tickets_available == 0, "GAME IS YET TO END")

        # Pick a winner
        winner_id = sp.as_nat(sp.now - sp.timestamp(0)) % self.data.max_tickets
        winner_address = self.data.players[winner_id]

        # Send the reward to the winner
        sp.send(winner_address, sp.balance)

        # Reset the game
        self.data.players = {}
        self.data.tickets_available = self.data.max_tickets

        

@sp.add_test(name = "main")
def test():
    scenario = sp.test_scenario()

    
    admin = sp.address("tz1i1THJ4MHiqTWsHNcZNU4YT8tPtqZW5NYE")

    # Test accounts
    alice = sp.test_account("alice")
    bob = sp.test_account("bob")
    mike = sp.test_account("mike")
    charles = sp.test_account("charles")
    john = sp.test_account("john")

    # Contract instance
    lottery = Lottery()
    scenario += lottery

    # buy_ticket
    scenario.h2("buy_ticket (valid tests)")
    
    # buy only one ticket with exact amount of tez (1 tez)
    # scenario += lottery.buy_ticket(sp.nat(1)).run(amount = sp.tez(1), sender = alice)

    # buy only one ticket with excess tez
    scenario += lottery.buy_ticket(sp.nat(1)).run(amount = sp.tez(2), sender = bob)

    # buy multiple tickets with exact amount of tez
    scenario += lottery.buy_ticket(sp.nat(2)).run(amount = sp.tez(2), sender = mike)

    # buy multiple tickets with excess tez
    scenario += lottery.buy_ticket(sp.nat(2)).run(amount = sp.tez(5), sender = charles)

    # end_game
    scenario.h2("end_game (valid test)")
    scenario += lottery.end_game().run(sender = admin, now = sp.timestamp(20))


    scenario.h2("buy_ticket (some edge cases)")
    # buy multiple tickets without enough tez
    scenario += lottery.buy_ticket(sp.nat(3)).run(amount = sp.tez(2), sender = bob, valid = False)

    # buy multiple tickets that are more than the available tickets
    # (still a valid test, except that the player will only get <tickets_available> number of tickets)
    scenario += lottery.buy_ticket(sp.nat(6)).run(amount = sp.tez(6), sender = bob)

    # buy a ticket when there are no available tickets (failure test)
    scenario += lottery.buy_ticket(sp.nat(1)).run(amount = sp.tez(1), sender = john, valid = False)

    scenario += lottery.end_game().run(sender = admin, now = sp.timestamp(20))

    scenario.h2("change_ticket_cost (valid test)")
    # change ticket_cost to 2 tez
    scenario += lottery.change_ticket_cost(sp.tez(2)).run(sender = admin)

    scenario.h2("change_ticket_cost (failure test)")
    # failure test... ticket_cost remains 2 tez
    scenario += lottery.change_ticket_cost(sp.tez(3)).run(sender = alice, valid = False)    

    scenario.h2("change_max_tickets (valid test)")
    # change max_tickets to 10
    scenario += lottery.change_max_tickets(sp.nat(10)).run(sender = admin)

    scenario.h2("change_max_tickets (failure test)")
    # failure test... max_tickets remains 10
    scenario += lottery.change_max_tickets(sp.nat(15)).run(sender = bob, valid = False)
    
    # change_max_tickets when game already started (failure test)
    # alice bought 1 ticket, game started
    scenario += lottery.buy_ticket(sp.nat(1)).run(amount = sp.tez(2), sender = alice)
    scenario += lottery.change_max_tickets(sp.nat(15)).run(sender = admin, valid = False)

    # end_game when the game has not finished yet
    scenario.h2("end_game (failure test)")
    scenario += lottery.end_game().run(sender = admin, now = sp.timestamp(20), valid = False)

    scenario.h2("verify that more tickets = more chance of winning")
    scenario += lottery.buy_ticket(sp.nat(9)).run(amount = sp.tez(18), sender = bob)
    # at this point, alice bought only 1 ticket while bob bought 9
    # can end_game now since max_tickets is 10
    scenario += lottery.end_game().run(sender = admin, now = sp.timestamp(2023))
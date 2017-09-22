#! /usr/bin/env python3
import csv
import elo
from bs4 import BeautifulSoup


class Player(object):
    def __init__(self, token, rating=None):
        self.token = token
        if rating is not None:
            self.rating = elo.RATING_CLASS(rating)
        else:
            self.init_rating()

    def __repr__(self):
        return self.__class__.__name__ + \
            "({self.token}, {self.rating})".format(self=self)

    def init_rating(self):
        self.rating = elo.INITIAL


class Rater(object):
    def __init__(self, iterable):
        self.players = {}
        for line in iterable:
            if line[0] in self.players:
                raise ValueError(
                    "A token may only be specified once. Token: {}".format(
                        line[0]
                    )
                )
            self.players[line[0]] = Player(*line)

    @staticmethod
    def adjust_all(ranking):
        """
        Adjust the ratings of given Players according to the ranked results.

        In a ranking every player won from all players before it.
        """
        new_ratings = [
            elo.rate(player.rating, [
                ((pi < oi), opponent.rating)
                for oi, opponent in enumerate(ranking)
                if opponent is not player
                ]
            )
            for pi, player in enumerate(ranking)
        ]

        for player, rating in zip(ranking, new_ratings):
            player.rating = rating

    def restart(self):
        for player in self.players.values():
            player.init_rating()


class Controller(object):

    PLAYER_NAME_TO_IP = {
        'scr_server 1': 3001,
        'scr_server 2': 3002,
        'scr_server 3': 3003,
        'scr_server 4': 3004,
        'scr_server 5': 3005,
        'scr_server 6': 3006,
        'scr_server 7': 3007,
        'scr_server 8': 3008,
        'scr_server 9': 3009,
        'scr_server 10': 3010
    }

    def __init__(self, ratings_file):
        """
        Orchestrate the races and save the ratings.

        When the rating is left out of the ratings file for a token, it is
        assigned the default rating, which will be saved to the same file
        when running `save_ratings`.
        """
        self.ratings_file = ratings_file
        with open(self.ratings_file) as fd:
            self.rater = Rater(map(self.clean_rating_line, csv.reader(fd)))

    @staticmethod
    def clean_rating_line(iterable):
        li = list(iterable)
        if len(li) != 1 and len(li) != 2:
            raise ValueError(
                "A ratings file should only contain lines with one or two "
                "values, got {}".format(li)
            )
        if len(li) == 2:
            try:
                li[1] = elo.RATING_CLASS(li[1])
            except ValueError as error:
                raise ValueError(
                    "The second value of a rating line should be "
                    "interpretable as {}. I received the following error "
                    "while casting:\n\t{}".format(
                        elo.RATING_CLASS.__name__,
                        error
                    )
                )
        return li

    def save_ratings(self):
        with open(self.ratings_file, 'w') as fd:
            csv.writer(fd).writerows(
                (p.token, p.rating) for p in self.rater.players.values()
            )

    def read_ranking(results_file):
        """
        Return a ranked list of player names read from the given results file.

        NB. Player names are _not_ tokens. One should first look up which token
            corresponds with which player name.
        """
        soup = BeautifulSoup(results_file, 'xml')
        result_soup = soup.find('section', attrs={'name': 'Results'})
        rank_soup = result_soup.find('section', attrs={'name': 'Rank'})
        ranks = [
            (
                int(section['name']),
                section.find('attstr', attrs={'name': 'name'})['val']
            )
            for section in rank_soup.findAll('section')
        ]
        return list(zip(*sorted(ranks)))[1]

    def restart(self):
        """Restart the tournament, making all ratings equal."""
        self.rater.restart()


if __name__ == '__main__':
    # players = [
    #     Player(1),
    #     Player(2),
    #     Player(3),
    # ]
    # Player(4),
    # Player(5),
    # Player(6),
    # Player(7),
    # Player(8),
    # Player(9),

    # adjust_all(players)
    # print(players)
    fh = Controller('ratings_file.csv')
    fh.restart()
    fh.save_ratings()

#! /usr/bin/env python3
import logging

import os
import csv
import time
import shutil
import subprocess
from collections import OrderedDict

import elo
import yaml
from bs4 import BeautifulSoup

logger = logging.getLogger(None if __name__ == '__main__' else __name__)


def path_rel_to_dir(path, direcotry):
    if not os.path.isabs(path):
        path = os.path.join(direcotry, path)
    return path


class OrderedLoader(yaml.Loader):
    def construct_mapping(self, node, deep=False):
        # self.flatten_mapping(node)
        return OrderedDict(self.construct_pairs(node, deep))


OrderedLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    OrderedLoader.construct_mapping
)


class Player(object):
    """
    Every argument of `start_command` will be formatted using
        `format(port=<value>)`

    `start_command` is issued with `working_dir` as working directory.
    """

    def __init__(self, token, start_command=['./start.sh', '-p', '{port}'],
                 working_dir=None, stdout='./stdout.txt',
                 stderr='./stderr.txt', rating=None):
        self.token = token
        self.start_command = start_command
        self.stdout = stdout
        self.stderr = stderr
        self.working_dir = working_dir \
            if working_dir is not None \
            else '../driver/' + self.token

        if rating is not None:
            self.rating = elo.RATING_CLASS(rating)
        else:
            self.init_rating()

    def __repr__(self):
        return self.__class__.__name__ + "({self.token!r}, " \
            "{self.start_command!r}, " \
            "{self.rating!r}, " \
            ")".format(self=self)

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

    def configure_player(self, token, **dic):
        if token in self.players:
            player = self.players[token]
            for key, value in dic.items():
                setattr(player, key, value)
        else:
            self.players[token] = Player(token, **dic)

    def restart(self):
        for player in self.players.values():
            player.init_rating()


class Controller(object):
    def __init__(self, ratings_file,
                 config_file='example_torcs_config.xml',
                 server_stdout='server_out.txt',
                 server_stderr='server_err.txt',
                 result_path='../../../.torcs/results/',
                 player_name_to_ip=OrderedDict([
                    ('scr_server 1', 3001),
                    ('scr_server 2', 3002),
                    ('scr_server 3', 3003),
                    ('scr_server 4', 3004),
                    ('scr_server 5', 3005),
                    ('scr_server 6', 3006),
                    ('scr_server 7', 3007),
                    ('scr_server 8', 3008),
                    ('scr_server 9', 3009),
                    ('scr_server 10', 3010),
                 ]),
                 shutdown_wait=1):
        """
        Orchestrate the races and save the ratings.

        When the rating is left out of the ratings file for a token, it is
        assigned the default rating, which will be saved to the same file
        when running `save_ratings`.
        """
        self.ratings_file = ratings_file
        with open(self.ratings_file) as fd:
            self.rater = Rater(map(self.clean_rating_line, csv.reader(fd)))

        self.config_file = config_file
        self.server_stdout = server_stdout
        self.server_stderr = server_stderr
        self.result_path = result_path
        self.player_name_to_ip = player_name_to_ip
        self.shutdown_wait = shutdown_wait

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

    def race_tokens(self, tokens):
        return self.race_once(map(self.rater.players.get, tokens))

    def race_once(self, players):
        """
        Run one race with TORCS and the given players.

        NB. Please make sure the number of players given matches the specified
            number of players in the configuration file of this Controller.

        The output can be found under your torcs installation directory/results
        """

        # ENSURE OUTPUT DIR EXISTS! -- TORCS does this automatically
        # out_dir = os.path.join(
        #     self.result_path,
        #     '.'.join(self.config_file.split('.')[:-1])  # remove extension
        # )
        # if not os.path.isdir(out_dir):
        #     os.mkdir(out_dir)
        players = list(players)
        open_files = []

        try:
            # Start server
            server_stdout = open(self.server_stdout, 'w')
            open_files.append(server_stdout)
            server_stderr = open(self.server_stderr, 'w')
            open_files.append(server_stderr)

            logger.info("Starting TORCS...")
            server_process = subprocess.Popen(
                ['torcs', '-r', os.path.abspath(self.config_file)],
                stdout=server_stdout,
                stderr=server_stderr,
            )

            # Start players
            logger.info("Starting players...")
            player_processes = []
            for port, player in zip(self.player_name_to_ip.values(), players):
                stdout = open(
                    path_rel_to_dir(player.stdout, player.working_dir),
                    'w'
                )
                open_files.append(stdout)
                stderr = open(
                    path_rel_to_dir(player.stderr, player.working_dir),
                    'w'
                )
                open_files.append(stderr)
                player_processes.append(subprocess.Popen(
                    map(lambda s: s.format(port=port), player.start_command),
                    cwd=player.working_dir,
                    stdout=stdout,
                    stderr=stderr,
                ))
                logger.info("Started {}".format(player))

            # Shut down server
            logger.info("Waiting for TORCS to finish...")
            server_process.wait()

        finally:
            # Exit running processes
            procs = [server_process] + player_processes

            # First be nice
            for proc in procs:
                if proc.poll() is None:
                    proc.terminate()

            # Wait a second to give the processes some time
            time.sleep(self.shutdown_wait)

            # Time's up
            for proc in procs:
                if proc.poll() is None:
                    proc.kill()

            # Double check
            for proc in procs:
                if proc.poll() is None:
                    logger.warning(
                        "The following process could not be killed: {}".format(
                            proc
                        )
                    )

            # Close all open files
            for fd in open_files:
                logger.info("Closing {}".format(fd.name))
                try:
                    fd.close()
                except Exception as e:
                    logger.error(e)

        # Give the players the server output
        for player in players:
            shutil.copyfile(
                self.server_stdout,
                os.path.join(
                    player.working_dir,
                    os.path.basename(self.server_stdout)
                )
            )
            shutil.copyfile(
                self.server_stderr,
                os.path.join(
                    player.working_dir,
                    os.path.basename(self.server_stderr)
                )
            )

        # Do something with result
        logger.warning("The result of this race was ignored.")

    @staticmethod
    def load_config(config_file):
        with open(config_file) as fd:
            config = yaml.load(fd, OrderedLoader)
        controller = Controller(**config['controller'])
        for token, player_conf in config['players'].items():
            controller.rater.configure_player(token, **player_conf)
        return controller


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
    # fh = Controller('example_ratings_file.csv')
    # fh.restart()
    # fh.race_once('foo')
    # fh.save_ratings()

    controller = Controller.load_config('./example_config.yml')
    controller.race_tokens('player' + str(i) for i in range(5))

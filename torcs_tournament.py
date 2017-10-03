#! /usr/bin/env python3
import logging

import os
import csv
import time
import shutil
import pathlib
import datetime
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


class ParseError(Exception):
    pass


class Player(object):
    """
    Every argument of `start_command` will be formatted using
        `format(port=<value>)`

    `start_command` is issued with `working_dir` as working directory.
    """

    def __init__(self, token, rating=None,
                 start_command=['./start.sh', '-p', '{port}'],
                 working_dir=None, output_dir='./output/',
                 stdout='./{timestamp}-stdout.txt',
                 stderr='./{timestamp}-stderr.txt'):
        self.token = token
        self.start_command = start_command
        self.stdout = stdout
        self.stderr = stderr
        self.working_dir = working_dir if working_dir is not None \
            else 'drivers/' + self.token
        self.output_dir = output_dir if os.path.isabs(output_dir) \
            else os.path.join(self.working_dir, output_dir)
        if not os.path.exists(self.output_dir):
            os.mkdir(self.output_dir)
        if rating is not None:
            self.rating = elo.RATING_CLASS(rating)
        else:
            self.init_rating()

    def __str__(self):
        return self.__class__.__name__ + "({self.token!r}, " \
            "{self.rating!r}, " \
            "{self.start_command!r}, " \
            ")".format(self=self)

    def init_rating(self):
        self.rating = elo.INITIAL


class Rater(object):
    def __init__(self, players=(), filename=None):
        self.players = {}
        for player in players:
            if player.token in self.players:
                raise ValueError(
                    "A token may only be specified once. Token: {}".format(
                        player.token
                    )
                )
            self.players[player.token] = player
        self.filename = filename
        if self.filename is not None:
            self.read_file()

    def filename_check(self, filename=None):
        if filename is None:
            if self.filename is None:
                raise ValueError(
                    "Please specify a filename as first argument or assign it "
                    "to `self.filename`."
                )
            else:
                filename = self.filename
        return filename

    def read_file(self, filename=None):
        filename = self.filename_check(filename)
        with open(filename) as fd:
            self.set_ratings(map(self.clean_line, csv.reader(fd)))

    def set_ratings(self, iterable):
        tokens = set()
        for line in iterable:
            token = line[0]
            if token in tokens:
                raise ValueError(
                    "A token may only be specified once. Token: {}".format(
                        token
                    )
                )
            tokens.add(token)
            if len(line) > 2:
                raise ValueError(
                    "No extra information next to a token and the desired "
                    "rating should be specified: {}".format(line)
                )
            if len(line) == 2:
                self.players[token].rating = elo.RATING_CLASS(line[1])

    @staticmethod
    def clean_line(iterable):
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

    def save_ratings(self, filename=None):
        filename = self.filename_check(filename)
        with open(filename, 'w') as fd:
            csv.writer(fd).writerows(
                sorted(
                    ((p.token, p.rating) for p in self.players.values()),
                    key=lambda p: p[1]
                )
            )

    @staticmethod
    def adjust_all(ranking):
        """
        Adjust the ratings of given Players according to the ranked results.

        In a ranking every player won from all players before it.
        """
        ranking = list(ranking)
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

    # def configure_player(self, token, **dic):
    #     if token in self.players:
    #         player = self.players[token]
    #         for key, value in dic.items():
    #             setattr(player, key, value)
    #     else:
    #         self.players[token] = Player(token, **dic)

    def restart(self):
        for player in self.players.values():
            player.init_rating()


class Controller(object):
    def __init__(self, rater,
                 config_file='example_torcs_config.xml',
                 server_stdout='{timestamp}-server_out.txt',
                 server_stderr='{timestamp}-server_err.txt',
                 result_path='../../../.torcs/results/',
                 result_filename_format="{driver} - {base}",
                 timestamp_format='%Y-%m-%d-%H.%M',
                 driver_to_port=OrderedDict([
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
                 rater_backup_filename=None,
                 shutdown_wait=1):
        """
        Orchestrate the races and save the ratings.

        When the rating is left out of the ratings file for a token, it is
        assigned the default rating, which will be saved to the same file
        when running `save_ratings`.
        """
        self.rater = rater
        self.config_file = config_file
        self.server_stdout = server_stdout
        self.server_stderr = server_stderr
        self.result_path = result_path
        self.result_filename_format = result_filename_format
        self.timestamp_format = timestamp_format
        self.driver_to_port = driver_to_port
        self.rater_backup_filename = rater_backup_filename
        self.shutdown_wait = shutdown_wait
        logger.debug("Result path: {}".format(self.result_path))

    def timestamp(self):
        return datetime.datetime.now().strftime(self.timestamp_format)

    @staticmethod
    def read_ranking(results_file):
        """
        Return a ranked list of driver names read from the given results file.

        NB. Driver names are _not_ tokens. One should first look up which token
            corresponds with which driver name.
        """
        with open(results_file) as fd:
            soup = BeautifulSoup(fd, 'xml')
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

    @staticmethod
    def read_lineup(config_file):
        with open(config_file) as fd:
            soup = BeautifulSoup(fd, 'xml')
        drivers_sec = soup.find('section', attrs={'name': 'Drivers'})
        drivers = []
        for sec in drivers_sec.findAll('section'):
            tag, attrs = 'attstr', {'name': 'module'}
            module = sec.find(tag, attrs=attrs)
            if module is None:
                raise ParseError(
                    "Error parsing {file}: expected a {tag} tag with the "
                    "following attributes: {attrs!r}".format(
                        file=config_file,
                        tag=tag,
                        attrs=attrs
                    )
                )

            expected = 'scr_server'
            if module.get('val', Exception()) != expected:
                raise ParseError(
                    "Error parsing {file}: all drivers are expected to be the "
                    "'{expected}' module.".format(
                        file=config_file,
                        expected=expected
                    )
                )

            tag, attrs = 'attnum', {'name': 'idx'}
            idx = sec.find(tag, attrs=attrs)
            if idx is None:
                raise ParseError(
                    "Error parsing {file}: expected a {tag} tag with the "
                    "following attributes: {attrs!r}".format(
                        file=config_file,
                        tag=tag,
                        attrs=attrs
                    )
                )
            val = idx.get('val', None)
            if val is None:
                raise ParseError(
                    "Error parsing {file}: expected {tag} to have the "
                    "attribute {attr}.".format(
                        file=config_file,
                        tag=tag,
                        attr='val',
                    )
                )
            drivers.append((sec['name'], val))

        # I now have a list of (rank, id) pairs
        # Somehow, the number in the name of the scr_server driver is one
        # larger that the `idx` of the driver.
        return [
            'scr_server {}'.format(int(idx) + 1)
            for _, idx in sorted(drivers)
        ]

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

        # Read drivers from config
        drivers = self.read_lineup(self.config_file)
        if len(drivers) != len(players):
            raise ValueError(
                "{nplay} players where given, but {file} specifies {ndriv} "
                "drivers".format(
                    nplay=len(players),
                    ndriv=len(drivers),
                    file=self.config_file
                )
            )

        driver_to_player = OrderedDict(zip(drivers, players))

        open_files = []

        try:
            # Start server
            server_stdout = open(
                self.server_stdout.format(timestamp=self.timestamp()),
                'w'
            )
            open_files.append(server_stdout)
            server_stderr = open(
                self.server_stderr.format(timestamp=self.timestamp()),
                'w'
            )
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
            for driver, player in driver_to_player.items():
                stdout = open(
                    path_rel_to_dir(
                        player.stdout.format(timestamp=self.timestamp()),
                        player.output_dir
                    ),
                    'w'
                )
                open_files.append(stdout)
                stderr = open(
                    path_rel_to_dir(
                        player.stderr.format(timestamp=self.timestamp()),
                        player.output_dir
                    ),
                    'w'
                )
                open_files.append(stderr)
                player_processes.append(subprocess.Popen(
                    map(
                        lambda s: s.format(port=self.driver_to_port[driver]),
                        player.start_command
                    ),
                    cwd=player.working_dir,
                    stdout=stdout,
                    stderr=stderr,
                ))
                logger.debug("Started {}".format(player))

            # Check no one crashed in the mean time
            for proc in player_processes:
                if proc.poll() is not None:
                    raise subprocess.CalledProcessError(
                        proc.returncode,
                        proc.args
                    )

            # Wait for server
            logger.info("Waiting for TORCS to finish...")
            server_process.wait()

        finally:

            logger.info("Stopping...")

            # Exit running processes
            procs = [server_process] + player_processes

            # Wait a second to give the processes some time
            time.sleep(self.shutdown_wait)

            # First be nice
            for proc in procs:
                if proc.poll() is None:
                    logger.info("Terminating {}".format(proc))
                    proc.terminate()

            # Wait a second to give the processes some time
            time.sleep(self.shutdown_wait)

            # Time's up
            for proc in procs:
                if proc.poll() is None:
                    logger.warning("Killing {}".format(proc))
                    proc.kill()

            # Double check
            for proc in procs:
                if proc.poll() is None:
                    logger.warning(
                        "The following process could not be killed: {}".format(
                            proc.args
                        )
                    )

            # Close all open files
            for fd in open_files:
                logger.debug("Closing {}".format(fd.name))
                try:
                    fd.close()
                except Exception as e:
                    logger.error(e)

        # Give the players the server output
        for player in players:
            shutil.copyfile(
                server_stdout.name,
                os.path.join(
                    player.output_dir,
                    os.path.basename(server_stdout.name)
                )
            )
            shutil.copyfile(
                server_stderr.name,
                os.path.join(
                    player.output_dir,
                    os.path.basename(server_stderr.name)
                )
            )

        # Find the correct results file
        logger.debug("Result path: {}".format(self.result_path))
        out_dir = os.path.join(
            self.result_path,
            # remove head path and extension
            '.'.join(os.path.split(self.config_file)[1].split('.')[:-1])
        )

        out_base = sorted(os.listdir(out_dir))[-1]
        out_file = os.path.join(
            out_dir,
            out_base
        )

        # Give the players the results file
        for driver, player in driver_to_player.items():
            shutil.copyfile(
                out_file,
                os.path.join(
                    player.output_dir,
                    self.result_filename_format.format(
                        driver=driver,
                        base=out_base
                    )
                )
            )

        # Update ratings according to ranking
        ranked_drivers = self.read_ranking(out_file)
        self.rater.adjust_all(map(driver_to_player.get, ranked_drivers))
        if self.rater_backup_filename is not None:
            self.rater.save_ratings(
                self.rater_backup_filename.format(timestamp=self.timestamp())
            )

    @staticmethod
    def load_config(config_file):
        with open(config_file) as fd:
            config = yaml.load(fd, OrderedLoader)
        rater = Rater(
            (
                Player(token, **player_conf)
                for token, player_conf in config['players'].items()
            ),
            **config.get('rater', {})
        )
        rater.read_file()
        controller = Controller(rater, **config.get('controller', {}))
        return controller


class QueueCreator(object):
    @staticmethod
    def touch(filename):
        """
        Touch a file.

        I.E. create it if it does not exist or change the last modified time
        to the current time if it does.
        """
        pathlib.Path(filename).touch()

    @staticmethod
    def get_last_modified(filename):
        return os.path.getmtime(filename)


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('config_file')
    parser.add_argument('-l', '--level', default='INFO')
    args = parser.parse_args()
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
    # fh = Controller('example_ratings_file.csv')
    # fh.restart()
    # fh.race_once('foo')
    # fh.save_ratings()
    logging.basicConfig(level=args.level)
    controller = Controller.load_config(args.config_file)
    controller.race_tokens(
        # ['martin', 'player1', 'player2', 'player3', 'player4']
        ['martin']
    )
    logger.warning("I'm still racing a hard coded set of teams.")
    controller.rater.save_ratings()

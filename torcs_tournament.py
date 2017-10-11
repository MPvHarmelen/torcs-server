#! /usr/bin/env python3
import logging

import os
import re
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
    Container for player information.

    Every argument of `start_command` will be formatted using
        `format(port=<value>)`

    `start_command` is issued with `working_dir` as working directory and
    `process_owner` as user. If `process_owner` is None, `token` will be used.

    The filenames `stdout` and `stderr` are relative to `output_dir`.
    """

    def __init__(self, token, working_dir, rating=None,
                 start_command=['./start.sh', '-p', '{port}'],
                 output_dir='./output/',
                 stdout='./{timestamp}-stdout.txt',
                 stderr='./{timestamp}-stderr.txt'):
        self.token = token
        self.working_dir = working_dir
        self.start_command = start_command
        self.stdout = stdout
        self.stderr = stderr
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
            ")".format(self=self)

    def __repr__(self):
        return self.__class__.__name__ + "({self.token!r}, " \
            "{self.rating!r}, " \
            "{self.start_command!r}, " \
            "{self.working_dir!r}, " \
            "{self.output_dir!r}, " \
            "{self.stdout!r}, " \
            "{self.stderr!r}, " \
            ")".format(self=self)

    def init_rating(self):
        self.rating = elo.INITIAL


class Rater(object):
    def __init__(self, players=(), filename=None):
        self.player_map = {}
        for player in players:
            self.add_player(player)
        self.filename = filename
        if self.filename is not None:
            self.read_file()

    def add_player(self, player):
        """Add a player to this rater."""
        if player.token in self.player_map:
            raise ValueError(
                "A token may only be specified once. Token: {}".format(
                    player.token
                )
            )
        self.player_map[player.token] = player

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
                self.player_map[token].rating = elo.RATING_CLASS(line[1])

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
        """
        Save the ratings of all players to a file.

        If a filename is specified, that file is used, otherwise
        `self.filename` is used. If neither is specified, a ValueError is
        raised.
        """
        filename = self.filename_check(filename)
        logger.info("Saving ratings in {}".format(filename))
        with open(filename, 'w') as fd:
            csv.writer(fd).writerows(
                sorted(
                    ((p.token, p.rating) for p in self.player_map.values()),
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

    def restart(self):
        for player in self.player_map.values():
            player.init_rating()


class Controller(object):
    def __init__(self, rater, queue, torcs_config_file,
                 server_stdout='{timestamp}-server_out.txt',
                 server_stderr='{timestamp}-server_err.txt',
                 result_path='~/.torcs/results/',
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

        N.B. `~` is only expanded to the user directory in `result_path` at
             initialisation of the controller.
        """
        self.rater = rater
        self.queue = queue
        self.torcs_config_file = torcs_config_file
        self.server_stdout = server_stdout
        self.server_stderr = server_stderr
        self.result_path = os.path.expanduser(result_path)
        self.result_filename_format = result_filename_format
        self.timestamp_format = timestamp_format
        self.driver_to_port = driver_to_port
        self.rater_backup_filename = rater_backup_filename
        self.shutdown_wait = shutdown_wait
        logger.debug("Result path: {}".format(self.result_path))

        # Read drivers from config
        self.drivers = self.read_lineup(self.torcs_config_file)

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
    def read_lineup(torcs_config_file):
        with open(torcs_config_file) as fd:
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
                        file=torcs_config_file,
                        tag=tag,
                        attrs=attrs
                    )
                )

            expected = 'scr_server'
            if module.get('val', Exception()) != expected:
                raise ParseError(
                    "Error parsing {file}: all drivers are expected to be the "
                    "'{expected}' module.".format(
                        file=torcs_config_file,
                        expected=expected
                    )
                )

            tag, attrs = 'attnum', {'name': 'idx'}
            idx = sec.find(tag, attrs=attrs)
            if idx is None:
                raise ParseError(
                    "Error parsing {file}: expected a {tag} tag with the "
                    "following attributes: {attrs!r}".format(
                        file=torcs_config_file,
                        tag=tag,
                        attrs=attrs
                    )
                )
            val = idx.get('val', None)
            if val is None:
                raise ParseError(
                    "Error parsing {file}: expected {tag} to have the "
                    "attribute {attr}.".format(
                        file=torcs_config_file,
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

    def race_and_save(self, simulate=False):
        """
        Run a race (see `Controller.race`) and save the ratings.
        """
        self.race(simulate=simulate)
        self.rater.save_ratings()

    def race(self, simulate=False):
        """
        Run a race

        Automatically determine the number of players to be raced and ask the
        queue which players are next. Race the players, save the results and
        update the queue.
        """
        players = self.queue.first_n(len(self.drivers))
        logger.info("Racing: {}".format(', '.join(
            repr(player.token) for player in players
        )))
        self.race_once(players, simulate=simulate)
        self.queue.requeue(players)

    def race_tokens(self, tokens, simulate=False):
        return self.race_once(
            map(self.rater.player_map.get, tokens),
            simulate=simulate
        )

    def race_once(self, players, simulate=False):
        """
        Run one race with TORCS and the given players.

        Also make a backup of the ratings if `self.rater_backup_filename` is
        not None.

        NB. Please make sure the number of players given matches the specified
            number of players in the configuration file of this Controller.

        The output can be found under:
            <torcs installation directory>/results
        """
        players = list(players)

        if len(self.drivers) != len(players):
            raise ValueError(
                "{nplay} players where given, but {file} specifies {ndriv} "
                "drivers".format(
                    nplay=len(players),
                    ndriv=len(self.drivers),
                    file=self.torcs_config_file
                )
            )

        driver_to_player = OrderedDict(zip(self.drivers, players))

        open_files = []
        processes = []

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
            if simulate:
                logger.warning(
                    "This is a simulation! No child processes are started."
                )
            else:
                server_process = subprocess.Popen(
                    ['torcs', '-r', os.path.abspath(self.torcs_config_file)],
                    stdout=server_stdout,
                    stderr=server_stderr,
                )
                processes.append(server_process)

            # Start players
            logger.info("Starting players...")
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
                if not simulate:
                    processes.append(subprocess.Popen(
                        map(
                            lambda s: s.format(
                                port=self.driver_to_port[driver]
                            ),
                            player.start_command
                        ),
                        cwd=player.working_dir,
                        stdout=stdout,
                        stderr=stderr,
                    ))
                logger.debug("Started {}".format(player))

            # Check no one crashed in the mean time
            for proc in processes:
                if proc.poll() is not None:
                    raise subprocess.CalledProcessError(
                        proc.returncode,
                        proc.args
                    )

            # Wait for server
            logger.info("Waiting for TORCS to finish...")
            if not simulate:
                server_process.wait()

        except:
            logger.error("An error occurred, trying to stop gracefully...")
            raise

        finally:
            # Exit running processes

            if not simulate:
                # Wait a second to give the processes some time
                time.sleep(self.shutdown_wait)

                # First be nice
                for proc in processes:
                    if proc.poll() is None:
                        logger.info("Terminating {}".format(proc))
                        proc.terminate()

                # Wait a second to give the processes some time
                time.sleep(self.shutdown_wait)

                # Time's up
                for proc in processes:
                    if proc.poll() is None:
                        logger.warning("Killing {}".format(proc))
                        proc.kill()

                # Double check
                for proc in processes:
                    if proc.poll() is None:
                        logger.error(
                            "The following process could not be killed: {}"
                            .format(proc.args)
                        )

            # Close all open files
            for fd in open_files:
                logger.debug("Closing {}".format(fd.name))
                try:
                    fd.close()
                except Exception as e:
                    logger.error(e)
            logger.info("Success!")

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
            '.'.join(os.path.split(self.torcs_config_file)[1].split('.')[:-1])
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

        # Make a backup if self.rater_backup_filename is given
        if self.rater_backup_filename is not None:
            backup_filename = self.rater_backup_filename.format(
                timestamp=self.timestamp()
            )
            # logger.info("Backing up ratings in {}".format(backup_filename))
            self.rater.save_ratings(
                backup_filename
            )

    @staticmethod
    def load_config(config_file):
        error_regex = re.compile(
            r"__init__\(\) got an unexpected keyword argument '(\w+)'"
        )
        with open(config_file) as fd:
            config = yaml.load(fd, OrderedLoader)
        try:
            rater = Controller.load_rater(config)
            fbq = Controller.load_fbq(config, rater.player_map.values())
            controller = Controller(rater, fbq, **config.get('controller', {}))
        except TypeError as e:
            match = error_regex.fullmatch(e.args[0])
            if match is not None:
                config_key = match.groups()[0]
                logger.debug("Match: {}".format(config_key))
                raise ValueError(
                    "Unexpected configuration key in {filename}: {key!r}"
                    .format(filename=config_file, key=config_key)
                ) from e
            else:
                logger.debug("No match...")
                raise
        return controller

    @staticmethod
    def load_rater(config_dic):
        rater = Rater(
            (
                Player(token, **player_conf)
                for token, player_conf in config_dic['players'].items()
            ),
            **config_dic.get('rater', {})
        )
        rater.read_file()
        return rater

    @staticmethod
    def load_fbq(config_dic, players=()):
        return FileBasedQueue(players, **config_dic.get('queue', {}))


class FileBasedQueue(object):
    """
    Queue players according to the last modified time of a specifically named
    file in their `working_dir`.
    """

    def __init__(self, players, filename='start.sh'):
        self.filename = filename
        self.players = players

    @staticmethod
    def touch(filename):
        """
        Touch a file.

        I.E. create it if it does not exist or change the last modified time
        to the current time if it does.
        """
        logger.debug("Touching: {}".format(filename))
        pathlib.Path(filename).touch()
        logger.debug("Touched!")

    @staticmethod
    def get_last_modified(filename):
        modified_time = os.path.getmtime(filename)
        logger.debug("Filename: {}".format(filename))
        logger.debug("Modified time: {}".format(modified_time))
        return modified_time

    def get_filename(self, player):
        """Get the full path to the queue file of a player"""
        return os.path.join(
            player.working_dir,
            self.filename
        )

    def first_n(self, n):
        """
        Get the `n` players that are first in line
        """
        return sorted(
            self.players,
            key=lambda p: self.get_last_modified(self.get_filename(p)),
            # reverse=True,
        )[:n]

    def requeue(self, players):
        """
        Put the given players at the end of the queue

        In this case this is done by touching their respective queue files
        in the order the players are passed.
        """
        for player in players:
            self.touch(self.get_filename(player))


if __name__ == '__main__':
    # Parse command line arguments
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('config_file')
    parser.add_argument('-l', '--level', default='INFO')
    parser.add_argument('-s', '--simulate', action="store_true")
    args = parser.parse_args()

    # Initialise logging
    logging.basicConfig(level=args.level)

    # Race
    controller = Controller.load_config(args.config_file)
    controller.race_and_save(simulate=args.simulate)
    logger.info("Done!")

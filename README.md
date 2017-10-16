# torcs-server
Install torcs and run tournaments using ELO rankings.

Useful information can be found on [this blog](http://www.xed.ch/help/torcs.html).

# Installation
First create a patched version of Torcs, by either finding readily patched source code or patching it yourself (see [Patching](#patching).

## Easy
Make sure you're using a patched version of TORCS 1.3.7 and place the zip (`torcs-1.3.7-patched.zip`) in the root of this repository. Now run `./easy-install.sh`. Done!

## Manual
Place the patched source code anywhere (just remember where) and run the following command to install the necessary requirements (taken from [this pdf](https://arxiv.org/pdf/1304.1672.pdf) and experience).

```bash
xargs sudo apt-get install < system_requirements.txt
```

Now `cd` into your version of the patched Torcs source code and run:

```bash

./configure
make
sudo make install
make datainstall
```

# Patching
To install a patched version of Torcs, download version 1.3.4 (or 1.3.7?) and [this patch](https://sourceforge.net/projects/cig/files/SCR%20Championship/Server%20Linux/2.1/) (linked from [here](http://cs.adelaide.edu.au/~optlog/SCR2015/software.html)) and put them in the root of this repository.


... (documentation missing)

# Running the system
To run a race make sure you have a `.yml` configuration file that satisfies your wishes (see Configuration details) and run:

```bash
./torcs_tournament.py path/to/configuration_file.yml
```

For more advanced command line options run `./torcs_tournament.py --help`.

## Configuration details
There are two types of configuration files: the `.yml` files are used by the Python application and the `.xml` files are used by TORCS. Only the `.yml` files are documented here.

The `.yml` files contain keyword arguments for the constructors of the `Player`, `Rater`, `Controller` and `FileBasedQueue` classes under the keys `players`, `rater`, `controller` and `queue` keys, respectively. The following example shows the accepted keys and their default values, with `<!this kind of description!>` for values that must be specified by the user and `<this kind of description>` for automatic values. If a value (or key) is not described using `<!this kind of description!>`, it may be left out and the default or automatic value will be used.

```yaml
players:
    # All occurrences of `{port}` in `start_command` will be replaced by the
    # correct port before running the command. `start_command` is issued with
    # `working_dir` as working directory and `process_owner` as user. If
    # `process_owner` is not specified, `token` will be used.
    #
    # The filenames `stdout` and `stderr` are relative to `output_dir`.

    <!team token!>:
        working_dir: <!path to the team folder!>
        # Rating of the `Player`, read from ratings file or initialised at
        # 1200 if not specified in the ratings file. If this key is specified
        # in the configuration file it will overwrite the rating of the
        # player at the start of every run.
        rating: <see comment>
        start_command: ['./start.sh', '-p', '{port}']
        output_dir: './output/'
        stdout: './{timestamp}-stdout.txt'
        stderr: './{timestamp}-stderr.txt'
        process_owner: <the team token>
    <!a second team token!>:
        ...
    <!another team token!>:
        ...
    ...
rater:
    filename: <!path to the ratings file!>
    ignore_unknown_ratings: False
controller:
    torcs_config_file: <!path to TORCS configuration file!>
    server_stdout: '{timestamp}-server_out.txt'
    server_stderr: '{timestamp}-server_err.txt'
    separate_player_uid: False
    result_path: '~/.torcs/results/'
    result_filename_format: "{driver} - {base}"
    timestamp_format: '%Y-%m-%d-%H.%M'
    # Specifies which TORCS driver names correspond to which ports
    driver_to_port:
        scr_server 1: 3001
        scr_server 2: 3002
        scr_server 3: 3003
        scr_server 4: 3004
        scr_server 5: 3005
        scr_server 6: 3006
        scr_server 7: 3007
        scr_server 8: 3008
        scr_server 9: 3009
        scr_server 10: 3010
    # If specified a backup of the ratings file will be made after the race
    rater_backup_filename: None
    # Time to wait before (forcefully) terminating child processes in seconds
    # after a race
    shutdown_wait: 1
    # Time to wait before checking all player processes are still alive when
    # starting a race
    crash_check_wait: 0.2
queue:
    # Filename used to check the last modified time, relative to
    # `Player.working_dir`.
    filename: 'start.sh'
```

Instead of specifying the players in the main configuration file, the `players` key may also contain a path to a `.yml` file containing the player specification, e.g.:

```yaml
# Main configuration file
players: path/to/player_config.yml
# Other settings
...
```

```yaml
# player_config.yml
<!team token!>:
    # Config
    ...
<!a second team token!>:
    ...
<!another team token!>:
    ...
...
```

# Ratings file
If the ratings file does not exist, a new file is created. All tokens specified in the configuration are added to the (new) ratings file. This means that you do not have to edit the ratings file if you do not want to do anything fancy.

The ratings file used in `torcs_tournament.Controller` must be a csv file with lines containing the group token and (optionally) the player rating. If no rating is given the value `elo.INITIAL` is used. A token may appear only once in the file. An example file would look as follows:

```
random_token1,1500
random_token3
random_token5,400
random_token6,400
```

# TORCS configuration file
The easiest way to create a TORCS configuration file is to start TORCS (run `torcs`) and configure a race using the UI. The configuration file can now be found under `~/.torcs/config/raceman/<name-of-race-type>.xml`.

For the section `Drivers` the section numbering determines the racing order, while the `idx` attribute determines "which" SCR server is used, thus which port number is used. The SCR server uses port `300{idx}`, where `idx` ranges from 0 to 9.

# Results
The results are saved to a file in each players working directory

# To Do
 - [X] Read player names from torcs config file and choose ports accordingly in `Controller.race_once`
 - [ ] Feed player configuration to the constructor instead of just setting them as attributes

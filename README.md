# TORCS Controller
Install torcs and run tournaments using ELO rankings.

Useful information can be found on [this blog](http://www.xed.ch/help/torcs.html).

# Installation
If you have installed a patched version of TORCS (which can be found on your path), set up the system by installing the required packages:

```bash
pip install -r requirements.txt
```

# Running the system
To run a race make sure you have a `.yml` configuration file that satisfies your wishes (see [Configuration details](#configuration-details)) and run:

```bash
./torcs_tournament.py path/to/configuration_file.yml
```

For more advanced command line options run `./torcs_tournament.py --help`.

To use the example files, first **make sure the full path pointing to your copy of this repository does not contain any spaces**. Change the working directory of `player` in `example_players.yml` to point to somewhere you cloned [this python client](https://www.github.com/mpvharmelen/torcs-client) (or any other client that can be started using the start command specified in the [Configuration Details](#configuration-details)), `cd` to the root of this repository and run:

```bash
./torcs_tournament.py example_config.yml
```

# TORCS Installation
First make sure you have a patched version of torcs, by either finding readily patched source code or patching it yourself (see [Patching](#patching)).

## Easy installation
Make sure you're using a patched version of TORCS 1.3.7 and place the zip (`torcs-1.3.7-patched.zip`) in the root of this repository. Now run `./easy-install.sh`. Done!

## Manual installation
Place the patched source code anywhere (just remember where) and `cd` into it.
Run the following command to install the necessary requirements (taken from [this pdf](https://arxiv.org/pdf/1304.1672.pdf) and experience).

```bash
xargs sudo apt-get install < system_requirements.txt
```

Now run the following commands to install TORCS. (Don't be afraid of the warnings.)

```bash
./configure
make
sudo make install
make datainstall
```

## Patching
The computational intelligence course uses version 1.3.7. Patching this version, however, is **not** tested. If you really want to patch your own TORCS installation instead of using the provided patched source for version 1.3.7, follow these instructions. These instructions are to patch the source of TORCS version 1.3.**4**. Try patching version 1.3.7 at your own risk 😊

To create your own patched version of torcs, download version 1.3.4 (or 1.3.7 at your own risk) and [this patch](https://sourceforge.net/projects/cig/files/SCR%20Championship/Server%20Linux/2.1/) (linked from the [SCRC 2015 software page](http://cs.adelaide.edu.au/~optlog/SCR2015/software.html)).

Unpack the TORCS source and the unpack the patch *inside* the source directory. `cd` to the patch directory (e.g. `cd torcs-1.3.4/scr-patch`) and run `sh ./do_patch.sh`.

In the TORCS source, on line `373` of `torcs-1.3.4/src/drivers/olethros/geometry.cpp` add `std::` just before `isnan` (which is at position `17`). In programmer jargon: insert `std::` at `torcs-1.3.4/src/drivers/olethros/geometry.cpp:373:17`.

That was it! Now follow the [manual installation instructions](#manual-installation).

# Configuration details
There are two types of configuration files: the `.yml` files are used by the Python application and the `.xml` files are used by TORCS. Only the `.yml` files are documented here.

The `.yml` files contain keyword arguments for the constructors of the `Player`, `Rater`, `Controller` and `FileBasedQueue` classes under the keys `players`, `rater`, `controller` and `queue` keys, respectively. The following example shows the accepted keys and their default values, with `<!this kind of description!>` for values that must be specified by the user and `<this kind of description>` for automatic values. If a value (or key) is not described using `<!this kind of description!>`, it may be left out and the default or automatic value will be used.

```yaml
players:
    # All occurrences of `{port}` in `start_command` will be replaced by the
    # correct port before running the command. `start_command` is issued with
    # `working_dir` as working directory and, depending on the controller
    # settings, with `process_owner` as user. If `process_owner` is not
    # specified, `token` will be used.
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
        output_dir: ./output/
        stdout: ./{timestamp}-stdout.txt
        stderr: ./{timestamp}-stderr.txt
        message_file: ./current_rating.txt
        rating_message: "Your current rating is: {rating}"
        process_owner: <the team token>
    <!a second team token!>:
        ...
    <!another team token!>:
        ...
    ...
rater:
    filename: <!path to the ratings file!>
    ignore_unknown_players: False
queue:
    # Filename used to check the last modified time, relative to
    # `Player.working_dir`.
    filename: start.sh
controller:
    # NB. The full path to the TORCS config file may not contain spaces,
    #     even if you only specify a relative path.
    torcs_config_file: <!path to TORCS configuration file!>
    server_stdout: {timestamp}-server_out.txt
    server_stderr: {timestamp}-server_err.txt
    # Whether to run each player process with their own UID
    separate_player_uid: False
    set_file_owner: False
    set_file_mode: False
    # The maximum number of times a race can be restarted with a different
    # player because a player crashed too early
    max_attempts: <the number of players>
    # If specified a backup of the ratings file will be made after the race
    rater_backup_filename: None
    result_filename_format: "{driver} - {base}"
    timestamp_format: %Y-%m-%d-%H.%M
    result_path: ~/.torcs/results/
    torcs_command: ['torcs', '-r', '{config_file}']
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
    # Whether to raise an exception if TORCS completed to quickly
    raise_on_too_fast_completion: True
    # If TORCS completed faster than this, a warning is issued
    torcs_min_time: 1
    # Time to wait after starting TORCS to ask for its child processes
    torcs_child_wait: 0.5
    # Time to wait before terminating child processes in seconds
    # after a race and forcefully killing them after terminating them
    shutdown_wait: 1
    # Time to wait before checking all player processes are still alive when
    # starting a race
    crash_check_wait: 0.2
    # File mode specified as (base ten) integer.
    # Read, write, execute for owner only: 0o700 = 448
    file_mode: 448
    # Whether to stop Dropbox before a race
    stop_dropbox: False
    dropbox_stop_command: ['dropbox', 'stop']
    # Whether to start Dropbox again after a race
    start_dropbox: False
    dropbox_start_command: ['dropbox', 'start']
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
The easiest way to create a TORCS configuration file is to start TORCS (run `torcs`) and configure a race using the GUI. The configuration file can now be found under `~/.torcs/config/raceman/<name-of-race-type>.xml`.

For the section `Drivers` the section numbering determines the racing order, while the `idx` attribute determines "which" SCR server is used, thus which port number is used. The SCR server uses port `300{idx+1}`, where `idx` ranges from 0 to 9.

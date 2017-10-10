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
**COMMAND**

The configuration file contains key/value pairs that are fed to the constructors of the controller (`Controller`) and the players (`Player`).

The format of the configuration file is as follows:

```yaml
players:
    some_token:
        settings_key: value
        another_key: value2
    another_token:
        a_third_key: value
        settings_key: value4
controller:
    fookey: foovalue
    barkey: barvalue
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

# torcs-server
Install torcs and run tournaments using ELO rankings.

Useful information can be found on [this blog](http://www.xed.ch/help/torcs.html).

# Installation
First create a patched version of Torcs, by either finding readily patched source code or patching it yourself (see [Patching](#patching).

Place it anywhere (just remember where) and run the following command to install the necessary requirements (taken from [this pdf](https://arxiv.org/pdf/1304.1672.pdf) and experience).

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

# Ratings file
The ratings file used in `torcs_tournament.Controller` must be a csv file with lines containing the group token and (optionally) the player rating. If no rating is given the value `elo.INITIAL` is used. A token may appear only once in the file. An example file would look as follows:

```
random_token1,1500
random_token3
random_token5,400
random_token6,400
```

# Running the system
If not settings are changed

# TORCS configuration file
The easiest way to create a TORCS configuration file is to start TORCS (run `torcs`) and configure a race using the UI. The configuration file can now be found under `~/.torcs/config/raceman/<name-of-race-type>.xml`.

For the section `Drivers` the section numbering determines the racing order, while the `idx` attribute determines "which" SCR server is used, thus which port number is used. The SCR server uses port `300{idx}`, where `idx` ranges from 0 to 9.

# To Do
 - [ ] Read player names from torcs config file and choose ports accordingly in `Controller.race_once`

#! /bin/bash


# Needed for this script
sudo apt-get install -y build-essential unzip

# Needed for TORCS
xargs sudo apt-get install -y < system_requirements.txt

unzip torcs-1.3.7-patched.zip

cd torcs-1.3.7-patched

./configure
make
sudo make install
make datainstall

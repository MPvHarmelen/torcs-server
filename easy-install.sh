#! /bin/bash

xargs sudo apt-get install < system_requirements.txt

unzip torcs-1.3.7-patched.zip

cd torcs-1.3.7-patched.zip

./configure
make
sudo make install
make datainstall

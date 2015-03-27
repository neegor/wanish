#!/usr/bin/env bash

sudo apt-get update
sudo apt-get -y install  python3-setuptools
sudo easy_install3 -U pip
sudo apt-get -y install python3-dev libxml2-dev libxslt-dev zlib1g-dev
sudo pip3 install requests lxml cssselect chardet numpy snowballstemmer networkx
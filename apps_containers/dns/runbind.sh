#!/bin/bash

cd /var/cache/bind

exec /usr/sbin/named -4 -g

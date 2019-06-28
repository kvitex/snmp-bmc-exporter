#!/bin/sh
export FLASK_APP=$1
/usr/bin/env python3 -m flask run --host=$2 --port=$3
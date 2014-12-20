#!/bin/sh
# +------------------------------------------------------------------+
# |             ____ _               _        __  __ _  __           |
# |            / ___| |__   ___  ___| | __   |  \/  | |/ /           |
# |           | |   | '_ \ / _ \/ __| |/ /   | |\/| | ' /            |
# |           | |___| | | |  __/ (__|   <    | |  | | . \            |
# |            \____|_| |_|\___|\___|_|\_\___|_|  |_|_|\_\           |
# |                                                                  |
# | Copyright Mathias Kettner 2014             mk@mathias-kettner.de |
# +------------------------------------------------------------------+
#
# This file is part of Check_MK.
# The official homepage is at http://mathias-kettner.de/check_mk.
#
# check_mk is free software;  you can redistribute it and/or modify it
# under the  terms of the  GNU General Public License  as published by
# the Free Software Foundation in version 2.  check_mk is  distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;  with-
# out even the implied warranty of  MERCHANTABILITY  or  FITNESS FOR A
# PARTICULAR PURPOSE. See the  GNU General Public License for more de-
# ails.  You should have  received  a copy of the  GNU  General Public
# License along with GNU Make; see the file  COPYING.  If  not,  write
# to the Free Software Foundation, Inc., 51 Franklin St,  Fifth Floor,
# Boston, MA 02110-1301 USA.

# This is an example for migration of RRD data. Many things are hard
# coded here. But it might be a starting point for writing your own
# migration script.

NEU=CPU_load.rrd
ALT=CPU_load_5min.rrd

if [ ! -f $ALT -o ! -f $NEU ] ; then
    echo "Ausgelassen, RRDs nicht da"
    exit 0
fi


DS1=DS:1:GAUGE:8640:0:100
DS2=DS:2:GAUGE:8640:0:100
DS3=DS:3:GAUGE:8640:0:100
RRA=$(grep -v '#' < /etc/nagios/rra.cfg )

echo -n "Sauge alte RRD-Datenbank $ALT aus..."
rrdtool dump $ALT \
   | sed -n 's/<!.*\/ \(1214......\).*<v> \([^ ]*\) .*/\1:\2:\2:\2/p' \
   | sort -n \
   > werte
echo OK

echo -n "Ermittle aeltesten Zeitstempel..."
FIRST=$(head -n1 werte | cut -d: -f1)
echo "$FIRST"

echo -n "Lege RRD-Datenbank $NEU.neu an..."

rrdtool create $NEU.neu -s 60 -b $FIRST $DS1 $DS2 $DS3 $RRA && echo OK || exit 1
chown nagios.nagios $NEU.neu

echo -n "Speise Daten aus $ALT ein..."
   xargs -n 1 rrdtool update $NEU.neu < werte 2>/dev/null
rm -f werte
mv $NEU.neu $NEU
echo OK

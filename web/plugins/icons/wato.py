#!/usr/bin/python
# -*- encoding: utf-8; py-indent-offset: 4 -*-
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

import wato

def wato_link(folder, site, hostname, where):
    if not config.wato_enabled:
        return ""

    if 'X' in html.display_options:
        url = "wato.py?folder=%s&host=%s" % \
           (html.urlencode(folder), html.urlencode(hostname))
        if where == "inventory":
            url += "&mode=inventory"
            help = _("Edit services")
            icon = "services"
        else:
            url += "&mode=edithost"
            help = _("Edit this host")
            icon = "wato"
        return '<a href="%s">%s</a>' % (url, html.render_icon(icon, help))
    else:
        return ""

def paint_wato(what, row, tags, custom_vars):
    if not wato.may_see_hosts() or html.mobile:
        return

    filename = row["host_filename"]
    if filename.startswith("/wato/") and filename.endswith("hosts.mk"):
        wato_folder = filename[6:-8].rstrip("/")
        if what == "host":
            return wato_link(wato_folder, row["site"], row["host_name"], "edithost")
        elif row["service_description"] in [ "Check_MK inventory", "Check_MK Discovery" ]:
            return wato_link(wato_folder, row["site"], row["host_name"], "inventory")

multisite_icons.append({
 'host_columns': [ "filename" ],
 'paint':  paint_wato,
})



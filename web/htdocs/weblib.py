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

import config
import lib
import re

def ajax_tree_openclose():
    html.load_tree_states()

    tree = html.var("tree")
    name = html.var_utf8("name")

    if not tree or not name:
        MKUserError('tree or name parameter missing')

    html.set_tree_state(tree, name, html.var("state"))
    html.save_tree_states()
    html.write('OK') # Write out something to make debugging easier

#   .--Row Selector--------------------------------------------------------.
#   |      ____                 ____       _           _                   |
#   |     |  _ \ _____      __ / ___|  ___| | ___  ___| |_ ___  _ __       |
#   |     | |_) / _ \ \ /\ / / \___ \ / _ \ |/ _ \/ __| __/ _ \| '__|      |
#   |     |  _ < (_) \ V  V /   ___) |  __/ |  __/ (__| || (_) | |         |
#   |     |_| \_\___/ \_/\_/   |____/ \___|_|\___|\___|\__\___/|_|         |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   | Saves and loads selected row information of the current user         |
#   +----------------------------------------------------------------------+

import os, time
from lib import make_nagios_directory

def init_selection():
    # Generate the initial selection_id
    selection_id()

    cleanup_old_selections()

def cleanup_old_selections():
    # Loop all selection files and compare the last modification time with
    # the current time and delete the selection file when it is older than
    # the livetime.
    path = config.user_confdir + '/rowselection'
    try:
        for f in os.listdir(path):
            if f[1] != '.' and f.endswith('.mk'):
                p = path + '/' + f
                if time.time() - os.stat(p).st_mtime > config.selection_livetime:
                    os.unlink(p)
    except OSError:
        pass # no directory -> no cleanup

# Generates a selection id or uses the given one
def selection_id():
    if not html.has_var('selection'):
        sel_id = lib.gen_id()
        html.set_var('selection', sel_id)
        return sel_id
    else:
        sel_id = html.var('selection')
        # Avoid illegal file access by introducing .. or /
        if not re.match("^[-0-9a-zA-Z]+$", sel_id):
            new_id = lib.gen_id()
            html.set_var('selection', new_id)
            return new_id
        else:
            return sel_id

def get_rowselection(ident):
    vo = config.load_user_file("rowselection/%s" % selection_id(), {})
    return vo.get(ident, [])

def set_rowselection(ident, rows, action):
    vo = config.load_user_file("rowselection/%s" % selection_id(), {}, True)

    if action == 'set':
        vo[ident] = rows

    elif action == 'add':
        vo[ident] = list(set(vo.get(ident, [])).union(rows))

    elif action == 'del':
        vo[ident] = list(set(vo.get(ident, [])) - set(rows))

    elif action == 'unset':
        del vo[ident]

    if not os.path.exists(config.user_confdir + '/rowselection'):
        make_nagios_directory(config.user_confdir + '/rowselection')

    config.save_user_file("rowselection/%s" % selection_id(), vo, True)

def ajax_set_rowselection():
    ident = html.var('id')

    action = html.var('action', 'set')
    if action not in [ 'add', 'del', 'set', 'unset' ]:
        raise MKUserError(_('Invalid action'))

    rows  = html.var('rows', '').split(',')

    set_rowselection(ident, rows, action)

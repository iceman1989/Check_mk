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

pagehandlers.update({
    "wato"                    : wato.page_handler,
    "wato_ajax_replication"   : wato.ajax_replication,
    "wato_ajax_activation"    : wato.ajax_activation,
    "automation_login"        : wato.page_automation_login,
    "automation"              : wato.page_automation,
    "user_profile"            : wato.page_user_profile,
    "user_change_pw"          : lambda: wato.page_user_profile(change_pw=True),
    "ajax_set_foldertree"     : wato.ajax_set_foldertree,
    "wato_ajax_diag_host"     : wato.ajax_diag_host,
    "wato_ajax_profile_repl"  : wato.ajax_profile_repl,
    "wato_ajax_execute_check" : wato.ajax_execute_check,
})

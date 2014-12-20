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


declare_user_attribute(
    "force_authuser",
    Checkbox(
        title = _("Visibility of Hosts/Services"),
        label = _("Only show hosts and services the user is a contact for"),
        help = _("When this option is checked, then the status GUI will only "
                 "display hosts and services that the user is a contact for - "
                 "even if he has the permission for seeing all objects."),
    ),
    permission = "general.see_all"
)

declare_user_attribute(
    "force_authuser_webservice",
    Checkbox(
        title = _("Visibility of Hosts/Services (Webservice)"),
        label = _("Export only hosts and services the user is a contact for"),
        help = _("When this option is checked, then the Multisite webservice "
                 "will only export hosts and services that the user is a contact for - "
                 "even if he has the permission for seeing all objects."),
    ),
    permission = "general.see_all"
)


declare_user_attribute(
    "disable_notifications",
    Checkbox(
        title = _("Disable Notifications"),
        label = _("Temporarily disable <b>all</b> notifications!"),
        help = _("When this option is active the you will not get <b>any</b> "
                 "alerts or other notifications via email, SMS or similar. "
                 "This overrides all other notification settings or rules, so make "
                 "sure that you know what you do."),
    ),
    permission = "general.disable_notifications",
    domain = "check_mk",
)

declare_user_attribute(
    "start_url",
    TextAscii(title = _("Start-URL to display in main frame"),
              help = _("When you point your browser to the Multisite GUI, usually the dashboard "
                       "is shown in the main (right) frame. You can replace this with any other "
                       "URL you like here."),
              size = 80,
              default_value = "dashboard.py",
              attrencode = True),
    domain = "multisite")


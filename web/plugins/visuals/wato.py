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

class FilterWatoFile(Filter):
    def __init__(self):
        Filter.__init__(self, "wato_folder", _("WATO Folder"), "host", ["filename"], [])
        self.last_wato_data_update = None

    def available(self):
        return config.wato_enabled and wato.have_folders()

    def load_wato_data(self):
        self.tree = wato.get_folder_tree()
        self.path_to_tree = {} # will be filled by self.folder_selection
        self.selection = self.folder_selection(self.tree, "", 0)
        self.last_wato_data_update = time.time()

    def check_wato_data_update(self):
        if not self.last_wato_data_update or time.time() - self.last_wato_data_update > 5:
            self.load_wato_data()

    def display(self):
        self.check_wato_data_update()
        # Note: WATO Folders that the user has not permissions to must not be visible.
        # Permissions in this case means, that the user has view permissions for at
        # least one host in that folder.
        result = html.live.query("GET hosts\nCache: reload\nColumns: filename\nStats: state >= 0\n")
        allowed_folders = set([""])
        for path, host_count in result:
            # convert '/wato/server/hosts.mk' to 'server'
            folder = path[6:-9]
            # allow the folder an all of its parents
            parts = folder.split("/")
            subfolder = ""
            for part in parts:
                if subfolder:
                    subfolder += "/"
                subfolder += part
                allowed_folders.add(subfolder)

        html.select(self.name, [("", "")] + [ entry for entry in self.selection if (entry[0] in allowed_folders) ])

    def filter(self, infoname):
        self.check_wato_data_update()
        current = html.var(self.name)
        if current:
            return "Filter: host_filename ~ ^/wato/%s/\n" % current.replace("\n", "") # prevent insertions attack
        else:
            return ""

    # Construct pair-list of ( folder-path, title ) to be used
    # by the HTML selection box. This also updates self._tree,
    # a dictionary from the path to the title.
    def folder_selection(self, folder, prefix, depth):
        my_path = folder[".path"]
        if depth:
            title_prefix = "&nbsp;&nbsp;&nbsp;" * depth + "` " + "- " * depth
        else:
            title_prefix = ""
        self.path_to_tree[my_path] = folder["title"]
        sel = [ (my_path , title_prefix + folder["title"]) ]
        sel += self.sublist(folder.get(".folders", {}), my_path, depth)
        return sel

    def sublist(self, elements, my_path, depth):
        vs = elements.values()
        vs.sort(lambda a, b: cmp(a["title"].lower(), b["title"].lower()))
        sel = []
        for e in vs:
            sel += self.folder_selection(e, my_path, depth + 1)
        return sel

    def heading_info(self):
        # FIXME: There is a problem with caching data and changing titles of WATO files
        # Everything is changed correctly but the filter object is stored in the
        # global multisite_filters var and self.path_to_tree is not refreshed when
        # rendering this title. Thus the threads might have old information about the
        # file titles and so on.
        # The call below needs to use some sort of indicator wether the cache needs
        # to be renewed or not.
        self.check_wato_data_update()
        current = html.var(self.name)
        if current and current != "/":
            return self.path_to_tree.get(current)

declare_filter(10, FilterWatoFile())

if "wato_folder" not in ubiquitary_filters:
    ubiquitary_filters.append("wato_folder") # show in all views

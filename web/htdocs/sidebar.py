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

import config, defaults, livestatus, views, pprint, os, copy, userdb
import notify, urlparse
from lib import *

# Constants to be used in snapins
snapin_width = 230


# Datastructures and functions needed before plugins can be loaded
loaded_with_language = False
sidebar_snapins = {}
search_plugins  = []

def load_plugins():
    global loaded_with_language
    if loaded_with_language == current_language:
        return

    # Load all snapins
    global sidebar_snapins
    sidebar_snapins = {}
    global search_plugins
    search_plugins = []
    load_web_plugins("sidebar", globals())

    # This must be set after plugin loading to make broken plugins raise
    # exceptions all the time and not only the first time (when the plugins
    # are loaded).
    loaded_with_language = current_language

    # Declare permissions: each snapin creates one permission
    config.declare_permission_section("sidesnap", _("Sidebar snapins"), do_sort = True)
    for name, snapin in sidebar_snapins.items():
        config.declare_permission("sidesnap.%s" % name,
            snapin["title"],
            snapin["description"],
            snapin["allowed"])

# Helper functions to be used by snapins
def link(text, url, target="main", onclick = None):
    # Convert relative links into absolute links. We have three kinds
    # of possible links and we change only [3]
    # [1] protocol://hostname/url/link.py
    # [2] /absolute/link.py
    # [3] relative.py
    if not (":" in url[:10]) and not url.startswith("javascript") and url[0] != '/':
        url = defaults.url_prefix + "check_mk/" + url
    onclick = onclick and (' onclick="%s"' % html.attrencode(onclick)) or ''
    return '<a onfocus="if (this.blur) this.blur();" target="%s" ' \
           'class=link href="%s"%s>%s</a>' % \
            (html.attrencode(target or ""), html.attrencode(url), onclick, html.attrencode(text))

def simplelink(text, url, target="main"):
    html.write(link(text, url, target) + "<br>\n")

def bulletlink(text, url, target="main", onclick = None):
    html.write("<li class=sidebar>" + link(text, url, target, onclick) + "</li>\n")

def iconlink(text, url, icon):
    linktext = '<img class=iconlink src="images/icon_%s.png">%s' % \
         (html.attrencode(icon), html.attrencode(text))
    html.write('<a target=main class="iconlink link" href="%s">%s</a><br>' % \
            (html.attrencode(url), linktext))

def begin_footnote_links():
    html.write("<div class=footnotelink>")

def end_footnote_links():
    html.write("</div>\n")

def footnotelinks(links):
    begin_footnote_links()
    for text, target in links:
        html.write(link(text, target))
    end_footnote_links()

def iconbutton(what, url, target="side", handler="", name="", css_class = ""):
    if target == "side":
        onclick = "onclick=\"get_url('%s', %s, '%s')\"" % \
                   (url, handler, name)
        href = "#"
        tg = ""
    else:
        onclick = ""
        href = "%scheck_mk/%s" % (defaults.url_prefix, url)
        tg = "target=%s" % target
    css_class = css_class and " " + css_class or ""
    html.write("<a href=\"%s\" %s %s><img class=\"iconbutton%s\" onmouseover=\"hilite_icon(this, 1)\" onmouseout=\"hilite_icon(this, 0)\" align=absmiddle src=\"%scheck_mk/images/button_%s_lo.png\"></a>\n " % (href, onclick, tg, css_class, defaults.url_prefix, what))

def nagioscgilink(text, target):
    html.write("<li class=sidebar><a target=\"main\" class=link href=\"%snagios/cgi-bin/%s\">%s</a></li>" % \
            (defaults.url_prefix, target, html.attrencode(text)))

def heading(text):
    html.write("<h3>%s</h3>\n" % html.attrencode(text))

# Load current state of user's sidebar. Convert from
# old format (just a snapin list) to the new format
# (dictionary) on the fly
def load_user_config():
    path = config.user_confdir + "/sidebar.mk"
    try:
        user_config = eval(file(path).read())
        if type(user_config) == list:
            user_config = {
                "snapins" : user_config,
                "fold":     False,
            }
    except:
        user_config = {
            "snapins": config.sidebar,
            "fold":    False,
        }

    # Remove entries the user is not allowed for or which have state "off" (from legacy version)
    # silently skip configured but not existant snapins
    user_config["snapins"] = [
          entry for entry in user_config["snapins"]
                if entry[0] in sidebar_snapins
                   and entry[1] != "off"
                   and config.may("sidesnap." + entry[0])]

    return user_config

def save_user_config(user_config):
    if config.may("general.configure_sidebar"):
        config.save_user_file("sidebar", user_config)

def sidebar_head():
    html.write('<div id="side_header">')
    html.write('<div id="side_fold"></div>')
    html.write('<a title="%s" target="main" href="%s">'
               '<div id="side_version">%s</div>'
               '</a>'
               '</div>\n' % (_("Go to main overview"), html.attrencode(config.user.get("start_url") or config.start_url), defaults.check_mk_version))

def render_messages():
    for msg in notify.get_gui_messages():
        if 'gui_hint' in msg['methods']:
            html.write('<div class="popup_msg" id="message-%s">' % msg['id'])
            html.write('<a href="javascript:void(0)" class="close" onclick="message_close(\'%s\')">x</a>' % msg['id'])
            html.write(html.attrencode(msg['text']).replace('\n', '<br />\n'))
            html.write('</div>\n')
        if 'gui_popup' in msg['methods']:
            html.javascript('alert(\'%s\'); mark_message_read("%s")' %
                (html.attrencode(msg['text']).replace('\n', '\\n'), msg['id']))

def ajax_get_messages():
    render_messages()

def ajax_message_read():
    try:
        notify.delete_gui_message(html.var('id'))
        html.write("OK")
    except:
        if config.debug:
            raise
        html.write("ERROR")

def sidebar_foot():
    html.write('<div id="side_footer">')
    if config.may("general.configure_sidebar"):
        html.icon_button("sidebar_add_snapin.py", _("Add snapin to the sidebar"), "sidebar_addsnapin",
                         target="main")
    # editing the profile is not possible on remote sites which are sync targets
    # of a central WATO system
    if config.wato_enabled and \
       (config.may("general.edit_profile") or config.may("general.change_password")):
        html.icon_button("user_profile.py", _("Edit your personal settings, change your password"),
            "sidebar_settings", target="main")
    if config.may("general.logout") and not config.auth_by_http_header:
        html.icon_button("logout.py", _("Log out"), "sidebar_logout", target="_top")

    html.icon_button("return void();", _("You have pending messages."),
                     "sidebar_messages", onclick = 'read_message()', id = 'msg_button', style = 'display:none')
    html.write('<div id="messages" style="display:none;">')
    render_messages()
    html.write('</div>')

    html.write("<div class=copyright>%s</div>\n" %
        _("&copy; <a target=\"_blank\" href=\"http://mathias-kettner.de\">Mathias Kettner</a>"))
    html.write('</div>')

    if load_user_config()["fold"]:
        html.final_javascript("foldSidebar();")

# Standalone sidebar
def page_side():
    if not config.may("general.see_sidebar"):
        return
    if config.sidebar_notify_interval is not None:
        interval = config.sidebar_notify_interval
    else:
        interval = 'null'
    html.html_head(_("Check_MK Sidebar"), javascripts=["sidebar"], stylesheets=["sidebar", "status"])
    html.write('<body class="side')
    if config.screenshotmode:
        html.write(" screenshotmode")
    html.write('" onload="initScrollPos(); setSidebarHeight(); init_messages(%s);" '
               'onunload="storeScrollPos()">\n' % interval)
    html.write('<div id="check_mk_sidebar">\n')

    views.load_views()
    sidebar_head()
    user_config = load_user_config()
    refresh_snapins = []
    restart_snapins = []

    scrolling = ''
    if config.sidebar_show_scrollbar:
        scrolling = ' class=scroll'

    html.write('<div id="side_content"%s>' % scrolling)
    for name, state in user_config["snapins"]:
        if not name in sidebar_snapins or not config.may("sidesnap." + name):
            continue
        # Performs the initial rendering and might return an optional refresh url,
        # when the snapin contents are refreshed from an external source
        refresh_url = render_snapin(name, state)
        if sidebar_snapins.get(name).get("refresh", False):
            refresh_snapins.append([name, refresh_url])
        elif sidebar_snapins.get(name).get("restart", False):
            refresh_snapins.append([name, refresh_url])
            restart_snapins.append(name)
    html.write('</div>')
    sidebar_foot()
    html.write('</div>')

    html.write("<script language=\"javascript\">\n")
    if restart_snapins:
        html.write("sidebar_restart_time = %s\n" % time.time())
    html.write("sidebar_update_interval = %0.2f;\n" % config.sidebar_update_interval)
    html.write("registerEdgeListeners();\n")
    html.write("setSidebarHeight();\n")
    html.write("refresh_snapins = %r;\n" % refresh_snapins)
    html.write("restart_snapins = %r;\n" % restart_snapins)
    html.write("sidebar_scheduler();\n")
    html.write("window.onresize = function() { setSidebarHeight(); };\n")
    html.write("if (contentFrameAccessible()) { update_content_location(); };\n")
    html.write("</script>\n")

    html.body_end()

def render_snapin(name, state):
    snapin = sidebar_snapins.get(name)
    styles = snapin.get("styles")
    if styles:
        html.write("<style>\n%s\n</style>\n" % styles)

    html.write("<div id=\"snapin_container_%s\" class=snapin>\n" % name)
    if state == "closed":
        style = ' style="display:none"'
        headclass = "closed"
        minimaxi = "maxi"
    else:
        style = ""
        headclass = "open"
        minimaxi = "mini"
    toggle_url = "sidebar_openclose.py?name=%s&state=" % name

    html.write('<div class="head %s" ' % headclass)

    # If the user may modify the sidebar then add code for dragging the snapin
    if config.may("general.configure_sidebar"):
        html.write("onmouseover=\"document.body.style.cursor='move';\" "
                   "onmouseout=\"document.body.style.cursor='';\" "
                   "onmousedown=\"snapinStartDrag(event)\" onmouseup=\"snapinStopDrag(event)\">")
    else:
        html.write(">")


    # Icon for mini/maximizing, does not need permission
    html.write('<div class="minisnapin">')
    iconbutton(minimaxi + "snapin", None,
               "side", "toggle_sidebar_snapin(this, '%s')" % toggle_url, 'snapin_'+name)
    html.write('</div>')

    if config.may("general.configure_sidebar"):
        # Button for closing (removing) a snapin
        html.write('<div class="closesnapin">')
        iconbutton("closesnapin", "sidebar_openclose.py?name=%s&state=off" % name,
                   "side", "removeSnapin", 'snapin_'+name)
        html.write('</div>')

    # The heading. A click on the heading mini/maximizes the snapin
    html.write("<b class=heading onclick=\"toggle_sidebar_snapin(this,'%s')\" "
               "onmouseover=\"this.style.cursor='pointer'\" "
               "onmouseout=\"this.style.cursor='auto'\">%s</b>" % (toggle_url, snapin["title"]))

    # End of header
    html.write("</div>")

    # Now comes the content
    html.write("<div id=\"snapin_%s\" class=content%s>\n" % (name, style))
    refresh_url = ''
    try:
        url = snapin["render"]()
        # Fetch the contents from an external URL. Don't render it on our own.
        if not url is None:
            refresh_url = url
            html.write('<script>get_url("%s", updateContents, "snapin_%s")</script>' % (refresh_url, name))
    except Exception, e:
        snapin_exception(e)
    html.write('</div><div class="foot"%s></div>\n' % style)
    html.write('</div>')
    return refresh_url

def snapin_exception(e):
    if config.debug:
        raise
    else:
        html.write("<div class=snapinexception>\n"
                "<h2>%s</h2>\n"
                "<p>%s</p></div>" % (_('Error'), e))

def ajax_fold():
    config = load_user_config()
    config["fold"] = not not html.var("fold")
    save_user_config(config)


def ajax_openclose():
    config = load_user_config()
    new_snapins = []
    for name, usage in config["snapins"]:
        if html.var("name") == name:
            usage = html.var("state")
        if usage != "off":
            new_snapins.append((name, usage))
    config["snapins"] = new_snapins
    save_user_config(config)

def ajax_snapin():
    # Update online state of the user (if enabled)
    userdb.update_user_access_time(config.user_id)

    snapname = html.var("name")
    if snapname:
        snapnames = [ snapname ]
    else:
        snapnames = html.var('names', '').split(',')

    html.plug()
    snapin_code = []
    try:
        for snapname in snapnames:
            if not config.may("sidesnap." + snapname):
                continue
            snapin = sidebar_snapins.get(snapname)

            # When restart snapins are about to be refreshed, only render
            # them, when the core has been restarted after their initial
            # rendering
            if not snapin.get('refresh') and snapin.get('restart'):
                since = float(html.var('since', 0))
                newest = since
                for site in html.site_status.values():
                    prog_start = site.get("program_start", 0)
                    if prog_start > newest:
                        newest = prog_start
                if newest <= since:
                    # no restart
                    snapin_code.append('')
                    continue

            try:
                snapin["render"]()
            except Exception, e:
                snapin_exception(e)
            snapin_code.append(html.drain())

        html.unplug()
        html.write('[%s]' % ','.join([ '"%s"' % s.replace('"', '\\"').replace('\n', '') for s in snapin_code]))
    except Exception, e:
        html.flush()
        html.unplug()
        html.log('Exception during snapin refresh: %s' % e)
        raise

def move_snapin():
    if not config.may("general.configure_sidebar"):
        return

    snapname_to_move = html.var("name")
    beforename = html.var("before")

    user_config = load_user_config()

    # Get current state of snaping being moved (open, closed)
    snap_to_move = None
    for name, state in user_config["snapins"]:
        if name == snapname_to_move:
            snap_to_move = name, state
    if not snap_to_move:
        return # snaping being moved not visible. Cannot be.

    # Build new config by removing snaping at current position
    # and add before "beforename" or as last if beforename is not set
    new_snapins = []
    for name, state in user_config["snapins"]:
        if name == snapname_to_move:
            continue # remove at this position
        elif name == beforename:
            new_snapins.append(snap_to_move)
        new_snapins.append( (name, state) )
    if not beforename: # insert as last
        new_snapins.append(snap_to_move)

    user_config["snapins"] = new_snapins
    save_user_config(user_config)

def page_add_snapin():
    if not config.may("general.configure_sidebar"):
        raise MKGeneralException(_("You are not allowed to change the sidebar."))

    html.header(_("Available snapins"), stylesheets=["pages", "sidebar", "status"])
    used_snapins = [name for (name, state) in load_user_config()["snapins"]]

    addname = html.var("name")
    if addname in sidebar_snapins and addname not in used_snapins and html.check_transaction():
        user_config = load_user_config()
        user_config["snapins"].append((addname, "open"))
        save_user_config(user_config)
        used_snapins = [name for (name, state) in load_user_config()["snapins"]]
        html.reload_sidebar()

    names = sidebar_snapins.keys()
    names.sort()
    html.write('<div class="add_snapin">\n')
    for name in names:
        if name in used_snapins:
            continue
        if not config.may("sidesnap." + name):
            continue # not allowed for this user

        snapin = sidebar_snapins[name]
        title = snapin["title"]
        description = snapin.get("description", "")
        transid = html.get_transid()
        url = 'sidebar_add_snapin.py?name=%s&_transid=%s&pos=top' % (name, transid)
        html.write('<div class=snapinadder '
                   'onmouseover="this.style.cursor=\'pointer\';" '
                   'onmousedown="window.location.href=\'%s\'; return false;">' % url)

        html.write("<div class=snapin_preview>")
        html.write("<div class=clickshield></div>")
        render_snapin(name, "open")
        html.write("</div>")
        html.write("<div class=description>%s</div>" % (description))

        html.write("</div>")

    html.write("</div>\n")
    html.footer()


def ajax_speedometer():
    try:
        # Try to get values from last call in order to compute
        # driftig speedometer-needle and to reuse the scheduled
        # check reate.
        last_perc          = float(html.var("last_perc"))
        scheduled_rate     = float(html.var("scheduled_rate"))
        last_program_start = int(html.var("program_start"))

        # Get the current rates and the program start time. If there
        # are more than one site, we simply add the start times.
        data = html.live.query_summed_stats("GET status\n"
               "Columns: service_checks_rate program_start")
        current_rate = data[0]
        program_start = data[1]

        # Recompute the scheduled_rate only if it is not known (first call)
        # or if one of the sites has been restarted. The computed value cannot
        # change during the monitoring since it just reflects the configuration.
        # That way we save CPU resources since the computation of the
        # scheduled checks rate needs to loop over all hosts and services.
        if last_program_start != program_start:
            # These days, we configure the correct check interval for Check_MK checks.
            # We do this correctly for active and for passive ones. So we can simply
            # use the check_interval of all services. Hosts checks are ignored.
            #
            # Manually added services without check_interval could be a problem, but
            # we have no control there.
            scheduled_rate = html.live.query_summed_stats(
                        "GET services\n"
                        "Stats: suminv check_interval\n")[0] / 60.0

        percentage = 100.0 * current_rate / scheduled_rate;
        title = _("Scheduled service check rate: %.1f/s, current rate: %.1f/s, that is "
                  "%.0f%% of the scheduled rate" %
                  (scheduled_rate, current_rate, percentage))

    except Exception, e:
        scheduled_rate = 0
        program_start = 0
        percentage = 0
        last_perc = 0
        title = _("No performance data: ") + str(e)

    html.write(repr([scheduled_rate, program_start, percentage, last_perc, str(title)]))


def ajax_switch_masterstate():
    site = html.var("site")
    column = html.var("switch")
    state = int(html.var("state"))
    commands = {
        ( "enable_notifications",     1) : "ENABLE_NOTIFICATIONS",
        ( "enable_notifications",     0) : "DISABLE_NOTIFICATIONS",
        ( "execute_service_checks",   1) : "START_EXECUTING_SVC_CHECKS",
        ( "execute_service_checks",   0) : "STOP_EXECUTING_SVC_CHECKS",
        ( "execute_host_checks",      1) : "START_EXECUTING_HOST_CHECKS",
        ( "execute_host_checks",      0) : "STOP_EXECUTING_HOST_CHECKS",
        ( "enable_flap_detection",    1) : "ENABLE_FLAP_DETECTION",
        ( "enable_flap_detection",    0) : "DISABLE_FLAP_DETECTION",
        ( "process_performance_data", 1) : "ENABLE_PERFORMANCE_DATA",
        ( "process_performance_data", 0) : "DISABLE_PERFORMANCE_DATA",
        ( "enable_event_handlers",    1) : "ENABLE_EVENT_HANDLERS",
        ( "enable_event_handlers",    0) : "DISABLE_EVENT_HANDLERS",
    }

    command = commands.get((column, state))
    if command:
        html.live.command("[%d] %s" % (int(time.time()), command), site)
        html.live.set_only_sites([site])
        html.live.query("GET status\nWaitTrigger: program\nWaitTimeout: 10000\nWaitCondition: %s = %d\nColumns: %s\n" % \
               (column, state, column))
        html.live.set_only_sites()
        render_master_control()
    else:
        html.write(_("Command %s/%d not found") % (html.attrencode(column), state))

def ajax_del_bookmark():
    try:
        num = int(html.var("num"))
    except ValueError:
        raise MKGeneralException(_("Invalid bookmark id."))
    bookmarks = load_bookmarks()
    try:
        del bookmarks[num]
    except IndexError:
        raise MKGeneralException(_("Unknown bookmark id: %d. This is probably a problem with reload or browser history. Please try again.") % html.attrencode(num))
    save_bookmarks(bookmarks)
    render_bookmarks()

def ajax_add_bookmark():
    title = html.var("title")
    href = html.var("href")
    if title and href:
        bookmarks = load_bookmarks()
        referer = html.req.headers_in.get("Referer")

        if referer:
            ref_p = urlparse.urlsplit(referer)
            url_p = urlparse.urlsplit(href)

            # If http/https or user, pw, host, port differ, don't try to shorten
            # the URL to be linked. Simply use the full URI
            if ref_p.scheme == url_p.scheme and ref_p.netloc == url_p.netloc:
                # We try to remove http://hostname/some/path/check_mk from the
                # URI. That keeps the configuration files (bookmarks) portable.
                # Problem here: We have not access to our own URL, only to the
                # path part. The trick: we use the Referrer-field from our
                # request. That points to the sidebar.
                referer = ref_p.path
                href    = url_p.path
                if url_p.query:
                    href += '?' + url_p.query
                removed = 0
                while '/' in referer and referer.split('/')[0] == href.split('/')[0]:
                    referer = referer.split('/', 1)[1]
                    href = href.split('/', 1)[1]
                    removed += 1

                if removed == 1:
                    # removed only the first "/". This should be an absolute path.
                    href = '/' + href
                elif '/' in referer:
                    # there is at least one other directory layer in the path, make
                    # the link relative to the sidebar.py's topdir. e.g. for pnp
                    # links in OMD setups
                    href = '../' + href

        bookmarks.append((title, href))
        save_bookmarks(bookmarks)
    render_bookmarks()


def page_edit_bookmark():
    html.header(_("Edit Bookmark"))
    try:
        n = int(html.var("num"))
    except ValueError:
        raise MKGeneralException(_("Invalid bookmark id."))
    bookmarks = load_bookmarks()
    if n >= len(bookmarks):
        raise MKGeneralException(_("Unknown bookmark id: %d. This is probably a problem with reload or browser history. Please try again.") % html.attrencode(n))

    if html.var("save") and html.check_transaction():
        title = html.var("title")
        url = html.var("url")
        bookmarks[n] = (title, url)
        save_bookmarks(bookmarks)
        html.reload_sidebar()

    html.begin_form("edit_bookmark")
    if html.var("save"):
        title = html.var("title")
        url = html.var("url")
        bookmarks[n] = (title, url)
        save_bookmarks(bookmarks)
        html.reload_sidebar()
    else:
        title, url = bookmarks[n]
        html.set_var("title", title)
        html.set_var("url", url)

    html.write("<table class=edit_bookmarks>")
    html.write("<tr><td>%s</td><td>" % _('Title:'))
    html.text_input("title", size = 50)
    html.write("</td></tr><tr><td>%s:</td><td>" % _('URL'))
    html.text_input("url", size = 50)
    html.write("</td></tr><tr><td></td><td>")
    html.button("save", _("Save"))
    html.write("</td></tr></table>\n")
    html.hidden_field("num", str(n))
    html.end_form()

    html.footer()

def ajax_tag_tree():
    newconf = int(html.var("conf"))
    tree_conf = config.load_user_file("virtual_host_tree", {"tree": 0, "cwd": {}})
    if type(tree_conf) == int:
        tree_conf = {"cwd":{}} # convert from old style
    tree_conf["tree"] = newconf
    config.save_user_file("virtual_host_tree", tree_conf)

def ajax_tag_tree_enter():
    path = html.var("path") and html.var("path").split("|") or []
    tree_conf = config.load_user_file("virtual_host_tree", {"tree": 0, "cwd": {}})
    tree_conf["cwd"][tree_conf["tree"]] = path
    config.save_user_file("virtual_host_tree", tree_conf)


#.
#   .--Quicksearch---------------------------------------------------------.
#   |         ___        _      _                            _             |
#   |        / _ \ _   _(_) ___| | _____  ___  __ _ _ __ ___| |__          |
#   |       | | | | | | | |/ __| |/ / __|/ _ \/ _` | '__/ __| '_ \         |
#   |       | |_| | |_| | | (__|   <\__ \  __/ (_| | | | (__| | | |        |
#   |        \__\_\\__,_|_|\___|_|\_\___/\___|\__,_|_|  \___|_| |_|        |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   | Handles ajax search reuquests (like issued by the quicksearch dialog |
#   '----------------------------------------------------------------------'

def parse_search_query(s):
    types = {'h': 'hosts', 'hg': 'hostgroups', 's': 'services', 'sg': 'servicegroups'}

    found_filters = []
    if ":" in s:
        regex = "(^((hg)|h|(sg)|s)| (hg|h|sg|s)):"
        found = []
        matches = re.finditer(regex, s)
        for match in matches:
            found.append((match.group(1), match.start()))

        found_filters = []
        current_string = s
        for token_type, token_offset in found[-1::-1]:
            found_filters.append( (types[token_type.lstrip()],
                                   to_regex(current_string[token_offset+len(token_type)+1:]).strip()) )
            current_string = current_string[:token_offset]

    if found_filters:
        return found_filters
    else:
        return [("hosts", to_regex(s))]

# Ensures the provided search string is a regex, does some basic conversion
# and then tries to verify it is a regex
def to_regex(s):
    s = s.replace('*', '.*')
    try:
        re.compile(s)
    except re.error:
        raise MKGeneralException(_('You search statement is not valid. You need to provide a regular '
            'expression (regex). For example you need to e use <tt>\\\\</tt> instead of <tt>\\</tt> '
            'if you like to search for a single backslash.'))
    return s

def is_ipaddress(s):
    try:
        octets = map(int, s.strip(".").split("."))
        for o in octets:
            if o < 0 or o > 255:
                return False
        return True
    except:
        return False

def plugin_matches_filters(plugin, used_filters):
    if not ((len(used_filters) > 1) == (plugin.get("required_types") != None)):
        return False

    if len(used_filters) == 1: # Simple filters
        if plugin.get("lq_table", plugin.get("id")) != used_filters[0][0]:
            return False
    else:                      # Multi filters
        # used_filters example [ ('services', 'CPU'), ('hosts', 'localhost'), ('services', 'Mem') ]
        search_types = list(set(map(lambda x: x[0], used_filters)))
        # Only allow plugins with specified "required_types"
        if not plugin.get("required_types"):
            return False

        # If search_types does not include all required fields -> do not use
        for entry in plugin["required_types"]:
            if entry not in search_types:
                return False

        # If there are unknown types in the search -> do not use
        for entry in search_types:
            if entry not in plugin["required_types"] + plugin.get("optional_types", []):
                return False
    return True

def search_url_tmpl(used_filters, row, exact = True):
    if not row:
        def find_plugin(filters):
            for entry in search_plugins:
                if plugin_matches_filters(entry, filters):
                    return entry, {}, {}
            return None, None, None
        plugin, row_options, row_data = find_plugin(used_filters)
        if not plugin: # find a plugin for the first used filter
            plugin, row_options, row_data = find_plugin([used_filters[0]])
        if not plugin:
            return ""  # shouldn't happen..
    else:
        plugin, row_options, row_data = row

    def find_tmpl():
        if exact: # Get the match template
            if plugin.get("match_url_tmpl_func"):
                return False, plugin['match_url_tmpl_func'](used_filters, row_data)
            if plugin.get("match_url_tmpl"):
                return False, plugin.get("match_url_tmpl")

            # Default match templates
            ty = plugin.get("dftl_url_tmpl", plugin.get("id"))
            if ty == 'hosts':
                return False, 'view.py?view_name=host&host=%(name)s&site=%(site)s'
            elif ty == 'hostgroups':
                return False, 'view.py?view_name=hostgroup&hostgroup=%(name)s&site=%(site)s'
            elif ty == 'servicegroups':
                return False, 'view.py?view_name=servicegroup&servicegroup=%(name)s&site=%(site)s'
            elif ty == 'services':
                return True, 'view.py?view_name=allservices&service_regex=%(name)s&site=%(site)s'
        else: # Get the search template
            if plugin.get("search_url_tmpl_func"):
                return False, plugin['search_url_tmpl_func'](used_filters, row_data)
            if plugin.get("search_url_tmpl"):
                return False, plugin.get("search_url_tmpl")

            # Default search templates
            ty = plugin.get("dftl_url_tmpl", plugin.get("id"))
            if ty == 'hosts':
                return False, 'view.py?view_name=searchhost&host_regex=%(name)s&filled_in=filter'
            elif ty == 'hostgroups':
                return False, 'view.py?view_name=hostgroups&hostgroup_regex=%(name)s&site=%(site)s'
            elif ty == 'servicegroups':
                return False, 'view.py?view_name=svcgroups&servicegroup_name=%(name)s&site=%(site)s'
            elif ty == 'services':
                return False, 'view.py?view_name=allservices&service_regex=%(name)s&site=%(site)s'

    # Search the template
    escape_regex, url_tmpl = find_tmpl()

    # Some templates with single filters contain %(name)s, %(search)s, %(site)
    if len(used_filters) == 1:
        if exact:
            site = row_data.get("site")
            name = row_data.get(get_row_name(row))
            # In case of an exact match, not the original search statement is used,
            # instead the name of the row provided by livestatus is used. This needs
            # to be escaped as it is no regex
            if escape_regex:
                name = name.replace('\\', '\\\\')
        else:
            site = ""
            name = used_filters[0][1]

        url_tmpl = url_tmpl % {
            'name'   : html.urlencode(name),
            'search' : html.urlencode(name),
            'site'   : site,
        }

    return url_tmpl


def search_livestatus(used_filters):
    try:
        limit = config.quicksearch_dropdown_limit
    except:
        limit = 80

    # We need to know which plugin lead to finding a particular host, so it
    # is neccessary to make one query for each plugin - sorry. For example
    # for the case, that a host can be found via alias or name.
    data = []

    html.live.set_prepend_site(True)
    for plugin in search_plugins:
        if 'filter_func' not in plugin:
            continue

        if not plugin_matches_filters(plugin, used_filters):
            continue

        lq_filter = plugin['filter_func'](used_filters)
        if lq_filter:
            lq_table   = plugin.get("lq_table", plugin.get("id"))
            lq_columns = plugin.get("lq_columns")
            lq         = "GET %s\nCache: reload\nColumns: %s\n%sLimit: %d\n" % \
                          (lq_table, " ".join(lq_columns), lq_filter, limit)
            #html.debug("<br>%s" % lq.replace("\n", "<br>"))

            lq_columns = [ "site" ] + lq_columns
            for row in html.live.query(lq):
                # Put result columns into a dict
                row_dict = {}
                for idx, col in enumerate(row):
                    row_dict[lq_columns[idx]] = col

                # The plugin itself might add more info to the row
                # This is saved into an extra dict named options
                options = {}
                if plugin.get("match_url_tmpl_func"):
                    options["url"] = plugin["match_url_tmpl_func"](used_filters, row_dict)

                data.append([ plugin ] + [ options ] + [ row_dict ])
            if len(data) >= limit:
                break

    for plugin in search_plugins:
        if "search_func" in plugin and plugin_matches_filters(plugin, used_filters):
            for row in plugin['search_func'](used_filters):
                row_options, row_data = row
                data.append((plugin, row_options, row_data))

    html.live.set_prepend_site(False)

    # Apply the limit once again (search_funcs of plugins could have added some results)
    data = data[:limit]

    used_keys = []

    # Function to create a unqiue hashable key from a row
    def get_key(row):
        plugin, row_options, row_data = row
        name = row_data.get(get_row_name(row))
        return (row_data.get("site"), row_data.get("host_name"), name)

    # Remove duplicate rows
    used_keys = []
    new_data  = []
    for row in data:
        row_key = get_key(row)
        if row_key not in used_keys:
            new_data.append(row)
            used_keys.append(row_key)
    data = new_data

    # Sort data if its not a host filter
    def sort_data(data):
        sorted_data = data
        def sort_fctn(a, b):
            return cmp(get_key(a), get_key(b))
        data.sort(cmp = sort_fctn)
        return sorted_data

    if len(used_filters) == 1 and used_filters[0][0] != "hosts":
        data = sort_data(data)

    return data


def format_result(row, render_options):
    plugin, row_options, row_data = row
    name_column = get_row_name(row)
    name        = row_data.get(name_column)
    url         = row_options["url"]
    css         = plugin.get("css_class", plugin["id"])

    name_append = ""
    if render_options.get("display_site"):
        name_append += " (%s)" % row_data.get("site")
    if render_options.get("display_host"):
        # Don't append the host name if its already the display name..
        if not name_column == "host_name" and row_data.get("host_name"):
            name_append += " &lt;%s&gt;" % row_data.get("host_name")
    if name_append:
        name = "%s %s" % (name, name_append)

    escaped_name = name.replace('\\', '\\\\')
    html.write('<a id="result_%s" class="%s" href="%s" onClick="mkSearchClose()" target="main">%s' %
                (escaped_name, css, url, name))
    html.write('</a>\n')


def get_row_name(row):
    plugin, row_options, row_data = row
    if plugin.get("qs_show"):
        return plugin.get("qs_show")
    elif plugin.get("lq_columns"):
        return plugin.get("lq_columns")[0]
    return ""

def render_search_results(used_filters, objects, format_func = format_result):
    # When results contain infos from several sites or hosts, display
    # display that info in the result text
    options = {}
    values  = {}
    for row in objects:
        plugin, row_options, row_data = row
        name = get_row_name(row)

        for action, name in [ ("display_site", "site"),
                              ("display_host", "host_name") ]:
            if row_data.get(name):
                values.setdefault(action, row_data.get(name))
                # If this values differs from the default setting -> set is as option
                if values.get(action) != row_data.get(name):
                    options[action] = True

    # Remove duplicate entries, i.e. with the same name and the same URL.
    unique = set([])
    for row in objects:
        plugin, row_options, row_data = row
        # Find missing urls
        name = get_row_name(row)
        if "url" not in row_options:
            row_options["url"] = search_url_tmpl(used_filters, row)

        obj_id = (row_options["url"], name)
        if obj_id not in unique:
            format_func(row, options)
            unique.add(obj_id)

def process_search(q):
    used_filters = parse_search_query(q)

    data = search_livestatus(used_filters)
    if len(used_filters) == 1 and used_filters[0][0] == "hosts" and not data:
        # When asking for hosts and no host found, try searching services instead
        data = search_livestatus([("services", used_filters[0][1])])
        return data, [("services", used_filters[0][1])]

    return data, used_filters

def ajax_search():
    q = html.var('q').strip()
    if not q:
        return

    data, used_filters = process_search(q)
    if not data:
        return

    try:
        render_search_results(used_filters, data)
    except Exception, e:
        html.write("error")
        import traceback
        html.write(traceback.format_exc())
        html.write(repr(e))


def search_open():
    q = html.var('q').strip()
    if not q:
        return

    data, used_filters = process_search(q)
    if not used_filters:
        return

    if data and len(data) == 1:
        url = search_url_tmpl(used_filters, data[0])
    else:
        url = search_url_tmpl(used_filters, data and data[0] or None, exact = False)

    html.set_http_header('Location', url)
    from mod_python import apache
    raise apache.SERVER_RETURN, apache.HTTP_MOVED_TEMPORARILY

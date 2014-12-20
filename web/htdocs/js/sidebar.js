// +------------------------------------------------------------------+
// |             ____ _               _        __  __ _  __           |
// |            / ___| |__   ___  ___| | __   |  \/  | |/ /           |
// |           | |   | '_ \ / _ \/ __| |/ /   | |\/| | ' /            |
// |           | |___| | | |  __/ (__|   <    | |  | | . \            |
// |            \____|_| |_|\___|\___|_|\_\___|_|  |_|_|\_\           |
// |                                                                  |
// | Copyright Mathias Kettner 2014             mk@mathias-kettner.de |
// +------------------------------------------------------------------+
//
// This file is part of Check_MK.
// The official homepage is at http://mathias-kettner.de/check_mk.
//
// check_mk is free software;  you can redistribute it and/or modify it
// under the  terms of the  GNU General Public License  as published by
// the Free Software Foundation in version 2.  check_mk is  distributed
// in the hope that it will be useful, but WITHOUT ANY WARRANTY;  with-
// out even the implied warranty of  MERCHANTABILITY  or  FITNESS FOR A
// PARTICULAR PURPOSE. See the  GNU General Public License for more de-
// ails.  You should have  received  a copy of the  GNU  General Public
// License along with GNU Make; see the file  COPYING.  If  not,  write
// to the Free Software Foundation, Inc., 51 Franklin St,  Fifth Floor,
// Boston, MA 02110-1301 USA.

var browser         = navigator.userAgent.toLowerCase();
var weAreIEF__k     = ((browser.indexOf("msie") != -1) && (browser.indexOf("opera") == -1));
var weAreOpera      = browser.indexOf("opera") != -1;
var weAreFirefox    = browser.indexOf("firefox") != -1 || browser.indexOf("namoroka") != -1;
var g_content_loc   = null;

var sidebar_folded = false;

//
// Sidebar styling and scrolling stuff
//

/************************************************
 * Register events
 *************************************************/

// First firefox and then IE
if (window.addEventListener) {
  window.addEventListener("mousemove",     function(e) {
                                             snapinDrag(e);
                                             dragScroll(e);
                                             return false;
                                           }, false);
  window.addEventListener("mousedown",        startDragScroll, false);
  window.addEventListener("mouseup",          stopDragScroll,  false);
  if(weAreFirefox)
    window.addEventListener('DOMMouseScroll', scrollWheel,     false);
  else
    window.addEventListener('mousewheel',     scrollWheel,     false);
} else {
  document.documentElement.onmousemove  = function(e) {
    // snapin drag 'n drop
    snapinDrag(e);
    // drag/drop scrolling
    dragScroll(e);
    return false;
  };
  // drag/drop scrolling
  document.documentElement.onmousedown  = startDragScroll;
  document.documentElement.onmouseup    = stopDragScroll;
  // mousewheel scrolling
  document.documentElement.onmousewheel = scrollWheel;
}

// This ends drag scrolling when moving the mouse out of the sidebar
// frame while performing a drag scroll.
// This is no 100% solution. When moving the mouse out of browser window
// without moving the mouse over the edge elements the dragging is not ended.
function registerEdgeListeners(obj) {
    var edges;
    if (!obj)
        edges = [ parent.frames[1], document.getElementById('side_header'), document.getElementById('side_footer') ];
    else
        edges = [ obj ];

    for(var i = 0; i < edges.length; i++) {
        // It is possible to open other domains in the content frame - don't register
        // the event in that case. It is not permitted by most browsers!
        if(!contentFrameAccessible())
            continue;

        if (window.addEventListener)
            edges[i].addEventListener("mousemove", stop_snapin_dragging, false);
        else
            edges[i].onmousemove = stop_snapin_dragging;
    }
    edges = null;
}

function stop_snapin_dragging(e) {
    stopDragScroll(e);
    snapinTerminateDrag(e);
    return false;
}

/************************************************
 * snapin drag/drop code
 *************************************************/

var snapinDragging = false;
var snapinOffset   = [ 0, 0 ];
var snapinStartPos = [ 0, 0 ];
var snapinScrollTop = 0;

function snapinStartDrag(event) {
  if (!event)
    event = window.event;

  var target = getTarget(event);
  var button = getButton(event);

  // Skip calls when already dragging or other button than left mouse
  if (snapinDragging !== false || button != 'LEFT' || target.tagName != 'DIV')
    return true;

  if (event.stopPropagation)
    event.stopPropagation();
  event.cancelBubble = true;

  snapinDragging = target.parentNode;

  // Save relative offset of the mouse to the snapin title to prevent flipping on drag start
  snapinOffset   = [ event.clientY - target.parentNode.offsetTop,
                     event.clientX - target.parentNode.offsetLeft ];
  snapinStartPos = [ event.clientY, event.clientX ];
  snapinScrollTop = document.getElementById('side_content').scrollTop;

  // Disable the default events for all the different browsers
  if (event.preventDefault)
    event.preventDefault();
  else
    event.returnValue = false;
  return false;
}

function snapinDrag(event) {
  if (!event)
    event = window.event;

  if (snapinDragging === false)
    return true;

  // Is the mouse placed of the title bar of the snapin?
  // It can move e.g. if the scroll wheel is wheeled during dragging...

  // Drag the snapin
  snapinDragging.style.position = 'absolute';
  var newTop = event.clientY  - snapinOffset[0] - snapinScrollTop;
  newTop += document.getElementById('side_content').scrollTop;
  snapinDragging.style.top      = newTop + 'px';
  snapinDragging.style.left     = (event.clientX - snapinOffset[1]) + 'px';
  snapinDragging.style.zIndex   = 200;

  // Refresh the drop marker
  removeSnapinDragIndicator();

  var line = document.createElement('div');
  line.setAttribute('id', 'snapinDragIndicator');
  var o = getSnapinTargetPos();
  if (o != null) {
    snapinAddBefore(o.parentNode, o, line);
    o = null;
  } else {
    snapinAddBefore(snapinDragging.parentNode, null, line);
  }
  line = null;
	return true;
}

function snapinAddBefore(par, o, add) {
  if (o != null) {
    par.insertBefore(add, o);
    o = null;
  } else {
    par.appendChild(add);
  }
  add = null;
}

function removeSnapinDragIndicator() {
  var o = document.getElementById('snapinDragIndicator');
  if (o) {
    o.parentNode.removeChild(o);
    o = null;
  }
}

function snapinDrop(event, targetpos) {
  if (snapinDragging == false)
    return true;

  // Reset properties
  snapinDragging.style.top      = '';
  snapinDragging.style.left     = '';
  snapinDragging.style.position = '';

  // Catch quick clicks without movement on the title bar
  // Don't reposition the object in this case.
  if (snapinStartPos[0] == event.clientY && snapinStartPos[1] == event.clientX) {
    if (event.preventDefault)
      event.preventDefault();
    if (event.stopPropagation)
      event.stopPropagation();
    event.returnValue = false;
    return false;
  }

  var par = snapinDragging.parentNode;
  par.removeChild(snapinDragging);
  snapinAddBefore(par, targetpos, snapinDragging);

  // Now send the new information to the backend
  var thisId = snapinDragging.id.replace('snapin_container_', '');

  var before = '';
  if (targetpos != null)
    before = '&before=' + targetpos.id.replace('snapin_container_', '');
  get_url('sidebar_move_snapin.py?name=' + thisId + before);
  thisId = null;
  targetpos = null;
}

function snapinTerminateDrag() {
  if(snapinDragging == false)
    return true;
	removeSnapinDragIndicator();
  // Reset properties
  snapinDragging.style.top      = '';
  snapinDragging.style.left     = '';
  snapinDragging.style.position = '';
  snapinDragging = false;
}

function snapinStopDrag(event) {
  if (!event)
    event = window.event;

  removeSnapinDragIndicator();
  snapinDrop(event, getSnapinTargetPos());
  snapinDragging = false;
}

function getDivChildNodes(node) {
  var children = [];
  var childNodes = node.childNodes;
  for(var i = 0; i < childNodes.length; i++)
    if(childNodes[i].tagName === 'DIV')
      children.push(childNodes[i]);
  childNodes = null;
  return children;
}

function getSnapinList() {
  if (snapinDragging === false)
    return true;

  var l = [];
  var childs = getDivChildNodes(snapinDragging.parentNode);
  for(var i = 0; i < childs.length; i++) {
    var child = childs[i];
    // Skip
    // - non snapin objects
    // - currently dragged object
    if (child.id && child.id.substr(0, 7) == 'snapin_' && child.id != snapinDragging.id)
      l.push(child);
  }

  return l;
}

function getSnapinCoords(obj) {
  var snapinTop = snapinDragging.offsetTop;
  // + document.getElementById('side_content').scrollTop;

  var bottomOffset = obj.offsetTop + obj.clientHeight - snapinTop;
  if (bottomOffset < 0)
    bottomOffset = -bottomOffset;

  var topOffset = obj.offsetTop - snapinTop;
  if (topOffset < 0)
    topOffset = -topOffset;

  var offset = topOffset;
  var corner = 0;
  if (bottomOffset < topOffset) {
    offset = bottomOffset
    corner = 1;
  }

  return [ bottomOffset, topOffset, offset, corner ];
}

function getSnapinTargetPos() {
  var snapinTop = snapinDragging.offsetTop;
  var childs = getSnapinList();
  var objId = -1;
  var objCorner = -1;

  // Find the nearest snapin to current left/top corner of
  // the currently dragged snapin
  for(var i = 0; i < childs.length; i++) {
    var child = childs[i];

    if (!child.id || child.id.substr(0, 7) != 'snapin_' || child.id == snapinDragging.id)
      continue;

    // Initialize with the first snapin in the list
    if (objId === -1) {
      objId = i;
      var coords = getSnapinCoords(child)
      objCorner = coords[3];
      continue;
    }

    // First check which corner is closer. Upper left or
    // the bottom left.
    var curCoords = getSnapinCoords(childs[objId]);
    var newCoords = getSnapinCoords(child);

    // Is the upper left corner closer?
    if (newCoords[2] < curCoords[2]) {
      objCorner = newCoords[3];
      objId = i;
    }
  }

  // Is the dragged snapin dragged above the first one?
  if (objId == 0 && objCorner == 0)
      return childs[0];
  else
      return childs[(parseInt(objId)+1)];
}

/************************************************
 * misc sidebar stuff
 *************************************************/

// Checks if the sidebar can access the content frame. It might be denied
// by the browser since it blocks cross domain access.
function contentFrameAccessible() {
    try {
        var d = parent.frames[1].document;
        d = null;
        return true;
    } catch (e) {
        return false;
    }
}

function update_content_location() {
    // init the original frameset title
    if (typeof(window.parent.orig_title) == 'undefined') {
        window.parent.orig_title = window.parent.document.title;
    }

    var content_frame = window.parent.frames[1];

    // Change the title to add the right frame title to reflect the
    // title of the content URL in the framesets title (window title or tab title)
    if (content_frame.document.title != '') {
        var page_title = window.parent.orig_title + ' - ' + content_frame.document.title;
    } else {
        var page_title = window.parent.orig_title;
    }
    window.parent.document.title = page_title;

    // Construct the URL to be called on page reload
    var parts = window.parent.location.pathname.split('/')
    parts.pop();
    var cmk_path = parts.join('/');
    var rel_url = content_frame.location.pathname + content_frame.location.search + content_frame.location.hash
    var index_url = cmk_path + '/index.py?start_url=' + encodeURIComponent(rel_url);

    if (window.parent.history.replaceState) {
        if (rel_url && rel_url != 'blank') {
            // Update the URL to be called on reload, e.g. via F5, to make the
            // frameset switch to exactly this URL
            window.parent.history.replaceState({}, page_title, index_url);

            // only update the internal flag var if the url was not blank and has been updated
            //otherwise try again on next scheduler run
            g_content_loc = parent.frames[1].document.location.href;
        }
    } else {
        // Only a browser without history.replaceState support reaches this. Sadly
        // we have no F5/reload fix for them...
        g_content_loc = parent.frames[1].document.location.href;
    }
}

function debug(s) {
  window.parent.frames[1].document.write(s+'<br />');
}


// Set the size of the sidebar_content div to fit the whole screen
// but without scrolling. The height of the header and footer divs need
// to be treated here.
var g_just_resizing = 0;
function setSidebarHeight() {
  var oHeader  = document.getElementById('side_header');
  var oContent = document.getElementById('side_content');
  var oFooter  = document.getElementById('side_footer');
  var height   = pageHeight();

  // Resize sidebar frame on Chrome (and other webkit browsers)
  if (isWebkit()) {
      var oldcols = parent.document.body.cols.split(",");
      var oldwidth = parseInt(oldcols[0]);
      var width = oHeader.clientWidth;
      var target_width = oldwidth * 280.0 / width;
      var newcols = target_width.toString() + ",*";
      parent.document.body.cols = newcols;
  }

  // Don't handle zero heights
  if (height == 0)
    return;

  oContent.style.height = (height - oHeader.clientHeight - oFooter.clientHeight + 4) + 'px';

  oFooter = null;
  oContent = null;
  oHeader = null;
}

var scrolling = true;

function scrollwindow(speed){
  var c = document.getElementById('side_content');

  if (scrolling) {
    c.scrollTop += speed;
    setTimeout("scrollwindow("+speed+")", 10);
  }

  c = null;
}

/************************************************
 * drag/drop scrollen
 *************************************************/

var dragging = false;
var startY = 0;
var startScroll = 0;

function startDragScroll(event) {
  if (!event)
    event = window.event;

  if (sidebar_folded) {
      unfoldSidebar();
      return false;
  }
  else if (!sidebar_folded && event.clientX < 10) {
      foldSidebar();
      return false;
  }


  var target = getTarget(event);
  var button = getButton(event);

  if (dragging === false && button == 'LEFT'
      && target.tagName != 'A'
      && target.tagName != 'INPUT'
      && target.tagName != 'SELECT'
      && !(target.tagName == 'DIV' && target.className == 'heading')) {
    if (event.preventDefault)
      event.preventDefault();
    if (event.stopPropagation)
      event.stopPropagation();
    event.returnValue = false;

    dragging = event;
    startY = event.clientY;
    startScroll = document.getElementById('side_content').scrollTop;

    return false;
  }
  return true;
}

function stopDragScroll(event){
  dragging = false;
}

function dragScroll(event) {
  if (!event)
    event = window.event;

  if (dragging === false)
    return true;

  if (event.preventDefault)
    event.preventDefault();
  event.returnValue = false;

  if (event.stopPropagation)
    event.stopPropagation();
  event.cancelBubble = true;

  var inhalt = document.getElementById('side_content');
  var diff = startY - event.clientY;

  inhalt.scrollTop += diff;

	// Opera does not fire onunload event which is used to store the scroll
	// position. So call the store function manually here.
  if(weAreOpera)
    storeScrollPos();

  startY = event.clientY;

  dragging = event;
  inhalt = null;

  return false;
}

function foldSidebar()
{
    sidebar_folded = true;
    document.getElementById('check_mk_sidebar').style.position = "relative";
    document.getElementById('check_mk_sidebar').style.left = "-265px";
    if (isWebkit()) {
        var oldcols = parent.document.body.cols.split(",");
        var oldwidth = parseInt(oldcols[0]);
        var new_width = 10.0 / 280.0 * oldwidth;
        parent.document.body.cols = new_width.toString() + ",*";
    }
    else
        parent.document.body.cols = "10,*";
    get_url('sidebar_fold.py?fold=yes');
}


function unfoldSidebar()
{
    document.getElementById('check_mk_sidebar').style.position = "";
    document.getElementById('check_mk_sidebar').style.left = "0";
    parent.document.body.cols = "280,*";
    sidebar_folded = false;
    get_url('sidebar_fold.py?fold=');
}



/************************************************
 * Mausrad scrollen
 *************************************************/

function handle(delta) {
  if (delta < 0) {
    scrolling = true;
    scrollwindow(-delta*20);
    scrolling = false;
  } else {
    scrolling = true;
    scrollwindow(-delta*20);
    scrolling = false;
  }
}

/** Event handler for mouse wheel event.
 */
function scrollWheel(event){
  var delta = 0;
  if (!event)
    event = window.event;

  if (event.wheelDelta)
    delta = event.wheelDelta / 120;
  else if (event.detail)
    delta = -event.detail / 3;

  if (delta)
    handle(delta);

	// Opera does not fire onunload event which is used to store the scroll
	// position. So call the store function manually here.
  if(weAreOpera)
    storeScrollPos();

  if (event.preventDefault)
    event.preventDefault();
  else
    event.returnValue = false;
  return false;
}


//
// Sidebar ajax stuff
//

// The refresh snapins do reload after a defined amount of time
refresh_snapins = null;
// The restart snapins are notified about the restart of the nagios instance(s)
restart_snapins = null;
// Contains a timestamp which holds the time of the last nagios restart handling
sidebar_restart_time = null;
// Configures the number of seconds to reload all snapins which request it
sidebar_update_interval = null;

// Removes a snapin from the sidebar without reloading anything
function removeSnapin(id, code) {
  var container = document.getElementById(id).parentNode;
  var myparent = container.parentNode;
  myparent.removeChild(container);

  // remove this snapin from the refresh list, if it is contained
  for (var i in refresh_snapins) {
      var name    = refresh_snapins[i][0];
      if (id == "snapin_" + name) {
          refresh_snapins.splice(i, 1);
          break;
      }
  }

  // reload main frame if it is just displaying the "add snapin" page
  var href = encodeURIComponent(parent.frames[1].location);
  if (href.indexOf("sidebar_add_snapin.py") > -1)
      parent.frames[1].location.reload();

  href = null;
  container = null;
  myparent = null;
}


function toggle_sidebar_snapin(oH2, url) {
    // oH2 can also be an <a>. In that case it is the minimize
    // image itself

    var childs;
    if (oH2.tagName == "A")
        childs = oH2.parentNode.parentNode.parentNode.childNodes;
    else
        childs = oH2.parentNode.parentNode.childNodes;
    for (var i in childs) {
        child = childs[i];
        if (child.tagName == 'DIV' && child.className == 'content')
            var oContent = child;
        else if (child.tagName == 'DIV' && (child.className == 'head open' || child.className == "head closed"))
            var oHead = child;
        else if (child.tagName == 'DIV' && child.className == 'foot')
            var oFoot = child;
    }
    var oImgMini = oHead.childNodes[0].childNodes[0].childNodes[0];

    // FIXME: Does oContent really exist?
    var closed = oContent.style.display == "none";
    if (closed) {
        oContent.style.display = "block";
        oFoot.style.display = "block";
        oHead.className = "head open";
        oImgMini.src = "images/button_minisnapin_lo.png";
    }
    else {
        oContent.style.display = "none";
        oFoot.style.display = "none";
        oHead.className = "head closed";
        oImgMini.src = "images/button_maxisnapin_lo.png";
    }
    /* make this persistent -> save */
    get_url(url + (closed ? "open" : "closed"));
    oContent = null;
    oHead = null;
    oFoot = null;
    childs = null;
}

function reload_main_plus_sidebar(id, code) {
    parent.frames[1].location.reload(); /* reload main frame */
    parent.frames[0].location.reload(); /* reload side bar */
}

function switch_site(switchvar) {
    get_url("switch_site.py?" + switchvar, reload_main_plus_sidebar, null);
    /* After the site switch has been done, everything must be reloaded since
       everything is affected by the switch */
}

var g_seconds_to_update = null;

function refresh_single_snapin(name) {
    var url = 'sidebar_snapin.py?names=' + name;
    var ids = [ 'snapin_' + name ];
    get_url(url, bulkUpdateContents, ids);
}

function sidebar_scheduler() {
    if (g_seconds_to_update == null)
        g_seconds_to_update = sidebar_update_interval;
    else
        g_seconds_to_update -= 1;

    var newcontent = "";
    var to_be_updated = [];

    for (var i = 0; i < refresh_snapins.length; i++) {
        var name = refresh_snapins[i][0];
        if (refresh_snapins[i][1] != '') {
            // Special handling for snapins like the nagvis maps snapin which request
            // to be updated from a special URL, use direct update of those snapins
            // from this url
            var url = refresh_snapins[i][1];

            if (g_seconds_to_update <= 0) {
                get_url(url, updateContents, "snapin_" + name);
            }
        } else {
            // Internal update handling, use bulk update
            to_be_updated.push(name);
        }
    }

    // Are there any snapins to be bulk updates?
    if(to_be_updated.length > 0) {
        if (g_seconds_to_update <= 0) {
            var url = 'sidebar_snapin.py?names=' + to_be_updated.join(',');
            if (sidebar_restart_time !== null)
                url += '&since=' + sidebar_restart_time;

            var ids = [];
            for (var i = 0, len = to_be_updated.length; i < len; i++) {
                ids.push('snapin_' + to_be_updated[i]);
            }

            get_url(url, bulkUpdateContents, ids);
        }
    }

    if (g_sidebar_notify_interval !== null) {
        var timestamp = Date.parse(new Date()) / 1000;
        if (timestamp % g_sidebar_notify_interval == 0) {
            update_messages();
        }
    }

    // Detect page changes and re-register the mousemove event handler
    // in the content frame. another bad hack ... narf
    if(contentFrameAccessible() && g_content_loc != parent.frames[1].document.location.href) {
        registerEdgeListeners(parent.frames[1]);
        update_content_location();
    }

    if (g_seconds_to_update <= 0)
        g_seconds_to_update = sidebar_update_interval;

    setTimeout(function(){sidebar_scheduler();}, 1000);
}

function addBookmark() {
    href = parent.frames[1].location;
    title = parent.frames[1].document.title;
    get_url("add_bookmark.py?title=" + encodeURIComponent(title)
            + "&href=" + encodeURIComponent(href), updateContents, "snapin_bookmarks");
}

/************************************************
 * Save/Restore scroll position
 *************************************************/

function setCookie(cookieName, value,expiredays) {
    var exdate = new Date();
    exdate.setDate(exdate.getDate() + expiredays);
    document.cookie = cookieName + "=" + encodeURIComponent(value) +
        ((expiredays == null) ? "" : ";expires=" + exdate.toUTCString());
}

function getCookie(cookieName) {
    if(document.cookie.length == 0)
        return null;

    var cookieStart = document.cookie.indexOf(cookieName + "=");
    if(cookieStart == -1)
        return null;

    cookieStart = cookieStart + cookieName.length + 1;
    var cookieEnd = document.cookie.indexOf(";", cookieStart);
    if(cookieEnd == -1)
        cookieEnd = document.cookie.length;
    return decodeURIComponent(document.cookie.substring(cookieStart, cookieEnd));
}

function initScrollPos() {
    var scrollPos = getCookie('sidebarScrollPos');
    if(!scrollPos)
        scrollPos = 0;
    document.getElementById('side_content').scrollTop = scrollPos;
}

function storeScrollPos() {
    setCookie('sidebarScrollPos', document.getElementById('side_content').scrollTop, null);
}

/************************************************
 * WATO Folders snapin handling
 *************************************************/

// FIXME: Make this somehow configurable - use the start url?
g_last_view   = 'dashboard.py?name=main';
g_last_folder = '';

// highlight the followed link (when both needed snapins are available)
function highlight_link(link_obj, container_id) {
    var this_snapin = document.getElementById(container_id);
    if (container_id == 'snapin_container_wato_folders')
        var other_snapin = document.getElementById('snapin_container_views');
    else
        var other_snapin = document.getElementById('snapin_container_wato_folders');

    if (this_snapin && other_snapin) {
        if (this_snapin.getElementsByClassName)
            var links = this_snapin.getElementsByClassName('link');
        else
            var links = document.getElementsByClassName('link', this_snapin);

        for (var i = 0; i < links.length; i++) {
            links[i].style.fontWeight = 'normal';
        }

        link_obj.style.fontWeight = 'bold';
    }
}

function wato_folders_clicked(link_obj, folderpath) {
    g_last_folder = folderpath;
    highlight_link(link_obj, 'snapin_container_wato_folders');
    parent.frames[1].location = g_last_view + '&wato_folder=' + encodeURIComponent(g_last_folder);
}

function wato_views_clicked(link_obj) {
    g_last_view = link_obj.href;

    highlight_link(link_obj, 'snapin_container_views');
    highlight_link(link_obj, 'snapin_container_dashboards');

    if (g_last_folder != '') {
        // Navigate by using javascript, cancel following the default link
        parent.frames[1].location = g_last_view + '&wato_folder=' + encodeURIComponent(g_last_folder);
        return false;
    } else {
        // Makes use the url stated in href attribute
        return true;
    }
}

/************************************************
 * WATO Foldertree (Standalone) snapin handling
 *************************************************/

/* Foldable Tree in snapin */
function wato_tree_click(link_obj, folderpath) {
    var topic  = document.getElementById('topic').value;
    var target = document.getElementById('target_' + topic).value;

    if(target.substr(0, 9) == 'dashboard') {
        dashboard_name = target.substr(10, target.length);
        href = 'dashboard.py?name=' + encodeURIComponent(dashboard_name);
    } else {
        href = 'view.py?view_name=' + encodeURIComponent(target);
    }

    href += '&wato_folder=' + encodeURIComponent(folderpath);

    parent.frames[1].location = href;
}

function wato_tree_topic_changed(topic_field) {
    // First toggle the topic dropdown field
    var topic = topic_field.value;

    // Hide all select fields but the wanted one
    var select_fields = document.getElementsByTagName('select');
    for(var i = 0; i < select_fields.length; i++) {
        if(select_fields[i].id && select_fields[i].id.substr(0, 7) == 'target_') {
            select_fields[i].selected = '';
            if(select_fields[i].id == 'target_' + topic) {
                select_fields[i].style.display = 'inline';
            } else {
                select_fields[i].style.display = 'none';
            }
        }
    }

    // Then send the info to python code via ajax call for persistance
    get_url('ajax_set_foldertree.py?topic=' + encodeURIComponent(topic) + '&target=');
}

function wato_tree_target_changed(target_field) {
    var topic = target_field.id.substr(7, target_field.id.length);
    var target = target_field.value;

    // Send the info to python code via ajax call for persistance
    get_url('ajax_set_foldertree.py?topic=' + encodeURIComponent(topic) + '&target=' + encodeURIComponent(target));
}

// adds a variable to a GET url, but tries to remove that
// variable, if it is already existing in the URL. In order
// to simplify the thing, we just look at the *end* of the
// URL. This is not perfect but sufficient in order to avoid the URL
// getting longer and longer.
function add_html_var(url, varname, value) {
    var re = new RegExp('&' + varname + '=[^&]*');
    var new_url = url.replace(re, "");
    if (new_url.indexOf('?') != '-1')
        new_url += "&" + varname + "=" + encodeURIComponent(value);
    else
        new_url += "?" + varname + "=" + encodeURIComponent(value);
    return new_url;
}


/************************************************
 * Popup Message Handling
 *************************************************/

// integer representing interval in seconds or <null> when disabled.
var g_sidebar_notify_interval;

function init_messages(interval) {
    g_sidebar_notify_interval = interval;

    // Are there pending messages? Render the initial state of
    // trigger button
    update_message_trigger();
}

function handle_update_messages(_unused, code) {
    // add new messages to container
    var c = document.getElementById('messages');
    if (c) {
        c.innerHTML = code;
        executeJSbyObject(c);
        update_message_trigger();
    }
}

function update_messages() {
    // Remove all pending messages from container
    var c = document.getElementById('messages');
    if (c) {
        c.innerHTML = '';
    }

    // retrieve new messages
    get_url('sidebar_get_messages.py', handle_update_messages);
}

function get_hint_messages(c) {
    var hints;
    if (c.getElementsByClassName)
        hints = c.getElementsByClassName('popup_msg');
    else
        hints = document.getElementsByClassName('popup_msg', c);
    return hints;
}

function update_message_trigger() {
    var c = document.getElementById('messages');
    if (c) {
        var b = document.getElementById('msg_button');
        var hints = get_hint_messages(c);
        if (hints.length > 0) {
            // are there pending messages? make trigger visible
            b.style.display = 'inline';

            // Create/Update a blinking number label
            var l = document.getElementById('msg_label');
            if (!l) {
                var l = document.createElement('span');
                l.setAttribute('id', 'msg_label');
                b.appendChild(l);
            }

            l.innerHTML = '' + hints.length;
        } else {
            // no messages: hide the trigger
            b.style.display = 'none';
        }
    }
}

function mark_message_read(msg_id) {
    get_url('sidebar_message_read.py?id=' + msg_id);

    // Update the button state
    update_message_trigger();
}

function read_message() {
    var c = document.getElementById('messages');
    if (!c)
        return;

    // extract message from teh message container
    var hints = get_hint_messages(c);
    var msg = hints[0];
    c.removeChild(msg);

    // open the next message in a window
    c.parentNode.appendChild(msg);

    // tell server that the message has been read
    var msg_id = msg.id.replace('message-', '');
    mark_message_read(msg_id);
}

function message_close(msg_id) {
    var m = document.getElementById('message-' + msg_id);
    if (m) {
        m.parentNode.removeChild(m);
    }
}

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

import math, os, time, re, sre_constants, urlparse, forms
from lib import *

def type_name(v):
    try:
        return type(v).__name__
    except:
        return html.attrencode(type(v))

# Abstract base class of all value declaration classes.
class ValueSpec:
    def __init__(self, **kwargs):
        self._title         = kwargs.get("title")
        self._help          = kwargs.get("help")
        if "default_value" in kwargs:
            self._default_value = kwargs.get("default_value")
        self._validate      = kwargs.get("validate")

    def title(self):
        return self._title

    def help(self):
        return self._help

    # Create HTML-form elements that represent a given
    # value and let the user edit that value. The varprefix
    # is prepended to the HTML variable names and is needed
    # in order to make the variable unique in case that another
    # Value of the same type is being used as well.
    # The function may assume that the type of the value is valid.
    def render_input(self, varprefix, value):
        pass

    # Sets the input focus (cursor) into the most promiment
    # field of the HTML code previously rendered with render_input()
    def set_focus(self, varprefix):
        html.set_focus(varprefix)

    # Create a canonical, minimal, default value that
    # matches the datatype of the value specification and
    # fullfills also data validation.
    def canonical_value(self):
        return None

    # Return a default value for this variable. This
    # is optional and only used in the value editor
    # for same cases where the default value is known.
    def default_value(self):
        try:
            if type(self._default_value) == type(lambda:True):
                return self._default_value()
            else:
                return self._default_value
        except:
            return self.canonical_value()

    # Creates a text-representation of the value that can be
    # used in tables and other contextes. It is to be read
    # by the user and need not to be parsable.
    # The function may assume that the type of the value is valid.
    #
    # In the current implementation this function is only used to
    # render the object for html code. So it is allowed to add
    # html code for better layout in the GUI.
    def value_to_text(self, value):
        return repr(value)

    # Create a value from the current settings of the
    # HTML variables. This function must also check the validity
    # and may raise a MKUserError in case of invalid set variables.
    def from_html_vars(self, varprefix):
        return None

    # Check if a given value matches the
    # datatype of described by this class. This method will
    # be used by cmk -X on the command line in order to
    # validate main.mk (some happy day in future)
    def validate_datatype(self, value, varprefix):
        pass

    # Check if a given value is within the ranges that are
    # allowed for this type of value. This function should
    # assume that the data type is valid (either because it
    # has been returned by from_html_vars() or because it has
    # been checked with validate_datatype()).
    def validate_value(self, value, varprefix):
        self.custom_validate(value, varprefix)

    # Needed for implementation of customer validation
    # functions that are configured by the user argument
    # validate = .... Problem: this function must be
    # called by *every* validate_value() function in all
    # subclasses - explicitely.
    def custom_validate(self, value, varprefix):
        if self._validate:
            self._validate(value, varprefix)


# A fixed non-editable value, e.g. to be use in "Alternative"
class FixedValue(ValueSpec):
    def __init__(self, value, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._value = value
        self._totext = kwargs.get("totext")

    def canonical_value(self):
        return self._value

    def render_input(self, varprefix, value):
        html.write(self.value_to_text(value))

    def value_to_text(self, value):
        if self._totext != None:
            return self._totext
        elif type(value) == unicode:
            return value
        else:
            return str(value)

    def from_html_vars(self, varprefix):
        return self._value

    def validate_datatype(self, value, varprefix):
        if not self._value == value:
            raise MKUserError(varprefix, _("Invalid value, must be '%r' but is '%r'" % (self._value, value)))

    def validate_value(self, value, varprefix):
        self.validate_datatype(value, varprefix)
        ValueSpec.custom_validate(self, value, varprefix)

# Time in seconds
class Age(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._label    = kwargs.get("label")
        self._minvalue = kwargs.get("minvalue")
        self._display  = kwargs.get("display", ["days", "hours", "minutes", "seconds"])

    def canonical_value(self):
        if self._minvalue:
            return self._minvalue
        else:
            return 0

    def render_input(self, varprefix, value):
        days,    rest    = divmod(value, 60*60*24)
        hours,   rest    = divmod(rest,   60*60)
        minutes, seconds = divmod(rest,      60)

        html.write("<div>")
        if self._label:
            html.write(self._label + " ")

        takeover = 0
        first = True
        for uid, title, value, tkovr_fac in [ ("days",    _("days"),  days,    24),
                                              ("hours",   _("hours"), hours,   60),
                                              ("minutes", _("mins"),  minutes, 60),
                                              ("seconds", _("secs"),  seconds, 60) ]:
            if uid in self._display:
                value += takeover
                takeover = 0
                html.number_input(varprefix + "_" + uid, value, first and 3 or 2)
                html.write(" %s " % title)
                first = False
            else:
                takeover = (takeover + value) * tkovr_fac
        html.write("</div>")

    def from_html_vars(self, varprefix):
        return (
               saveint(html.var(varprefix+'_days', 0))   * 3600 * 24
             + saveint(html.var(varprefix+'_hours',0))   * 3600
             + saveint(html.var(varprefix+'_minutes',0)) * 60
             + saveint(html.var(varprefix+'_seconds',0))
        )

    def value_to_text(self, value):
        days,    rest    = divmod(value, 60*60*24)
        hours,   rest    = divmod(rest,   60*60)
        minutes, seconds = divmod(rest,      60)
        parts = []
        for title, count in [
            ( _("days"), days, ),
            ( _("hours"), hours, ),
            ( _("minutes"), minutes, ),
            ( _("seconds"), seconds, )]:
            if count:
                parts.append("%d %s" % (count, title))

        if parts:
            return " ".join(parts)
        else:
            return _("no time")


    def validate_datatype(self, value, varprefix):
        if type(value) != int:
            raise MKUserError(varprefix, _("The value %r has type %s, but must be of type int") %
                        (value, type_name(value)))

    def validate_value(self, value, varprefix):
        if self._minvalue != None and value < self._minvalue:
            raise MKUserError(varprefix, _("%s is too low. The minimum allowed value is %s." % (
                                     value, self._minvalue)))

# Editor for a single integer
class Integer(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._size           = kwargs.get("size", 5)
        self._minvalue       = kwargs.get("minvalue")
        self._maxvalue       = kwargs.get("maxvalue")
        self._label          = kwargs.get("label")
        self._unit           = kwargs.get("unit", "")
        self._thousand_sep   = kwargs.get("thousand_sep")
        self._display_format = kwargs.get("display_format", "%d")
        self._align          = kwargs.get("align", "left")

        if "size" not in kwargs and "maxvalue" in kwargs and kwargs["maxvalue"] != None:
            self._size = 1 + int(math.log10(self._maxvalue)) + \
               (type(self._maxvalue) == float and 3 or 0)

    def canonical_value(self):
        if self._minvalue:
            return self._minvalue
        else:
            return 0

    def render_input(self, varprefix, value, convfunc = saveint):
        if self._label:
            html.write(self._label)
            html.write("&nbsp;")
        if self._align == "right":
            style = "text-align: right;"
        else:
            style = ""
        if value == "": # This is needed for ListOfIntegers
            html.text_input(varprefix, "", "number", size = self._size, style = style)
        else:
            html.number_input(varprefix, self._display_format % convfunc(value), size = self._size, style = style)
        if self._unit:
            html.write("&nbsp;")
            html.write(self._unit)

    def from_html_vars(self, varprefix):
        try:
            return int(html.var(varprefix))
        except:
            raise MKUserError(varprefix,
                  _("The text <b><tt>%s</tt></b> is not a valid integer number." % html.var(varprefix)))

    def value_to_text(self, value):
        text = self._display_format % value
        if self._thousand_sep:
            sepped = ""
            rest = text
            while len(rest) > 3:
                sepped = self._thousand_sep + rest[-3:] + sepped
                rest = rest[:-3]
            sepped = rest + sepped
            text = sepped

        if self._unit:
            text += "&nbsp;" + self._unit
        return text

    def validate_datatype(self, value, varprefix):
        if type(value) not in [ int, long ]:
            raise MKUserError(varprefix, _("The value %r has the wrong type %s, but must be of type int")
            % (value, type_name(value)))

    def validate_value(self, value, varprefix):
        if self._minvalue != None and value < self._minvalue:
            raise MKUserError(varprefix, _("%s is too low. The minimum allowed value is %s." % (
                                     value, self._minvalue)))
        if self._maxvalue != None and value > self._maxvalue:
            raise MKUserError(varprefix, _("%s is too high. The maximum allowed value is %s." % (
                                     value, self._maxvalue)))
        ValueSpec.custom_validate(self, value, varprefix)

# Filesize in Byte,Kbyte,Mbyte,Gigatbyte, Terrabyte
class Filesize(Integer):
    def __init__(self, **kwargs):
        Integer.__init__(self, **kwargs)
        self._names = [ 'Byte', 'KByte', 'MByte', 'GByte', 'TByte', ]


    def get_exponent(self, value):
        for exp, unit_name in list(enumerate(self._names))[::-1]:
            if value == 0:
               return 0,0
            if value % (1024 ** exp) == 0:
                return exp, value / (1024 ** exp)

    def render_input(self, varprefix, value):
        exp, count = self.get_exponent(value)
        html.number_input(varprefix + '_size', count, size = self._size)
        html.write("&nbsp;")
        html.select(varprefix + '_unit', enumerate(self._names), exp)

    def from_html_vars(self, varprefix):
        try:
            return int(html.var(varprefix + '_size')) * (1024 ** int(html.var(varprefix + '_unit')))
        except:
            raise MKUserError(varprefix + '_size', _("Please enter a valid integer number"))

    def value_to_text(self, value):
        exp, count = self.get_exponent(value)
        return "%s %s" %  (count, self._names[exp])


# Editor for a line of text
class TextAscii(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._label         = kwargs.get("label")
        self._size          = kwargs.get("size", 25) # also possible: "max"
        self._cssclass      = kwargs.get("cssclass", "text")
        self._strip         = kwargs.get("strip", True)
        self._attrencode    = kwargs.get("attrencode", True)
        self._allow_empty   = kwargs.get("allow_empty", _("none"))
        self._empty_text    = kwargs.get("empty_text", "")
        self._read_only     = kwargs.get("read_only")
        self._none_is_empty = kwargs.get("none_is_empty", False)
        self._forbidden_chars = kwargs.get("forbidden_chars", "")
        self._regex         = kwargs.get("regex")
        self._regex_error   = kwargs.get("regex_error",
            _("Your input does not match the required format."))
        self._minlen        = kwargs.get('minlen', None)
        if type(self._regex) == str:
            self._regex = re.compile(self._regex)
        self._prefix_buttons = kwargs.get("prefix_buttons", [])

    def canonical_value(self):
        return ""

    def render_input(self, varprefix, value):
        if value == None:
            value = ""
        elif type(value) != unicode:
            value = str(value)

        if self._label:
            html.write(self._label)
            html.write("&nbsp;")

        if self._prefix_buttons:
            html.write('<div style="white-space: nowrap;">')
        html.text_input(varprefix, value, size = self._size, read_only = self._read_only, cssclass = self._cssclass)
        self.render_buttons()
        if self._prefix_buttons:
            html.write('</div>')

    def render_buttons(self):
        if self._prefix_buttons:
            html.write("&nbsp;")
            for icon, textfunc, help in self._prefix_buttons:
                try:
                    text = textfunc()
                except:
                    text = textfunc
                html.icon_button("#", help, icon, onclick="vs_textascii_button(this, '%s', 'prefix');" % text)


    def value_to_text(self, value):
        if not value:
            return self._empty_text
        else:
            if self._attrencode:
                return html.attrencode(value)
            else:
                return value

    def from_html_vars(self, varprefix):
        value = html.var(varprefix, "")
        if self._strip:
            value = value.strip()
        if self._none_is_empty and not value:
            return None
        else:
            return value

    def validate_datatype(self, value, varprefix):
        if self._none_is_empty and value == None:
            return

        if type(value) != str:
            raise MKUserError(varprefix, _("The value must be of type str, but it has type %s") %
                                                                    type_name(value))

    def validate_value(self, value, varprefix):
        try:
            unicode(value)
        except:
            raise MKUserError(varprefix, _("Non-ASCII characters are not allowed here."))
        if self._forbidden_chars:
            for c in self._forbidden_chars:
                if c in value:
                    raise MKUserError(varprefix, _("The character <tt>%s</tt> is not allowed here.") % c)
        if self._none_is_empty and value == "":
            raise MKUserError(varprefix, _("An empty value must be represented with None here."))
        if not self._allow_empty and value.strip() == "":
            raise MKUserError(varprefix, _("An empty value is not allowed here."))
        if value and self._regex:
            if not self._regex.match(value):
                raise MKUserError(varprefix, self._regex_error)

        if self._minlen != None and len(value) < self._minlen:
            raise MKUserError(varprefix, _("You need to provide at least %d characters.") % self._minlen)

        ValueSpec.custom_validate(self, value, varprefix)

class TextUnicode(TextAscii):
    def __init__(self, **kwargs):
        TextAscii.__init__(self, **kwargs)

    def from_html_vars(self, varprefix):
        return html.var_utf8(varprefix, "").strip()

    def validate_datatype(self, value, varprefix):
        if type(value) not in [ str, unicode ]:
            raise MKUserError(varprefix, _("The value must be of type str or unicode, but it has type %s") %
                                                                                type_name(value))

# Internal ID as used in many places (for contact names, group name,
# an so on)
class ID(TextAscii):
    def __init__(self, **kwargs):
        TextAscii.__init__(self, **kwargs)
        self._regex = re.compile('^[a-zA-Z_][-a-zA-Z0-9_]*$')
        self._regex_error = _("An identifier must only consist of letters, digits, dash and underscore and it must start with a letter or underscore.")

# Same as the ID class, but allowing unicode objects
class UnicodeID(TextUnicode):
    def __init__(self, **kwargs):
        TextAscii.__init__(self, **kwargs)
        self._regex = re.compile(r'^[\w][-\w0-9_]*$', re.UNICODE)
        self._regex_error = _("An identifier must only consist of letters, digits, dash and underscore and it must start with a letter or underscore.")

class RegExp(TextAscii):
    def __init__(self, **kwargs):
        TextAscii.__init__(self, attrencode = True, cssclass = 'text regexp', **kwargs)
        self._mingroups = kwargs.get("mingroups", 0)
        self._maxgroups = kwargs.get("maxgroups")

    def validate_value(self, value, varprefix):
        TextAscii.validate_value(self, value, varprefix)

        # Check if the string is a valid regex
        try:
            compiled = re.compile(value)
        except sre_constants.error, e:
            raise MKUserError(varprefix, _('Invalid regular expression: %s') % e)

        if compiled.groups < self._mingroups:
            raise MKUserError(varprefix, _("Your regular expression containes <b>%d</b> groups. "
                 "You need at least <b>%d</b> groups.") % (compiled.groups, self._mingroups))
        if self._maxgroups != None and compiled.groups > self._maxgroups:
            raise MKUserError(varprefix, _("Your regular expression containes <b>%d</b> groups. "
                 "It must have at most <b>%d</b> groups.") % (compiled.groups, self._maxgroups))

        ValueSpec.custom_validate(self, value, varprefix)


class RegExpUnicode(TextUnicode, RegExp):
    def __init__(self, **kwargs):
        TextUnicode.__init__(self, attrencode = True, **kwargs)
        RegExp.__init__(self, **kwargs)

    def validate_value(self, value, varprefix):
        TextUnicode.validate_value(self, value, varprefix)
        RegExp.validate_value(self, value, varprefix)
        ValueSpec.custom_validate(self, value, varprefix)

class EmailAddress(TextAscii):
    def __init__(self, **kwargs):
        kwargs.setdefault("size", 40)
        TextAscii.__init__(self, **kwargs)
        self._regex = re.compile('^[A-Z0-9._%+-]+@(localhost|[A-Z0-9.-]+\.[A-Z]{2,4})$', re.I)
        self._make_clickable = kwargs.get("make_clickable", False)

    def value_to_text(self, value):
        if not value:
            return TextAscii.value_to_text(self, value)
        elif self._make_clickable:
            return '<a href="mailto:%s">%s</a>' % (html.attrencode(value), html.attrencode(value))
        else:
            return value


# Network as used in routing configuration, such as
# "10.0.0.0/8" or "192.168.56.1"
class IPv4Network(TextAscii):
    def __init__(self, **kwargs):
        kwargs.setdefault("size", 18)
        TextAscii.__init__(self, **kwargs)

    def validate_value(self, value, varprefix):
        if "/" in value:
            try:
                network, bits = value.split("/")
                bits = int(bits)
            except:
                raise MKUserError(varprefix, _("Please use the syntax X.X.X.X/YY"))
        else:
            network = value
            bits = 32

        if bits < 0 or bits > 32:
            raise MKUserError(varprefix, _("Invalid number of bits. Must be in range 1 ... 32"))

        if value.count(".") != 3:
            raise MKUserError(varprefix, _("The network must contain three dots"))

        octets = self.validate_ipaddress(network, varprefix)

        # Make sure that non-network bits are zero
        l = (octets[0] << 24) + (octets[1] << 16) + (octets[2] << 8) + (octets[3])
        for b in range(bits, 32):
            if l & (2 ** (31-b)) != 0:
                raise MKUserError(varprefix, _("Please make sure that only the %d non-network bits are non-zero") % bits)

        ValueSpec.custom_validate(self, value, varprefix)


    def validate_ipaddress(self, value, varprefix):
        try:
            octets = map(int, value.split("."))
            if len(octets) != 4:
                raise MKUserError(varprefix, _("Please specify four octets (X.X.X.X/YY)"))
            for o in octets:
                if o < 0 or o > 255:
                    raise MKUserError(varprefix, _("Invalid octet %d (must be in range 1 ... 255)") % o)
            return octets
        except MKUserError:
            raise
        except:
            raise MKUserError(varprefix, _("Invalid IP address syntax"))


class IPv4Address(IPv4Network):
    def __init__(self, **kwargs):
        kwargs.setdefault("size", 16)
        IPv4Network.__init__(self, **kwargs)

    def validate_value(self, value, varprefix):
        self.validate_ipaddress(value, varprefix)
        ValueSpec.custom_validate(self, value, varprefix)

# A host name with or without domain part. Also allow IP addresses
class Hostname(TextAscii):
    def __init__(self, **kwargs):
        TextAscii.__init__(self, **kwargs)
        self._regex = re.compile('^[-0-9a-zA-Z_.]+$')
        self._regex_error = _("Please enter a valid hostname or IPv4 address.")

class AbsoluteDirname(TextAscii):
    def __init__(self, **kwargs):
        TextAscii.__init__(self, **kwargs)
        self._regex = re.compile('^(/|(/[^/]+)+)$')
        self._regex_error = _("Please enter a valid absolut pathname with / as a path separator.")


# Valuespec for a HTTP Url (not HTTPS), that
# automatically adds http:// to the value
class HTTPUrl(TextAscii):
    def __init__(self, **kwargs):
        TextAscii.__init__(self, **kwargs)
        self._target= kwargs.get("target")

    def validate_value(self, value, varprefix):
        TextAscii.validate_value(self, value, varprefix)
        if value:
            if not value.startswith("http://"):
                raise MKUserError(varprefix, _("The URL must begin with http://"))
        ValueSpec.custom_validate(self, value, varprefix)

    def from_html_vars(self, varprefix):
        value = TextAscii.from_html_vars(self, varprefix)
        if value:
            if not "://" in value:
                value = "http://" + value
        return value

    def value_to_text(self, url):
        if not url.startswith("http://"):
            url = "http://" + url
        try:
            parts = urlparse.urlparse(url)
            if parts.path in [ '', '/' ]:
                text = parts.netloc
            else:
                text = url[7:]
        except:
            text = url[7:]

        # Remove trailing / if the url does not contain
        # any path component
        return '<a %shref="%s">%s</a>' % (
            (self._target and 'target="%s" ' % self._target or ""),
            html.attrencode(url), html.attrencode(text))

class TextAreaUnicode(TextUnicode):
    def __init__(self, **kwargs):
        TextUnicode.__init__(self, **kwargs)
        self._cols = kwargs.get("cols", 60)
        self._rows = kwargs.get("rows", 20)  # Allowed: "auto" -> Auto resizing
        self._minrows = kwargs.get("minrows", 0) # Minimum number of initial rows when "auto"
        self._monospaced = kwargs.get("monospaced", False) # select TT font

    def value_to_text(self, value):
        if self._monospaced:
            return "<pre class=ve_textarea>%s</pre>" % html.attrencode(value)
        else:
            return html.attrencode(value).replace("\n", "<br>")

    def render_input(self, varprefix, value):
        if value == None:
            value = "" # should never happen, but avoids exception for invalid input
        if self._rows == "auto":
            func = 'valuespec_textarea_resize(this);'
            attrs = { "onkeyup" : func, "onmousedown" : func, "onmouseup" : func, "onmouseout" : func }
            if html.has_var(varprefix):
                rows = len(html.var(varprefix).splitlines())
            else:
                rows = len(value.splitlines())
            rows = max(rows, self._minrows)
        else:
            attrs = {}
            rows = self._rows

        if self._monospaced:
            attrs["class"] = "tt"

        html.text_area(varprefix, value, rows=rows, cols=self._cols, attrs = attrs)


    # Overridded because we do not want to strip() here and remove '\r'
    def from_html_vars(self, varprefix):
        text = html.var_utf8(varprefix, "").replace('\r', '')
        if text and not text.endswith("\n"):
            text += "\n" # force newline at end
        return text

# A variant of TextAscii() that validates a path to a filename that
# lies in an existing directory.
# TODO: Rename the valuespec here to ExistingFilename or somehting similar
class Filename(TextAscii):
    def __init__(self, **kwargs):
        TextAscii.__init__(self, **kwargs)
        if "size" not in kwargs:
            self._size = 60
        if "default" in kwargs:
            self._default_path = kwargs["default"]
        else:
            self._default_path = "/tmp/foo"
        if "trans_func" in kwargs:
            self._trans_func = kwargs["trans_func"]
        else:
            self._trans_func = None

    def canonical_value(self):
        return self._default_path

    def validate_value(self, value, varprefix):
        # The transformation function only changes the value for validation. This is
        # usually a function which is later also used within the code which uses
        # this variable to e.g. replace macros
        if self._trans_func:
            value = self._trans_func(value)

        if len(value) == 0:
            raise MKUserError(varprefix, _("Please enter a filename."))

        if value[0] != "/":
            raise MKUserError(varprefix, _("Sorry, only absolute filenames are allowed. "
                                           "Your filename must begin with a slash."))
        if value[-1] == "/":
            raise MKUserError(varprefix, _("Your filename must not end with a slash."))

        dir = value.rsplit("/", 1)[0]
        if not os.path.isdir(dir):
            raise MKUserError(varprefix, _("The directory %s does not exist or is not a directory." % dir))

        # Write permissions to the file cannot be checked here since we run with Apache
        # permissions and the file might be created with Nagios permissions (on OMD this
        # is the same, but for others not)

        ValueSpec.custom_validate(self, value, varprefix)

class ListOfStrings(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        if "valuespec" in kwargs:
            self._valuespec = kwargs.get("valuespec")
        elif "size" in kwargs:
            self._valuespec = TextAscii(size=kwargs["size"])
        else:
            self._valuespec = TextAscii()
        self._vertical = kwargs.get("orientation", "vertical") == "vertical"
        self._allow_empty = kwargs.get("allow_empty", True)
        self._empty_text  = kwargs.get("empty_text", "")

    def render_input(self, vp, value):
        # Form already submitted?
        if html.has_var(vp + "_0"):
            value = self.from_html_vars(vp)
            # Remove variables from URL, so that they do not appear
            # in hidden_fields()
            nr = 0
            while html.has_var(vp + "_%d" % nr):
                html.del_var(vp + "_%d" % nr)
                nr += 1

        html.write('<div class="listofstrings %s" id="%s">' % (self._vertical and 'vertical' or 'horizontal', vp))

        for nr, s in enumerate(value + [""]):
            html.write('<div>')
            self._valuespec.render_input(vp + "_%d" % nr, s)
            html.write('</div>')
        html.write('</div>')
        html.javascript("list_of_strings_init('%s');" % vp);

    def canonical_value(self):
        return []

    def value_to_text(self, value):
        if not value:
            return self._empty_text

        if self._vertical:
            s = '<table>'
            for v in value:
                s += '<tr><td>%s</td></tr>' % self._valuespec.value_to_text(v)
            return s + '</table>'
        else:
            return ", ".join([ self._valuespec.value_to_text(v) for v in value ])

    def from_html_vars(self, vp):
        value = []
        nr = 0
        while True:
            varname = vp + "_%d" % nr
            if not html.has_var(varname):
                break
            if html.var(varname, "").strip():
                value.append(self._valuespec.from_html_vars(varname))
            nr += 1
        return value

    def validate_datatype(self, value, vp):
        if type(value) != list:
            raise MKUserError(varprefix, _("Expected data type is "
            "list, but your type is %s." % type_name(value)))
        for nr, s in enumerate(value):
            self._valuespec.validate_datatype(s, vp + "_%d" % nr)

    def validate_value(self, value, vp):
        if len(value) == 0 and not self._allow_empty:
            if self._empty_text:
                msg = self._empty_text
            else:
                msg = _("Please specify at least one value")
            raise MKUserError(vp + "_0", msg)
        if self._valuespec:
            for nr, s in enumerate(value):
                self._valuespec.validate_value(s, vp + "_%d" % nr)
        ValueSpec.custom_validate(self, value, vp)

class ListOfIntegers(ListOfStrings):
    def __init__(self, **kwargs):
        int_args = {}
        for key in [ "minvalue", "maxvalue" ]:
            if key in kwargs:
                int_args[key] = kwargs[key]
        int_args["display_format"] = "%s"
        int_args["convfunc"] = lambda x: x != "" and saveint(x) or ""
        int_args["minvalue"] = 17
        int_args["default_value"] = 34
        valuespec = Integer(**int_args)
        kwargs["valuespec"] = valuespec
        ListOfStrings.__init__(self, **kwargs)

# Generic list-of-valuespec ValueSpec with Javascript-based
# add/delete/move
class ListOf(ValueSpec):
    def __init__(self, valuespec, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._valuespec = valuespec
        self._magic = kwargs.get("magic", "@!@")
        self._rowlabel = kwargs.get("row_label")
        self._add_label = kwargs.get("add_label", _("Add new element"))
        self._movable = kwargs.get("movable", True)
        self._totext = kwargs.get("totext")
        self._allow_empty = kwargs.get("allow_empty", True)
        self._empty_text  = kwargs.get("empty_text")
        if not self._empty_text:
            self._empty_text = _("Please specify at least on entry")

    def del_button(self, vp, nr):
        js = "valuespec_listof_delete(this, '%s', '%s')" % (vp, nr)
        html.icon_button("#", _("Delete this entry"), "delete", onclick=js)

    def move_button(self, vp, nr, where):
        js = "valuespec_listof_move(this, '%s', '%s', '%s')" % (vp, nr, where)
        where_name = {
            "up" : _("up"),
            "down" : _("down"),
        }
        html.empty_icon_button() # needed as placeholder
        html.icon_button("#", _("Move this entry %s") % (where_name[where]),
           where, onclick=js, style = (not self._movable) and "display: none" or "")

    # Implementation idea: we render our element-valuespec
    # once in a hidden div that is not evaluated. All occurances
    # of a magic string are replaced with the actual number
    # of entry, while beginning with 1 (this makes visual
    # numbering in labels, etc. possible). The current number
    # of entries is stored in the hidden variable 'varprefix'
    def render_input(self, varprefix, value):

        # Beware: the 'value' is only the default value in case the form
        # has not yet been filled in. In the complain phase we must
        # ignore 'value' but reuse the input from the HTML variables -
        # even if they are not syntactically correct. Calling from_html_vars
        # here is *not* an option since this might not work in case of
        # a wrong user input.

        # Render reference element for cloning
        html.write('<table style="display:none" id="%s_prototype">' % varprefix)
        html.write('<tr><td class=vlof_buttons>')
        html.hidden_field(varprefix + "_indexof_" + self._magic, "", add_var=True) # reconstruct order after moving stuff
        self.del_button(varprefix, self._magic)
        if self._movable:
            self.move_button(varprefix, self._magic, "up")
            self.move_button(varprefix, self._magic, "down")
        html.write('</td><td class=vlof_content>')
        self._valuespec.render_input(
            varprefix + "_" + self._magic,
            self._valuespec.default_value())
        html.write('</td></tr></table>')

        # In the 'complain' phase, where the user already saved the
        # form but the validation failed, we must not display the
        # original 'value' but take the value from the HTML variables.
        if html.has_var("%s_count" % varprefix):
            filled_in = True
            count = len(self.get_indexes(varprefix))
            value = [None] * count # dummy for the loop
        else:
            filled_in = False
            count = len(value)

        html.hidden_field('%s_count' % varprefix,
            str(count),
            id = '%s_count' % varprefix,
            add_var = True)

        # Actual table of currently existing entries
        html.write('<table class="valuespec_listof" id="%s_table">' % varprefix)

        # FIXME: Use plug/unplug mechanism instead of transform / then remove transform
        for nr, v in enumerate(value):
            html.push_transformation(lambda x: x.replace(self._magic, str(nr+1)))
            html.write('<tr><td class=vlof_buttons>')
            html.hidden_field(varprefix + "_indexof_%d" % (nr+1), "", add_var=True) # reconstruct order after moving stuff
            self.del_button(varprefix, nr+1)
            if self._movable:
                self.move_button(varprefix, self._magic, "up") # visibility fixed by javascript
                self.move_button(varprefix, self._magic, "down")
            html.write("</td><td class=vlof_content>")
            self._valuespec.render_input(varprefix + "_%d" % (nr+1), v)
            html.write("</td></tr>")
            html.pop_transformation()
        html.write("</table>")
        html.write("<br>")
        html.jsbutton(varprefix + "_add", self._add_label,
            "valuespec_listof_add('%s', '%s')" % (varprefix, self._magic));
        html.javascript("valuespec_listof_fixarrows(document.getElementById('%s_table').childNodes[0]);" % varprefix)

    def canonical_value(self):
        return []

    def value_to_text(self, value):
        if self._totext:
            if "%d" in self._totext:
                return self._totext % len(value)
            else:
                return self._totext
        else:
            s = '<table>'
            for v in value:
                s += '<tr><td>%s</td></tr>' % self._valuespec.value_to_text(v)
            return s + '</table>'

    def get_indexes(self, varprefix):
        count = int(html.var(varprefix + "_count"))
        n = 1
        indexes = {}
        while n <= count:
            indexof = html.var(varprefix + "_indexof_%d" % n)
            # for deleted entries, we have removed the whole row, therefore indexof is None
            if indexof != None:
                indexes[int(indexof)] = n
            n += 1
        return indexes

    def from_html_vars(self, varprefix):
        indexes = self.get_indexes(varprefix)
        value = []
        k = indexes.keys()
        k.sort()
        for i in k:
            val = self._valuespec.from_html_vars(varprefix + "_%d" % indexes[i])
            value.append(val)
        return value

    def validate_datatype(self, value, varprefix):
        if type(value) != list:
            raise MKUserError(varprefix, _("The type must be list, but is %s") % type_name(value))
        for n, v in enumerate(value):
            self._valuespec.validate_datatype(v, varprefix + "_%d" % (n+1))

    def validate_value(self, value, varprefix):
        if not self._allow_empty and len(value) == 0:
            raise MKUserError(varprefix, self._empty_text)
        for n, v in enumerate(value):
            self._valuespec.validate_value(v, varprefix + "_%d" % (n+1))
        ValueSpec.custom_validate(self, value, varprefix)


# A generic valuespec where the user can choose from a list of sub-valuespecs.
# Each sub-valuespec can be added only once
class ListOfMultiple(ValueSpec):
    def __init__(self, choices, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._choices = choices
        self._choice_dict = dict(choices)
        self._size = kwargs.get("size")
        self._add_label = kwargs.get("add_label", _("Add element"))
        self._delete_style = kwargs.get("delete_style", "default") # or "filter"

    def del_button(self, varprefix, ident):
        js = "vs_listofmultiple_del('%s', '%s')" % (varprefix, ident)
        html.icon_button("#", _("Delete this entry"), "delete", onclick=js)

    def render_input(self, varprefix, value):
        # Beware: the 'value' is only the default value in case the form
        # has not yet been filled in. In the complain phase we must
        # ignore 'value' but reuse the input from the HTML variables -
        # even if they are not syntactically correct. Calling from_html_vars
        # here is *not* an option since this might not work in case of
        # a wrong user input.

        # Special styling for filters
        if self._delete_style == "filter":
            extra_css=" filter"
        else:
            extra_css=""

        # In the 'complain' phase, where the user already saved the
        # form but the validation failed, we must not display the
        # original 'value' but take the value from the HTML variables.
        if html.var("%s_active" % varprefix):
            value = self.from_html_vars(varprefix)

        # Save all selected items
        html.hidden_field('%s_active' % varprefix,
            ';'.join([ k for k in value.keys() if k in self._choice_dict]),
            id = '%s_active' % varprefix, add_var = True)

        # Actual table of currently existing entries
        html.write('<table class="valuespec_listof%s" id="%s_table">' % (extra_css, varprefix))

        def render_content():
            html.write('<td class="vlof_content%s">' % extra_css)
            vs.render_input(prefix, value.get(ident))
            html.write("</td>")

        def render_del():
            html.write('<td class="vlof_buttons%s">' % extra_css)
            self.del_button(varprefix, ident)
            html.write('</td>')

        for ident, vs in self._choices:
            cls = ident not in value and 'unused' or ''
            prefix = varprefix + '_' + ident
            html.write('<tr id="%s_row" class="%s">' % (prefix, cls))
            if self._delete_style == "filter":
                render_content()
                render_del()
            else:
                render_del()
                render_content()
            html.write("</tr>")
        html.write("</table>")
        html.write("<br>")

        choosable = [('', '')] + [ (ident, vs.title()) for ident, vs in self._choices if ident not in value ]
        attrs = {}
        if self._size != None:
            attrs["style"] = "width: %dex" % self._size
        if self._delete_style == "filter":
            attrs["class"] = "vlof_filter"
        html.select(varprefix + '_choice', choosable, attrs=attrs)
        html.javascript('vs_listofmultiple_init(\'%s\');' % varprefix)
        html.jsbutton(varprefix + '_add', self._add_label, "vs_listofmultiple_add('%s')" % varprefix)

    def canonical_value(self):
        return {}

    def value_to_text(self, value):
        s = '<table>'
        for ident, val in value:
            vs = self._choice_dict[ident]
            s += '<tr><td>%s</td><td>%s</td></tr>' % (vs.title(), vs.value_to_text(val))
        return s + '</table>'

    def from_html_vars(self, varprefix):
        value = {}
        active = html.var('%s_active' % varprefix).strip()
        if not active:
            return value

        for ident in active.split(';'):
            vs = self._choice_dict[ident]
            value[ident] = vs.from_html_vars(varprefix + '_' + ident)
        return value

    def validate_datatype(self, value, varprefix):
        if type(value) != dict:
            raise MKUserError(varprefix, _("The type must be dict, but is %s") % type_name(value))
        for ident, val in value.items():
            self._choice_dict[ident].validate_datatype(val, varprefix + '_' + ident)

    def validate_value(self, value, varprefix):
        for ident, val in value.items():
            self._choice_dict[ident].validate_value(val, varprefix + '_' + ident)
        ValueSpec.custom_validate(self, value, varprefix)


# Same but for floating point values
class Float(Integer):
    def __init__(self, **kwargs):
        Integer.__init__(self, **kwargs)
        self._decimal_separator = kwargs.get("decimal_separator", ".")
        self._display_format = kwargs.get("display_format", "%.2f")
        self._allow_int = kwargs.get("allow_int", False)

    def render_input(self, varprefix, value):
        Integer.render_input(self, varprefix, value, convfunc = savefloat)

    def canonical_value(self):
        return float(Integer.canonical_value(self))

    def value_to_text(self, value):
        return Integer.value_to_text(self, value).replace(".", self._decimal_separator)

    def from_html_vars(self, varprefix):
        try:
            return float(html.var(varprefix))
        except:
            raise MKUserError(varprefix,
            _("The text <b><tt>%s</tt></b> is not a valid floating point number." % html.var(varprefix)))

    def validate_datatype(self, value, varprefix):
        if type(value) != float and not \
            (type(value) not in [ int, long ] and self._allow_int):
            raise MKUserError(varprefix, _("The value %r has type %s, but must be of type float%s") %
                 (value, type_name(value), self._allow_int and _(" or int") or ""))


class Percentage(Float):
    def __init__(self, **kwargs):
        Float.__init__(self, **kwargs)
        if "minvalue" not in kwargs:
            self._minvalue = 0.0
        if "maxvalue" not in kwargs:
            self._maxvalue = 101.0
        if "unit" not in kwargs:
            self._unit = "%"
        if "display_format" not in kwargs:
            self._display_format = "%.1f"

        self._allow_int = kwargs.get("allow_int", False)

    def value_to_text(self, value):
        return (self._display_format + "%%") % value

    def validate_datatype(self, value, varprefix):
        if self._allow_int:
            if type(value) not in [ int, float ]:
                raise MKUserError(varprefix, _("The value %r has type %s, but must be either float or int")
                                % (value, type_name(value)))
        else:
            Float.validate_datatype(self, value, varprefix)


class Checkbox(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._label = kwargs.get("label")
        self._true_label = kwargs.get("true_label", _("on"))
        self._false_label = kwargs.get("false_label", _("off"))
        self._onclick = kwargs.get("onclick")

    def canonical_value(self):
        return False

    def render_input(self, varprefix, value):
        html.checkbox(varprefix, value, label = self._label, onclick=self._onclick)

    def value_to_text(self, value):
        return value and self._true_label or self._false_label

    def from_html_vars(self, varprefix):
        if html.var(varprefix):
            return True
        else:
            return False

    def validate_datatype(self, value, varprefix):
        if type(value) != bool:
            raise MKUserError(varprefix, _("The value %r has type %s, but must be of type bool") %
                    (value, type_name(value)))

# A type-save dropdown choice. Parameters:
# help_separator: if you set this to a character, e.g. "-", then
# value_to_texg will omit texts from the character up to the end of
# a choices name.
# Note: The list of choices may contain 2-tuples or 3-tuples.
# The format is (value, text {, icon} )
# choices may also be a function that returns - when called
# wihtout arguments - such a tuple list. That way the choices
# can by dynamically computed
class DropdownChoice(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._choices = kwargs["choices"]
        self._help_separator = kwargs.get("help_separator")
        self._label = kwargs.get("label")
        self._prefix_values = kwargs.get("prefix_values", False)
        self._sorted = kwargs.get("sorted", False)

        self._no_preselect       = kwargs.get("no_preselect",       False)
        self._no_preselect_value = kwargs.get("no_preselect_value", None)
        self._no_preselect_title = kwargs.get("no_preselect_title", "") # if not preselected
        self._no_preselect_error = kwargs.get("no_preselect_error", _("Please make a selection"))

    def choices(self):
        result = []
        if type(self._choices) == list:
            result = self._choices
        else:
            result = self._choices()

        if self._no_preselect:
            return [(self._no_preselect_value, self._no_preselect_title)] + result
        else:
            return result

    def canonical_value(self):
        choices = self.choices()
        if len(choices) > 0:
            return choices[0][0]
        else:
            return None

    def render_input(self, varprefix, value):
        if self._label:
            html.write("%s " % self._label)
        # Convert values from choices to keys
        defval = "0"
        options = []
        for n, entry in enumerate(self.choices()):
            if self._prefix_values:
                entry = (entry[0], "%s - %s" % entry)
            options.append((str(n),) + entry[1:])
            if entry[0] == value:
                defval = str(n)
        if len(options) == 0:
            html.write(_("There are no options to select from"))
        elif len(options[0]) == 3:
            html.icon_select(varprefix, options, defval)
        else:
            if not self._sorted:
                html.select(varprefix, options, defval)
            else:
                html.sorted_select(varprefix, options, defval)

    def value_to_text(self, value):
        for entry in self.choices():
            val, title = entry[:2]
            if value == val:
                if self._help_separator:
                    return title.split(self._help_separator, 1)[0].strip()
                else:
                    return title
        return _("(other: %s)" % html.attrencode(value))

    def from_html_vars(self, varprefix):
        sel = html.var(varprefix)
        for n, entry in enumerate(self.choices()):
            val = entry[0]
            if sel == str(n):
                return val
        return self.default_value() # can only happen if user garbled URL or len(choices) == 0

    def validate_value(self, value, varprefix):
        if self._no_preselect and value == self._no_preselect_value:
            raise MKUserError(varprefix, self._no_preselect_error)

        ValueSpec.custom_validate(self, value, varprefix)

    def validate_datatype(self, value, varprefix):
        for val, title in self.choices():
            if val == value:
                return
        raise MKUserError(varprefix, _("Invalid value %s, must be in %s") %
            (value, ", ".join([v for (v,t) in self.choices()])))


# Special conveniance variant for monitoring states
class MonitoringState(DropdownChoice):
    def __init__(self, **kwargs):
        choices = [ ( 0, _("OK")),
                    ( 1, _("WARN")),
                    ( 2, _("CRIT")),
                    ( 3, _("UNKNOWN")) ]
        kwargs.setdefault("default_value", 0)
        DropdownChoice.__init__(self, choices=choices, **kwargs)

# A Dropdown choice where the elements are ValueSpecs.
# The currently selected ValueSpec will be displayed.
# The text representations of the ValueSpecs will be used as texts.
# A ValueSpec of None is also allowed and will return
# the value None. It is also allowed to leave out the
# value spec for some of the choices (which is the same as
# using None).
# The resulting value is either a single value (if no
# value spec is defined for the selected entry) or a pair
# of (x, y) where x is the value of the selected entry and
# y is the value of the valuespec assigned to that entry.
# choices is a list of triples: [ ( value, title, vs ), ... ]
class CascadingDropdown(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)

        if type(kwargs["choices"]) == list:
            self._choices = self.normalize_choices(kwargs["choices"])
        else:
            self._choices = kwargs["choices"] # function, store for later

        self._separator = kwargs.get("separator", ", ")
        self._html_separator = kwargs.get("html_separator", "<br>")
        self._sorted = kwargs.get("sorted", True)

    def normalize_choices(self, choices):
        new_choices = []
        for entry in choices:
            if len(entry) == 2: # plain entry with no sub-valuespec
                entry = entry + (None,) # normlize to three entries
            new_choices.append(entry)
        return new_choices

    def choices(self):
        if type(self._choices) == list:
            return self._choices
        else:
            return self.normalize_choices(self._choices())

    def canonical_value(self):
        choices = self.choices()
        if choices[0][2]:
            return (choices[0][0], choices[0][2].canonical_value())
        else:
            return choices[0][0]

    def default_value(self):
        try:
            return self._default_value
        except:
            choices = self.choices()
            if choices[0][2]:
                return (choices[0][0], choices[0][2].default_value())
            else:
                return choices[0][0]

    def render_input(self, varprefix, value):
        def_val = '0'
        options = []
        choices = self.choices()
        for nr, (val, title, vs) in enumerate(choices):
            options.append((str(nr), title))
            # Determine the default value for the select, so the
            # the dropdown pre-selects the line corresponding with value.
            # Note: the html.select() with automatically show the modified
            # selection, if the HTML variable varprefix_sel aleady
            # exists.
            if value == val or (
                type(value) == tuple and value[0] == val):
                def_val = str(nr)

        vp = varprefix + "_sel"
        onchange="valuespec_cascading_change(this, '%s', %d);" % (varprefix, len(choices))
        if self._sorted:
            html.select(vp, options, def_val, onchange=onchange)
        else:
            html.sorted_select(vp, options, def_val, onchange=onchange)

        # make sure, that the visibility is done correctly, in both
        # cases:
        # 1. Form painted for the first time (no submission yet, vp missing in URL)
        # 2. Form already submitted -> honor URL variable vp for visibility
        cur_val = html.var(vp)

        html.write(self._html_separator)
        for nr, (val, title, vs) in enumerate(choices):
            if vs:
                vp = varprefix + "_%d" % nr
                # Form already submitted once (and probably in complain state)
                if cur_val != None:
                    try:
                        def_val_2 = vs.from_html_vars(vp)
                    except MKUserError:
                        def_val_2 = vs.default_value()
                    if cur_val == str(nr):
                        disp = ""
                    else:
                        disp = "none"
                else: # form painted the first time
                    if value == val \
                       or (type(value) == tuple and value[0] == val):
                        def_val_2 = value[1]
                        disp = ""
                    else:
                        def_val_2 = vs.default_value()
                        disp = "none"
                html.write('<span id="%s_%s_sub" style="display: %s">' % (varprefix, nr, disp))
                html.help(vs.help())
                vs.render_input(vp, def_val_2)
                html.write('</span>')

    def value_to_text(self, value):
        choices = self.choices()
        for val, title, vs in choices:
            if (vs and value[0] == val) or \
               (value == val):
                if not vs:
                    return title
                else:
                    return title + self._separator + \
                       vs.value_to_text(value[1])
        return "" # Nothing selected? Should never happen

    def from_html_vars(self, varprefix):
        choices = self.choices()
        try:
            sel = int(html.var(varprefix + "_sel"))
        except:
            sel = 0
        val, title, vs = choices[sel]
        if vs:
            val = (val, vs.from_html_vars(varprefix + "_%d" % sel))
        return val

    def validate_datatype(self, value, varprefix):
        choices = self.choices()
        for nr, (val, title, vs) in enumerate(choices):
            if value == val or (
                type(value) == tuple and value[0] == val):
                if vs:
                    if type(value) != tuple or len(value) != 2:
                        raise MKUserError(varprefix + "_sel", _("Value must a tuple with two elements."))
                    vs.validate_datatype(value[1], varprefix + "_%d" % nr)
                return
        raise MKUserError(_("Value %r is not allowed here.") % value)

    def validate_value(self, value, varprefix):
        choices = self.choices()
        for nr, (val, title, vs) in enumerate(choices):
            if value == val or (
                type(value) == tuple and value[0] == val):
                if vs:
                    vs.validate_value(value[1], varprefix + "_%d" % nr)
                ValueSpec.custom_validate(self, value, varprefix)
                return
        raise MKUserError(varprefix, _("Value %r is not allowed here.") % (value, ))



# The same logic as the dropdown choice, but rendered
# as a group of radio buttons.
# columns == None or unset -> separate with "&nbsp;"
class RadioChoice(DropdownChoice):
    def __init__(self, **kwargs):
        DropdownChoice.__init__(self, **kwargs)
        self._columns = kwargs.get("columns")

    def render_input(self, varprefix, value):
        html.begin_radio_group()
        if self._columns != None:
            html.write("<table class=radiochoice>")
            html.write("<tr>")

        if self._sorted:
            choices = self._choices[:]
            choices.sort(cmp=lambda a,b: cmp(a[1], b[1]))
        else:
            choices = self._choices
        for n, entry in enumerate(choices):
            if self._columns != None:
                html.write("<td>")
            if len(entry) > 2 and entry[2] != None: # icon!
                label = '<img class=icon align=absmiddle src="images/icon_%s.png" title="%s">' % \
                        ( entry[2], entry[1].encode("utf-8"))
            else:
                label = entry[1]
            html.radiobutton(varprefix, str(n), value == entry[0], label)
            if len(entry) > 3 and entry[3]:
                html.write('<p>%s</p>' % entry[3])
            if self._columns != None:
                html.write("</td>")
                if (n+1) % self._columns == 0 and (n+1) < len(self._choices):
                    html.write("<tr></tr>")
            else:
                html.write("&nbsp;")
        if self._columns != None:
            mod = len(self._choices) % self._columns
            if mod:
                html.write("<td></td>" * (self._columns - mod - 1))
            html.write("</tr></table>")
        html.end_radio_group()



# A list of checkboxes representing a list of values
class ListChoice(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._choices = kwargs.get("choices")
        self._columns = kwargs.get("columns", 1)
        self._allow_empty = kwargs.get("allow_empty", True)
        self._loaded_at = None
        self._render_function = kwargs.get("render_function",
                  lambda id, val: val)
        self._toggle_all = kwargs.get("toggle_all", False)
        self._render_orientation = kwargs.get("render_orientation", "horizontal") # other: vertical

    # In case of overloaded functions with dynamic elements
    def load_elements(self):
        if self._choices != None:
            if type(self._choices) == list:
                self._elements = self._choices
            else:
                self._elements = self._choices()
            return

        if self._loaded_at != id(html):
            self._elements = self.get_elements()
            self._loaded_at = id(html) # unique for each query!

    def canonical_value(self):
        return []

    def render_input(self, varprefix, value):
        self.load_elements()
        if self._toggle_all:
            html.write("<a href=\"javascript:vs_list_choice_toggle_all('%s')\">%s</a>" %
                        (varprefix, _("Check / Uncheck all")))
        html.write("<table id=\"%s_tbl\" class=listchoice>" % varprefix)
        for nr, (key, title) in enumerate(self._elements):
            if nr % self._columns == 0:
                if nr > 0:
                    html.write("</tr>")
                html.write("<tr>")
            html.write("<td>")
            html.checkbox("%s_%d" % (varprefix, nr), key in value, label = title)
            html.write("</td>")
        html.write("</tr></table>")
        # Make sure that at least one variable with the prefix is present
        html.hidden_field(varprefix, "1")

    def value_to_text(self, value):
        self.load_elements()
        d = dict(self._elements)
        texts = [ self._render_function(v, d.get(v,v)) for v in value ]
        if self._render_orientation == "horizontal":
            return ", ".join(texts)
        else:
            return "<table><tr><td>" + "<br>".join(texts) + "</td></tr></table>"

    def from_html_vars(self, varprefix):
        self.load_elements()
        value = []

        for nr, (key, title) in enumerate(self._elements):
            if html.get_checkbox("%s_%d" % (varprefix, nr)):
                value.append(key)
        return value

    def validate_datatype(self, value, varprefix):
        self.load_elements()
        if type(value) != list:
            raise MKUserError(varprefix, _("The datatype must be list, but is %s") % type_name(value))
        d = dict(self._elements)
        for v in value:
            if v not in d:
                raise MKUserError(varprefix, _("%s is not an allowed value") % v)

    def validate_value(self, value, varprefix):
        if not self._allow_empty and not value:
            raise MKUserError(varprefix, _('You have to select at least one element.'))
        ValueSpec.custom_validate(self, value, varprefix)

# A alternative way of editing list choices
class MultiSelect(ListChoice):
    def __init__(self, **kwargs):
        ListChoice.__init__(self, **kwargs)

    def _render_field(self, name, choices, selected = []):
        html.write("<select multiple name=\"%s\">\n" % name)
        for key, title in choices:
            if key in selected:
                sel = " selected"
            else:
                sel = ""
            html.write('<option value="%s"%s>%s</option>\n' % (key, sel, title))
        html.write("</select>\n")

    def render_input(self, varprefix, value):
        self.load_elements()
        self._render_field(varprefix, self._elements, value)

    def from_html_vars(self, varprefix):
        self.load_elements()
        value = []
        hv = html.list_var(varprefix)
        for key, title in self._elements:
            if key in hv:
                value.append(key)
        return value

# Implements a choice of items which is realized with
# two ListChoices select fields. One contains all available
# items and one contains all selected items.
# Optionally you can have the user influance the order of
# the entries by simply clicking them in a certain order.
# If that feature is not being used, then the original order
# of the elements is always being kept.
class DualListChoice(ListChoice):
    def __init__(self, **kwargs):
        ListChoice.__init__(self, **kwargs)
        self._autoheight = kwargs.get("autoheight", True)
        self._custom_order = kwargs.get("custom_order", False)
        self._instant_add = kwargs.get("instant_add", False)
        self._enlarge_active = kwargs.get("enlarge_active", False)

    def render_input(self, varprefix, value):
        self.load_elements()
        if not self._elements:
            html.write(_("There are no elements for selection."))
            return

        selected   = []
        unselected = []
        if self._custom_order:
            edict = dict(self._elements)
            allowed_keys = edict.keys()
            for v in value:
                if v in allowed_keys:
                    selected.append((v, edict[v]))
            for v in allowed_keys:
                if v not in value:
                    unselected.append((v, edict[v]))
        else:
            for e in self._elements:
                if e[0] in value:
                    selected.append(e)
                else:
                    unselected.append(e)

        select_func   = 'vs_duallist_switch(\'unselected\', \'%s\', %d);' % (varprefix, self._custom_order and 1 or 0)
        unselect_func = 'vs_duallist_switch(\'selected\', \'%s\', 1);' % varprefix

        html.write('<table class="vs_duallist"><tr><td class="head">')
        html.write(_('Available'))
        if not self._instant_add:
            html.write('<a href="javascript:%s" class="control add">&gt;</a>' % select_func)
        html.write('</td><td class="head">')
        html.write(_('Selected'))
        if not self._instant_add:
            html.write('<a href="javascript:%s" class="control del">&lt;</a>' % unselect_func)
        html.write('</td></tr><tr><td>')

        if self._instant_add:
            onchange_unselected = select_func
            onchange_selected   = unselect_func
        else:
            onchange_unselected = ''
            onchange_selected = ''

        if self._enlarge_active:
            onchange_selected   += ';vs_duallist_enlarge(\'selected\', \'%s\')' % varprefix
            onchange_unselected += ';vs_duallist_enlarge(\'unselected\', \'%s\')' % varprefix

        html.sorted_select(varprefix + '_unselected', unselected,
                           attrs = {
                               'size'       : 5,
                               'multiple'   : 'multiple',
                               'style'      : self._autoheight and 'height:auto' or '',
                               'ondblclick' : not self._instant_add and select_func or '',
                           },
                           onchange = onchange_unselected)
        html.write('</td><td>')
        func = self._custom_order and html.select or html.sorted_select
        func(varprefix + '_selected', selected,
                           attrs = {
                               'size'       : 5,
                               'multiple'   : 'multiple',
                               'style'      : self._autoheight and 'height:auto' or '',
                               'ondblclick' : not self._instant_add and unselect_func or '',
                           },
                           onchange = onchange_selected)
        html.write('</td></tr></table>')
        html.hidden_field(varprefix, '|'.join([k for k, v in selected]), id = varprefix, add_var = True)

    def from_html_vars(self, varprefix):
        self.load_elements()
        selected = html.var(varprefix, '').split('|')
        value = []
        if self._custom_order:
            edict = dict(self._elements)
            allowed_keys = edict.keys()
            for v in selected:
                if v in allowed_keys:
                    value.append(v)
        else:
            for key, title in self._elements:
                if key in selected:
                    value.append(key)
        return value

# A type-save dropdown choice with one extra field that
# opens a further value spec for entering an alternative
# Value.
class OptionalDropdownChoice(DropdownChoice):
    def __init__(self, **kwargs):
        DropdownChoice.__init__(self, **kwargs)
        self._explicit = kwargs["explicit"]
        self._otherlabel = kwargs.get("otherlabel", _("Other"))

    def canonical_value(self):
        return self._explicit.canonical_value()

    def value_is_explicit(self, value):
        return value not in [ c[0] for c in self.choices() ]

    def render_input(self, varprefix, value):
        defval = "other"
        options = []
        for n, (val, title) in enumerate(self.choices()):
            options.append((str(n), title))
            if val == value:
                defval = str(n)
        if self._sorted:
            options.sort(cmp = lambda a,b: cmp(a[1], b[1]))
        options.append(("other", self._otherlabel))
        html.select(varprefix, options, defval, # attrs={"style":"float:left;"},
                    onchange="valuespec_toggle_dropdown(this, '%s_ex');" % varprefix )
        if html.has_var(varprefix):
            div_is_open = html.var(varprefix) == "other"
        else:
            div_is_open = self.value_is_explicit(value)

        html.write('<span id="%s_ex" style="white-space: nowrap; %s">' % (
            varprefix, not div_is_open and "display: none;" or ""))
        html.write("&nbsp;")

        if defval == "other":
            input_value = value
        else:
            input_value = self._explicit.default_value()
        self._explicit.render_input(varprefix + "_ex", input_value)
        html.write("</span>")

    def value_to_text(self, value):
        for val, title in self.choices():
            if val == value:
                return title
        return self._explicit.value_to_text(value)

    def from_html_vars(self, varprefix):
        choices = self.choices()
        sel = html.var(varprefix)
        if sel == "other":
            return self._explicit.from_html_vars(varprefix + "_ex")

        for n, (val, title) in enumerate(choices):
            if sel == str(n):
                return val
        return choices[0][0] # can only happen if user garbled URL

    def validate_value(self, value, varprefix):
        if self.value_is_explicit(value):
            self._explicit.validate_value(value, varprefix)
        # else valid_datatype already has made the job
        ValueSpec.custom_validate(self, value, varprefix)

    def validate_datatype(self, value, varprefix):
        for val, title in self.choices():
            if val == value:
                return
        self._explicit.validate_datatype(value, varprefix + "_ex")


# Input of date with optimization for nearby dates
# in the future. Useful for example for alarms. The
# date is represented by a UNIX timestamp where the
# seconds are silently ignored.
def round_date(t):
    return int(t) / seconds_per_day * seconds_per_day

def today():
    return round_date(time.time())

seconds_per_day = 86400

weekdays = {
   0: _("Monday"),
   1: _("Tuesday"),
   2: _("Wednesday"),
   3: _("Thursday"),
   4: _("Friday"),
   5: _("Saturday"),
   6: _("Sunday"),
}

class Weekday(DropdownChoice):
    def __init__(self, **kwargs):
        choices = weekdays.items()
        choices.sort()
        kwargs['choices'] = choices
        DropdownChoice.__init__(self, **kwargs)


class RelativeDate(OptionalDropdownChoice):
    def __init__(self, **kwargs):
        choices = [
            (0, _("today")),
            (1, _("tomorrow"))
        ]
        weekday = time.localtime(today()).tm_wday
        for w in range(2, 7):
            wd = (weekday + w) % 7
            choices.append((w, weekdays[wd]))
        for w in range(0, 7):
            wd = (weekday + w) % 7
            if w < 2:
                title = _(" next week")
            else:
                title = _(" in %d days") % (w + 7)
            choices.append((w + 7, weekdays[wd] + title))

        kwargs['choices']    = choices
        kwargs['explicit']   = Integer()
        kwargs['otherlabel'] = _("in ... days")

        OptionalDropdownChoice.__init__(self, **kwargs)

        if "default_days" in kwargs:
            self._default_value = kwargs["default_days"] * seconds_per_day + today()
        else:
            self._default_value = today()

    def canonical_value(self):
        return self._default_value

    def render_input(self, varprefix, value):
        reldays = (round_date(value) - today()) / seconds_per_day
        OptionalDropdownChoice.render_input(self, varprefix, reldays)

    def value_to_text(self, value):
        reldays = (round_date(value) - today()) / seconds_per_day
        if reldays == -1:
            return _("yesterday")
        elif reldays == -2:
            return _("two days ago")
        elif reldays < 0:
            return _("%d days ago") % -reldays
        elif reldays < len(self._choices):
            return self._choices[reldays][1]
        else:
            return _("in %d days") % reldays

    def from_html_vars(self, varprefix):
        reldays = OptionalDropdownChoice.from_html_vars(self, varprefix)
        return today() + reldays * seconds_per_day

    def validate_datatype(self, value, varprefix):
        if type(value) not in [ float, int ]:
            raise MKUserError(varprefix, _("Date must be a number value"))

    def validate_value(self, value, varprefix):
        ValueSpec.custom_validate(self, value, varprefix)

# A ValueSpec for editing a date. The date is
# represented as a UNIX timestamp x where x % seconds_per_day
# is zero (or will be ignored if non-zero), as long es
# include_time is not set to True
class AbsoluteDate(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._show_titles = kwargs.get("show_titles", True)
        self._label = kwargs.get("label")
        self._include_time = kwargs.get("include_time", False)
        self._format = kwargs.get("format", self._include_time and "%F %T" or "%F")
        self._default_value = kwargs.get("default_value", None)
        self._allow_empty = kwargs.get('allow_empty', False)

    def default_value(self):
        if self._default_value != None:
            return self._default_value
        else:
            if self._allow_empty:
                return None

            if self._include_time:
                return time.time()
            else:
                return today()

    def canonical_value(self):
        return self.default_value()

    def split_date(self, value):
        lt = time.localtime(value)
        return lt.tm_year, lt.tm_mon, lt.tm_mday, \
               lt.tm_hour, lt.tm_min, lt.tm_sec

    def render_input(self, varprefix, value):
        if self._label:
            html.write("%s&nbsp;" % self._label)

        if self._show_titles:
            html.write('<table class=vs_date>')
            html.write('<tr><th>%s</th><th>%s</th><th>%s</th>' % (
                    _("Year"), _("Month"), _("Day")))
            if self._include_time:
                html.write('<th></th><th>%s</th><th>%s</th><th>%s</th>' % (
                   _("Hour"), _("Minute"), _("Sec.")))
            html.write('</tr><tr><td>')
        year, month, day, hour, mmin, sec = self.split_date(value)
        html.number_input(varprefix + "_year", year, size=4)
        if self._show_titles:
            html.write('</td><td>')
        else:
            html.write(" ")
        html.number_input(varprefix + "_month", month, size=2)
        if self._show_titles:
            html.write('</td><td>')
        else:
            html.write(" ")
        html.number_input(varprefix + "_day", day, size=2)
        if self._show_titles:
            html.write('</td>')

        if self._include_time:
            if self._show_titles:
                html.write('<td>&nbsp</td><td>')
            else:
                html.write(" ")
            html.number_input(varprefix + "_hour", hour, size=2)

            if self._show_titles:
                html.write('</td><td>')
            else:
                html.write(" ")
            html.number_input(varprefix + "_min", mmin, size=2)

            if self._show_titles:
                html.write('</td><td>')
            else:
                html.write(" ")
            html.number_input(varprefix + "_sec", sec, size=2)
            if self._show_titles:
                html.write('</td>')

        if self._show_titles:
            html.write('</tr></table>')

    def set_focus(self, varprefix):
        html.set_focus(varprefix + "_year")

    def value_to_text(self, value):
        return time.strftime(self._format, time.localtime(value))

    def from_html_vars(self, varprefix):
        parts = []
        entries = [
            ("year", 1970, 2038),
            ("month",   1,   12),
            ("day",     1,   31)]
        if self._include_time:
            entries += [
              ("hour", 0, 23),
              ("min",  0, 59),
              ("sec",  0, 59),
            ]

        for what, mmin, mmax in entries:
            try:
                varname = varprefix + "_" + what
                part = int(html.var(varname))
            except:
                if self._allow_empty:
                    return None
                else:
                    raise MKUserError(varname, _("Please enter a correct number"))
            if part < mmin or part > mmax:
                raise MKUserError(varname, _("The value for %s must be between %d and %d" % (_(what), mmin, mmax)))
            parts.append(part)

        # Construct broken time from input fields. Assume no-dst
        parts += [0] * (self._include_time and 3 or 6)
        # Convert to epoch
        epoch = time.mktime(tuple(parts))
        # Convert back to localtime in order to know DST setting
        localtime = time.localtime(epoch)
        # Enter DST setting of that time
        parts[-1] = localtime.tm_isdst
        # Convert to epoch again
        return time.mktime(tuple(parts))

    def validate_datatype(self, value, varprefix):
        if value == None and self._allow_empty:
            return
        if type(value) not in [ int, float ]:
            raise MKUserError(varprefix, _("The type of the timestamp must be int or float, but is %s") %
                              type_name(value))

    def validate_value(self, value, varprefix):
        if (not self._allow_empty and value == None) or value < 0 or int(value) > (2**31-1):
            return MKUserError(varprefix, _("%s is not a valid UNIX timestamp") % value)
        ValueSpec.custom_validate(self, value, varprefix)


# Valuespec for entering times like 00:35 or 16:17. Currently
# no seconds are supported. But this could easily be added.
# The value itself is stored as a pair of integers, a.g.
# (0, 35) or (16, 17). If the user does not enter a time
# the vs will return None.
class Timeofday(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._allow_24_00 = kwargs.get("allow_24_00", False)
        self._allow_empty = kwargs.get("allow_empty", True)

    def canonical_value(self):
        if self._allow_empty:
            return None
        else:
            return (0, 0)

    def render_input(self, varprefix, value):
        text = value and ("%02d:%02d" % value) or ""
        html.text_input(varprefix, text, size = 5)

    def value_to_text(self, value):
        if value == None:
            return ""
        else:
            return "%02d:%02d" % value

    def from_html_vars(self, varprefix):
        # Fully specified
        text = html.var(varprefix, "").strip()
        if not text:
            return None

        if re.match("^(24|[0-1][0-9]|2[0-3]):[0-5][0-9]$", text):
            return tuple(map(int, text.split(":")))

        # only hours
        try:
            b = int(text)
            return (b, 0)
        except:
            raise MKUserError(varprefix,
                   _("Invalid time format '<tt>%s</tt>', please use <tt>24:00</tt> format.") % text)

    def validate_datatype(self, value, varprefix):
        if self._allow_empty and value == None:
            return

        if type(value) != tuple:
            raise MKUserError(varprefix, _("The datatype must be tuple, but ist %s" % type_name(value)))

        if len(value) != 2:
            raise MKUserError(varprefix, _("The tuple must contain two elements, but you have %d" % len(value)))

        for x in value:
            if type(x) != int:
                raise MKUserError(varprefix, _("All elements of the tuple must be of type int, you have %s" % type_name(x)))

    def validate_value(self, value, varprefix):
        if not self._allow_empty and value == None:
            raise MKUserError(varprefix, _("Please enter a time."))
        if self._allow_24_00:
            max_value = (24, 0)
        else:
            max_value = (23, 59)
        if value > max_value:
            raise MKUserError(varprefix, _("The time must not be greater than %02d:%02d." % max_value))
        elif value[0] < 0 or value[1] < 0 or value[0] > 24 or value[1] > 59:
            raise MKUserError(varprefix, _("Hours/Minutes out of range"))
        ValueSpec.custom_validate(self, value, varprefix)


# Range like 00:15 - 18:30
class TimeofdayRange(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._allow_empty = kwargs.get("allow_empty", True)
        self._bounds = (
            Timeofday(allow_empty = self._allow_empty,
                      allow_24_00 = True),
            Timeofday(allow_empty = self._allow_empty,
                      allow_24_00 = True),
        )

    def canonical_value(self):
        if self._allow_empty:
            return None
        else:
            return (0, 0), (24, 0)

    def render_input(self, varprefix, value):
        if value == None:
            value = (None, None)
        self._bounds[0].render_input(varprefix + "_from", value[0])
        html.write("&nbsp;-&nbsp;")
        self._bounds[1].render_input(varprefix + "_until", value[1])

    def value_to_text(self, value):
        return self._bounds[0].value_to_text(value[0]) + "-" + \
               self._bounds[1].value_to_text(value[1])

    def from_html_vars(self, varprefix):
        from_value = self._bounds[0].from_html_vars(varprefix + "_from")
        until_value = self._bounds[1].from_html_vars(varprefix + "_until")
        if (from_value == None) != (until_value == None):
            raise MKUserError(varprefix + "_from", _("Please leave either both from and until empty or enter two times."))
        if from_value == None:
            return None
        else:
            return (from_value, until_value)

    def validate_datatype(self, value, varprefix):
        if self._allow_empty and value == None:
            return

        if type(value) != tuple:
            raise MKUserError(varprefix, _("The datatype must be tuple, but ist %s" % type_name(value)))

        if len(value) != 2:
            raise MKUserError(varprefix, _("The tuple must contain two elements, but you have %d" % len(value)))

        self._bounds[0].validate_datatype(value[0], varprefix + "_from")
        self._bounds[1].validate_datatype(value[1], varprefix + "_until")

    def validate_value(self, value, varprefix):
        self._bounds[0].validate_value(value[0], varprefix + "_from")
        self._bounds[1].validate_value(value[1], varprefix + "_until")
        if value[0] > value[1]:
            raise MKUserError(varprefix + "_until", _("The <i>from</i> time must not be greater then the <i>until</i> time."))
        ValueSpec.custom_validate(self, value, varprefix)

month_names = [
  _("January"),   _("February"), _("March"),    _("April"),
  _("May"),       _("June"),     _("July"),     _("August"),
  _("September"), _("October"),  _("November"), _("December")
]

class Timerange(CascadingDropdown):
    def __init__(self, **kwargs):
        self._title = _('Time range')

        if 'choices' not in kwargs:
            kwargs['choices'] = []

        if kwargs.get('allow_empty', False):
            kwargs['choices'] += [
                (None, ''),
            ]

        kwargs['choices'] += [
            ( "d0",  _("Today") ),
            ( "d1",  _("Yesterday") ),

            ( "w0",  _("This week") ),
            ( "w1",  _("Last week") ),

            ( "m0",  _("This month") ),
            ( "m1",  _("Last month") ),

            ( "y0",  _("This year") ),
            ( "y1",  _("Last year") ),

            ( "age", _("The last..."), Age() ),
            ( "date", _("Explicit date..."),
                Tuple(
                    orientation = "horizontal",
                    title_br = False,
                    elements = [
                        AbsoluteDate(title = _("From:")),
                        AbsoluteDate(title = _("To:")),
                    ],
                ),
            ),
        ]

        if kwargs.get('include_time', False):
            kwargs['choices'].append(
                ( "time", _("Explicit time..."),
                    Tuple(
                        orientation = "horizontal",
                        title_br = False,
                        elements = [
                            AbsoluteDate(
                                title = _("From:"),
                                include_time = True,
                            ),
                            AbsoluteDate(
                                title = _("To:"),
                                include_time = True,
                            ),
                        ],
                    ),
                )
            )

        CascadingDropdown.__init__(self, **kwargs)

    def compute_range(self, rangespec):
        now = time.time()
        if rangespec[0] == 'age':
            from_time = now - rangespec[1]
            until_time = now
            title = _("The last ") + Age().value_to_text(rangespec[1])
            return (from_time, until_time), title
        elif rangespec[0] in [ 'date', 'time' ]:
            from_time, until_time = rangespec[1]
            if from_time > until_time:
                raise MKUserError("avo_rangespec_9_0_year", _("The end date must be after the start date"))
            until_time += 86400 # Consider *end* of this day
            title = AbsoluteDate().value_to_text(from_time) + " ... " + \
                    AbsoluteDate().value_to_text(until_time)
            return (from_time, until_time), title

        else:
            # year, month, day_of_month, hour, minute, second, day_of_week, day_of_year, is_daylightsavingtime
            broken = list(time.localtime(now))
            broken[3:6] = 0, 0, 0 # set time to 00:00:00
            midnight = time.mktime(broken)

            until_time = now
            if rangespec[0] == 'd': # this/last Day
                from_time = time.mktime(broken)
                titles = _("Today"), _("Yesterday")

            elif rangespec[0] == 'w': # week
                from_time = midnight - (broken[6]) * 86400
                titles = _("This week"), _("Last week")

            elif rangespec[0] == 'm': # month
                broken[2] = 1
                from_time = time.mktime(broken)
                last_year = broken[0] - ((broken[1] == 1) and 1 or 0)
                titles = month_names[broken[1] - 1] + " " + str(broken[0]), \
                         month_names[(broken[1] + 10) % 12] + " " + str(last_year)

            elif rangespec[0] == 'y': # year
                broken[1:3] = [1, 1]
                from_time = time.mktime(broken)
                titles = str(broken[0]), str(broken[0]-1)

            if rangespec[1] == '0':
                return (from_time, now), titles[0]

            else: # last (previous)
                if rangespec[0] == 'd':
                    return (from_time - 86400, from_time), titles[1]
                elif rangespec[0] == 'w':
                    return (from_time - 7 * 86400, from_time), titles[1]

                until_time = from_time
                from_broken = list(time.localtime(from_time))
                if rangespec[0] == 'y':
                    from_broken[0] -= 1
                else: # m
                    from_broken[1] -= 1
                    if from_broken[1] == 0:
                        from_broken[1] = 12
                        from_broken[0] -= 1
                return (time.mktime(from_broken), until_time), titles[1]

class PNPTimerange(Timerange):
    def __init__(self, **kwargs):
        choosable = [
            ("0", _("4 Hours")),  ("1", _("25 Hours")),
            ("2", _("One Week")), ("3", _("One Month")),
            ("4", _("One Year")),
        ]

        if kwargs.get('allow_all', True):
            choosable.append(("", _("All")))

        kwargs['choices'] = [
            ('pnp_view', _("PNP View"), DropdownChoice(
                default_value = '1',
                choices = choosable,
            )),
        ]
        Timerange.__init__(self, **kwargs)


# A selection of various date formats
def DateFormat(**args):
    args.setdefault("title", _("Date format"))
    args.setdefault("default_value", "%Y-%m-%d")
    args["choices"] = [
        ("%Y-%m-%d", "1970-12-18"),
        ("%d.%m.%Y", "18.12.1970"),
        ("%m/%d/%Y", "12/18/1970"),
        ("%d.%m.",   "18.12."),
        ("%m/%d",    "12/18"),
    ]
    return DropdownChoice(**args)


def TimeFormat(**args):
    args.setdefault("title", _("Time format"))
    args.setdefault("default_value", "%H:%M:%S")
    args["choices"] = [
        ("%H:%M:%S",    "18:27:36"),
        ("%l:%M:%S %p", "12:27:36 PM"),
        ("%H:%M",       "18:27"),
        ("%l:%M %p",    "6:27 PM"),
        ("%H",          "18"),
        ("%l %p",      "6 PM"),
    ]
    return DropdownChoice(**args)



# Make a configuration value optional, i.e. it may be None.
# The user has a checkbox for activating the option. Example:
# debug_log: it is either None or set to a filename.
class Optional(ValueSpec):
    def __init__(self, valuespec, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._valuespec = valuespec
        self._label = kwargs.get("label")
        self._negate = kwargs.get("negate", False)
        self._none_label = kwargs.get("none_label", _("(unset)"))
        self._none_value = kwargs.get("none_value", None)
        self._sameline = kwargs.get("sameline", False)
        self._indent = kwargs.get("indent", True)

    def canonical_value(self):
        return self._none_value

    def render_input(self, varprefix, value):
        div_id = "option_" + varprefix
        checked = html.get_checkbox(varprefix + "_use")
        if checked == None:
            if self._negate:
                checked = value == self._none_value
            else:
                checked = value != self._none_value

        html.write("<span>")

        if self._label is not None:
            label = self._label
        elif self.title():
            label = _(self.title())
        elif self._negate:
            label = _(" Ignore this option")
        else:
            label = _(" Activate this option")

        html.checkbox(varprefix + "_use" , checked,
                      onclick="valuespec_toggle_option(this, %r, %r)" %
                         (div_id, self._negate and 1 or 0),
                      label = label)

        if self._sameline:
            html.write("&nbsp;")
        else:
            html.write("<br>")
        html.write("</span>")
        if checked == self._negate:
            display = "none"
        else:
            display = ""
        if self._indent:
            indent = 40
        else:
            indent = 0

        html.write('<span id="%s" style="margin-left: %dpx; display: %s">' % (div_id, indent, display))
        if value == self._none_value:
            value = self._valuespec.default_value()
        if self._valuespec.title():
            html.write(self._valuespec.title() + " ")
        self._valuespec.render_input(varprefix + "_value", value)
        html.write('</span>\n')

    def value_to_text(self, value):
        if value == self._none_value:
            return self._none_label
        else:
            return self._valuespec.value_to_text(value)

    def from_html_vars(self, varprefix):
        if html.get_checkbox(varprefix + "_use") != self._negate:
            return self._valuespec.from_html_vars(varprefix + "_value")
        else:
            return self._none_value

    def validate_datatype(self, value, varprefix):
        if value != self._none_value:
            self._valuespec.validate_datatype(value, varprefix + "_value")

    def validate_value(self, value, varprefix):
        if value != self._none_value:
            self._valuespec.validate_value(value, varprefix + "_value")
        ValueSpec.custom_validate(self, value, varprefix)

# Makes a configuration value optional, while displaying the current
# value as text with a checkbox in front of it. When the checkbox is being checked,
# the text hides and the encapsulated valuespec is being shown.
class OptionalEdit(Optional):
    def __init__(self, valuespec, **kwargs):
        Optional.__init__(self, valuespec, **kwargs)
        self._label = ''

    def render_input(self, varprefix, value):
        div_id = "option_" + varprefix
        checked = html.get_checkbox(varprefix + "_use")
        if checked == None:
            if self._negate:
                checked = True
            else:
                checked = False

        html.write("<span>")

        if self._label is not None:
            label = self._label
        elif self.title():
            label = _(self.title())
        elif self._negate:
            label = _(" Ignore this option")
        else:
            label = _(" Activate this option")

        html.checkbox(varprefix + "_use" , checked,
                      onclick="valuespec_toggle_option(this, %r, %r);valuespec_toggle_option(this, %r, %r)" %
                         (div_id + '_on', self._negate and 1 or 0,
                          div_id + '_off', self._negate and 0 or 1),
                      label = label)

        html.write("&nbsp;")
        html.write("</span>")

        display_on  = checked == self._negate and 'none' or ''
        display_off = checked != self._negate and 'none' or ''

        if value == None:
            value = self._valuespec.default_value()

        html.write('<span id="%s_off" style="display:%s">' % (div_id, display_off))
        html.write(value)
        html.write('</span>')

        html.write('<span id="%s_on" style="display:%s">' % (div_id, display_on))
        if self._valuespec.title():
            html.write(self._valuespec.title() + " ")
        self._valuespec.render_input(varprefix + "_value", value)
        html.write('</span>\n')

    def from_html_vars(self, varprefix):
        return self._valuespec.from_html_vars(varprefix + "_value")

# Handle case when there are several possible allowed formats
# for the value (e.g. strings, 4-tuple or 6-tuple like in SNMP-Communities)
# The different alternatives must have different data types that can
# be distinguished with validate_datatype.
class Alternative(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._elements = kwargs["elements"]
        self._match = kwargs.get("match") # custom match function
        self._style = kwargs.get("style", "radio") # alternative: "dropdown"
        self._show_alternative_title = kwargs.get("show_alternative_title")

    # Return the alternative (i.e. valuespec)
    # that matches the datatype of a given value. We assume
    # that always one matches. No error handling here.
    def matching_alternative(self, value):
        if self._match:
            return self._elements[self._match(value)]

        for vs in self._elements:
            try:
                vs.validate_datatype(value, "")
                return vs
            except:
                pass

    def render_input(self, varprefix, value):
        if self._style == "radio":
            self.render_input_radio(varprefix, value)
        else:
            self.render_input_dropdown(varprefix, value)

    def render_input_dropdown(self, varprefix, value):
        mvs = self.matching_alternative(value)
        options = []
        sel_option = html.var(varprefix + "_use")
        for nr, vs in enumerate(self._elements):
            if not sel_option and vs == mvs:
                sel_option = str(nr)
            options.append((str(nr), vs.title()))
        onchange="valuespec_cascading_change(this, '%s', %d);" % (varprefix, len(options))
        html.select(varprefix + "_use", options, sel_option, onchange)
        html.write("&nbsp;")

        for nr, vs in enumerate(self._elements):
            if str(nr) == sel_option:
                disp = ""
                cur_val = value
            else:
                disp = "none"
                cur_val = vs.default_value()

            html.write('<span id="%s_%s_sub" style="display: %s">' %
                    (varprefix, nr, disp))
            html.help(vs.help())
            vs.render_input(varprefix + "_%d" % nr, cur_val)
            html.write("</span>")




    def render_input_radio(self, varprefix, value):
        mvs = self.matching_alternative(value)
        for nr, vs in enumerate(self._elements):
            if html.has_var(varprefix + "_use"):
                checked = html.var(varprefix + "_use") == str(nr)
            else:
                checked = vs == mvs

            html.help(vs.help())
            title = vs.title()
            if not title and nr:
                html.write("&nbsp;&nbsp;")

            html.radiobutton(varprefix + "_use", str(nr), checked, title)
            if title:
                html.write("<ul>")
            if vs == mvs:
                val = value
            else:
                val = vs.default_value()
            vs.render_input(varprefix + "_%d" % nr, val)
            if title:
                html.write("</ul>\n")

    def set_focus(self, varprefix):
        # TODO: Set focus to currently active option
        pass

    def canonical_value(self):
        return self._elements[0].canonical_value()

    def value_to_text(self, value):
        vs = self.matching_alternative(value)
        if vs:
            output = ""
            if self._show_alternative_title and vs.title():
                output = "%s<br>" % vs.title()
            return output + vs.value_to_text(value)
        else:
            return _("invalid:") + " " + html.attrencode(str(value))

    def from_html_vars(self, varprefix):
        nr = int(html.var(varprefix + "_use"))
        vs = self._elements[nr]
        return vs.from_html_vars(varprefix + "_%d" % nr)

    def validate_datatype(self, value, varprefix):
        for vs in self._elements:
            try:
                vs.validate_datatype(value, "")
                return
            except:
                pass
        raise MKUserError(varprefix,
            _("The data type of the value does not match any of the "
              "allowed alternatives."))

    def validate_value(self, value, varprefix):
        vs = self.matching_alternative(value)
        for nr, v in enumerate(self._elements):
            if vs == v:
                vs.validate_value(value, varprefix + "_%d" % nr)
        ValueSpec.custom_validate(self, value, varprefix)


# Edit a n-tuple (with fixed size) of values
class Tuple(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._elements = kwargs["elements"]
        self._show_titles = kwargs.get("show_titles", True)
        self._orientation = kwargs.get("orientation", "vertical")
        self._title_br = kwargs.get("title_br", True)

    def canonical_value(self):
        return tuple([x.canonical_value() for x in self._elements])

    def default_value(self):
        return tuple([x.default_value() for x in self._elements])

    def render_input(self, varprefix, value):
        if self._orientation != "float":
            html.write('<table class="valuespec_tuple">')
            if self._orientation == "horizontal":
                html.write("<tr>")

        for no, element in enumerate(self._elements):
            try:
                val = value[no]
            except:
                val = element.default_value()
            vp = varprefix + "_" + str(no)
            if self._orientation == "vertical":
                html.write("<tr>")
            elif self._orientation == "float":
                html.write(" ")

            if self._show_titles:
                elem_title = element.title()
                if elem_title:
                    title = element.title()[0].upper() + element.title()[1:]
                else:
                    title = ""
                if self._orientation == "vertical":
                    html.write("<td class=tuple_left>%s" % title)
                    html.help(element.help())
                    html.write("</td>")
                elif self._orientation == "horizontal":
                    html.write("<td class=tuple_td><span class=title>%s" % title)
                    html.help(element.help())
                    html.write("</span>")
                    if self._title_br:
                        html.write("<br>")
                    else:
                        html.write(" ")
                else:
                    html.write(" ")
                    html.help(element.help())

            if self._orientation == "vertical":
                html.write("<td class=tuple_right>")
            element.render_input(vp, val)
            if self._orientation != "float":
                html.write("</td>")
                if self._orientation == "vertical":
                    html.write("</tr>")
        if self._orientation == "horizontal":
            html.write("</tr>")
        if self._orientation != "float":
            html.write("</table>")

    def set_focus(self, varprefix):
        self._elements[0].set_focus(varprefix + "_0")

    def value_to_text(self, value):
        return "" + ", ".join([ element.value_to_text(val)
                         for (element, val)
                         in zip(self._elements, value)]) + ""

    def from_html_vars(self, varprefix):
        value = []
        for no, element in enumerate(self._elements):
            vp = varprefix + "_" + str(no)
            value.append(element.from_html_vars(vp))
        return tuple(value)

    def validate_value(self, value, varprefix):
        for no, (element, val) in enumerate(zip(self._elements, value)):
            vp = varprefix + "_" + str(no)
            element.validate_value(val, vp)
        ValueSpec.custom_validate(self, value, varprefix)

    def validate_datatype(self, value, varprefix):
        if type(value) != tuple:
            raise MKUserError(varprefix,
            _("The datatype must be a tuple, but is %s") % type_name(value))
        if len(value) != len(self._elements):
            raise MKUserError(varprefix,
            _("The number of elements in the tuple must be exactly %d.") % len(self._elements))

        for no, (element, val) in enumerate(zip(self._elements, value)):
            vp = varprefix + "_" + str(no)
            element.validate_datatype(val, vp)

class Dictionary(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._elements = kwargs["elements"]
        self._empty_text = kwargs.get("empty_text", _("(no parameters)"))
        self._required_keys = kwargs.get("required_keys", [])
        self._ignored_keys = kwargs.get("ignored_keys", [])
        self._default_keys = kwargs.get("default_keys", []) # keys present in default value
        if "optional_keys" in kwargs:
            ok = kwargs["optional_keys"]
            if type(ok) == list:
                self._required_keys = \
                    [ e[0] for e in self._get_elements() if e[0] not in ok ]
                self._optional_keys = True
            elif ok:
                self._optional_keys = True
            else:
                self._optional_keys = False
        else:
            self._optional_keys = True
        if "hidden_keys" in kwargs:
            self._hidden_keys = kwargs["hidden_keys"]
        else:
            self._hidden_keys = []

        self._columns = kwargs.get("columns", 1) # possible: 1 or 2
        self._render = kwargs.get("render", "normal") # also: "form" -> use forms.section()
        self._form_narrow = kwargs.get("form_narrow", False) # used if render == "form"
        self._form_isopen = kwargs.get("form_isopen", True) # used if render == "form"
        self._headers = kwargs.get("headers") # "sup" -> small headers in oneline mode
        self._migrate = kwargs.get("migrate") # value migration from old tuple version
        self._indent = kwargs.get("indent", True)

    def migrate(self, value):
        if self._migrate:
            return self._migrate(value)
        else:
            return value

    def _get_elements(self):
        if type(self._elements) == type(lambda: None):
            return self._elements()
        elif type(self._elements) == list:
            return self._elements
        else:
            return []

    # Additional variale form allows to specify the rendering
    # style right now
    def render_input(self, varprefix, value, form=None):
        value = self.migrate(value)
        if type(value) != dict:
            value = {} # makes code simpler in complain phase
        if form == True:
            self.render_input_form(varprefix, value)
        elif self._render == "form" and form == None:
            self.render_input_form(varprefix, value)
        else:
            self.render_input_normal(varprefix, value, self._render == "oneline")

    def render_input_normal(self, varprefix, value, oneline = False):
        headers_sup = oneline and self._headers == "sup"
        if headers_sup or not oneline:
            html.write("<table class=dictionary>")
        if headers_sup:
            html.write('<tr>')
        for param, vs in self._get_elements():
            if param in self._hidden_keys:
                continue
            if not oneline:
                html.write('<tr><td class=dictleft>')
            div_id = varprefix + "_d_" + param
            vp     = varprefix + "_p_" + param
            colon_printed = False
            if self._optional_keys and param not in self._required_keys:
                visible = html.get_checkbox(vp + "_USE")
                if visible == None:
                    visible = param in value
                label = vs.title()
                if self._columns == 2:
                    label += ":"
                    colon_printed = True
                html.checkbox(vp + "_USE", param in value,
                              onclick="valuespec_toggle_option(this, %r)" % div_id,
                              label=label)
            else:
                visible = True
                if vs.title():
                    if headers_sup:
                        html.write('<td><b class=header>')
                    html.write(" %s" % vs.title())
                    if oneline:
                        if self._headers == "sup":
                            html.write('</b><br>')
                        else:
                            html.write(": ")

            if self._columns == 2:
                if vs.title() and not colon_printed:
                    html.write(':')
                html.help(vs.help())
                if not oneline:
                    html.write('</td><td class=dictright>')
            else:
                if not oneline:
                    html.write("<br>")

            html.write('<div class="dictelement%s" id="%s" style="display: %s">' % (
                ((self._indent and self._columns == 1) and " indent" or ""),
                div_id, not visible and "none" or (oneline and "inline-block" or "")))
            if self._columns == 1:
                html.help(vs.help())
            # Remember: in complain mode we do not render 'value' (the default value),
            # but re-display the values from the HTML variables. We must not use 'value'
            # in that case.
            if type(value) == dict:
                vs.render_input(vp, value.get(param, vs.default_value()))
            else:
                vs.render_input(vp, None)
            html.write("</div>")
            if not oneline:
                html.write("</td></tr>")
            elif headers_sup:
                html.write("</td>")

        if not oneline:
            html.write("</table>")
        elif oneline and self._headers == "sup":
            html.write('</tr></table>')

    def render_input_form(self, varprefix, value):
        if self._headers:
            for header, sections in self._headers:
                self.render_input_form_header(varprefix, value, header, sections)
        else:
            self.render_input_form_header(varprefix, value, self.title() or _("Properties"), None)

    def render_input_form_header(self, varprefix, value, title, sections):
        forms.header(title, isopen=self._form_isopen, narrow=self._form_narrow)
        for param, vs in self._get_elements():
            if param in self._hidden_keys:
                continue

            if sections and param not in sections:
                continue

            div_id = varprefix + "_d_" + param
            vp     = varprefix + "_p_" + param
            if self._optional_keys and param not in self._required_keys:
                visible = html.get_checkbox(vp + "_USE")
                if visible == None:
                    visible = param in value
                onclick = "valuespec_toggle_option(this, %r)" % div_id
                checkbox_code = '<input type=checkbox name="%s" %s onclick="%s">' % (
                    vp + "_USE", visible and "CHECKED" or "", onclick)
                html.add_form_var(vp + "_USE")
                forms.section(vs.title(), checkbox=checkbox_code)
            else:
                visible = True
                forms.section(vs.title())

            html.write('<div id="%s" style="display: %s">' % (
                div_id, not visible and "none" or ""))
            html.help(vs.help())
            vs.render_input(vp, value.get(param, vs.default_value()))
            html.write("</div>")

    def set_focus(self, varprefix):
        elem = self._get_elements()
        if elem:
            elem[0][1].set_focus(varprefix + "_p_" + elem[0][0])

    def canonical_value(self):
        return dict([
            (name, vs.canonical_value())
             for (name, vs)
             in self._get_elements()
             if name in self._required_keys or not self._optional_keys])

    def default_value(self):
        def_val = {}
        for name, vs in self._get_elements():
            if name in self._required_keys or not self._optional_keys or name in self._default_keys:
                def_val[name] = vs.default_value()

        return def_val

    def value_to_text(self, value):
        value = self.migrate(value)
        oneline = self._render == "oneline"
        if not value:
            return self._empty_text

        if not oneline:
            s = '<table class=vs_dict_text>'
        else:
            s = ""
        elem = self._get_elements()
        for param, vs in elem:
            if param in value:
                text = vs.value_to_text(value[param])
                if oneline:
                    if param != elem[0][0]:
                        s += ", "
                    s += "%s: %s" % (vs.title(), text)
                else:
                    s += "<tr><td>%s:&nbsp;</td><td>%s</td></tr>" % (vs.title(), text)
        if not oneline:
            s += '</table>'
        return s

    def from_html_vars(self, varprefix):
        value = {}
        for param, vs in self._get_elements():
            vp = varprefix + "_p_" + param
            if not self._optional_keys \
                or param in self._required_keys \
                or html.get_checkbox(vp + "_USE"):
                value[param] = vs.from_html_vars(vp)
        return value

    def validate_datatype(self, value, varprefix):
        value = self.migrate(value)

        if type(value) != dict:
            raise MKUserError(varprefix, _("The type must be a dictionary, but it is a %s") % type_name(value))

        for param, vs in self._get_elements():
            if param in value:
                vp = varprefix + "_p_" + param
                try:
                    vs.validate_datatype(value[param], vp)
                except MKUserError, e:
                    raise MKUserError(e.varname, _("%s: %s") % (vs.title(), e.message))
            elif not self._optional_keys or param in self._required_keys:
                raise MKUserError(varprefix, _("The entry %s is missing") % vs.title())

        # Check for exceeding keys
        allowed_keys = [ p for (p,v) in self._get_elements() ]
        if self._ignored_keys:
            allowed_keys += self._ignored_keys
        for param in value.keys():
            if param not in allowed_keys:
                raise MKUserError(varprefix, _("Undefined key '%s' in the dictionary. Allowed are %s.") %
                        (param, ", ".join(allowed_keys)))

    def validate_value(self, value, varprefix):
        value = self.migrate(value)

        for param, vs in self._get_elements():
            if param in value:
                vp = varprefix + "_p_" + param
                vs.validate_value(value[param], vp)
            elif not self._optional_keys or param in self._required_keys:
                raise MKUserError(varprefix, _("The entry %s is missing") % vs.title())
        ValueSpec.custom_validate(self, value, varprefix)


# Base class for selection of a Nagios element out
# of a given list that must be loaded from a file.
# Examples: GroupSelection, TimeperiodSelection. Child
# class must define a function get_elements() that
# returns a dictionary from element keys to element
# titles.
class ElementSelection(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._loaded_at = None
        self._label = kwargs.get("label")

    def load_elements(self):
        if self._loaded_at != id(html):
            self._elements = self.get_elements()
            self._loaded_at = id(html) # unique for each query!

    def canonical_value(self):
        self.load_elements()
        if len(self._elements) > 0:
            return self._elements.keys()[0]
        else:
            raise MKUserError(None,
              _("There are not defined any elements for this selection yet."))

    def render_input(self, varprefix, value):
        self.load_elements()
        if len(self._elements) == 0:
            html.write(_("There are not defined any elements for this selection yet."))
        else:
            if self._label:
                html.write("%s&nbsp;" % self._label)
            html.sorted_select(varprefix, self._elements.items(), value)

    def value_to_text(self, value):
        self.load_elements()
        return self._elements.get(value, value)

    def from_html_vars(self, varprefix):
        return html.var(varprefix)

    def validate_value(self, value, varprefix):
        self.load_elements()
        if len(self._elements) == 0:
            raise MKUserError(varprefix,
              _("You cannot save this rule. There are not defined any elements for this selection yet."))
        if value not in self._elements:
            raise MKUserError(varprefix, _("%s is not an existing element in this selection.") % (value,))
        ValueSpec.custom_validate(self, value, varprefix)

    def validate_datatype(self, value, varprefix):
        if type(value) != str:
            raise MKUserError(varprefix, _("The datatype must be str (string), but is %s") % type_name(value))


class AutoTimestamp(FixedValue):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)

    def canonical_value(self):
        return time.time()

    def from_html_vars(self, varprefix):
        return time.time()

    def value_to_text(self, value):
        return time.strftime("%F %T", time.localtime(value))

    def validate_datatype(self, value, varprefix):
        if type(value) not in [ int, float ]:
            return MKUserError(varprefix, _("Invalid datatype of timestamp: must be int or float."))

# Fully transparant VS encapsulating a vs in a foldable
# container.
class Foldable(ValueSpec):
    def __init__(self, valuespec, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._valuespec = valuespec
        self._open = kwargs.get("open", False)
        self._title_function = kwargs.get("title_function", None)

    def render_input(self, varprefix, value):
        try:
            title_value = value
            if html.form_submitted():
                try:
                    title_value = self._valuespec.from_html_vars(varprefix)
                except:
                    pass
            title = self._title_function(title_value)
        except:
            title = self._valuespec.title()
            if not title:
                title = _("(no title)")
        html.begin_foldable_container("valuespec_foldable", varprefix, self._open,
                       title, False)
        html.help(self._valuespec.help())
        self._valuespec.render_input(varprefix, value)
        html.end_foldable_container()

    def set_focus(self, varprefix):
        self._valuespec.set_focus(varprefix)

    def canonical_value(self):
        return self._valuespec.canonical_value()

    def default_value(self):
        return self._valuespec.default_value()

    def value_to_text(self, value):
        return self._valuespec.value_to_text(value)

    def from_html_vars(self, varprefix):
        return self._valuespec.from_html_vars(varprefix)

    def validate_datatype(self, value, varprefix):
        self._valuespec.validate_datatype(value, varprefix)

    def validate_value(self, value, varprefix):
        self._valuespec.validate_value(value, varprefix)
        ValueSpec.custom_validate(self, value, varprefix)


# Transforms the value from one representation to
# another while being completely transparent to the user.
# forth: function that converts a value into the representation
#        needed by the encapsulated vs
# back:  function that converts a value created by the encapsulated
#        vs back to the outer representation

class Transform(ValueSpec):
    def __init__(self, valuespec, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._valuespec = valuespec
        self._back = kwargs.get("back")
        self._forth = kwargs.get("forth")

    def forth(self, value):
        if self._forth:
            return self._forth(value)
        else:
            return value

    def back(self, value):
        if self._back:
            return self._back(value)
        else:
            return value

    def title(self):
        if self._title:
            return self._title
        else:
            return self._valuespec.title()

    def render_input(self, varprefix, value):
        self._valuespec.render_input(varprefix, self.forth(value))

    def set_focus(self, *args):
        self._valuespec.set_focus(*args)

    def canonical_value(self):
        return self.back(self._valuespec.canonical_value())

    def default_value(self):
        return self.back(self._valuespec.default_value())

    def value_to_text(self, value):
        return self._valuespec.value_to_text(self.forth(value))

    def from_html_vars(self, varprefix):
        return self.back(self._valuespec.from_html_vars(varprefix))

    def validate_datatype(self, value, varprefix):
        self._valuespec.validate_datatype(self.forth(value), varprefix)

    def validate_value(self, value, varprefix):
        self._valuespec.validate_value(self.forth(value), varprefix)
        ValueSpec.custom_validate(self, value, varprefix)

class LDAPDistinguishedName(TextAscii):
    def __init__(self, **kwargs):
        TextAscii.__init__(self, **kwargs)
        self.enforce_suffix = kwargs.get('enforce_suffix')

    def validate_value(self, value, varprefix):
        TextAscii.validate_value(self, value, varprefix)

        # Check wether or not the given DN is below a base DN
        if self.enforce_suffix and value and not value.lower().endswith(self.enforce_suffix.lower()):
            raise MKUserError(varprefix, _('Does not ends with "%s".') % self.enforce_suffix)
        ValueSpec.custom_validate(self, value, varprefix)


class Password(TextAscii):
    def __init__(self, **kwargs):
        TextAscii.__init__(self, attrencode = True, **kwargs)

    def render_input(self, varprefix, value):
        if value == None:
            value = ""

        if self._label:
            html.write(self._label)
            html.write("&nbsp;")
        html.password_input(varprefix, str(value), size = self._size)

    def value_to_text(self, value):
        if value == None:
            return _("none")
        else:
            return '******'

class PasswordSpec(TextAscii):
    def __init__(self, **kwargs):
        TextAscii.__init__(self, **kwargs)

    def render_input(self, varprefix, value):
        TextAscii.render_input(self, varprefix, value)
        if not value:
            html.icon_button("#", _(u"Randomize password"), "random",
                onclick="vs_passwordspec_randomize(this);")

class FileUpload(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._allow_empty = kwargs.get('allow_empty', True)

    def canonical_value(self):
        if self._allow_empty:
            return None
        else:
            return ''

    def validate_value(self, value, varprefix):
        if not self._allow_empty and value == None:
            raise MKUserError(varprefix, _('Please select a file.'))

    def render_input(self, varprefix, value):
        html.upload_file(varprefix)

    def from_html_vars(self, varprefix):
        # returns a triple of (filename, mime-type, content)
        return html.uploaded_file(varprefix)

class IconSelector(ValueSpec):
    def __init__(self, **kwargs):
        ValueSpec.__init__(self, **kwargs)
        self._prefix      = kwargs.get('prefix', 'icon_')
        self._subdir      = kwargs.get('subdir', '')
        self._num_cols    = kwargs.get('num_cols', 12)
        self._allow_empty = kwargs.get('allow_empty', True)
        if self._subdir:
            self._html_path = os.path.join('images', self._subdir)
        else:
            self._html_path = 'images'
        self._empty_img = kwargs.get('emtpy_img', 'empty')

        self._exclude = [
            'trans',
            'empty',
        ]

    def available_icons(self):
        if defaults.omd_root:
            dirs = [
                os.path.join(defaults.omd_root, "local/share/check_mk/web/htdocs/images", self._subdir),
                os.path.join(defaults.omd_root, "share/check_mk/web/htdocs/images", self._subdir),
            ]
        else:
            dirs = [ os.path.join(defaults.web_dir, "htdocs/images", self._subdir) ]

        icons = set([])
        for dir in dirs:
            if os.path.exists(dir):
                icons.update([ i[len(self._prefix):-4] for i in os.listdir(dir)
                           if i[-4:] == '.png' and os.path.isfile(dir + "/" + i)
                              and i.startswith(self._prefix) ])

        for exclude in self._exclude:
            try:
                icons.remove(exclude)
            except KeyError:
                pass

        icons = list(icons)
        icons.sort()
        return icons

    def render_icon(self, icon, onclick = '', title = '', id = ''):
        path = "%s/%s%s.png" % (self._html_path, self._prefix, html.attrencode(icon))

        if onclick:
            html.write('<a href="javascript:void(0)" onclick="%s">' % onclick)
        html.write('<img align=absmiddle id="%s" class=icon title="%s" src="%s">' % (id, title, path))
        if onclick:
            html.write('</a>')

    def render_input(self, varprefix, value):
        if not value:
            value = self._empty_img

        html.write('<div class="popup_container">')
        html.hidden_field(varprefix + "_value", value or '', varprefix + "_value", add_var = True)
        self.render_icon(value, 'toggle_popup(event, \'%s\')' % varprefix,
                        _('Choose another Icon'), id = varprefix + '_img')
        if not value:
            html.write('<a href="javascript:void(0)" onclick="toggle_popup(event, \'%s\')">%s</a>' %
                            (varprefix, _('Select an Icon')))
        html.write('<div id="%s_popup" class="popup" style="display:none">' % varprefix)
        html.write('<table>')
        empty = self._allow_empty and ['empty'] or []
        for nr, icon in enumerate(empty + self.available_icons()):
            if nr == 0:
                html.write('<tr>')
            elif nr % self._num_cols == 0:
                html.write('</tr><tr>')

            html.write('<td>')
            self.render_icon(icon,
                onclick = 'vs_iconselector_select(event, \'%s\', \'%s\')' % (varprefix, icon),
                title = _('Choose this Icon'), id = varprefix + '_i_' + icon)
            html.write('</td>')
        html.write('</tr>')
        html.write('</table>')
        html.write('</div>')
        html.write('</div>')

    def from_html_vars(self, varprefix):
        icon = html.var(varprefix + '_value')
        if icon == 'empty':
            return None
        else:
            return icon

    def value_to_text(self, value):
        self.render_icon(value)

    def validate_datatype(self, value, varprefix):
        if value is not None and type(value) != str:
            raise MKUserError(varprefix, _("The type is %s, but should be str") % type(value))

    def validate_value(self, value, varprefix):
        if value and value not in self.available_icons():
            raise MKUserError(varprefix, _("The selected icon image does not exist."))

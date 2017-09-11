#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  antergos-welcome.py
#
#  Copyright 2012-2013 "Korora Project" <dev@kororaproject.org>
#  Copyright 2013 "Manjaro Linux" <support@manjaro.org>
#  Copyright 2014-2016 Antergos <devs@antergos.com>
#  Copyright 2015 Martin Wimpress <code@flexion.org>
#
#  Antergos-welcome is free software: you can redistribute it and/or modify
#  it under the temms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Antergos-welcome is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Antergos-welcome. If not, see <http://www.gnu.org/licenses/>.

""" Welcome screen for Antergos """

import inspect
import os
import signal
import subprocess
import sys
import urllib.request
import urllib.error
import webbrowser
import locale
import gettext

from client import SimpleWelcomed

from simplejson import dumps as to_json

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0')
from gi.repository import Gtk, Gdk, Gio, GLib, WebKit2

# Useful vars for gettext (translations)
_APP_NAME = "antergos-welcome"
_LOCALE_DIR = "/usr/share/locale"


class WelcomeConfig(object):
    """ Manages Welcome configuration """

    def __init__(self):
        # store our base architecture
        if os.uname()[4] == 'x86_64':
            self._arch = '64-bit'
        else:
            self._arch = '32-bit'

        # store we are a live CD session
        self._live = os.path.exists('/arch')

        # store full path to our binary
        self._welcome_bin_path = os.path.abspath(inspect.getfile(inspect.currentframe()))

        # store directory to our welcome configuration
        self._config_dir = os.path.expanduser('~/.config/antergos/welcome/')

        # store full path to our autostart symlink
        self._autostart_path = os.path.expanduser('~/.config/autostart/antergos-welcome.desktop')

        # ensure our config directory exists
        if not os.path.exists(self._config_dir):
            try:
                os.makedirs(self._config_dir)
            except OSError:
                pass
        # does autostart symlink exist
        self._autostart = os.path.exists(self._autostart_path)

    @property
    def arch(self):
        return self._arch

    @property
    def autostart(self):
        return self._autostart

    @autostart.setter
    def autostart(self, state):
        if state and not os.path.exists(self._autostart_path):
            # create the autostart symlink
            try:
                os.symlink(
                    '/usr/share/applications/antergos-welcome.desktop',
                    self._autostart_path)
            except OSError:
                pass
        elif not state and os.path.exists(self._autostart_path):
            # remove the autostart symlink
            try:
                os.unlink(self._autostart_path)
            except OSError:
                pass

        # determine autostart state based on absence of the disable file
        self._autostart = os.path.exists(self._autostart_path)

    @property
    def live(self):
        return self._live


class WelcomeWebView(WebKit2.WebView):
    def __init__(self):
        WebKit2.WebView.__init__(self)

        self._config = WelcomeConfig()

        self.welcomed = []

        self.connect('load-changed', self._load_changed_cb)
        self.connect('load-failed', self._load_failed_cb)

    def _push_config(self):
        self.run_javascript("$('#arch').html('%s')" % self._config.arch)
        self.run_javascript(
            "$('#autostart').toggleClass('icon-check', %s).toggleClass(\
            'icon-check-empty', %s)" % (to_json(self._config.autostart),
                                        to_json(not self._config.autostart)))
        if self._config.live:
            self.run_javascript("$('#install').toggleClass('hide', false);")
            self.run_javascript(
                "$('#install-cli').toggleClass('hide', false);")
        else:
            self.run_javascript("$('#build').toggleClass('hide', false);")
            self.run_javascript("$('#donate').toggleClass('hide', false);")

    def _load_changed_cb(self, view, load_event):
        if load_event == WebKit2.LoadEvent.FINISHED:
            self._push_config()
        elif load_event == WebKit2.LoadEvent.STARTED:
            uri = view.get_uri()
            try:
                if uri.index('#') > 0:
                    uri = uri[:uri.index('#')]
            except ValueError:
                pass

            if uri.startswith('cmd://'):
                self._do_command(uri)

    def _load_failed_cb(self, view, load_event, failing_uri, error):
        # Returns True to stop other handlers from being invoked for the event
        return True

    def _do_command(self, uri):
        if uri.startswith('cmd://'):
            uri = uri[6:]

        if uri == 'gnome-help':
            subprocess.Popen(['yelp'])
        elif uri == 'kde-help':
            subprocess.Popen(['khelpcenter'])
        elif uri == 'close' or uri == 'quit':
            self.quit()
        elif uri == 'toggle-startup':
            # toggle autostart
            self._config.autostart ^= True
            self._push_config()
        elif uri == 'drivers':
            # Install drivers
            print(uri, "NOT IMPLEMENTED!")
        elif uri == 'update':
            # pacman -Syu
            self.welcomed.append(SimpleWelcomed([], "refresh"))
            self.welcomed[-1].run_action()
            self.welcomed.append(SimpleWelcomed([], "system_upgrade"))
            self.welcomed[-1].run_action()
        elif uri == 'language':
            print(uri, "NOT IMPLEMENTED!")
        elif uri.startswith('apt-install?'):
            # pacman -S
            packages = uri[len('apt-install?'):].split(",")
            #self.pamac.install(packages)
            self.welcomed.append(SimpleWelcomed(packages, "install"))
            self.welcomed[-1].run_action()
        elif uri.startswith('apt-remove?'):
            # pacman -R
            packages = uri[len('apt-remove?'):].split(",")
            self.welcomed.append(SimpleWelcomed(packages, "remove"))
            self.welcomed[-1].run_action()
        elif uri == 'backup':
            print(uri, "NOT IMPLEMENTED!")
        elif uri == 'firewall':
            print(uri, "NOT IMPLEMENTED!")
        elif uri == 'users':
            print(uri, "NOT IMPLEMENTED!")
        elif uri.startswith("link?"):
            webbrowser.open_new_tab(uri[5:])
        else:
            print('Unknown command: %s' % uri)

    def quit(self):
        for client in self.welcomed:
            client.quit()
        w = self.get_toplevel()
        #w.destroy()
        w.quit()

class WelcomeApp(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id="com.antergos.welcome",
                         flags=Gio.ApplicationFlags.FLAGS_NONE,
                         **kwargs)
        self.window = None

    def setup_gettext(self):
        """ This allows to translate all py texts (not the glade ones) """

        gettext.textdomain(_APP_NAME)
        gettext.bindtextdomain(_APP_NAME, _LOCALE_DIR)

        locale_code, encoding = locale.getdefaultlocale()
        lang = gettext.translation(_APP_NAME, _LOCALE_DIR, [locale_code], None, True)
        lang.install()

    def do_startup(self):
        Gtk.Application.do_startup(self)

    def do_activate(self):
        # We only allow a single window and raise any existing ones
        if not self.window:
            # Windows are associated with the application
            # when the last one is closed the application shuts down
            self.window = WelcomeWindow(application=self, title="Antergos Welcome")

        self.window.present()


class WelcomeWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        Gtk.ApplicationWindow.__init__(self, title="", application=app)

        self.set_data_path()

        # This will be in the windows group and have the "win" prefix
        max_action = Gio.SimpleAction.new_stateful("maximize", None,
                                           GLib.Variant.new_boolean(False))
        max_action.connect("change-state", self.on_maximize_toggle)
        self.add_action(max_action)

        # Keep it in sync with the actual state
        self.connect(
            "notify::is-maximized",
            lambda obj, pspec: max_action.set_state(GLib.Variant.new_boolean(obj.props.is_maximized)))

        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_name('antergos-welcome')
        self.set_title('')
        self.set_geometry(768, 496)

        icon_dir = os.path.join(self._data_path, 'img/logos', 'antergos.png')
        if os.path.exists(icon_dir):
            self.set_icon_from_file(icon_dir)
        else:
            print("Cannot load icon file ", icon_dir)

        # build webkit container
        self.webview = WelcomeWebView()

        # load our index file
        file = os.path.abspath(os.path.join(self._data_path, 'index.html'))
        uri = 'file://' + urllib.request.pathname2url(file)
        self.webview.load_uri(uri)

        # build scrolled window widget and add our appwebview container
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.add(self.webview)

        # build a an autoexpanding box and add our scrolled window
        b = Gtk.VBox(homogeneous=False, spacing=0)
        b.pack_start(sw, expand=True, fill=True, padding=0)

        # add the box to the parent window and show
        self.add(b)
        self.connect('delete-event', self.close)
        self.show_all()


    def set_geometry(self, width, height):
        """ Sets Cnchi window geometry """
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)
        self.set_size_request(width, height)
        self.set_default_size(width, height)

        geom = Gdk.Geometry()
        geom.min_width = width
        geom.min_height = height
        geom.max_width = width
        geom.max_height = height
        geom.base_width = width
        geom.base_height = height
        geom.width_inc = 0
        geom.height_inc = 0

        hints = (Gdk.WindowHints.MIN_SIZE |
                 Gdk.WindowHints.MAX_SIZE |
                 Gdk.WindowHints.BASE_SIZE |
                 Gdk.WindowHints.RESIZE_INC)
        self.set_geometry_hints(None, geom, hints)

    def set_data_path(self):
        # Wstablish our location
        self._location = os.path.dirname(
            os.path.abspath(inspect.getfile(inspect.currentframe())))

        # Check for relative path
        if(os.path.exists(os.path.join(self._location, '../data/'))):
            print('Using relative path for data source.\
                   Non-production testing.')
            self._data_path = os.path.join(self._location, '../data/')
        elif(os.path.exists('/usr/share/antergos/welcome/')):
            print('Using /usr/share/antergos/welcome/ path.')
            self._data_path = '/usr/share/antergos/welcome/'
        else:
            print('Unable to source the antergos-welcome data directory.')
            sys.exit(1)

    def on_maximize_toggle(self, action, value):
        action.set_state(value)
        if value.get_boolean():
            self.maximize()
        else:
            self.unmaximize()

    def quit(self):
        self.destroy()



app = WelcomeApp()
app.run(sys.argv)

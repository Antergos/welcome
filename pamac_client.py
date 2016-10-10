#!/usr/bin/python3
# -*- coding:utf-8 -*-
#
# Copyright 2014-2016 Antergos <devs@antergos.com>
#
# Antergos Welcome is free software: you can redistribute it and/or modify
# it under the temms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Antergos Welcome is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Antergos Welcome. If not, see <http://www.gnu.org/licenses/>.
#

import sys, os
import gi
gi.require_version('Polkit', '1.0')
from gi.repository import GObject, Gio, GLib, Polkit


class PamacClient(object):
    def __init__(self):
        self.interface = None
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            """
            g_bus_type: value,
            g_connection: value,
            g_default_timeout: value,
            g_flags: value,
            g_interface_name: value,
            g_name: value,
            g_object_path: value,
            """
            self.dbus_proxy = Gio.DBusProxy.new_sync(
                self.bus,
                Gio.DBusProxyFlags.NONE,
                None,
                'org.manjaro.pamac',
                '/org/manjaro/pamac',
                'org.manjaro.pamac',
                None)

            self.bus.signal_subscribe(
                "org.manjaro.pamac",
                "org.manjaro.pamac",
                "RefreshFinished",
                None,
                None,
                0,
                self.on_refresh_finished,
                None,
                None)
        except Exception as err:
            print(err)
            print("Can't find pamac. Is it really installed?")

    def on_refresh_finished(self, status):
        print("on_refresh_finished called!")

    def refresh(self):
        if self.dbus_proxy:
            try:
                print("StartRefresh called!")
                res = self.dbus_proxy.call_sync(
                    "StartRefresh",
                    GLib.Variant("(b)", (False, )),
                    Gio.DBusCallFlags.NONE,
                    -1,
                    None)
            except Exception as err:
                print(err)

        """
        			try {
				pamac_daemon = Bus.get_proxy_sync (BusType.SYSTEM, "org.manjaro.pamac", "/org/manjaro/pamac");
				pamac_daemon.refresh_finished.connect (on_refresh_finished);
				pamac_daemon.start_refresh (false);
				loop = new MainLoop ();
				loop.run ();
			} catch (IOError e) {
				stderr.printf ("IOError: %s\n", e.message);
			}
        """

    def check_authorization_cb(self, authority, res, loop):
        try:
            result = authority.check_authorization_finish(res)
            if result.get_is_authorized():
                print("Authorized")
            elif result.get_is_challenge():
                print("Challenge")
            else:
                print("Not authorized")
        except GObject.GError as error:
             print("Error checking authorization: %s" % error.message)

        print("Authorization check has been cancelled "
              "and the dialog should now be hidden.")

    def do_cancel(self, cancellable):
        print("Timer has expired; cancelling authorization check")
        cancellable.cancel()
        return False

    def check_authorization(self):
        action_id = "org.freedesktop.policykit.exec"
        authority = Polkit.Authority.get()
        subject = Polkit.UnixProcess.new(os.getppid())

        cancellable = Gio.Cancellable()
        GObject.timeout_add(10 * 1000, self.do_cancel, cancellable)

        authority.check_authorization(subject,
            action_id,
            None,
            Polkit.CheckAuthorizationFlags.ALLOW_USER_INTERACTION,
            cancellable,
            check_authorization_cb)

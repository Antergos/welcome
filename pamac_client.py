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
            self.dbus_proxy = Gio.DBusProxy.new_sync(
                self.bus,
                Gio.DBusProxyFlags.NONE,
                None,
                'org.manjaro.pamac',
                '/org/manjaro/pamac',
                'org.manjaro.pamac',
                None)

            self.signal_subscribe(
                "RefreshFinished",
                self.on_refresh_finished)

            self.signal_subscribe(
                "GetAuthorizationFinished",
                self.on_get_authorization_finished)
        except Exception as err:
            print(err)
            print("Can't find pamac. Is it really installed?")

    def signal_subscribe(self, signal_name, callback):
        if self.bus:
            self.bus.signal_subscribe(
                "org.manjaro.pamac",
                "org.manjaro.pamac",
                signal_name,
                None,
                None,
                0,
                callback,
                None,
                None)

    def get_authorization(self):
        if self.dbus_proxy:
            print("GetAuthorization called!")
            res = self.dbus_proxy.call_sync(
                "StartGetAuthorization",
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None)

    def on_get_authorization_finished(self, connection, sender_name, object_path, interface_name, signal_name, parameters, user_data, unknown):
        print("on_get_authorization_finished")
        print("connection", connection)
        print("sender_name", sender_name)
        print("object_path", object_path)
        print("interface_name", interface_name)
        print("signal_name", signal_name)
        print("parameters", parameters)
        print("user_data", user_data)
        print("unknown", unknown)

    def refresh(self):
        """ pacman -Sy """
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

    def on_refresh_finished(self, connection, sender_name, object_path, interface_name, signal_name, parameters, user_data, unknown):
        print("on_refresh_finished called!")
        print("connection", connection)
        print("sender_name", sender_name)
        print("object_path", object_path)
        print("interface_name", interface_name)
        print("signal_name", signal_name)
        print("parameters", parameters)
        print("user_data", user_data)
        print("unknown", unknown)

    def update(self):
        """ pacman -Syu """
        print("NOT IMPLEMENTED!")


    """
    flags = (1 << 4); //Alpm.TransFlag.CASCADE
			if (pamac_config.recurse) {
				flags |= (1 << 5); //Alpm.TransFlag.RECURSE
			}
    """"
    def install(self, pkgs):
        """ pacman -S pkgs """
        if self.dbus_proxy:
            try:
                print("Install called!")
                flags = 0
                # Int32 flags
                # Array of String to_install
                # Array of String to_remove
                # Array of String to_load
                res = self.dbus_proxy.call_sync(
                    "StartTransPrepare",
                    GLib.Variant("(iasasas)", (flags, pkgs, None, None)),
                    Gio.DBusCallFlags.NONE,
                    -1,
                    None)
            except Exception as err:
                print(err)

    def remove(self, pkgs):
        """ pacman -R pkgs """
        print("NOT IMPLEMENTED!")

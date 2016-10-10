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

            self.bus.signal_subscribe(
                "org.manjaro.pamac",
                "org.manjaro.pamac",
                "GetAuthorizationFinished",
                None,
                None,
                0,
                self.on_get_authorization_finished,
                None,
                None)
        except Exception as err:
            print(err)
            print("Can't find pamac. Is it really installed?")

    def get_authorization(self):
        if self.dbus_proxy:
            print("GetAuthorization called!")
            res = self.dbus_proxy.call_sync(
                "StartGetAuthorization",
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None)

    def on_get_authorization_finished(self, p1, p2, p3, p4, p5, p6, p7, p8):
        print("on_get_authorization_finished")
        print(p1, p2, p3, p4, p5, p6, p7, p8)

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


    """
GDBusConnection *connection,
                        const gchar *sender_name,
                        const gchar *object_path,
                        const gchar *interface_name,
                        const gchar *signal_name,
                        GVariant *parameters,
                        gpointer user_data
    """

    def on_refresh_finished(self, connection, sender_name, object_path, interface_name, signal_name, parameters, user_data):
        print("on_refresh_finished called!")
        print(connection, sender_name, object_path, interface_name, signal_name, parameters, user_data)

    def update(self):
        """ pacman -Syu """
        print("NOT IMPLEMENTED!")

    def install(self, pkgs):
        """ pacman -S pkgs """
        print("NOT IMPLEMENTED!")

    def remove(self, pkgs):
        """ pacman -R pkgs """
        print("NOT IMPLEMENTED!")

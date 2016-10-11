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
                "TransPrepareFinished",
                self.on_transaction_prepare_finished)

            self.signal_subscribe(
                "TransCommitFinished",
                self.on_transaction_commit_finished)

            self.signal_subscribe(
                "GetUpdatesFinished",
                self.on_get_updates_finished)
        except Exception as err:
            print(err)
            print("Can't find pamac. Is it really installed?")

    def signal_subscribe(self, signal_name, callback, user_data=None):
        if self.bus:
            self.bus.signal_subscribe(
                "org.manjaro.pamac", # sender
                "org.manjaro.pamac", # interface_name
                signal_name, # member
                None, # object_path
                None, # arg0
                0, # flags
                callback, # callback
                user_data, # user_data
                None) # user_data_free_func

    def call_sync(self, method_name, params=None):
        if self.dbus_proxy:
            try:
                print(method_name, "called!")
                res = self.dbus_proxy.call_sync(
                    method_name,
                    params, # GLib.Variant(description, values)
                    Gio.DBusCallFlags.NONE,
                    -1,
                    None)
            except Exception as err:
                print(err)

    def refresh(self):
        """ pacman -Sy """
        variant = GLib.Variant("(b)", (False, ))
        self.call_sync("StartRefresh", variant)

    def on_refresh_finished(self, connection, sender_name, object_path, interface_name, signal_name, parameters, user_data, user_data_free_func):
        print("on_refresh_finished called!")
        print("connection", connection)
        print("sender_name", sender_name)
        print("object_path", object_path)
        print("interface_name", interface_name)
        print("signal_name", signal_name)
        print("parameters", parameters)
        print("user_data", user_data)
        print("user_data_free_func", user_data_free_func)

    """
    flags = (1 << 4); // Cascade
	flags |= (1 << 5); // Recurse
    """
    def transaction_prepare(self, flags, to_install, to_remove, to_load):
        variant = GLib.Variant("(iasasas)", (flags, to_install, to_remove, to_load))
        self.call_sync("StartTransPrepare", variant)

    def on_transaction_prepare_finished(self, connection, sender_name, object_path, interface_name, signal_name, parameters, user_data, user_data_free_func):
        print("on_transaction_prepare_finished")
        print("connection", connection)
        print("sender_name", sender_name)
        print("object_path", object_path)
        print("interface_name", interface_name)
        print("signal_name", signal_name)
        print("parameters", parameters)
        print("user_data", user_data)
        print("user_data_free_func", user_data_free_func)

    def transaction_commit(self):
        self.call_sync("StartTransCommit")

    def on_transaction_commit_finished(self, connection, sender_name, object_path, interface_name, signal_name, parameters, user_data, user_data_free_func):
        print("on_transaction_commit_finished")
        print("connection", connection)
        print("sender_name", sender_name)
        print("object_path", object_path)
        print("interface_name", interface_name)
        print("signal_name", signal_name)
        print("parameters", parameters)
        print("user_data", user_data)
        print("user_data_free_func", user_data_free_func)

    def get_updates(self):
        self.call_sync("StartGetUpdates")

    def on_get_updates_finished(self, connection, sender_name, object_path, interface_name, signal_name, parameters, user_data, user_data_free_func):
        print("on_get_updates_finished")
        print("connection", connection)
        print("sender_name", sender_name)
        print("object_path", object_path)
        print("interface_name", interface_name)
        print("signal_name", signal_name)
        print("parameters", parameters)
        print("user_data", user_data)
        print("user_data_free_func", user_data_free_func)


    def install(self, pkgs):
        """ pacman -S pkgs """
        flags = 0
        self.transaction_prepare(flags, pkgs, None, None)

    def remove(self, pkgs):
        """ pacman -R pkgs """
        flags = 0
        self.transaction_prepare(flags, None, pkgs, None)

    def update(self):
        """ pacman -Syu """
        self.get_updates()

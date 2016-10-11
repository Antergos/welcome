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
    _name = 'org.manjaro.pamac'
    _object_path = '/org/manjaro/pamac'
    _interface_name = 'org.manjaro.pamac'

    def __init__(self):
        self.interface = None
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

            self.dbus_proxy = Gio.DBusProxy.new_sync(
                self.bus, # connection
                Gio.DBusProxyFlags.NONE,
                None, # info
                PamacClient._name,
                PamacClient._object_path,
                PamacClient._interface_name,
                None)

            self.connect("RefreshFinished", self.on_refresh_finished)
            self.connect("TransPrepareFinished", self.on_transaction_prepare_finished)
            self.connect("TransCommitFinished", self.on_transaction_commit_finished)
            self.connect("GetUpdatesFinished", self.on_get_updates_finished)
        except Exception as err:
            print(err)
            print("Can't find pamac. Is it really installed?")

    def connect(self, signal_name, callback, user_data=None):
        if self.bus:
            self.bus.signal_subscribe(
                PamacClient._name, # sender
                PamacClient._interface_name, # interface_name
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
                # print(method_name, "called!")
                res = self.dbus_proxy.call_sync(
                    method_name,
                    params, # GLib.Variant(description, values)
                    Gio.DBusCallFlags.NONE,
                    -1,
                    None)
            except Exception as err:
                print(err)
            return res

    def get_current_error(self):
        return self.call_sync("GetCurrentError")

    def refresh(self):
        """ pacman -Sy """
        variant = GLib.Variant("(b)", (False, ))
        self.call_sync("StartRefresh", variant)

    def on_refresh_finished(
            self, connection, sender_name, object_path, interface_name,
            signal_name, parameters, user_data, user_data_free_func):
        print("on_refresh_finished result:", parameters)

    def transaction_prepare(self, flags, to_install, to_remove, to_load):
        """
        flags = (1 << 4); // Cascade
        flags |= (1 << 5); // Recurse
        """
        variant = GLib.Variant("(iasasas)", (flags, to_install, to_remove, to_load))
        self.call_sync("StartTransPrepare", variant)

    def on_transaction_prepare_finished(
            self, connection, sender_name, object_path, interface_name,
            signal_name, parameters, user_data, user_data_free_func):
        if parameters[0] == False:
            error = self.get_current_error()
            print(error)
        else:
            self.transaction_commit()

    def transaction_commit(self):
        self.call_sync("StartTransCommit")

    def on_transaction_commit_finished(
            self, connection, sender_name, object_path, interface_name,
            signal_name, parameters, user_data, user_data_free_func):
        if parameters[0] == False:
            error = self.get_current_error()
            print(error)

    def get_updates(self):
        check_aur_updates = False
        variant = GLib.Variant("(b)", (check_aur_updates, ))
        self.call_sync("StartGetUpdates", variant)

    def on_get_updates_finished(
            self, connection, sender_name, object_path, interface_name,
            signal_name, parameters, user_data, user_data_free_func):
        param1 = parameters[0]
        (unknown, pkgs_info, unknown2) = param1
        msg = ""
        pkgs = []
        for pkg_info in pkgs_info:
            (pkg, old_ver, new_ver, repo, size) = pkg_info
            msg += "Update {0} from {1} to {2}\n".format(pkg, old_ver, new_ver)
            pkgs.append(pkg)
        print(msg)

    def sys_upgrade_prepare(self):
        enable_downgrade = True
        temporary_ignorepkgs = [""]
        variant = GLib.Variant("(bas)", (enable_downgrade, temporary_ignorepkgs))
        self.call_sync("StartSysupgradePrepare", variant)

    # ------------------------------------------------------------------------

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
        #self.get_updates()
        self.sys_upgrade_prepare()

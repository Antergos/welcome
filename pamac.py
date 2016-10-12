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
gi.require_version('Notify', '0.7')

from gi.repository import GObject, Gio, GLib, Polkit, Notify

def _(x):
    return x

class SimplePamac(GObject.GObject):
    def __init__(self, packages, action=""):
        GObject.GObject.__init__(self)
        self._timeout=100
        self.packages = packages
        self.action = action
        self.refresh_before_install = False
        self.loop = GLib.MainLoop()
        self.client = PamacClient()
        if self.packages:
            print('Processing: ' + ', '.join(self.packages))

    def on_error(self, error):
        my_message = str(error)
        msg_dialog = Gtk.MessageDialog(transient_for=self,
                                       modal=True,
                                       destroy_with_parent=True,
                                       message_type=Gtk.MessageType.ERROR,
                                       buttons=Gtk.ButtonsType.CLOSE,
                                       text=_("Antergos Welcome - Error"))
        msg_dialog.format_secondary_text(my_message)
        msg_dialog.run()
        msg_dialog.destroy()

    def on_finished_refresh(self, status, error):
        self.do_notify(status)
        if status != 'exit-success':
            self.loop.quit()
            return False
        # Refresh finished, let's install
        GLib.timeout_add(self._timeout, self.do_install)
        return True

    def on_finished_update(self, client, status, error):
        self.do_notify(status)
        self.loop.quit()
        if status != 'exit-success':
            return False
        return True

    def on_finished_install(self, client, status, error):
        self.do_notify(status)
        self.loop.quit()
        if status != 'exit-success':
            return False
        return True

    def on_finished_remove(self, client, status, error):
        self.do_notify(status)
        self.loop.quit()
        if status != 'exit-success':
            return False
        return True

    def do_notify(self, status):
        print('Status: ' + status)
        if self.action == 'install':
            title = _('Install')
            noun = _('Installation of ')
            action = _('installed.')
        elif self.action == 'remove':
            title = _('Remove')
            noun = _('Removal of ')
            action = _('removed.')
        elif self.action == 'update':
            title = _('Update')
            noun = _('Update of ')
            action = _('updated.')

        notify = None
        if status == 'exit-success':
            Notify.init(title + ' ' + _('complete'))
            notify = Notify.Notification.new(title + ' ' + _('complete'), ', '.join(self.packages) + ' ' + _('has been successfully ') + action, 'dialog-information')
        elif status == 'exit-cancelled':
            Notify.init(title + ' ' + _('cancelled'))
            notify = Notify.Notification.new(title + ' ' + _('cancelled'), noun + ', '.join(self.packages) + ' ' + _('was cancelled.'), 'dialog-information')
        elif status == 'processing':
            Notify.init(title + ' ' + _('started'))
            notify = Notify.Notification.new(title + ' ' + _('started'), noun + ', '.join(self.packages) + ' ' + _('has started.'), 'dialog-information')
        else:
            Notify.init(title + ' ' + _('failed'))
            notify = Notify.Notification.new(title + ' ' + _('failed'), noun + ', '.join(self.packages) + ' ' + _('failed.'), 'dialog-error')

        notify.show()

    def do_update(self):
        self.client.connect("finished", self.on_finished_update)
        self.client.update()
        self.do_notify('processing')
        return False

    def do_install(self):
        self.client.connect("finished", self.on_finished_install)
        self.client.install(self.packages)
        self.do_notify('processing')
        return False

    def do_remove(self):
        self.client.connect("finished", self.on_finished_remove)
        self.client.remove(self.packages)
        self.do_notify('processing')
        return False

    def do_refresh(self):
        self.client.connect("finished", self.on_finished_refresh)
        self.client.refresh()
        self.do_notify('processing')

    def run_action(self):
        if self.action == "install":
            self.install_packages()
        elif self.action == "remove":
            self.remove_packages()
        elif self.action == "update":
            self.update_packages()

    def install_packages(self):
        if self.refresh_before_install:
            GLib.timeout_add(self._timeout, self.do_refresh)
        else:
            GLib.timeout_add(self._timeout, self.do_install)
        self.loop.run()

    def remove_packages(self):
        GLib.timeout_add(self._timeout, self.do_remove)
        self.loop.run()

    def update_packages(self):
        GLib.timeout_add(self._timeout, self.do_update)
        self.loop.run()

class PamacClient(GObject.GObject):
    _name = 'org.manjaro.pamac'
    _object_path = '/org/manjaro/pamac'
    _interface_name = 'org.manjaro.pamac'

    __gsignals__ = {
        'finished': (GObject.SignalFlags.RUN_FIRST, None, (str,str))
    }

    def __init__(self):
        GObject.GObject.__init__(self)
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

            self.signal_subscribe("RefreshFinished", self.on_refresh_finished)
            self.signal_subscribe("TransPrepareFinished", self.on_transaction_prepare_finished)
            self.signal_subscribe("TransCommitFinished", self.on_transaction_commit_finished)
            self.signal_subscribe("GetUpdatesFinished", self.on_get_updates_finished)
        except Exception as err:
            print(err)
            print("Can't find pamac. Is it really installed?")

    def signal_subscribe(self, signal_name, callback, user_data=None):
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
        if parameters[0] == False:
            error = self.get_current_error()
            print(error)
            self.emit("finished", "exit-error", error)
        else:
            self.emit("finished", "exit-success")

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
            self.emit("finished", "exit-error", error)
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
            self.emit("finished", "exit-error", error)
        else:
            self.emit("finished", "exit-success", None)

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
        """ on_transaction_prepare_finished will be called when finished """
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

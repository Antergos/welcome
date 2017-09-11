#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  client.py
#
#  Copyright © 2015-2017 Antergos
#
#  This file is part of antergos-welcome
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

import sys, os
import gi

gi.require_version('Polkit', '1.0')
gi.require_version('Notify', '0.7')

from gi.repository import GObject, Gio, GLib, Polkit, Notify

try:
    from pydbus import SessionBus, SystemBus
    from pydbus.generic import signal
except ImportError as err:
    msg = "Can't import pydbus library: {}".format(err)
    logging.error(msg)
    print(msg)
    sys.exit(-1)

def _(x):
    return x

class SimpleWelcomed(GObject.GObject):
    def __init__(self, packages, action=""):
        GObject.GObject.__init__(self)
        self._timeout = 100
        self.packages = packages
        self.action = action
        self.refresh_before_install = False
        self.loop = GLib.MainLoop()
        self.client = WelcomedClient()
        self.client.connect("command-finished", self.on_command_finished)
        Notify.init("antergos-welcome")

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

    def quit(self):
        """ called when the app quits """
        Notify.uninit()
        self.loop.quit()

    def on_command_finished(self, client, uid, command, pkgs):
        # print("on_command_finished:, command)
        self.notify(command, 'exit-success')
        self.loop.quit()

    def prepare_message(self, command, status):
        dialog_type = 'dialog-information'
        title = ""
        msg = ""
        if command == 'install' or command == 'install_packages' or command == 'install_package':
            if status == 'exit-success':
                title = _("Installation succeeded!")
                if len(self.packages) > 1:
                    msg =  _('{} have been successfully installed').format(' '.join(self.packages))
                else:
                    msg = _('{} has been successfully installed').format(self.packages[0])
            elif status == 'processing':
                title = _("Installation")
                msg = _("Installing {} package(s)").format(' '.join(self.packages))
            else:
                title = _("Installation failed!")
                msg = _("Cannot install {} package(s)").format(' '.join(self.packages))
                dialog_type = 'dialog-error'
        elif command == 'remove' or command == 'remove_packages' or command == 'remove_package':
            if status == 'exit-success':
                title = _("Removal succeeded!")
                if len(self.packages) > 1:
                    msg =  _('{} have been successfully removed').format(' '.join(self.packages))
                else:
                    msg = _('{} has been successfully removed').format(self.packages[0])
            elif status == 'processing':
                title = _("Removal")
                msg = _("Removing {} package(s)").format(' '.join(self.packages))
            else:
                title = _("Removal failed!")
                msg = _("Cannot remove {} package(s)").format(' '.join(self.packages))
                dialog_type = 'dialog-error'
        elif command == 'refresh' or command == 'refresh_alpm':

            if status == 'exit-success':
                title = _("System refresh succeeded!")
                msg = _("System databases updated successfully")
            elif status == 'processing':
                title = _("System refresh")
                msg = _("Updating system databases...")
            else:
                title = _("System refresh failed!")
                msg = _("Cannot update system databases!")
                dialog_type = 'dialog-error'
        elif command == 'system_upgrade':

            if status == 'exit-success':
                title = _("System upgrade succeeded!")
                msg = _("System upgraded successfully")
            elif status == 'processing':
                title = _("System upgrade")
                msg = _("Upgrading system...")
            else:
                title = _("System upgrade failed!")
                msg = _("Cannot upgrade system!")
                dialog_type = 'dialog-error'
        else:
            title = _("Unknown action!")
            msg = _("Action '{}' is unknown").format(command)
            dialog_type = 'dialog-error'

        return (title, msg, dialog_type)

    def notify(self, command, status):
        # print('Status: ' + status)
        (title, msg, dialog_type) = self.prepare_message(command, status)
        Notify.Notification.new(title, msg, dialog_type).show()

    def _do_install_packages(self):
        self.notify('install', 'processing')
        self.client.install_packages(self.packages)
        return False

    def _do_remove_packages(self):
        self.notify('remove', 'processing')
        self.client.remove_packages(self.packages)
        return False

    def _do_refresh(self):
        self.notify('refresh', 'processing')
        self.client.refresh()
        return False

    def _do_system_upgrade(self):
        self.notify('system_upgrade', 'processing')
        self.client.system_upgrade()
        return False

    def run_action(self):
        if self.client.welcomed_ok:
            if self.action == "refresh":
                self.refresh()
            elif self.action == "system_upgrade":
                self.system_upgrade()
            elif self.action == "install":
                self.install_packages()
            elif self.action == "remove":
                self.remove_packages()

    def refresh(self):
        GLib.timeout_add(self._timeout, self._do_refresh)
        self.loop.run()

    def install_packages(self):
        if self.refresh_before_install:
            GLib.timeout_add(self._timeout, self._do_refresh)
        else:
            GLib.timeout_add(self._timeout, self._do_install_packages)
        self.loop.run()

    def remove_packages(self):
        GLib.timeout_add(self._timeout, self._do_remove_packages)
        self.loop.run()

    def system_upgrade(self):
        GLib.timeout_add(self._timeout, self._do_system_upgrade)
        self.loop.run()

class WelcomedClient(GObject.GObject):
    _name = 'com.antergos.welcome'
    _object_path = '/com/antergos/welcome'
    _interface_name = 'com.antergos.welcome'

    __gsignals__ = {
        'command-finished': (GObject.SignalFlags.RUN_FIRST, None,
            (str, str, GObject.TYPE_PYOBJECT))
    }

    def __init__(self):
        GObject.GObject.__init__(self)
        self.interface = None
        self.welcomed_ok = False
        try:
            self.bus = SystemBus()
            self.dbus_proxy = self.bus.get(
                WelcomedClient._name,
                WelcomedClient._object_path)

            if not self.dbus_proxy:
                self.welcomed_ok = False
            else:
                self.dbus_proxy.PropertiesChanged.connect(self.on_properties_changed)
                self.welcomed_ok = self.dbus_proxy.is_alpm_on()
        except Exception as err:
            print(err)
        finally:
            if not self.welcomed_ok:
                msg = _("Can't find Welcome d-bus service. Is it really installed?")
                Notify.init("antergos-welcome")
                Notify.Notification.new(_("ERROR!"), msg, 'dialog-error').show()

    def refresh(self):
        """ pacman -Sy """
        return self.dbus_proxy.refresh_alpm()

    def on_properties_changed(self, *params):
        """ A d-bus server property has changed """
        (sender, prop, not_used) = params
        # print("PARAMS:", params)
        if sender == WelcomedClient._name and 'command_finished' in prop.keys():
            (uid, command, pkgs) = prop['command_finished']
            self.emit("command-finished", uid, command, pkgs)

    def install_package(self, pkg):
        """ pacman -S pkg """
        return self.dbus_proxy.install_package(pkgs)

    def install_packages(self, pkgs):
        """ pacman -S pkgs """
        return self.dbus_proxy.install_packages(pkgs)

    def remove_package(self, package):
        """ pacman -R pkg """
        return self.dbus_proxy.remove_package(package)

    def remove_packages(self, pkgs):
        """ pacman -R pkgs """
        for pkg in pkgs:
            self.remove_package(pkg)

    def check_updates(self):
        return self.dbus_proxy.check_updates()

    def system_upgrade(self):
        return self.dbus_proxy.system_upgrade()

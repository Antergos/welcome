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

    """
    def on_finished_refresh(self, client, status, error):
        self.do_notify(status)
        if status != 'exit-success':
            self.loop.quit()
            return False
        if self.packages:
            # Refresh finished, let's install
            GLib.timeout_add(self._timeout, self.do_install)
        return True
    """

    def quit(self):
        self.loop.quit()

    def on_command_finished(self, client, uid, command, pkgs):
        #print("client", client)
        #print("uid", uid)
        #print("command", command)
        #print("pkgs", pkgs)
        self.do_notify('exit-success')
        self.loop.quit()

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
        self.do_notify('processing')
        self.client.update()
        return False

    def do_install(self):
        self.do_notify('processing')
        self.client.install(self.packages)
        return False

    def do_remove(self):
        self.do_notify('processing')
        self.client.remove(self.packages)
        return False

    def do_refresh(self):
        self.do_notify('processing')
        self.client.refresh()

    def run_action(self):
        if self.client.welcomed_ok:
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
                print(msg)
                Notify.init(_("Cannot connect with Welcomed"))
                notify = Notify.Notification.new(title, msg, 'dialog-error')
                notify.show()

    def refresh(self):
        """ pacman -Sy """
        print("refresh_alpm")
        return self.dbus_proxy.refresh_alpm()

    def on_properties_changed(self, *params):
        """ A d-bus server property has changed """
        (sender, prop, not_used) = params
        if sender == WelcomedClient._name and 'command_finished' in prop.keys():
            (uid, command, pkgs) = prop['command_finished']
            self.emit("command-finished", uid, command, pkgs)

    def install_packages(self, pkgs):
        """ pacman -S pkgs """
        #variant = GLib.Variant("(as)", (pkgs, ))
        #print("install_packages", pkgs)
        #return self.call_sync("install_packages", variant)
        return self.dbus_proxy.install_packages(pkgs)

    def remove_package(self, package):
        """ pacman -R pkg """
        #variant = GLib.Variant("(s)", (pkg))
        #return self.call_sync("remove_package", variant)
        return self.dbus_proxy.remove_package(package)

    def check_updates(self):
        #return self.call_sync("check_updates")
        return self.dbus_proxy.check_updates()

    def system_upgrade(self):
        #return self.call_sync("system_upgrade")
        return self.dbus_proxy.system_upgrade()

    # ------------------------------------------------------------------------

    def install(self, pkgs):
        self.install_packages(pkgs)

    def remove(self, pkgs):
        """ pacman -R pkgs """
        for pkg in pkgs:
            self.remove_package(pkg)

    def update(self):
        """ pacman -Syu """
        #self.get_updates()
        self.system_upgrade()

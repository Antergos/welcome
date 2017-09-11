#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  service.py
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

import json
import logging
import os
import subprocess
import sys
import threading
import uuid
from queue import Queue
import time
import errno

import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib

try:
    from pydbus import SessionBus, SystemBus
    from pydbus.generic import signal
except ImportError as err:
    msg = "Can't import pydbus library: {}".format(err)
    logging.error(msg)
    print(msg)
    sys.exit(-1)

try:
    from pacman import pac
except ImportError as err:
    logging.error(err.msg)
    msg = "Can't find {} bindings. Unable to install/uninstall apps".format(err.name)
    logging.error(msg)
    sys.exit(-1)


INTERFACE = 'com.antergos.welcome'


class DBusService(object):
    """
    <node>
        <interface name='com.antergos.welcome'>
            <method name='get_package_exists'>
                <arg type='s' name='package_name' direction='in'/>
                <arg type='s' name='response' direction='out'/>
            </method>
            <method name='check_updates'>
                <arg type='as' name='response' direction='out'/>
            </method>
            <method name='refresh_alpm'>
                <arg type='s' name='uid' direction='out'/>
            </method>
            <method name='install_package'>
                <arg type='s' name='package_name' direction='in'/>
                <arg type='s' name='response' direction='out'/>
            </method>
            <method name='remove_package'>
                <arg type='s' name='package_name' direction='in'/>
                <arg type='s' name='response' direction='out'/>
            </method>
            <method name='install_packages'>
                <arg type='as' name='package_names' direction='in'/>
                <arg type='as' name='response' direction='out'/>
            </method>
            <method name='system_upgrade'>
                <arg type='as' name='response' direction='out'/>
            </method>
            <method name='exit'/>
            <method name='is_alpm_on'>
                <arg type='b' name='response' direction='out'/>
            </method>
            <method name='is_package_installed'>
                <arg type='s' name='package_name' direction='in'/>
                <arg type='b' name='response' direction='out'/>
            </method>
            <property name="command_finished" type="(ssas)" access="readwrite">
                <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/>
            </property>
        </interface>
    </node>
    """


    def __init__(self, mainloop, object_path="/com/antergos/welcome"):
        self.alpm = None
        self.updates_available = self.store_loaded = False
        self.mainloop = mainloop
        self._command_finished = ()

        # We will store package metadata before its needed to improve
        # performance on the frontend.
        self.all_packages = {}

        self.initialize_alpm()

        # File lock db.lck (pacman)
        # Times are in seconds
        self.is_locked = False
        self.lock_file = "/var/lib/pacman/db.lck"
        self.lock_timeout = 30
        self.lock_delay = 1

        # lock to serialize alpm petitions (install/uninstall)
        self.lock = threading.Lock()

        self.command_queue = Queue()
        t = threading.Thread(target=self._command_queue_worker)
        t.daemon = True
        t.start()

    def initialize_alpm(self):
        try:
            self.alpm = pac.Pac()
            logging.debug("Alpm library initialized")
        except Exception as err:
            logging.error("Cannot initialize alpm library")
            sys.exit(-1)

    @staticmethod
    def get_uuid():
        return str(uuid.uuid1())

    # DBus methods -------------------------------------------------------------

    def get_package_exists(self, package_name):
        """ Checks for package in ALPM database. Return True if found, otherwise False. """
        pkg = self.alpm.get_package_info(package_name)
        return pkg is not {}

    def check_updates(self, dbus_context):
        """ Check for available updates. """
        if self.is_authorized(dbus_context):
            return self._check_updates()
        else:
            return []

    def is_alpm_on(self, dbus_context):
        if self.is_authorized(dbus_context):
            return bool(self.alpm)
        else:
            return False

    def is_package_installed(self, package_name):
        """ Return if the given package is installed. """
        return bool(self.alpm.is_package_installed(str(package_name)))

    def refresh_alpm(self, dbus_context):
        """ Refreshes alpm databases """
        if self.is_authorized(dbus_context):
            uid = self.get_uuid()
            self.command_queue.put((uid, 'refresh', []))
            return uid
        else:
            return ""

    def install_package(self, package_name, dbus_context):
        """ Install the given package. """
        if self.is_authorized(dbus_context):
            uid = self.get_uuid()
            self.command_queue.put((uid, 'install', [package_name]))
            return uid
        else:
            return ""

    def remove_package(self, package_name, dbus_context):
        """ Uninstall the given package. """
        if self.is_authorized(dbus_context):
            uid = self.get_uuid()
            self.command_queue.put((uid, 'remove', [package_name]))
            return uid
        else:
            return ""

    def install_packages(self, package_names, dbus_context):
        """ Install updates """
        if self.is_authorized(dbus_context):
            uid = self.get_uuid()
            self.command_queue.put((uid, 'install_packages', list(package_names)))
            return uid
        else:
            return ""

    def system_upgrade(self, dbus_context):
        """ Install updates """
        if self.is_authorized(dbus_context):
            uid = self.get_uuid()
#            self.command_queue.put((uid, 'refresh', []))
            self.command_queue.put((uid, 'system_upgrade', []))
            return uid
        else:
            return ""

    def exit(self, dbus_context):
        if self.is_authorized(dbus_context) and self.mainloop:
            self.mainloop.quit()

    # DBus signals -------------------------------------------------------------
    @property
    def command_finished(self):
        return self._command_finished

    @command_finished.setter
    def command_finished(self, value):
        self._command_finished = value
        logging.debug("command_finished")
        # print(value)
        self.PropertiesChanged("com.antergos.welcome", {"command_finished": self.command_finished}, [])

    PropertiesChanged = signal()

    # Internal alpm methods ----------------------------------------------------

    def _check_updates(self):
        """ Check for available updates. """
        updates = self.alpm.check_updates()
        logging.info(updates)
        if not updates:
            updates = []
        return updates

    def _refresh_alpm(self):
        with self.lock:
            logging.info("Refreshing databases...")
            try:
                self.alpm.refresh()
            except Exception as general_error:
                logging.error(general_error)

    def _install_package(self, package):
        with self.lock:
            logging.info("Installing %s", package)
            try:
                self.alpm.install([str(package)])
            except Exception as general_error:
                logging.error(general_error)

    def _remove_package(self, package):
        with self.lock:
            logging.info("Removing %s", package)
            try:
                self.alpm.remove([str(package)])
            except Exception as general_error:
                logging.error(general_error)

    def _install_packages(self, packages):
        with self.lock:
            logging.info("Installing %s", packages)
            try:
                self.alpm.install(packages)
            except Exception as general_error:
                logging.error(general_error)

    def _system_upgrade(self):
        with self.lock:
            logging.info("Full system upgrade...")
            try:
                self.alpm.system_upgrade()
            except Exception as general_error:
                logging.error(general_error)

    def _command_queue_worker(self):
        while True:
            if self.lock_ok():
                uid, command, packages = self.command_queue.get()
                if command == 'install':
                    self._install_package(packages[0])
                    # Send signal to frontends
                    self.command_finished = (uid, command, packages)
                elif command == 'install_packages':
                    self._install_packages(packages)
                    self.command_finished = (uid, command, packages)
                elif command == 'remove':
                    self._remove_package(packages[0])
                    self.command_finished = (uid, command, packages)
                elif command == 'refresh':
                    self._refresh_alpm()
                    self.command_finished = (uid, command, packages)
                elif command == 'check_updates':
                    output = self._check_updates()
                    self.command_finished = (uid, command, packages)
                elif command == 'system_upgrade':
                    self._system_upgrade()
                    self.command_finished = (uid, command, packages)
                elif command == 'frontend_loaded':
                    self._do_frontend_loaded()
                    self.command_finished = (uid, command, packages)
                else:
                    logging.error(_("Unknown command %s"), command)

    # Polkit -------------------------------------------------------------------

    def is_authorized(self, dbus_context, interactive=True):
        action_id = "com.antergos.welcome.install"
        details = {
            'polkit.icon': 'antergos-welcome',
            'polkit.message': 'antergos-welcome'}

        return dbus_context.check_authorization(action_id, details, interactive=True)


    # db.lck -------------------------------------------------------------------

    def lock_ok(self):
        if self._is_lock_available():
            return True
        # Lock exists, we will try to acquire it (waiting)
        if self._acquire_lock():
            # Yes! We got it! Delete it.
            self._release_lock()
            return True
        logging.error("db.lck exists and is owned by another process!")
        return False

    def _is_lock_available(self):
        """ Returns True if the file is currently available to be locked. """
        return not os.path.exists(self.lock_file)

    def _acquire_lock(self, delay=1, timeout=10):
        """
        Acquire the lock, if possible. Otherwise, check again every `delay`
        seconds until it either gets the lock or exceeds `timeout` number of
        seconds.
        """
        start_time = time.time()
        while True:
            try:
                # Attempt to create the lockfile.
                # These flags cause os.open to raise an OSError if the file already exists.
                fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                break;
            except OSError as err:
                if err.errno != errno.EEXIST:
                    logging.error("Cannot acquire lock!")
                    return False
                if (time.time() - start_time) >= timeout:
                    logging.error("Lock timeout!")
                    return False
                # wait delay seconds and try again
                time.sleep(delay)
        self.is_locked = True
        return True

    def _release_lock(self):
        """ Get rid of the lock by deleting the lockfile. """
        self.is_locked = False
        os.unlink(self.lockfile)

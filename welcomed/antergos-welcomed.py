#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  antergos-welcomed.py
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

import optparse
import logging
import gettext
import locale
import os
import sys

import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib

from pydbus import SessionBus, SystemBus

# DBus service
import service

APP_NAME = "antergos-welcomed"
LOCALE_DIR = "/usr/share/locale"


def parse_argv():
    """ Parse command line arguments, and return (options, args) pair. """

    parser = optparse.OptionParser()

    parser.add_option(
        '-d', '--debug', action='store_true',
        dest='debug', default=False,
        help=_('Enable debugging messages.'))

    parser.add_option(
        '-v', '--verbose', action='store_true',
        dest='verbose', default=False,
        help=_('Send logging messages to stdout instead of stderr.'))

    (opts, args) = parser.parse_args()
    return opts, args


def setup_logging(argv_options):
    """ Configure our logger """

    debug_level = argv_options.debug
    verbose = argv_options.verbose

    logger = logging.getLogger()

    logger.handlers = []

    if debug_level:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logger.setLevel(log_level)

    # Log format
    formatter = logging.Formatter(
        '[%(asctime)s] [%(module)s] %(levelname)s: %(message)s', "%Y-%m-%d %H:%M:%S")

    # Create file handler
    log_file = os.path.join('/var/log', "{}.log".format(APP_NAME))

    try:
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except PermissionError as permission_error:
        print("Can't open {0} : {1}".format(log_file, permission_error))

    if verbose:
        # Show log messages to stdout
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(log_level)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)


def setup_gettext():
    # This allows to translate all py texts (not the glade ones)
    gettext.textdomain(APP_NAME)
    gettext.bindtextdomain(APP_NAME, LOCALE_DIR)

    locale_code, encoding = locale.getdefaultlocale()
    lang = gettext.translation(APP_NAME, LOCALE_DIR, locale_code, None, True)
    lang.install()

    # With this we can use _("string") to translate
    gettext.install(APP_NAME, localedir=LOCALE_DIR, codeset=None, names=locale_code)


if __name__ == '__main__':
    setup_gettext()
    argv_options, argv_args = parse_argv()
    setup_logging(argv_options)

    mainloop = GLib.MainLoop()
    bus = SystemBus()
    logging.debug(_("Connected to the system bus"))
    bus.publish("com.antergos.welcome", service.DBusService(mainloop))

    mainloop.run()

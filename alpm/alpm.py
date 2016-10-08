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

import sys
import glob

from collections import OrderedDict
from alpm import alpm_events as events

try:
    import pyalpm
except ImportError as err:
    print(err)
    print("Check that you have python-alpm installed")
    sys.exit(-1)

class InvalidSyntax(Warning):
    """ Class to show warning when a pacman.conf parse error is issued """

    def __init__(self, filename, problem, arg):
        self.filename = filename
        self.problem = problem
        self.arg = arg

    def __str__(self):
        return "unable to parse {0}, {1}: {2}".format(self.filename, self.problem, self.arg)

class BasicPacman():
    """ Comunicates with libalpm using pyalpm """
    _ROOT_DIR = "/"
    _DB_PATH = "/var/lib/pacman"

    def __init__(self):
        self.repos = OrderedDict()

        for section, key, value in self.pacman_conf_repos_enumerator("/etc/pacman.conf"):
            if section != 'options':
                self.repos.setdefault(section, {})
                if key == 'Server':
                    self.repos[section].setdefault('urls', []).append(value)

        self.handle = pyalpm.Handle(BasicPacman._ROOT_DIR, BasicPacman._DB_PATH)

        if self.handle is None:
            print("Alpm initialization error!")
            raise pyalpm.error

        self.handle.logfile = "/var/log/pacman/pacman.log"
        self.handle.gpgdir = "/etc/pacman.d/gnupg/"
        self.handle.arch = "auto"
        self.handle.cachedirs = "/var/cache/pacman/pkg"

        # set "update" and "sync" databases
        for repo, info in self.repos.items():
            print(repo)
            servers = info['urls']
            db = self.handle.register_syncdb(repo, 0)
            db_servers = []
            for raw_url in servers:
                url = raw_url.replace("$repo", repo)
                url = url.replace("$arch", "auto")
                db_servers.append(url)
            db.servers = db_servers

        self.handle.logcb = None
        self.handle.dlcb = None
        self.handle.totaldlcb = None
        self.handle.eventcb = self.cb_event
        self.handle.questioncb = None
        self.handle.progresscb = self.cb_progress
        self.handle.fetchcb = None

    @staticmethod
    def pacman_conf_repos_enumerator(path):
        filestack = []
        current_section = None
        filestack.append(open(path))
        while len(filestack) > 0:
            f = filestack[-1]
            line = f.readline()
            if len(line) == 0:
                # end of file
                f.close()
                filestack.pop()
                continue

            line = line.strip()
            if len(line) == 0 or line[0] == '#':
                continue
            if line[0] == '[' and line[-1] == ']':
                current_section = line[1:-1]
                continue
            if current_section is None:
                raise InvalidSyntax(f.name, 'statement outside of a section', line)

            # read key, value
            key, equal, value = [x.strip() for x in line.partition('=')]

            # include files
            if equal == '=' and key == 'Include':
                filestack.extend(open(f) for f in glob.glob(value))
                continue

            if current_section != 'options':
                # repos only have the Server, SigLevel, Usage options
                if key in ('Server', 'SigLevel', 'Usage') and equal == '=':
                    yield (current_section, key, value)
                else:
                    raise InvalidSyntax(f.name, 'invalid key for repository configuration', line)
                continue

    def release(self):
        """ Release alpm handle """
        if self.handle is not None:
            del self.handle
            self.handle = None

    @staticmethod
    def finalize_transaction(transaction):
        """ Commit a transaction """
        all_ok = False
        try:
            print("Prepare alpm transaction...")
            transaction.prepare()
            print("Commit alpm transaction...")
            transaction.commit()
            all_ok = True
        except pyalpm.error as pyalpm_error:
            msg = _("Can't finalize alpm transaction: %s")
            print(msg, pyalpm_error)
            traceback.print_exc()
        finally:
            print("Releasing alpm transaction...")
            transaction.release()
            print("Alpm transaction done.")
        return all_ok

    def init_transaction(self, options=None):
        """ Transaction initialization """
        if options is None:
            options = {}

        transaction = None

        try:
            transaction = self.handle.init_transaction(
                nodeps=options.get('nodeps', False),
                dbonly=options.get('dbonly', False),
                force=options.get('force', False),
                needed=options.get('needed', False),
                alldeps=(options.get('mode', None) == pyalpm.PKG_REASON_DEPEND),
                allexplicit=(options.get('mode', None) == pyalpm.PKG_REASON_EXPLICIT),
                cascade=options.get('cascade', False),
                nosave=options.get('nosave', False),
                recurse=(options.get('recursive', 0) > 0),
                recurseall=(options.get('recursive', 0) > 1),
                unneeded=options.get('unneeded', False),
                downloadonly=options.get('downloadonly', False))
        except pyalpm.error as pyalpm_error:
            print("Can't init alpm transaction:", pyalpm_error)
        return transaction

    def remove(self, pkg_names, options=None):
        """ Removes a list of package names """

        if not options:
            options = {}

        # Prepare target list
        targets = []
        database = self.handle.get_localdb()
        for pkg_name in pkg_names:
            pkg = database.get_pkg(pkg_name)
            if pkg is None:
                print("Target {} not found".format(pkg_name))
                return False
            targets.append(pkg)

        transaction = self.init_transaction(options)

        if transaction is None:
            print("Can't init transaction")
            return False

        for pkg in targets:
            print("Adding package '{}' to remove transaction".format(pkg.name))
            transaction.remove_pkg(pkg)

        return self.finalize_transaction(transaction)

    def refresh(self):
        """ Sync databases like pacman -Sy """
        if self.handle is None:
            print("alpm is not initialised")
            raise pyalpm.error

        force = True
        res = True
        for database in self.handle.get_syncdbs():
            transaction = self.init_transaction()
            if transaction:
                database.update(force)
                transaction.release()
            else:
                res = False
        return res

    def install(self, pkgs, conflicts=None, options=None):
        """ Install a list of packages like pacman -S """

        if not conflicts:
            conflicts = []

        if not options:
            options = {}

        if self.handle is None:
            print("alpm is not initialised")
            raise pyalpm.error

        if len(pkgs) == 0:
            print("Package list is empty")
            raise pyalpm.error

        # Discard duplicates
        pkgs = list(set(pkgs))

        # `alpm.handle.get_syncdbs()` returns a list (the order is important) so we
        # have to ensure we don't clobber the priority of the repos.
        repos = OrderedDict()
        repo_order = []
        one_repo_groups = ['cinnamon', 'mate', 'mate-extra']
        db_match = [db for db in self.handle.get_syncdbs() if 'antergos' == db.name]
        antdb = OrderedDict()
        antdb['antergos'] = db_match[0]
        one_repo_groups = [antdb['antergos'].read_grp(one_repo_group)
                           for one_repo_group in one_repo_groups]
        one_repo_pkgs = {pkg for one_repo_group in one_repo_groups
                         for pkg in one_repo_group[1] if one_repo_group}

        for syncdb in self.handle.get_syncdbs():
            repo_order.append(syncdb)
            repos[syncdb.name] = syncdb

        targets = []
        print('REPO DB ORDER IS: %s', repo_order)

        for name in pkgs:
            _repos = repos

            if name in one_repo_pkgs:
                # pkg should be sourced from the antergos repo only.
                _repos = antdb

            result_ok, pkg = self.find_sync_package(name, _repos)

            if result_ok:
                # Check that added package is not in our conflicts list
                if pkg.name not in conflicts:
                    targets.append(pkg.name)
            else:
                # Couldn't find the package, check if it's a group
                group_pkgs = self.get_group_pkgs(name)
                if group_pkgs is not None:
                    # It's a group
                    for group_pkg in group_pkgs:
                        # Check that added package is not in our conflicts list
                        # Ex: connman conflicts with netctl(openresolv),
                        # which is installed by default with base group
                        if group_pkg.name not in conflicts:
                            targets.append(group_pkg.name)
                else:
                    # No, it wasn't neither a package nor a group. As we don't
                    # know if this error is fatal or not, we'll register it and
                    # we'll allow to continue.
                    print("Can't find a package or group called ", name)

        # Discard duplicates
        targets = list(set(targets))
        print(targets)

        if len(targets) == 0:
            print("No targets found")
            return False

        num_targets = len(targets)
        print("{} target(s) found".format(num_targets))

        # Maybe not all this packages will be downloaded, but it's
        # how many have to be there before starting the installation
        self.total_packages_to_download = num_targets

        transaction = self.init_transaction(options)

        if transaction is None:
            print("Can't initialize alpm transaction")
            return False

        for i in range(0, num_targets):
            result_ok, pkg = self.find_sync_package(targets.pop(), repos)
            if result_ok:
                transaction.add_pkg(pkg)
            else:
                print(pkg)

        return self.finalize_transaction(transaction)

    @staticmethod
    def find_sync_package(pkgname, syncdbs):
        """ Finds a package name in a list of DBs
        :rtype : tuple (True/False, package or error message)
        """
        for database in syncdbs.values():
            pkg = database.get_pkg(pkgname)
            if pkg is not None:
                return True, pkg
        return False, "Package '{0}' was not found.".format(pkgname)

    def get_group_pkgs(self, group):
        """ Get group's packages """
        for repo in self.handle.get_syncdbs():
            grp = repo.read_grp(group)
            if grp is not None:
                name, pkgs = grp
                return pkgs
        return None

    def is_package_installed(self, package_name):
        """ Check if package is already installed """
        database = self.handle.get_localdb()
        pkgs = database.search(*[package_name])
        names = []
        for pkg in pkgs:
            names.append(pkg.name)
        if package_name in names:
            return True
        else:
            return False

    # Callbacks

    def cb_event(self, event_type, event_txt):
        """ Converts action ID to descriptive text and enqueues it to the events queue """

        if event_type is alpm.ALPM_EVENT_CHECKDEPS_START:
            action = _('Checking dependencies...')
        elif event_type is alpm.ALPM_EVENT_FILECONFLICTS_START:
            action = _('Checking file conflicts...')
        elif event_type is alpm.ALPM_EVENT_RESOLVEDEPS_START:
            action = _('Resolving dependencies...')
        elif event_type is alpm.ALPM_EVENT_INTERCONFLICTS_START:
            action = _('Checking inter conflicts...')
        elif event_type is alpm.ALPM_EVENT_PACKAGE_OPERATION_START:
            # Shown in cb_progress
            action = ""
        elif event_type is alpm.ALPM_EVENT_INTEGRITY_START:
            action = _('Checking integrity...')
        elif event_type is alpm.ALPM_EVENT_LOAD_START:
            action = _('Loading packages...')
        elif event_type is alpm.ALPM_EVENT_DELTA_INTEGRITY_START:
            action = _("Checking target delta's integrity...")
        elif event_type is alpm.ALPM_EVENT_DELTA_PATCHES_START:
            action = _('Applying deltas to packages...')
        elif event_type is alpm.ALPM_EVENT_DELTA_PATCH_START:
            action = _('Applying delta patch to target package...')
        elif event_type is alpm.ALPM_EVENT_RETRIEVE_START:
            action = _('Downloading files from the repository...')
        elif event_type is alpm.ALPM_EVENT_DISKSPACE_START:
            action = _('Checking disk space...')
        elif event_type is alpm.ALPM_EVENT_KEYRING_START:
            action = _('Checking keys in keyring...')
        elif event_type is alpm.ALPM_EVENT_KEY_DOWNLOAD_START:
            action = _('Downloading missing keys into the keyring...')
        else:
            action = ""

        if len(action) > 0:
            print(action)

    def cb_progress(self, target, percent, total, current):
        """ Shows install progress """
        if target:
            msg = _("Installing {0} ({1}/{2})").format(target, current, total)
            print('info', msg)
        else:
            print('.', end="", flush=True)

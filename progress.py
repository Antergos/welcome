import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

class SimpleProgressDialog(Gtk.Dialog):
    def __init__(self, parent):
        Gtk.Dialog.__init__(self, title="Antergos Welcome")

        box = self.get_content_area()
        self.progressbar = Gtk.ProgressBar()
        box.pack_start(self.progressbar, True, True, 0)

        self.timeout_id = GLib.timeout_add(50, self.on_timeout, None)

    def on_timeout(self, user_data):
        """ Update value on the progress bar """
        self.progressbar.pulse()

        # As this is a timeout function, return True so that it
        # continues to get called
        return True

#!/usr/bin/env python3
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango, GdkPixbuf
import subprocess
import threading
import shutil
import os

ICON_PATH = "/usr/share/edbian-updater/icon_update.jpg"

def command_exists(cmd):
    return shutil.which(cmd) is not None


class Updater(Gtk.Window):
    def __init__(self):
        super().__init__(title="Edbian Updater PRO")
        self.set_default_size(1000, 750)

        # ---------------- ICON ----------------
        self.set_window_icon()

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(vbox)

        self.status = Gtk.Label(label="Ready")
        vbox.pack_start(self.status, False, False, 0)

        btn_box = Gtk.Box(spacing=6)
        vbox.pack_start(btn_box, False, False, 0)

        self.check_btn = Gtk.Button(label="Check updates")
        self.check_btn.connect("clicked", self.on_check)
        btn_box.pack_start(self.check_btn, True, True, 0)

        self.update_all_btn = Gtk.Button(label="Update ALL")
        self.update_all_btn.set_sensitive(False)
        self.update_all_btn.connect("clicked", self.on_update_all)
        btn_box.pack_start(self.update_all_btn, True, True, 0)

        # Progress
        self.phase_progress = Gtk.ProgressBar()
        self.package_progress = Gtk.ProgressBar()
        self.package_label = Gtk.Label(label="")
        vbox.pack_start(self.phase_progress, False, False, 0)
        vbox.pack_start(self.package_label, False, False, 0)
        vbox.pack_start(self.package_progress, False, False, 0)

        # Table
        self.store = Gtk.ListStore(bool, str, str, str, str, str)
        tree = Gtk.TreeView(model=self.store)

        toggle = Gtk.CellRendererToggle()
        toggle.connect("toggled", self.on_toggle_row)
        tree.append_column(Gtk.TreeViewColumn("✔", toggle, active=0))

        columns = ["Status", "Type", "Package", "Version", "Priority"]
        for i, col in enumerate(columns):
            renderer = Gtk.CellRendererText()
            tree.append_column(Gtk.TreeViewColumn(col, renderer, text=i+1))

        scroll = Gtk.ScrolledWindow()
        scroll.add(tree)
        vbox.pack_start(scroll, True, True, 0)

        # Log
        self.log = Gtk.TextView()
        self.log.set_editable(False)
        self.log.modify_font(Pango.FontDescription("monospace 10"))
        self.buffer = self.log.get_buffer()
        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_size_request(-1, 150)
        log_scroll.add(self.log)
        vbox.pack_start(log_scroll, False, False, 0)

        self.updates = []

    # ---------------- ICON ----------------
    def set_window_icon(self):
        try:
            if os.path.exists(ICON_PATH):
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(ICON_PATH)
                self.set_icon(pixbuf)
            else:
                print(f"[WARN] Icon not found: {ICON_PATH}")
        except Exception as e:
            print(f"[ERROR] Loading icon: {e}")

    def log_msg(self, text):
        end = self.buffer.get_end_iter()
        self.buffer.insert(end, text + "\n")

    # ---------------- CHECK ----------------
    def on_check(self, widget):
        self.store.clear()
        self.status.set_text("Checking updates...")
        self.check_btn.set_sensitive(False)

        def worker():
            updates = []

            subprocess.run(["pkexec", "apt", "update"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # -------- APT --------
            result = subprocess.run(
                ["apt", "list", "--upgradable"],
                capture_output=True,
                text=True
            )

            for line in result.stdout.splitlines()[1:]:
                if "/" in line:
                    parts = line.split()
                    pkg = parts[0].split("/")[0]
                    new_ver = parts[1]
                    old_ver = parts[-1].strip("[]")

                    priority = "normal"
                    if "security" in line:
                        priority = "security"
                    if "linux-image" in pkg or "linux-headers" in pkg:
                        priority = "kernel"

                    updates.append(("APT", pkg, f"{old_ver} → {new_ver}", priority))

            # -------- SNAP --------
            if command_exists("snap"):
                result = subprocess.run(
                    ["snap", "refresh", "--list"],
                    capture_output=True,
                    text=True
                )

                for line in result.stdout.splitlines():
                    if line.strip() and not line.startswith("Name"):
                        parts = line.split()
                        pkg = parts[0]
                        ver = f"{parts[1]} → {parts[2]}"
                        updates.append(("Snap", pkg, ver, "normal"))

            # -------- FLATPAK --------
            if command_exists("flatpak"):
                result = subprocess.run(
                    ["flatpak", "remote-ls", "--updates"],
                    capture_output=True,
                    text=True
                )

                for line in result.stdout.splitlines():
                    if line.strip():
                        pkg = line.split()[0]
                        updates.append(("Flatpak", pkg, "-", "normal"))

            GLib.idle_add(self.show_updates, updates)

        threading.Thread(target=worker).start()

    def show_updates(self, updates):
        self.updates = updates

        for system, pkg, version, priority in updates:
            self.store.append([False, "❌", system, pkg, version, priority])

        self.status.set_text(f"{len(updates)} updates available")
        self.check_btn.set_sensitive(True)
        self.update_all_btn.set_sensitive(True)

    # ---------------- UPDATE ----------------
    def on_update_all(self, widget):
        self.run_updates(self.updates)

    def run_updates(self, updates):
        def worker():
            total = len(updates)
            done = 0

            apt_pkgs = [p[1] for p in updates if p[0] == "APT"]
            snap_pkgs = [p[1] for p in updates if p[0] == "Snap"]
            flat_pkgs = [p[1] for p in updates if p[0] == "Flatpak"]

            if apt_pkgs:
                subprocess.run(["pkexec", "apt", "upgrade", "-y"])
                if any("linux" in p for p in apt_pkgs):
                    subprocess.run(["pkexec", "apt", "full-upgrade", "-y"])
                done += len(apt_pkgs)
                GLib.idle_add(self.package_progress.set_fraction, done / total)

            if snap_pkgs:
                subprocess.run(["pkexec", "snap", "refresh"] + snap_pkgs)
                done += len(snap_pkgs)
                GLib.idle_add(self.package_progress.set_fraction, done / total)

            for pkg in flat_pkgs:
                subprocess.run(["flatpak", "update", "-y", pkg])
                done += 1
                GLib.idle_add(self.package_progress.set_fraction, done / total)

            if os.path.exists("/var/run/reboot-required"):
                GLib.idle_add(self.log_msg, "⚠ Reboot required!")

            GLib.idle_add(self.finish)

        threading.Thread(target=worker).start()

    def finish(self):
        self.status.set_text("Finished")
        self.package_label.set_text("Done")

    def on_toggle_row(self, widget, path):
        self.store[path][0] = not self.store[path][0]


if __name__ == "__main__":
    win = Updater()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

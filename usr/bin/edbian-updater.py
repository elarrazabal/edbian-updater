#!/usr/bin/env python3
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GdkPixbuf

import subprocess
import threading
import os


ICON_PATH = "/usr/share/edbian-updater/icon_update.jpg"

class Updater(Gtk.Window):
   

    def __init__(self):
        super().__init__(title="Edbian Updater PRO")
        self.set_default_size(1100, 800)

        self.current_process = None
        self.log_file = "/tmp/edbian-updater.log"

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(vbox)

        # ================= STATUS CENTRADO =================
        status_box = Gtk.Box(spacing=6)
        status_box.set_halign(Gtk.Align.CENTER)
        vbox.pack_start(status_box, False, False, 0)

        self.status = Gtk.Label(label="Listo")
        self.spinner = Gtk.Spinner()

        status_box.pack_start(self.status, False, False, 0)
        status_box.pack_start(self.spinner, False, False, 0)

        # ================= BOTONES =================
        btn_box = Gtk.Box(spacing=6)
        vbox.pack_start(btn_box, False, False, 0)

        self.check_btn = Gtk.Button(label="Buscar actualizaciones")
        self.check_btn.connect("clicked", self.on_check)
        btn_box.pack_start(self.check_btn, True, True, 0)

        self.install_selected_btn = Gtk.Button(label="Instalar seleccionados")
        self.install_selected_btn.set_sensitive(False)
        self.install_selected_btn.connect("clicked", self.on_install_selected)
        btn_box.pack_start(self.install_selected_btn, True, True, 0)

        self.install_all_btn = Gtk.Button(label="Instalar TODO")
        self.install_all_btn.set_sensitive(False)
        self.install_all_btn.connect("clicked", self.on_install_all)
        btn_box.pack_start(self.install_all_btn, True, True, 0)

        # ================= TOGGLES =================
        toggle_box = Gtk.Box(spacing=10)
        vbox.pack_start(toggle_box, False, False, 0)

        self.t_all = Gtk.CheckButton(label="Todos")
        self.t_apt = Gtk.CheckButton(label="APT")
        self.t_flatpak = Gtk.CheckButton(label="Flatpak")
        self.t_snap = Gtk.CheckButton(label="Snap")

        for t in [self.t_all, self.t_apt, self.t_flatpak, self.t_snap]:
            t.connect("toggled", self.on_toggle_group)
            t.set_sensitive(False)
            toggle_box.pack_start(t, False, False, 0)

        # ================= LISTA =================
        self.store = Gtk.ListStore(bool, str, str, str, str)

        tree = Gtk.TreeView(model=self.store)

        toggle = Gtk.CellRendererToggle()
        toggle.connect("toggled", self.on_row_toggle)
        tree.append_column(Gtk.TreeViewColumn("✔", toggle, active=0))

        cols = ["Tipo", "Paquete", "Versión", "Origen"]
        for i, col in enumerate(cols):
            r = Gtk.CellRendererText()
            tree.append_column(Gtk.TreeViewColumn(col, r, text=i+1))

        scroll = Gtk.ScrolledWindow()
        scroll.add(tree)
        vbox.pack_start(scroll, True, True, 0)

        # ================= BOTONES INFERIORES RESTAURADOS =================
        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(bottom, False, False, 0)

        left_box = Gtk.Box()
        center_box = Gtk.Box()
        right_box = Gtk.Box()

        bottom.pack_start(left_box, True, True, 0)
        bottom.pack_start(center_box, False, False, 0)
        bottom.pack_end(right_box, True, True, 0)

        self.cancel_btn = Gtk.Button(label="Cancelar instalación")
        self.cancel_btn.set_sensitive(False)
        self.cancel_btn.connect("clicked", self.on_cancel)

        self.open_log_btn = Gtk.Button(label="Ver log")
        self.open_log_btn.set_sensitive(False)
        self.open_log_btn.connect("clicked", self.on_open_log)

        self.close_btn = Gtk.Button(label="Cerrar")
        self.close_btn.connect("clicked", self.on_close)

        left_box.pack_start(self.cancel_btn, False, False, 0)
        center_box.pack_start(self.open_log_btn, False, False, 0)
        right_box.pack_end(self.close_btn, False, False, 0)
        
        #========= Icono de la ventana
        self.set_window_icon()
        
    # =============== ICONO EN VENTANA ==========
    def set_window_icon(self):
        if os.path.exists(ICON_PATH):
            try:
                icon = GdkPixbuf.Pixbuf.new_from_file(ICON_PATH)
                self.set_icon(icon)
            except Exception:
                pass

    # ================= UI =================
    def set_busy(self, state):
        self.check_btn.set_sensitive(not state)
        self.install_selected_btn.set_sensitive(not state)
        self.install_all_btn.set_sensitive(not state)

        if state:
            self.spinner.start()
        else:
            self.spinner.stop()

    def set_status(self, text):
        GLib.idle_add(self.status.set_text, text)

    # ================= TOGGLES =================
    def on_toggle_group(self, widget):
        state = widget.get_active()

        for r in self.store:
            if widget == self.t_all:
                r[0] = state
            elif widget == self.t_apt and r[4] == "APT":
                r[0] = state
            elif widget == self.t_flatpak and r[4] == "Flatpak":
                r[0] = state
            elif widget == self.t_snap and r[4] == "Snap":
                r[0] = state

        self.update_buttons()

    def on_row_toggle(self, widget, path):
        self.store[path][0] = not self.store[path][0]
        self.update_buttons()

    def update_buttons(self):
        any_selected = any(r[0] for r in self.store)
        self.install_selected_btn.set_sensitive(any_selected)

    # ================= CHECK =================
    def on_check(self, widget):
        self.store.clear()
        self.set_busy(True)
        self.set_status("Buscando actualizaciones...")

        def worker():
            updates = []

            subprocess.run(["pkexec", "apt", "update"])

            apt = subprocess.run(["apt", "list", "--upgradable"],
                                 capture_output=True, text=True)

            for l in apt.stdout.splitlines()[1:]:
                if "/" in l:
                    pkg = l.split("/")[0]
                    ver = l.split()[1]
                    updates.append(("deb", pkg, ver, "APT"))

            fp = subprocess.run(
                [
                    "flatpak", "remote-ls", "--updates",
                    "--columns=application,name,ref"
                ],
                capture_output=True,
                text=True
            )

            for l in fp.stdout.splitlines():
                parts = l.split("\t")  # separación por TAB

                if len(parts) >= 3:
                    app_id = parts[0]     # org.mozilla.firefox
                    name = parts[1]       # Firefox (nombre amigable)
                    ref = parts[2]        # org.mozilla.firefox/x86_64/stable

                    # Si por lo que sea no hay nombre, fallback al ID
                    display_name = name if name else app_id

                    updates.append(("app", display_name, ref, "Flatpak"))
        
        
        
        
            snap = subprocess.run(["snap", "refresh", "--list"],
                                  capture_output=True, text=True)

            for l in snap.stdout.splitlines()[1:]:
                parts = l.split()
                if parts:
                    updates.append(("snap", parts[0], parts[1], "Snap"))

            GLib.idle_add(self.fill, updates)

        threading.Thread(target=worker).start()

    def fill(self, updates):
        self.set_busy(False)

        for u in updates:
            self.store.append([False, *u])

        for t in [self.t_all, self.t_apt, self.t_flatpak, self.t_snap]:
            t.set_sensitive(True)

        self.install_all_btn.set_sensitive(True)

        self.set_status(f"{len(updates)} actualizaciones disponibles")

    # ================= INSTALL =================
    def on_install_selected(self, widget):
        rows = [r[:] for r in self.store if r[0]]

        if not rows:
            return

        preview = self.preview_changes(rows)

        if self.show_preview_dialog(preview):
            self.install(rows)

    def on_install_all(self, widget):
        rows = [r[:] for r in self.store]

        if not rows:
            return

        preview = self.preview_changes(rows)

        if self.show_preview_dialog(preview):
            self.install(rows)
        
        
        
        

    def install(self, rows):
        self.set_busy(True)
        self.cancel_btn.set_sensitive(True)
        self.set_status("Instalando...")

        def worker():
            apt = [r[2] for r in rows if r[4] == "APT"]
            flatpak_refs = [r[3] for r in rows if r[4] == "Flatpak"]
            snap = [r[2] for r in rows if r[4] == "Snap"]

            if apt:
                subprocess.run(["pkexec", "apt-get", "-y", "install"] + apt)

            if flatpak_refs:
                for ref in flatpak_refs:
                    subprocess.run([
                        "flatpak",
                        "install",
                        "-y",
                        "--noninteractive",
                        ref
                    ])

            if snap:
                subprocess.run(["pkexec", "snap", "refresh"] + snap)

            GLib.idle_add(self.finish_install, rows)

        threading.Thread(target=worker).start()
        
        
    def preview_changes(self, rows):
        preview_text = ""

        # ===== APT =====
        apt = [r[2] for r in rows if r[4] == "APT"]
        if apt:
            result = subprocess.run(
                ["apt-get", "-s", "install"] + apt,
                capture_output=True,
                text=True
            )
            preview_text += "=== APT ===\n"
            preview_text += result.stdout + "\n"

        # ===== FLATPAK =====
        flatpak = [r[3] for r in rows if r[4] == "Flatpak"]
        if flatpak:
            preview_text += "=== FLATPAK ===\n"
            for ref in flatpak:
                result = subprocess.run(
                    ["flatpak", "install", "--assumeno", ref],
                    capture_output=True,
                    text=True
                )
                preview_text += f"\n--- {ref} ---\n"
                preview_text += result.stdout + "\n"

        # ===== SNAP =====
        snap = [r[2] for r in rows if r[4] == "Snap"]
        if snap:
            preview_text += "=== SNAP ===\n"
            for s in snap:
                preview_text += f"{s} será actualizado\n"

        return preview_text
        
        
        
    def show_preview_dialog(self, text):
        dialog = Gtk.Dialog(
            title="Resumen de cambios",
            transient_for=self,
            flags=0
        )
        dialog.set_default_size(700, 500)

        box = dialog.get_content_area()
        box.set_vexpand(True)
        box.set_hexpand(True)
        box.set_border_width(10)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        box.add(scroll)

        textview = Gtk.TextView()
        textview.set_editable(False)
        textview.set_monospace(True)
        textview.set_vexpand(True)
        textview.set_hexpand(True)

        buffer = textview.get_buffer()
        buffer.set_text(text)

        scroll.add(textview)

        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Instalar", Gtk.ResponseType.OK)

        dialog.show_all()
        response = dialog.run()
        dialog.destroy()

        return response == Gtk.ResponseType.OK        
        
        
        

    def finish_install(self, rows):
        to_remove = set((r[2], r[4]) for r in rows)

        for row in list(self.store):
            if (row[2], row[4]) in to_remove:
                self.store.remove(row.iter)

        self.cancel_btn.set_sensitive(False)
        self.set_busy(False)
        self.set_status("Instalación completada")

    # ================= CANCEL =================
    def on_cancel(self, widget):
        if self.current_process:
            self.current_process.terminate()
        self.set_busy(False)
        self.cancel_btn.set_sensitive(False)
        self.set_status("Cancelado")

    def on_close(self, widget):
        Gtk.main_quit()

    def on_open_log(self, widget):
        subprocess.Popen(["xdg-open", self.log_file])


if __name__ == "__main__":
    win = Updater()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

#!/usr/bin/env python3
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GdkPixbuf

import subprocess
import threading
import shutil
import os

ICON_PATH = "/usr/share/edbian-updater/icon_update.jpg"


class Updater(Gtk.Window):
    def __init__(self):
        super().__init__(title="Edbian Updater PRO")
        self.set_default_size(1100, 800)
        self.log_file = "/tmp/edbian-updater.log"

        self.current_process = None
        self.is_installing = False

        self.set_window_icon()

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(vbox)

        # ================= STATUS =================
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
        self.store = Gtk.ListStore(bool, str, str, str, str, str, str, str)

        tree = Gtk.TreeView(model=self.store)

        toggle = Gtk.CellRendererToggle()
        toggle.connect("toggled", self.on_row_toggle)
        tree.append_column(Gtk.TreeViewColumn("✔", toggle, active=0))

        cols = ["Tipo", "Paquete", "Versión", "Tamaño", "Origen"]

        for i, col in enumerate(cols):
            r = Gtk.CellRendererText()
            tree.append_column(Gtk.TreeViewColumn(col, r, text=i+1))

        scroll = Gtk.ScrolledWindow()
        scroll.add(tree)
        vbox.pack_start(scroll, True, True, 0)

        # ================= LOG =================
#        self.log_buffer = Gtk.TextBuffer()
#        self.tag_green = self.log_buffer.create_tag("green", foreground="#00FF00")

#        self.log_view = Gtk.TextView(buffer=self.log_buffer)
#        self.log_view.set_editable(False)
#        self.log_view.set_monospace(True)

#        log_scroll = Gtk.ScrolledWindow()
#        log_scroll.set_size_request(-1, 200)
#        log_scroll.add(self.log_view)

#        vbox.pack_start(log_scroll, False, True, 0)

        # ================= BOTONES INFERIORES =================
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
        
#        self.open_log_btn = Gtk.Button(label="Ver log")
#        self.open_log_btn.set_sensitive(False)
#        self.open_log_btn.connect("clicked", self.on_open_log)

        self.close_btn = Gtk.Button(label="Cerrar")
        self.close_btn.connect("clicked", self.on_close)

        left_box.pack_start(self.cancel_btn, False, False, 0)

#        center_box.pack_start(self.open_log_btn, False, False, 0)

        right_box.pack_end(self.close_btn, False, False, 0)

    # ================= ICONO =================
    def set_window_icon(self):
        if os.path.exists(ICON_PATH):
            try:
                self.set_icon(GdkPixbuf.Pixbuf.new_from_file(ICON_PATH))
            except:
                pass
    # ================= ESCRITURA DE LOG ==================
    def write_log(self, text):
        with open(self.log_file, "a") as f:
            f.write(text)

        if os.path.getsize(self.log_file) > 0:
            GLib.idle_add(self.open_log_btn.set_sensitive, True)
    
    
    # ================= LOG FIX RESTAURADO =================
#    def append_log(self, text):
#        def _append():
#            end = self.log_buffer.get_end_iter()
#            self.log_buffer.insert_with_tags(end, text, self.tag_green)
#            self.log_view.scroll_to_iter(self.log_buffer.get_end_iter(), 0, False, 0, 0)

#        GLib.idle_add(_append)

    # ================= TOGGLE =================
    def on_toggle_group(self, widget):
        state = widget.get_active()

        for r in self.store:
            if widget == self.t_all:
                r[0] = state
            elif widget == self.t_apt and r[5] == "APT":
                r[0] = state
            elif widget == self.t_flatpak and r[5] == "Flatpak":
                r[0] = state
            elif widget == self.t_snap and r[5] == "Snap":
                r[0] = state

        self.install_selected_btn.set_sensitive(any(r[0] for r in self.store))

    # ================= ROW =================
    def on_row_toggle(self, widget, path):
        self.store[path][0] = not self.store[path][0]
        self.install_selected_btn.set_sensitive(any(r[0] for r in self.store))

    # ================= CHECK =================
    def on_check(self, widget):
        self.store.clear()
        self.set_busy(True)
        self.set_status("Buscando actualizaciones...")

        def worker():
            subprocess.run(["pkexec", "bash", "-c", "apt update"])

            apt = subprocess.run(["apt", "list", "--upgradable"], capture_output=True, text=True)

            updates = []

            for l in apt.stdout.splitlines()[1:]:
                if "/" not in l:
                    continue

                parts = l.split()
                pkg = parts[0].split("/")[0]
                version = parts[1]

                updates.append(("APT", pkg, version, "-", "APT", "normal", ""))

            GLib.idle_add(self.fill, updates)

        threading.Thread(target=worker).start()

    # ================= FILL =================
    def fill(self, updates):
        self.set_busy(False)

        if not updates:
            self.set_status("Sistema actualizado")
            self.show_dialog("✔ Todas las aplicaciones están al día", True)
            return

        self.set_status(f"{len(updates)} actualizaciones disponibles")

        for u in updates:
            self.store.append([False, *u])

        self.install_all_btn.set_sensitive(True)
        self.close_btn.set_sensitive(True)

    # ================= INSTALL =================
    def on_install_selected(self, widget):
        self.install([r[:] for r in self.store if r[0]])

    def on_install_all(self, widget):
        rows = [r[:] for r in self.store]
        for r in self.store:
            r[0] = True
        self.install(rows)

    def install(self, rows):
        self.set_busy(True)
        self.cancel_btn.set_sensitive(True)
        self.set_status("Instalando...")

        def worker():
            apt = [r[2] for r in rows if r[5] == "APT"]

            if apt:
                self.run_cmd(["pkexec", "bash", "-c", "apt-get -y install " + " ".join(apt)])

            GLib.idle_add(self.finish, rows, True)

        threading.Thread(target=worker).start()

    # ================= CANCEL =================
    def on_cancel(self, widget):
        if self.current_process:
            self.current_process.terminate()
            self.current_process.kill()
            self.current_process = None

        self.set_busy(False)
        self.cancel_btn.set_sensitive(False)
        self.set_status("Cancelado")

        self.show_dialog("✖ Instalación cancelada", False)

    # ================= CLOSE =================
    def on_close(self, widget):
        Gtk.main_quit()

    # ================= ABRE LOG =================
    def on_open_log(self, widget):
        subprocess.Popen(["xdg-open", self.log_file])


    # ================= FIN =================
    def finish(self, rows, success):
        self.set_busy(False)
        self.cancel_btn.set_sensitive(False)

        if success:
            self.set_status("Finalizado")
            self.show_dialog("✔ Instalación completada correctamente", True)

    # ================= PROCESS =================
    def run_cmd(self, cmd):
        # Si viene con pkexec ya incluido, lo dejamos
        if cmd[0] == "pkexec":
            final_cmd = cmd
        else:
            final_cmd = cmd

        self.current_process = subprocess.Popen(
            final_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        self.write_log(line)
        
        def reader(process):
#            for line in iter(process.stdout.readline, ''):
#                GLib.idle_add(self.append_log, line)

            process.stdout.close()
            process.wait()

        threading.Thread(
            target=reader,
            args=(self.current_process,),
            daemon=True
        ).start()

    # ================= DIALOG =================
    def show_dialog(self, text, success=True):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.INFO if success else Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=text,
        )

        dialog.set_default_size(420, 140)

        dialog.run()
        dialog.destroy()

    # ================= UI =================
    def set_busy(self, state):
        self.check_btn.set_sensitive(not state)
        self.install_selected_btn.set_sensitive(not state)
        self.install_all_btn.set_sensitive(not state)
        self.close_btn.set_sensitive(not state)

        if state:
            self.spinner.start()
        else:
            self.spinner.stop()

    def set_status(self, text):
        GLib.idle_add(self.status.set_text, text)


if __name__ == "__main__":
    win = Updater()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

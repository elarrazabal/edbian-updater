#!/usr/bin/env python3
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GdkPixbuf

import subprocess
import threading
import os
import shutil


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
        
        
        # ================= LOG EN TIEMPO REAL =================

        log_frame = Gtk.Frame(label="Log de instalación")

        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_size_request(-1, 220)

        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_monospace(True)

        self.log_buffer = self.log_view.get_buffer()

        log_scroll.add(self.log_view)
        log_frame.add(log_scroll)

        vbox.pack_start(log_frame, False, True, 0)
        
        

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
            self.append_log("Lanzando worker....\n")
            try:
                updates = []
			
                has_flatpak = shutil.which("flatpak") is not None
                has_snap = shutil.which("snap") is not None
		
                self.append_log("Ejecutando apt update...\n")
                subprocess.run(["pkexec", "apt", "update"])

                apt = subprocess.run(["apt", "list", "--upgradable"],
                                 capture_output=True, text=True)

                for l in apt.stdout.splitlines()[1:]:
                    if "/" in l:
                        pkg = l.split("/")[0]
                        ver = l.split()[1]
                        updates.append(("deb", pkg, ver, "APT"))
                
                self.append_log("APT Update finalizado...\n")

                # ===== FLATPAK =====
                if has_flatpak:

                    self.append_log("Buscando actualizaciones Flatpak...\n")

                    fp = subprocess.run(
                        ["flatpak", "remote-ls", "--updates"],
                        capture_output=True,
                        text=True
                    )

                    self.append_log(fp.stdout + "\n")

                    lines = fp.stdout.splitlines()
                    
                    ####### Eliminar
                    
                    #self.append_log(f"LINES={repr(lines)}\n")
                    #####

                    # Saltar cabecera
                    ##### Descomentar
                    #for line in lines[1:]:
                    
                    ###### Eliminar
                    for line in lines:
                    #    if "ID de aplicación" in line:
                    #        continue

                    #   if "Application ID" in line:
                    #        continue
                    #####
                    
                        ##### Eliminar
                        #self.append_log(f"LINEA RAW: [{line}]\n")
                        ####

                        line = line.strip()

                        if not line:
                            ##### Eliminar
                            #self.append_log("VACIA\n")
                            #####
                            continue

                        parts = line.split()
                        
                        ##### Eliminar
                        #self.append_log(
                        #    f"PARTS={parts} LEN={len(parts)}\n"
                        #)
                        #####

                        if len(parts) < 2:
                            ##### Eliminar
                            #self.append_log("DESCARTADA\n")
                            ####
                            continue

                        nombre = parts[0]
                        appid = parts[1]

                        #version = "-"
                        
                        #### Eliminar y descomentar suprerior
                        version = parts[2] if len(parts) >= 3 else "-"

                        #self.append_log(
                        #    f"AÑADIENDO {nombre} {version}\n"
                        #)
                        ####

                        ###### Descomentar
                        #if len(parts) >= 3:
                        #    version = parts[2]
                        #######
                        
                        updates.append(
                            (
                                "app",
                                nombre,
                                version,
                                "Flatpak"
                            )
                        )

                self.append_log("Flatpak finalizado\n")
                    
        
                # ===== SNAP =====
                if has_snap:
                    
                    self.append_log("Ejecutando SNAP...\n")

                    snap = subprocess.run(
                        ["snap", "refresh", "--list"],
                        capture_output=True,
                        text=True
                    )

                    for l in snap.stdout.splitlines()[1:]:
                        parts = l.split()

                        if parts:
                            updates.append(
                                ("snap", parts[0], parts[1], "Snap")
                            )
                            
                
                
                ##### Eliminar este bloque
                
                #self.append_log(
                #    f"\nTOTAL UPDATES: {len(updates)}\n"
                #)

                #for u in updates:
                #    self.append_log(f"{u}\n")
                ###########
                

                GLib.idle_add(self.fill, updates)

            
                
                self.append_log("Finalizado SNAP...\n")
                
            except Exception as e:
                import traceback

                traceback.print_exc()
                error = traceback.format_exc()
                
                self.append_log(error)

                GLib.idle_add(
                    self.set_status,
                    f"Error: {e}"
                )
                
                GLib.idle_add(
                    self.set_status,
                    "Error durante la búsqueda"
                )
        
        threading.Thread(target=worker).start()
                

    def fill(self, updates):
        self.set_busy(False)
        
        ###### Eliminar bloque
        
        #print("FILL RECIBE:")
        #print(updates)
        
        ########

        for u in updates:
            ###### Eliminar
            #print("AÑADIENDO:", u)
            #######
            self.store.append([False, *u])
        
        #### Eliminar linea
        
        #print("FILAS:", len(self.store))
        
        ####

        self.t_all.set_sensitive(True)
        self.t_apt.set_sensitive(True)

        self.t_flatpak.set_sensitive(
            shutil.which("flatpak") is not None
        )

        self.t_snap.set_sensitive(
            shutil.which("snap") is not None
        )

        self.install_all_btn.set_sensitive(True)

        self.set_status(f"{len(updates)} actualizaciones disponibles")
        
        
        
        
    # ================= LOG =================

    def append_log(self, text):

        def update():

            end_iter = self.log_buffer.get_end_iter()

            self.log_buffer.insert(end_iter, text)

            mark = self.log_buffer.create_mark(
                None,
                self.log_buffer.get_end_iter(),
                False
            )

            self.log_view.scroll_mark_onscreen(mark)

            return False

        GLib.idle_add(update)


    def run_command_live(self, cmd):

        self.current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            universal_newlines=True,
            bufsize=1
        )

        with open(self.log_file, "a") as logfile:

            while True:

                line = self.current_process.stdout.readline()

                if not line and self.current_process.poll() is not None:
                    break

                if line:

                    logfile.write(line)
                    logfile.flush()

                    self.append_log(line)

        return self.current_process.wait()    
        
        
        
        

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
        self.open_log_btn.set_sensitive(True)

        self.set_status("Instalando...")

        self.log_buffer.set_text("")

        open(self.log_file, "w").close()

        def worker():

            apt = [r[2] for r in rows if r[4] == "APT"]

            flatpak_updates = any(
                r[4] == "Flatpak"
                for r in rows
            )

            snap = [r[2] for r in rows if r[4] == "Snap"]

            # ---------------- APT ----------------

            if apt:

                self.append_log(
                    "\n================ APT ================\n"
                )

                self.run_command_live(
                    [
                        "pkexec",
                        "apt-get",
                        "-y",
                        "install"
                    ] + apt
                )

            # ---------------- FLATPAK ----------------
            has_flatpak = shutil.which("flatpak") is not None
            if flatpak_updates and has_flatpak:

                self.append_log(
                    "\n============== FLATPAK ==============\n"
                )

                #
                # CORRECCIÓN:
                # Para actualizar aplicaciones Flatpak
                # NO se usa install.
                #

                self.run_command_live(
                    [
                        "pkexec",
                        "flatpak",
                        "update",
                        "-y"
                    ]
                )

            # ---------------- SNAP ----------------
            has_snap = shutil.which("snap") is not None
            if snap and has_snap:

                self.append_log(
                    "\n=============== SNAP ================\n"
                )

                self.run_command_live(
                    [
                        "pkexec",
                        "snap",
                        "refresh"
                    ] + snap
                )

            GLib.idle_add(self.finish_install, rows)

        threading.Thread(
            target=worker,
            daemon=True
        ).start()
        
        
    def preview_changes(self, rows):
        preview_text = ""

        has_flatpak = shutil.which("flatpak") is not None
        has_snap = shutil.which("snap") is not None

        apt_preview = ""
        flatpak_preview = ""
        snap_preview = ""

        # ================= APT =================
        apt = [r[2] for r in rows if r[4] == "APT"]

        if apt:
            result = subprocess.run(
                ["apt-get", "-s", "install"] + apt,
                capture_output=True,
                text=True
            )

            apt_preview += "=== APT ===\n"
            apt_preview += result.stdout + "\n"

        # ================= FLATPAK =================
        flatpak = [r for r in rows if r[4] == "Flatpak"]

        if flatpak and has_flatpak:
            flatpak_preview += "=== FLATPAK ===\n"
            flatpak_preview += (
                f"{len(flatpak)} aplicaciones Flatpak serán actualizadas\n\n"
            )

            # opcional: listado real de updates
            result = subprocess.run(
                ["flatpak", "remote-ls", "--updates"],
                capture_output=True,
                text=True
            )

            if result.stdout.strip():
                flatpak_preview += result.stdout + "\n"

        # ================= SNAP =================
        snap = [r[2] for r in rows if r[4] == "Snap"]

        if snap and has_snap:
            snap_preview += "=== SNAP ===\n"

            for s in snap:
                snap_preview += f"{s} será actualizado\n"

        # ================= OUTPUT FINAL =================
        preview_text += apt_preview
        preview_text += flatpak_preview
        preview_text += snap_preview

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

#!/usr/bin/env python3

import sys
import shutil
import subprocess
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QLabel,
    QProgressBar, QTableWidget, QTableWidgetItem, QTextEdit,
    QSystemTrayIcon, QMenu, QAction, QCheckBox, QDialog
)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QIcon, QColor, QFont

# ------------------------
# ICONO FIJO PARA .deb
# ------------------------
ICON_PATH = "/usr/share/edbian-updater/icon_update.jpg"

# ------------------------
# FUNCIONES AUX
# ------------------------
def command_exists(cmd):
    return shutil.which(cmd) is not None

# ------------------------
# THREAD CHECK UPDATES
# ------------------------
class CheckUpdates(QThread):
    result = pyqtSignal(list)
    def run(self):
        updates = []
        if command_exists("apt-get"):
            result = subprocess.run(
                ["apt-get", "-s", "upgrade"],
                capture_output=True,
                text=True
            )
            for line in result.stdout.splitlines():
                if line.startswith("Inst"):
                    pkg = line.split()[1]
                    if "security" in line.lower():
                        updates.append(("APT", pkg, "security"))
                    else:
                        updates.append(("APT", pkg, "normal"))
        if command_exists("flatpak"):
            result = subprocess.run(
                ["flatpak", "remote-ls", "--updates"],
                capture_output=True,
                text=True
            )
            for line in result.stdout.splitlines():
                if line.strip():
                    pkg = line.split("\t")[0]
                    updates.append(("Flatpak", pkg, "normal"))
        if command_exists("snap"):
            result = subprocess.run(
                ["snap", "refresh", "--list"],
                capture_output=True,
                text=True
            )
            for line in result.stdout.splitlines()[1:]:
                if line.strip():
                    pkg = line.split()[0]
                    updates.append(("Snap", pkg, "normal"))
        self.result.emit(updates)

# ------------------------
# THREAD UPDATE
# ------------------------
class UpdateWorker(QThread):
    log = pyqtSignal(str)
    progress = pyqtSignal(int)
    update_status = pyqtSignal(int)
    finished = pyqtSignal()
    def __init__(self, updates):
        super().__init__()
        self.updates = updates
    def run(self):
        total = len(self.updates)
        if total == 0:
            self.finished.emit()
            return
        for i, (system, pkg, typ) in enumerate(self.updates):
            self.log.emit(f"Updating {system}: {pkg}...\n")
            if system == "APT":
                subprocess.run(["pkexec", "apt-get", "install", "-y", pkg])
            elif system == "Flatpak":
                subprocess.run(["flatpak", "update", "-y", pkg])
            elif system == "Snap":
                subprocess.run(["pkexec", "snap", "refresh", pkg])
            percent = int(((i + 1) / total) * 100)
            self.progress.emit(percent)
            self.update_status.emit(i)
        self.finished.emit()

# ------------------------
# VENTANA MODAL SISTEMA ACTUALIZADO
# ------------------------
class UpToDateDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("System status")
        self.setWindowIcon(QIcon(ICON_PATH))  # Icono modal
        layout = QVBoxLayout()
        icon = QLabel("✔")
        icon.setAlignment(Qt.AlignCenter)
        icon_font = QFont()
        icon_font.setPointSize(40)
        icon.setFont(icon_font)
        text = QLabel("System is up to date")
        text.setAlignment(Qt.AlignCenter)
        text_font = QFont()
        text_font.setPointSize(16)
        text.setFont(text_font)
        layout.addWidget(icon)
        layout.addWidget(text)
        self.setLayout(layout)
        self.resize(300, 150)

# ------------------------
# VENTANA PRINCIPAL
# ------------------------
class Updater(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Edbian Updater")
        self.setWindowIcon(QIcon(ICON_PATH))  # Icono principal
        self.resize(900, 650)
        layout = QVBoxLayout()

        self.status = QLabel("Check updates")
        self.check_btn = QPushButton("Check updates")
        self.check_btn.clicked.connect(self.check_updates)

        self.update_btn = QPushButton("Update all")
        self.update_btn.setEnabled(False)  # deshabilitado por defecto
        self.update_btn.clicked.connect(self.update_all)

        self.progress = QProgressBar()
        self.progress.setVisible(False)

        self.auto_check = QCheckBox("Automatic check (30 min)")

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Status", "Type", "Package", "Priority"])

        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)

        legend = QLabel("❌ Pending | ✔ Updated | 🔐 Security | 📦 APT | 🧊 Flatpak | ⚡ Snap")

        layout.addWidget(self.status)
        layout.addWidget(self.check_btn)
        layout.addWidget(self.update_btn)
        layout.addWidget(self.auto_check)
        layout.addWidget(self.progress)
        layout.addWidget(self.table)
        layout.addWidget(QLabel("Log"))
        layout.addWidget(self.log_widget)
        layout.addWidget(legend)
        self.setLayout(layout)

        self.init_tray()

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_updates)
        self.auto_check.stateChanged.connect(self.toggle_auto)

    def init_tray(self):
        self.tray_ok = QIcon(ICON_PATH)
        self.tray_updates = QIcon(ICON_PATH)
        self.tray_security = QIcon(ICON_PATH)
        self.tray = QSystemTrayIcon(self.tray_ok)
        menu = QMenu()
        open_action = QAction("Open")
        quit_action = QAction("Quit")
        open_action.triggered.connect(self.show)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(open_action)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.show()

    # -------------------------
    # CHECK UPDATES
    # -------------------------
    def check_updates(self):
        self.table.setRowCount(0)
        self.status.setText("Scanning updates...")
        self.update_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0,0)  # spinner indeterminado

        self.log_widget.clear()
        self.checker = CheckUpdates()
        self.checker.result.connect(self.show_updates)
        self.checker.start()

    def show_updates(self, updates):
        self.progress.setVisible(False)
        self.updates = updates
        self.table.setRowCount(len(updates))
        security_found = False

        for row, (system, pkg, typ) in enumerate(updates):
            status = QTableWidgetItem("❌")
            status.setBackground(QColor(255,200,200))
            icon = "📦" if system=="APT" else "🧊" if system=="Flatpak" else "⚡"
            self.table.setItem(row,0,status)
            self.table.setItem(row,1,QTableWidgetItem(f"{icon} {system}"))
            self.table.setItem(row,2,QTableWidgetItem(pkg))
            if typ=="security":
                item = QTableWidgetItem("🔐 security")
                item.setBackground(QColor(255,180,180))
                security_found = True
            else:
                item = QTableWidgetItem("normal")
            self.table.setItem(row,3,item)

        # Activar botón solo si hay actualizaciones
        self.update_btn.setEnabled(len(updates) > 0)

        count = len(updates)
        if count==0:
            dialog = UpToDateDialog()
            dialog.exec_()
            self.status.setText("System up to date")
            self.tray.setIcon(self.tray_ok)
        else:
            self.status.setText(f"{count} updates available")
            self.tray.setIcon(self.tray_security if security_found else self.tray_updates)

    # -------------------------
    # UPDATE ALL
    # -------------------------
    def update_all(self):
        if not self.updates or len(self.updates)==0:
            return

        self.progress.setVisible(True)
        self.progress.setRange(0,100)
        self.progress.setValue(0)
        self.log_widget.clear()

        self.worker = UpdateWorker(self.updates)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.update_status.connect(self.mark_updated)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self.finish_update)
        self.worker.start()

    def mark_updated(self,row):
        item = QTableWidgetItem("✔")
        item.setBackground(QColor(200,255,200))
        self.table.setItem(row,0,item)

    def append_log(self,text):
        self.log_widget.append(text)

    def finish_update(self):
        self.status.setText("Update finished")
        self.tray.setIcon(self.tray_ok)
        self.progress.setVisible(False)
        self.update_btn.setEnabled(False)

    def toggle_auto(self):
        if self.auto_check.isChecked(): self.timer.start(1800000)
        else: self.timer.stop()

# ------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = Updater()
    window.show()
    sys.exit(app.exec_())

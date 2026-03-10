#!/usr/bin/env python3
import sys, os, subprocess, shutil
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout,
    QLabel, QProgressBar, QTableWidget, QTableWidgetItem,
    QSystemTrayIcon, QMenu, QAction, QCheckBox
)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, QSettings
from PyQt5.QtGui import QIcon

CONFIG_FILE = os.path.expanduser("~/.config/edbian-updater.ini")

def command_exists(cmd):
    return shutil.which(cmd) is not None

class CheckUpdates(QThread):
    result = pyqtSignal(list)
    def run(self):
        updates = []
        # APT
        if command_exists("apt"):
            res = subprocess.run(["apt","list","--upgradable"], capture_output=True, text=True)
            lines = res.stdout.splitlines()[1:]
            for line in lines:
                pkg = line.split("/")[0]
                updates.append(("APT", pkg))
        # Flatpak
        if command_exists("flatpak"):
            res = subprocess.run(["flatpak","remote-ls","--updates"], capture_output=True, text=True)
            lines = res.stdout.splitlines()
            for line in lines:
                pkg = line.split("\t")[0]
                updates.append(("Flatpak", pkg))
        # Snap
        if command_exists("snap"):
            res = subprocess.run(["snap","refresh","--list"], capture_output=True, text=True)
            lines = res.stdout.splitlines()[1:]
            for line in lines:
                pkg = line.split()[0]
                updates.append(("Snap", pkg))
        self.result.emit(updates)

class UpdateWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    def run(self):
        commands=[]
        if command_exists("apt"):
            commands += [["pkexec","apt","update"], ["pkexec","apt","upgrade","-y"]]
        if command_exists("flatpak"):
            commands.append(["flatpak","update","-y"])
        if command_exists("snap"):
            commands.append(["pkexec","snap","refresh"])
        total=len(commands)
        for i, cmd in enumerate(commands):
            subprocess.run(cmd)
            self.progress.emit(int((i+1)/total*100))
        self.finished.emit()

class Updater(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Edbian Updater")
        self.resize(700,500)
        layout = QVBoxLayout()
        self.status=QLabel("Pulsa 'Buscar actualizaciones'")
        self.check_btn=QPushButton("Buscar actualizaciones")
        self.check_btn.clicked.connect(self.check_updates)
        self.update_btn=QPushButton("Actualizar todo")
        self.update_btn.clicked.connect(self.update_all)
        self.progress=QProgressBar()
        self.table=QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Sistema","Paquete"])
        self.auto_check_box=QCheckBox("Comprobación automática cada 30 min")
        self.auto_check_box.stateChanged.connect(self.toggle_auto_check)
        layout.addWidget(self.status)
        layout.addWidget(self.check_btn)
        layout.addWidget(self.update_btn)
        layout.addWidget(self.auto_check_box)
        layout.addWidget(self.progress)
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.init_tray()
        self.auto_timer=QTimer()
        self.auto_timer.timeout.connect(self.check_updates)
        self.settings = QSettings(CONFIG_FILE, QSettings.IniFormat)
        auto_enabled = self.settings.value("auto_check", False, type=bool)
        self.auto_check_box.setChecked(auto_enabled)

    def init_tray(self):
        self.icon_ok = QIcon.fromTheme("emblem-default")
        self.icon_updates = QIcon.fromTheme("software-update-available")
        self.tray = QSystemTrayIcon(self.icon_ok)
        menu = QMenu()
        open_action = QAction("Abrir")
        quit_action = QAction("Salir")
        open_action.triggered.connect(self.show)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(open_action)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def check_updates(self):
        self.status.setText("Buscando actualizaciones...")
        self.checker=CheckUpdates()
        self.checker.result.connect(self.show_updates)
        self.checker.start()

    def show_updates(self, updates):
        self.table.setRowCount(len(updates))
        for row, (system,pkg) in enumerate(updates):
            self.table.setItem(row,0,QTableWidgetItem(system))
            self.table.setItem(row,1,QTableWidgetItem(pkg))
        total = len(updates)
        if total==0:
            self.status.setText("Sistema actualizado")
            self.tray.setIcon(self.icon_ok)
        else:
            self.status.setText(f"{total} actualizaciones disponibles")
            self.tray.setIcon(self.icon_updates)
            self.tray.showMessage("Actualizaciones disponibles",f"{total} paquetes para actualizar",QSystemTrayIcon.Information,4000)

    def update_all(self):
        self.progress.setValue(0)
        self.worker=UpdateWorker()
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self.finish_update)
        self.worker.start()

    def finish_update(self):
        self.status.setText("Actualización finalizada")
        self.progress.setValue(100)
        self.tray.setIcon(self.icon_ok)
        if self.auto_check_box.isChecked():
            self.check_updates()

    def toggle_auto_check(self, state):
        enabled = state==2
        if enabled:
            self.auto_timer.start(60*60*1000)
            self.status.setText("Comprobación automática activada")
        else:
            self.auto_timer.stop()
            self.status.setText("Comprobación automática desactivada")
        self.settings.setValue("auto_check", enabled)

app=QApplication(sys.argv)
window=Updater()
window.show()
sys.exit(app.exec_())

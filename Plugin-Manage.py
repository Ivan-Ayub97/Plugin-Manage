import json
import os
import shutil
import sys
from datetime import datetime

from PyQt5.QtCore import QSize, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPalette
from PyQt5.QtWidgets import (QApplication, QFileDialog, QGroupBox, QHBoxLayout,
                             QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QMessageBox, QProgressBar, QPushButton, QTextEdit,
                             QVBoxLayout, QWidget)


class BackupThread(QThread):
    update_progress = pyqtSignal(int)
    log_message = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, vst_paths, backup_dir):
        super().__init__()
        self.vst_paths = vst_paths
        self.backup_dir = backup_dir
        self.total_files = 0
        self.copied_files = 0
        self.cancelled = False
        self.index_path = os.path.join(self.backup_dir, "backup_index.json")

    def run(self):
        vst_extensions = ('.dll', '.vst3')
        index_data = self.load_index()

        # Calcular total de archivos
        for path in self.vst_paths:
            if os.path.exists(path):
                for _, _, files in os.walk(path):
                    self.total_files += len([f for f in files if f.endswith(vst_extensions)])

        if self.total_files == 0:
            self.log_message.emit("⚠️ No VST plugins found.")
            self.finished.emit()
            return

        # Copiar plugins
        for path in self.vst_paths:
            if self.cancelled:
                break
            for root, _, files in os.walk(path):
                for file in files:
                    if self.cancelled:
                        break
                    if file.endswith(vst_extensions):
                        src = os.path.join(root, file)
                        arch = "32_bit" if "Program Files (x86)" in root else "64_bit"
                        vst_type = "VST3" if file.endswith(".vst3") else "VST2"
                        vendor = os.path.basename(os.path.normpath(root))
                        target_dir = os.path.join(self.backup_dir, vst_type, arch, vendor)
                        os.makedirs(target_dir, exist_ok=True)
                        dst = os.path.join(target_dir, file)

                        plugin_key = f"{file}_{vst_type}_{arch}_{vendor}"
                        if os.path.exists(dst):
                            self.log_message.emit(f"🔁 Exists: {file}")
                        else:
                            try:
                                shutil.copy2(src, dst)
                                self.copied_files += 1
                                self.log_message.emit(f"✅ Copied: {file}")
                                index_data[plugin_key] = {
                                    "name": file,
                                    "type": vst_type,
                                    "arch": arch,
                                    "vendor": vendor,
                                    "original_path": src,
                                    "backup_path": dst,
                                    "backup_date": datetime.now().isoformat()
                                }
                            except Exception as e:
                                self.log_message.emit(f"❌ Error copying {file}: {e}")

                        progress = int((self.copied_files / self.total_files) * 100)
                        self.update_progress.emit(progress)

        self.save_index(index_data)
        self.update_progress.emit(100)
        self.finished.emit()

    def cancel(self):
        self.cancelled = True

    def load_index(self):
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_index(self, index_data):
        try:
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump(index_data, f, indent=4)
        except Exception as e:
            self.log_message.emit(f"⚠️ Index save error: {e}")


class PluginManage(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Plugin-Manage 1.0.0")
        self.setWindowIcon(QIcon("icon.ico"))
        self.setGeometry(100, 100, 900, 750)
        self.apply_dark_theme()

        self.default_paths = list(dict.fromkeys([
            r"C:\Program Files (x86)\Audio Plugins",
            r"C:\Program Files\Audio Plugins",
            r"C:\Program Files (x86)\VSTPlugins",
            r"C:\Program Files\VSTPlugins",
            r"C:\Program Files\Steinberg\VSTPlugins",
            r"C:\Program Files (x86)\Steinberg\VSTPlugins",
            r"C:\Program Files\Common Files\VST3",
            r"C:\Program Files (x86)\Common Files\VST3"
        ]))
        self.vst_paths = self.default_paths.copy()
        self.backup_directory = None
        self.index_data = {}

        self.init_ui()

    def apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(20, 20, 20))
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(50, 50, 50))
        palette.setColor(QPalette.ButtonText, QColor(255, 215, 0))
        palette.setColor(QPalette.Highlight, QColor(255, 215, 0))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        self.setPalette(palette)
        self.setStyleSheet("""
            QPushButton {
                background-color: #282828;
                border: 1px solid #555;
                padding: 6px;
                border-radius: 5px;
                color: #FFD700;
            }
            QPushButton:hover {
                background-color: #444444;
            }
            QGroupBox {
                border: 1px solid #666;
                border-radius: 6px;
                margin-top: 10px;
                padding: 10px;
                color: #FFD700;
            }
            QLabel, QLineEdit {
                color: white;
            }
            QTextEdit, QListWidget {
                background-color: #1e1e1e;
                color: white;
                border: 1px solid #555;
            }
            QProgressBar {
                text-align: center;
                color: white;
                border: 1px solid #444;
                background-color: #222;
            }
            QProgressBar::chunk {
                background-color: #FFD700;
            }
        """)

    def init_ui(self):
        layout = QVBoxLayout()

        # VST paths
        layout.addWidget(self.create_path_group())

        # Backup
        layout.addWidget(self.create_backup_group())

        # Plugins y acciones
        layout.addWidget(self.create_plugin_group())

        # Log
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.setLayout(layout)

    def create_path_group(self):
        group = QGroupBox("🎚️ VST Paths")
        vbox = QVBoxLayout()
        self.label_paths = QLabel("\n".join(self.vst_paths))
        vbox.addWidget(self.label_paths)

        btn_add = QPushButton("Add Path")
        btn_add.clicked.connect(self.add_vst_path)
        btn_remove = QPushButton("Remove Last")
        btn_remove.clicked.connect(self.remove_last_path)
        hbox = QHBoxLayout()
        hbox.addWidget(btn_add)
        hbox.addWidget(btn_remove)
        vbox.addLayout(hbox)

        group.setLayout(vbox)
        return group

    def create_backup_group(self):
        group = QGroupBox("📦 Backup")
        vbox = QVBoxLayout()

        self.btn_select_backup = QPushButton("Select Backup Folder")
        self.btn_select_backup.clicked.connect(self.select_backup_directory)
        vbox.addWidget(self.btn_select_backup)

        self.btn_start = QPushButton("Start Backup")
        self.btn_start.clicked.connect(self.start_backup)
        self.btn_start.setEnabled(False)
        vbox.addWidget(self.btn_start)

        self.btn_cancel = QPushButton("Cancel Backup")
        self.btn_cancel.clicked.connect(self.cancel_backup)
        self.btn_cancel.setEnabled(False)
        vbox.addWidget(self.btn_cancel)

        self.progress = QProgressBar()
        vbox.addWidget(self.progress)

        group.setLayout(vbox)
        return group

    def create_plugin_group(self):
        group = QGroupBox("🎛 Plugins Backed Up")
        vbox = QVBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search plugin by name...")
        self.search_input.textChanged.connect(self.filter_plugins)
        vbox.addWidget(self.search_input)

        self.list_plugins = QListWidget()
        vbox.addWidget(self.list_plugins)

        btn_restore = QPushButton("Restore Selected")
        btn_restore.clicked.connect(self.restore_selected)
        btn_export = QPushButton("Export Plugin Index")
        btn_export.clicked.connect(self.export_index)
        hbox = QHBoxLayout()
        hbox.addWidget(btn_restore)
        hbox.addWidget(btn_export)
        vbox.addLayout(hbox)

        group.setLayout(vbox)
        return group

    def add_vst_path(self):
        path = QFileDialog.getExistingDirectory(self, "Add VST Path")
        if path and path not in self.vst_paths:
            self.vst_paths.append(path)
            self.label_paths.setText("\n".join(self.vst_paths))
            self.log_output.append(f"➕ Added: {path}")
        elif path:
            self.log_output.append(f"⚠️ Already exists: {path}")

    def remove_last_path(self):
        if len(self.vst_paths) > len(self.default_paths):
            removed = self.vst_paths.pop()
            self.label_paths.setText("\n".join(self.vst_paths))
            self.log_output.append(f"➖ Removed: {removed}")
        else:
            QMessageBox.information(self, "Notice", "Default paths can't be removed.")

    def select_backup_directory(self):
        path = QFileDialog.getExistingDirectory(self, "Select Backup Folder")
        if path:
            self.backup_directory = path
            self.btn_start.setEnabled(True)
            self.load_index()
            self.log_output.append(f"📁 Backup folder set: {path}")

    def start_backup(self):
        if not self.backup_directory:
            QMessageBox.warning(self, "Warning", "Please select a backup folder.")
            return

        self.progress.setValue(0)
        self.log_output.clear()
        self.list_plugins.clear()
        self.backup_thread = BackupThread(self.vst_paths, self.backup_directory)
        self.backup_thread.update_progress.connect(self.progress.setValue)
        self.backup_thread.log_message.connect(self.log_output.append)
        self.backup_thread.finished.connect(self.on_backup_finished)
        self.backup_thread.start()

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)

    def cancel_backup(self):
        if hasattr(self, "backup_thread"):
            self.backup_thread.cancel()
            self.log_output.append("❌ Backup cancelled.")
            self.btn_cancel.setEnabled(False)
            self.btn_start.setEnabled(True)

    def on_backup_finished(self):
        self.log_output.append("✅ Backup completed.")
        self.btn_cancel.setEnabled(False)
        self.btn_start.setEnabled(True)
        self.load_index()

    def load_index(self):
        if not self.backup_directory:
            return
        index_path = os.path.join(self.backup_directory, "backup_index.json")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                self.index_data = json.load(f)
            self.update_plugin_list()

    def update_plugin_list(self):
        self.list_plugins.clear()
        for plugin in self.index_data.values():
            item = QListWidgetItem(f"{plugin['name']} | {plugin['vendor']} | {plugin['arch']}")
            item.setData(Qt.UserRole, plugin)
            self.list_plugins.addItem(item)

    def filter_plugins(self, text):
        self.list_plugins.clear()
        for plugin in self.index_data.values():
            if text.lower() in plugin['name'].lower():
                item = QListWidgetItem(f"{plugin['name']} | {plugin['vendor']} | {plugin['arch']}")
                item.setData(Qt.UserRole, plugin)
                self.list_plugins.addItem(item)

    def restore_selected(self):
        selected = self.list_plugins.currentItem()
        if selected:
            plugin = selected.data(Qt.UserRole)
            dest = QFileDialog.getExistingDirectory(self, "Select destination for restoration")
            if dest:
                try:
                    shutil.copy2(plugin["backup_path"], os.path.join(dest, plugin["name"]))
                    self.log_output.append(f"🔁 Restored: {plugin['name']}")
                except Exception as e:
                    self.log_output.append(f"❌ Error restoring: {e}")
        else:
            QMessageBox.information(self, "No selection", "Please select a plugin from the list.")

    def export_index(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Plugin Index", "plugin_index.json", "JSON Files (*.json)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.index_data, f, indent=4)
                self.log_output.append(f"📤 Index exported: {path}")
            except Exception as e:
                self.log_output.append(f"❌ Export error: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PluginManage()
    window.show()
    sys.exit(app.exec_())

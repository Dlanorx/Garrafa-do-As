import sys
import os
import json
import subprocess
import shutil
import glob
import re
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QDialog,
    QLineEdit, QComboBox, QFileDialog, QMessageBox, QGroupBox,
    QTextEdit, QSplitter, QFrame, QScrollArea, QStackedWidget,
    QCheckBox, QSpinBox, QTabWidget, QGridLayout
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer
from PySide6.QtGui import QFont, QPixmap, QIcon, QColor, QPalette, QImage

# ── Constants ──────────────────────────────────────────────────────────────────

APP_NAME = "Garrafa do AS"
DATA_DIR = Path.home() / ".local/share/garrafa-as"
BOTTLES_FILE = DATA_DIR / "bottles.json"
ICON_PATH = DATA_DIR / "icon.png"

COLORS = {
    "bg":       "#0f0f17",
    "panel":    "#17172a",
    "card":     "#1e1e35",
    "accent":   "#c94040",
    "accent2":  "#e8734a",
    "text":     "#e8e8f0",
    "subtext":  "#8888aa",
    "border":   "#2a2a45",
    "green":    "#4caf50",
    "yellow":   "#f0a500",
}

# ── Data helpers ───────────────────────────────────────────────────────────────

def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def load_bottles():
    if BOTTLES_FILE.exists():
        try:
            return json.loads(BOTTLES_FILE.read_text())
        except Exception:
            pass
    return {}

def save_bottles(data):
    ensure_data_dir()
    BOTTLES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

# ── Runner detection ───────────────────────────────────────────────────────────

def find_proton_versions():
    home = Path.home()
    paths = [
        home / ".steam/steam/steamapps/common",
        home / ".local/share/Steam/steamapps/common",
        home / ".var/app/com.valvesoftware.Steam/data/Steam/steamapps/common",
    ]
    found = []
    for p in paths:
        if p.is_dir():
            for d in sorted(p.iterdir(), reverse=True):
                exe = d / "proton"
                if exe.exists() and "Proton" in d.name:
                    found.append({"name": d.name, "path": str(exe)})
    return found

def find_wine():
    w = shutil.which("wine")
    if w:
        try:
            ver = subprocess.check_output(["wine", "--version"],
                                          stderr=subprocess.DEVNULL, text=True).strip()
        except Exception:
            ver = "wine"
        return [{"name": ver, "path": w}]
    return []

def get_all_runners():
    runners = find_proton_versions() + find_wine()
    if not runners:
        runners = [{"name": "Nenhum runner encontrado", "path": ""}]
    return runners

# ── Launch thread ──────────────────────────────────────────────────────────────

class LaunchThread(QThread):
    log_line = Signal(str)
    finished = Signal(int)

    def __init__(self, cmd, env):
        super().__init__()
        self.cmd = cmd
        self.env = env

    def run(self):
        try:
            proc = subprocess.Popen(
                self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, env=self.env
            )
            for line in proc.stdout:
                self.log_line.emit(line.rstrip())
            proc.wait()
            self.finished.emit(proc.returncode)
        except Exception as e:
            self.log_line.emit(f"Erro: {e}")
            self.finished.emit(-1)

# ── Add Game Dialog ────────────────────────────────────────────────────────────

class AddGameDialog(QDialog):
    def __init__(self, parent, runners, bottle_name, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Adicionar Jogo" if not existing else "Editar Jogo")
        self.setMinimumWidth(500)
        self.runners = runners
        self.result_data = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Name
        layout.addWidget(QLabel("Nome do jogo:"))
        self.name_edit = QLineEdit(existing.get("name", "") if existing else "")
        layout.addWidget(self.name_edit)

        # Executable
        layout.addWidget(QLabel("Executável (.exe):"))
        exe_row = QHBoxLayout()
        self.exe_edit = QLineEdit(existing.get("exe", "") if existing else "")
        self.exe_edit.setPlaceholderText("Caminho para o .exe")
        exe_row.addWidget(self.exe_edit)
        browse = QPushButton("…")
        browse.setFixedWidth(36)
        browse.clicked.connect(self._browse_exe)
        exe_row.addWidget(browse)
        layout.addLayout(exe_row)

        # Runner
        layout.addWidget(QLabel("Runner (Proton/Wine):"))
        self.runner_combo = QComboBox()
        for r in runners:
            self.runner_combo.addItem(r["name"], r["path"])
        if existing and existing.get("runner"):
            idx = self.runner_combo.findData(existing["runner"])
            if idx >= 0:
                self.runner_combo.setCurrentIndex(idx)
        layout.addWidget(self.runner_combo)

        # Prefix
        layout.addWidget(QLabel("Prefixo Wine (pasta):"))
        pfx_row = QHBoxLayout()
        default_pfx = str(DATA_DIR / "prefixes" / bottle_name /
                          (existing.get("name", "novo").replace(" ", "_") if existing else "novo"))
        self.pfx_edit = QLineEdit(existing.get("prefix", default_pfx) if existing else default_pfx)
        pfx_row.addWidget(self.pfx_edit)
        pfx_browse = QPushButton("…")
        pfx_browse.setFixedWidth(36)
        pfx_browse.clicked.connect(self._browse_pfx)
        pfx_row.addWidget(pfx_browse)
        layout.addLayout(pfx_row)

        # Extra args
        layout.addWidget(QLabel("Argumentos extras (opcional):"))
        self.args_edit = QLineEdit(existing.get("args", "") if existing else "")
        self.args_edit.setPlaceholderText("ex: -windowed -novid")
        layout.addWidget(self.args_edit)

        # DXVK
        self.dxvk_cb = QCheckBox("Ativar DXVK (melhor performance DirectX)")
        self.dxvk_cb.setChecked(existing.get("dxvk", True) if existing else True)
        layout.addWidget(self.dxvk_cb)

        # Esync
        self.esync_cb = QCheckBox("Ativar Esync")
        self.esync_cb.setChecked(existing.get("esync", True) if existing else True)
        layout.addWidget(self.esync_cb)

        # Buttons
        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        ok = QPushButton("Salvar")
        ok.setStyleSheet(f"background:{COLORS['accent']}; color:white; font-weight:bold; padding:6px 20px; border-radius:4px;")
        ok.clicked.connect(self._save)
        btn_row.addWidget(ok)
        layout.addLayout(btn_row)

    def _browse_exe(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar .exe",
                                               filter="Executáveis (*.exe *.EXE);;Todos (*)")
        if path:
            self.exe_edit.setText(path)
            if not self.name_edit.text():
                self.name_edit.setText(Path(path).stem)
            # auto prefix
            if not self.pfx_edit.text() or "novo" in self.pfx_edit.text():
                name = Path(path).stem.replace(" ", "_")
                self.pfx_edit.setText(str(DATA_DIR / "prefixes" / name))

    def _browse_pfx(self):
        path = QFileDialog.getExistingDirectory(self, "Selecionar pasta do prefixo")
        if path:
            self.pfx_edit.setText(path)

    def _save(self):
        name = self.name_edit.text().strip()
        exe = self.exe_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Atenção", "Nome é obrigatório.")
            return
        if not exe:
            QMessageBox.warning(self, "Atenção", "Selecione o executável.")
            return
        self.result_data = {
            "name": name,
            "exe": exe,
            "runner": self.runner_combo.currentData(),
            "runner_name": self.runner_combo.currentText(),
            "prefix": self.pfx_edit.text().strip(),
            "args": self.args_edit.text().strip(),
            "dxvk": self.dxvk_cb.isChecked(),
            "esync": self.esync_cb.isChecked(),
        }
        self.accept()

# ── Bottle Panel ───────────────────────────────────────────────────────────────

class BottlePanel(QWidget):
    def __init__(self, bottle_name, parent_app):
        super().__init__()
        self.bottle_name = bottle_name
        self.parent_app = parent_app
        self.launch_thread = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel(f"🍶  {self.bottle_name}")
        title.setStyleSheet(f"font-size:20px; font-weight:bold; color:{COLORS['text']};")
        header.addWidget(title)
        header.addStretch()

        add_btn = QPushButton("+ Adicionar Jogo")
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background:{COLORS['accent']}; color:white;
                font-weight:bold; border-radius:6px; padding:8px 16px;
            }}
            QPushButton:hover {{ background:{COLORS['accent2']}; }}
        """)
        add_btn.clicked.connect(self._add_game)
        header.addWidget(add_btn)
        layout.addLayout(header)

        # Games list
        self.games_layout = QVBoxLayout()
        self.games_layout.setSpacing(8)
        scroll_widget = QWidget()
        scroll_widget.setLayout(self.games_layout)
        scroll = QScrollArea()
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        layout.addWidget(scroll)

        # Log
        log_group = QGroupBox("Log de execução")
        log_group.setStyleSheet(f"QGroupBox {{ color:{COLORS['subtext']}; border:1px solid {COLORS['border']}; border-radius:6px; margin-top:6px; padding-top:6px; }}")
        lg = QVBoxLayout(log_group)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        self.log.setFont(QFont("Monospace", 9))
        self.log.setStyleSheet(f"background:{COLORS['bg']}; color:#76ff76; border:none;")
        lg.addWidget(self.log)
        layout.addWidget(log_group)

        self._refresh_games()

    def _refresh_games(self):
        # Clear
        while self.games_layout.count():
            item = self.games_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        bottles = load_bottles()
        games = bottles.get(self.bottle_name, {}).get("games", [])

        if not games:
            empty = QLabel("Nenhum jogo adicionado ainda.\nClique em '+ Adicionar Jogo' para começar.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color:{COLORS['subtext']}; font-size:14px; padding:40px;")
            self.games_layout.addWidget(empty)
            return

        for i, game in enumerate(games):
            card = self._make_game_card(game, i)
            self.games_layout.addWidget(card)

        self.games_layout.addStretch()

    def _make_game_card(self, game, index):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background:{COLORS['card']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
            }}
        """)
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 10, 12, 10)

        # Icon placeholder
        icon_lbl = QLabel("🎮")
        icon_lbl.setFixedSize(40, 40)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(f"font-size:24px; background:{COLORS['panel']}; border-radius:6px;")
        row.addWidget(icon_lbl)

        # Info
        info = QVBoxLayout()
        name_lbl = QLabel(game["name"])
        name_lbl.setStyleSheet(f"font-weight:bold; font-size:14px; color:{COLORS['text']};")
        info.addWidget(name_lbl)

        runner_lbl = QLabel(f"Runner: {game.get('runner_name', 'Desconhecido')}  •  "
                            f"DXVK: {'✓' if game.get('dxvk') else '✗'}  •  "
                            f"Esync: {'✓' if game.get('esync') else '✗'}")
        runner_lbl.setStyleSheet(f"color:{COLORS['subtext']}; font-size:11px;")
        info.addWidget(runner_lbl)
        row.addLayout(info)
        row.addStretch()

        # Buttons
        play_btn = QPushButton("▶  Jogar")
        play_btn.setStyleSheet(f"""
            QPushButton {{
                background:{COLORS['green']}; color:white;
                font-weight:bold; border-radius:5px; padding:7px 18px;
            }}
            QPushButton:hover {{ background:#66bb6a; }}
            QPushButton:disabled {{ background:#444; color:#888; }}
        """)
        play_btn.clicked.connect(lambda _, g=game: self._launch_game(g, play_btn))
        row.addWidget(play_btn)

        edit_btn = QPushButton("✎")
        edit_btn.setFixedWidth(36)
        edit_btn.setToolTip("Editar")
        edit_btn.setStyleSheet(f"background:{COLORS['panel']}; color:{COLORS['text']}; border-radius:5px; padding:7px;")
        edit_btn.clicked.connect(lambda _, i=index: self._edit_game(i))
        row.addWidget(edit_btn)

        del_btn = QPushButton("✕")
        del_btn.setFixedWidth(36)
        del_btn.setToolTip("Remover")
        del_btn.setStyleSheet(f"background:{COLORS['panel']}; color:{COLORS['accent']}; border-radius:5px; padding:7px;")
        del_btn.clicked.connect(lambda _, i=index: self._delete_game(i))
        row.addWidget(del_btn)

        return card

    def _add_game(self):
        runners = get_all_runners()
        dlg = AddGameDialog(self, runners, self.bottle_name)
        if dlg.exec() and dlg.result_data:
            bottles = load_bottles()
            bottles.setdefault(self.bottle_name, {}).setdefault("games", [])
            bottles[self.bottle_name]["games"].append(dlg.result_data)
            save_bottles(bottles)
            self._refresh_games()

    def _edit_game(self, index):
        bottles = load_bottles()
        games = bottles.get(self.bottle_name, {}).get("games", [])
        if index >= len(games):
            return
        runners = get_all_runners()
        dlg = AddGameDialog(self, runners, self.bottle_name, existing=games[index])
        if dlg.exec() and dlg.result_data:
            games[index] = dlg.result_data
            bottles[self.bottle_name]["games"] = games
            save_bottles(bottles)
            self._refresh_games()

    def _delete_game(self, index):
        bottles = load_bottles()
        games = bottles.get(self.bottle_name, {}).get("games", [])
        if index >= len(games):
            return
        name = games[index]["name"]
        reply = QMessageBox.question(self, "Remover", f"Remover '{name}'?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            games.pop(index)
            bottles[self.bottle_name]["games"] = games
            save_bottles(bottles)
            self._refresh_games()

    def _launch_game(self, game, btn):
        exe = game.get("exe", "")
        runner = game.get("runner", "")
        prefix = game.get("prefix", "")

        if not os.path.isfile(exe):
            QMessageBox.critical(self, "Erro", f"Executável não encontrado:\n{exe}")
            return

        # Build prefix dir
        if prefix:
            Path(prefix).mkdir(parents=True, exist_ok=True)

        # Build env
        env = os.environ.copy()
        if prefix:
            env["WINEPREFIX"] = prefix
        if game.get("dxvk"):
            env["DXVK_ASYNC"] = "1"
        if game.get("esync"):
            env["WINEESYNC"] = "1"
        env["WINEDEBUG"] = "-all"

        # Build command
        if runner and "proton" in runner.lower():
            env["STEAM_COMPAT_DATA_PATH"] = prefix or str(DATA_DIR / "compat")
            env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = str(
                Path(runner).parent.parent.parent.parent)
            cmd = [runner, "run", exe]
        elif runner:
            cmd = [runner, exe]
        else:
            cmd = ["wine", exe]

        if game.get("args"):
            cmd += game["args"].split()

        self.log.clear()
        self.log.append("$ " + " ".join(cmd))
        btn.setEnabled(False)
        btn.setText("Rodando…")

        self.launch_thread = LaunchThread(cmd, env)
        self.launch_thread.log_line.connect(self.log.append)
        self.launch_thread.finished.connect(lambda code, b=btn: self._on_done(code, b))
        self.launch_thread.start()

    def _on_done(self, code, btn):
        btn.setEnabled(True)
        btn.setText("▶  Jogar")
        self.log.append(f"\n[Encerrado — código {code}]")

# ── Main Window ────────────────────────────────────────────────────────────────

class GarrafaAS(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(900, 580)
        self._apply_theme()
        self._load_icon()
        self._build_ui()
        self._load_bottles()

    def _apply_theme(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background:{COLORS['bg']};
                color:{COLORS['text']};
                font-family: 'Segoe UI', 'Noto Sans', sans-serif;
            }}
            QGroupBox {{
                border:1px solid {COLORS['border']};
                border-radius:6px;
                margin-top:8px;
                padding-top:8px;
                color:{COLORS['subtext']};
            }}
            QLineEdit, QComboBox, QSpinBox {{
                background:{COLORS['card']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:4px;
                padding:5px;
            }}
            QScrollBar:vertical {{
                background:{COLORS['panel']};
                width:8px;
                border-radius:4px;
            }}
            QScrollBar::handle:vertical {{
                background:{COLORS['border']};
                border-radius:4px;
            }}
            QPushButton {{
                background:{COLORS['card']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:5px;
                padding:6px 12px;
            }}
            QPushButton:hover {{
                border-color:{COLORS['accent']};
            }}
            QDialog {{
                background:{COLORS['panel']};
            }}
            QCheckBox {{
                color:{COLORS['text']};
            }}
            QLabel {{
                color:{COLORS['text']};
            }}
            QMessageBox {{
                background:{COLORS['panel']};
            }}
        """)

    def _load_icon(self):
        # Procura o ícone no local instalado ou na mesma pasta do script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            "/usr/share/garrafa-as/icon.png",
            os.path.join(script_dir, "icon.png"),
        ]
        for src in candidates:
            if os.path.isfile(src):
                ensure_data_dir()
                if src != str(ICON_PATH):
                    shutil.copy(src, str(ICON_PATH))
                break
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Sidebar ──
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet(f"background:{COLORS['panel']}; border-right:1px solid {COLORS['border']};")
        sv = QVBoxLayout(sidebar)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(0)

        # Logo
        logo_widget = QWidget()
        logo_widget.setStyleSheet(f"background:{COLORS['bg']}; border-bottom:1px solid {COLORS['border']};")
        lv = QVBoxLayout(logo_widget)
        lv.setContentsMargins(12, 16, 12, 16)

        if ICON_PATH.exists():
            pix = QPixmap(str(ICON_PATH)).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            img_lbl = QLabel()
            img_lbl.setPixmap(pix)
            img_lbl.setAlignment(Qt.AlignCenter)
            lv.addWidget(img_lbl)

        app_title = QLabel(APP_NAME)
        app_title.setAlignment(Qt.AlignCenter)
        app_title.setStyleSheet(f"font-weight:bold; font-size:13px; color:{COLORS['text']}; margin-top:4px;")
        lv.addWidget(app_title)
        sv.addWidget(logo_widget)

        # Bottles label
        lbl = QLabel("  GARRAFAS")
        lbl.setStyleSheet(f"color:{COLORS['subtext']}; font-size:10px; padding:12px 12px 4px 12px; letter-spacing:2px;")
        sv.addWidget(lbl)

        # Bottle list
        self.bottle_list = QListWidget()
        self.bottle_list.setStyleSheet(f"""
            QListWidget {{
                background:transparent;
                border:none;
                color:{COLORS['text']};
            }}
            QListWidget::item {{
                padding:10px 16px;
                border-left:3px solid transparent;
            }}
            QListWidget::item:selected {{
                background:{COLORS['card']};
                border-left:3px solid {COLORS['accent']};
                color:white;
            }}
            QListWidget::item:hover {{
                background:{COLORS['card']};
            }}
        """)
        self.bottle_list.currentRowChanged.connect(self._switch_bottle)
        sv.addWidget(self.bottle_list)

        # Add bottle button
        add_bottle_btn = QPushButton("+ Nova Garrafa")
        add_bottle_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent;
                color:{COLORS['accent']};
                border:1px solid {COLORS['accent']};
                border-radius:6px;
                padding:8px;
                margin:8px;
                font-weight:bold;
            }}
            QPushButton:hover {{ background:{COLORS['accent']}; color:white; }}
        """)
        add_bottle_btn.clicked.connect(self._add_bottle)
        sv.addWidget(add_bottle_btn)

        del_bottle_btn = QPushButton("✕ Remover Garrafa")
        del_bottle_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent;
                color:{COLORS['subtext']};
                border:none;
                padding:4px;
                margin:0px 8px 8px 8px;
                font-size:11px;
            }}
            QPushButton:hover {{ color:{COLORS['accent']}; }}
        """)
        del_bottle_btn.clicked.connect(self._delete_bottle)
        sv.addWidget(del_bottle_btn)

        root.addWidget(sidebar)

        # ── Content area ──
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background:{COLORS['bg']};")

        # Empty state
        empty = QLabel("← Selecione ou crie uma Garrafa")
        empty.setAlignment(Qt.AlignCenter)
        empty.setStyleSheet(f"color:{COLORS['subtext']}; font-size:16px;")
        self.stack.addWidget(empty)

        root.addWidget(self.stack)

    def _load_bottles(self):
        bottles = load_bottles()
        self.bottle_list.clear()
        # Remove old bottle panels from stack (keep index 0 = empty state)
        while self.stack.count() > 1:
            w = self.stack.widget(1)
            self.stack.removeWidget(w)
            w.deleteLater()

        for name in bottles:
            self.bottle_list.addItem(QListWidgetItem(f"🍶  {name}"))
            panel = BottlePanel(name, self)
            self.stack.addWidget(panel)

        if self.bottle_list.count() > 0:
            self.bottle_list.setCurrentRow(0)

    def _switch_bottle(self, row):
        # row -1 = nothing selected
        self.stack.setCurrentIndex(row + 1)

    def _add_bottle(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Nova Garrafa")
        dlg.setMinimumWidth(320)
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Nome da garrafa:"))
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("ex: Jogos Windows, RPGs, etc.")
        v.addWidget(name_edit)
        row = QHBoxLayout()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(dlg.reject)
        row.addWidget(cancel)
        ok = QPushButton("Criar")
        ok.setStyleSheet(f"background:{COLORS['accent']}; color:white; font-weight:bold; padding:6px 20px; border-radius:4px;")
        ok.clicked.connect(dlg.accept)
        row.addWidget(ok)
        v.addLayout(row)

        if dlg.exec():
            name = name_edit.text().strip()
            if not name:
                return
            bottles = load_bottles()
            if name in bottles:
                QMessageBox.warning(self, "Atenção", "Já existe uma garrafa com esse nome.")
                return
            bottles[name] = {"games": []}
            save_bottles(bottles)
            self._load_bottles()
            # Select the new bottle
            for i in range(self.bottle_list.count()):
                if name in self.bottle_list.item(i).text():
                    self.bottle_list.setCurrentRow(i)
                    break

    def _delete_bottle(self):
        row = self.bottle_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Atenção", "Selecione uma garrafa primeiro.")
            return
        bottles = load_bottles()
        names = list(bottles.keys())
        if row >= len(names):
            return
        name = names[row]
        reply = QMessageBox.question(self, "Remover",
                                     f"Remover a garrafa '{name}' e todos os seus jogos?\n"
                                     "(Os arquivos do prefixo não serão deletados)",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            del bottles[name]
            save_bottles(bottles)
            self._load_bottles()


if __name__ == "__main__":
    ensure_data_dir()
    app = QApplication(sys.argv)
    win = GarrafaAS()
    win.show()
    sys.exit(app.exec())

import sys
import os
import json
import subprocess
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QDialog,
    QLineEdit, QComboBox, QFileDialog, QMessageBox, QGroupBox,
    QTextEdit, QFrame, QScrollArea, QStackedWidget, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QPixmap, QIcon

APP_NAME = "Garrafa do AS"
DATA_DIR = Path.home() / ".local/share/garrafa-as"
BOTTLES_FILE = DATA_DIR / "bottles.json"
ICON_PATH = DATA_DIR / "icon.png"
STYLE_PATH = Path("/usr/share/garrafa-as/style.qss")


def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_stylesheet():
    candidates = [
        Path("/usr/share/garrafa-as/style.qss"),
        Path(__file__).parent / "style.qss",
    ]
    for p in candidates:
        if p.exists():
            return p.read_text()
    return ""


def load_bottles():
    if not BOTTLES_FILE.exists():
        return {}
    try:
        return json.loads(BOTTLES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Aviso: não foi possível ler {BOTTLES_FILE}: {e}")
        return {}


def save_bottles(data):
    ensure_data_dir()
    try:
        BOTTLES_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except OSError as e:
        print(f"Erro ao salvar dados: {e}")


def find_proton_versions():
    home = Path.home()
    search_paths = [
        home / ".steam/steam/steamapps/common",
        home / ".local/share/Steam/steamapps/common",
        home / ".var/app/com.valvesoftware.Steam/data/Steam/steamapps/common",
    ]
    found = []
    seen = set()
    for base in search_paths:
        if not base.is_dir():
            continue
        for entry in sorted(base.iterdir(), reverse=True):
            exe = entry / "proton"
            if exe.exists() and "Proton" in entry.name and str(exe) not in seen:
                found.append({"name": entry.name, "path": str(exe)})
                seen.add(str(exe))
    return found


def find_wine():
    wine_path = shutil.which("wine")
    if not wine_path:
        return []
    try:
        version = subprocess.check_output(
            ["wine", "--version"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        version = "wine"
    return [{"name": version, "path": wine_path}]


def get_all_runners():
    runners = find_proton_versions() + find_wine()
    if not runners:
        return [{"name": "Nenhum runner encontrado", "path": ""}]
    return runners


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
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=self.env
            )
            for line in proc.stdout:
                self.log_line.emit(line.rstrip())
            proc.wait()
            self.finished.emit(proc.returncode)
        except FileNotFoundError:
            self.log_line.emit(f"Erro: comando não encontrado — {self.cmd[0]}")
            self.finished.emit(1)
        except OSError as e:
            self.log_line.emit(f"Erro ao iniciar processo: {e}")
            self.finished.emit(1)


class AddGameDialog(QDialog):
    def __init__(self, parent, runners, bottle_name, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Adicionar Jogo" if not existing else "Editar Jogo")
        self.setMinimumWidth(500)
        self.runners = runners
        self.bottle_name = bottle_name
        self.result_data = None
        ex = existing or {}

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Nome do jogo:"))
        self.name_edit = QLineEdit(ex.get("name", ""))
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Executável (.exe):"))
        exe_row = QHBoxLayout()
        self.exe_edit = QLineEdit(ex.get("exe", ""))
        self.exe_edit.setPlaceholderText("Caminho para o .exe")
        exe_row.addWidget(self.exe_edit)
        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(36)
        browse_btn.clicked.connect(self._browse_exe)
        exe_row.addWidget(browse_btn)
        layout.addLayout(exe_row)

        layout.addWidget(QLabel("Runner (Proton/Wine):"))
        self.runner_combo = QComboBox()
        for r in runners:
            self.runner_combo.addItem(r["name"], r["path"])
        if ex.get("runner"):
            idx = self.runner_combo.findData(ex["runner"])
            if idx >= 0:
                self.runner_combo.setCurrentIndex(idx)
        layout.addWidget(self.runner_combo)

        layout.addWidget(QLabel("Prefixo Wine:"))
        pfx_row = QHBoxLayout()
        default_prefix = str(
            DATA_DIR / "prefixes" / bottle_name /
            ex.get("name", "novo").replace(" ", "_")
        )
        self.pfx_edit = QLineEdit(ex.get("prefix", default_prefix))
        pfx_row.addWidget(self.pfx_edit)
        pfx_btn = QPushButton("…")
        pfx_btn.setFixedWidth(36)
        pfx_btn.clicked.connect(self._browse_prefix)
        pfx_row.addWidget(pfx_btn)
        layout.addLayout(pfx_row)

        layout.addWidget(QLabel("Argumentos extras (opcional):"))
        self.args_edit = QLineEdit(ex.get("args", ""))
        self.args_edit.setPlaceholderText("ex: -windowed -novid")
        layout.addWidget(self.args_edit)

        self.dxvk_cb = QCheckBox("Ativar DXVK")
        self.dxvk_cb.setChecked(ex.get("dxvk", True))
        layout.addWidget(self.dxvk_cb)

        self.esync_cb = QCheckBox("Ativar Esync")
        self.esync_cb.setChecked(ex.get("esync", True))
        layout.addWidget(self.esync_cb)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("Salvar")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _browse_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar executável",
            filter="Executáveis (*.exe *.EXE);;Todos (*)"
        )
        if not path:
            return
        self.exe_edit.setText(path)
        if not self.name_edit.text():
            self.name_edit.setText(Path(path).stem)
        if not self.pfx_edit.text() or "novo" in self.pfx_edit.text():
            name = Path(path).stem.replace(" ", "_")
            self.pfx_edit.setText(str(DATA_DIR / "prefixes" / self.bottle_name / name))

    def _browse_prefix(self):
        path = QFileDialog.getExistingDirectory(self, "Selecionar pasta do prefixo")
        if path:
            self.pfx_edit.setText(path)

    def _save(self):
        name = self.name_edit.text().strip()
        exe = self.exe_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "Atenção", "O nome do jogo é obrigatório.")
            return
        if not exe:
            QMessageBox.warning(self, "Atenção", "Selecione o executável do jogo.")
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

        header = QHBoxLayout()
        title = QLabel(f"🍶  {self.bottle_name}")
        title.setObjectName("bottleTitle")
        header.addWidget(title)
        header.addStretch()

        add_btn = QPushButton("+ Adicionar Jogo")
        add_btn.setObjectName("accentButton")
        add_btn.clicked.connect(self._add_game)
        header.addWidget(add_btn)
        layout.addLayout(header)

        self.games_layout = QVBoxLayout()
        self.games_layout.setSpacing(8)
        scroll_widget = QWidget()
        scroll_widget.setLayout(self.games_layout)
        scroll = QScrollArea()
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        scroll.setObjectName("gamesScroll")
        layout.addWidget(scroll)

        log_group = QGroupBox("Log de execução")
        lg = QVBoxLayout(log_group)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        self.log.setFont(QFont("Monospace", 9))
        self.log.setObjectName("logOutput")
        lg.addWidget(self.log)
        layout.addWidget(log_group)

        self._refresh_games()

    def _refresh_games(self):
        while self.games_layout.count():
            item = self.games_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        bottles = load_bottles()
        games = bottles.get(self.bottle_name, {}).get("games", [])

        if not games:
            empty = QLabel("Nenhum jogo adicionado ainda.\nClique em '+ Adicionar Jogo' para começar.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setObjectName("emptyLabel")
            self.games_layout.addWidget(empty)
            return

        for i, game in enumerate(games):
            self.games_layout.addWidget(self._make_game_card(game, i))

        self.games_layout.addStretch()

    def _make_game_card(self, game, index):
        card = QFrame()
        card.setObjectName("gameCard")

        row = QHBoxLayout(card)
        row.setContentsMargins(12, 10, 12, 10)

        icon_lbl = QLabel("🎮")
        icon_lbl.setFixedSize(40, 40)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setObjectName("gameIcon")
        row.addWidget(icon_lbl)

        info = QVBoxLayout()
        name_lbl = QLabel(game["name"])
        name_lbl.setObjectName("gameName")
        info.addWidget(name_lbl)

        details = f"Runner: {game.get('runner_name', 'Desconhecido')}  •  " \
                  f"DXVK: {'✓' if game.get('dxvk') else '✗'}  •  " \
                  f"Esync: {'✓' if game.get('esync') else '✗'}"
        details_lbl = QLabel(details)
        details_lbl.setObjectName("gameDetails")
        info.addWidget(details_lbl)

        row.addLayout(info)
        row.addStretch()

        play_btn = QPushButton("▶  Jogar")
        play_btn.setObjectName("playButton")
        play_btn.clicked.connect(lambda _, g=game: self._launch_game(g, play_btn))
        row.addWidget(play_btn)

        edit_btn = QPushButton("✎")
        edit_btn.setFixedWidth(36)
        edit_btn.setToolTip("Editar")
        edit_btn.clicked.connect(lambda _, i=index: self._edit_game(i))
        row.addWidget(edit_btn)

        del_btn = QPushButton("✕")
        del_btn.setFixedWidth(36)
        del_btn.setToolTip("Remover")
        del_btn.setObjectName("deleteButton")
        del_btn.clicked.connect(lambda _, i=index: self._delete_game(i))
        row.addWidget(del_btn)

        return card

    def _add_game(self):
        dlg = AddGameDialog(self, get_all_runners(), self.bottle_name)
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
        dlg = AddGameDialog(self, get_all_runners(), self.bottle_name, existing=games[index])
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
        reply = QMessageBox.question(
            self, "Remover jogo",
            f"Remover '{games[index]['name']}' da lista?",
            QMessageBox.Yes | QMessageBox.No
        )
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

        if prefix:
            Path(prefix).mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        if prefix:
            env["WINEPREFIX"] = prefix
        if game.get("dxvk"):
            env["DXVK_ASYNC"] = "1"
        if game.get("esync"):
            env["WINEESYNC"] = "1"
        env["WINEDEBUG"] = "-all"

        if runner and "proton" in runner.lower():
            env["STEAM_COMPAT_DATA_PATH"] = prefix or str(DATA_DIR / "compat")
            env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = str(
                Path(runner).parent.parent.parent.parent
            )
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

        # Muda para a pasta do executável para o Proton encontrar as DLLs
        exe_dir = os.path.dirname(os.path.abspath(exe))
        env["PWD"] = exe_dir
        os.chdir(exe_dir)

        self.launch_thread = LaunchThread(cmd, env)
        self.launch_thread.log_line.connect(self.log.append)
        self.launch_thread.finished.connect(lambda code, b=btn: self._on_done(code, b))
        self.launch_thread.start()

    def _on_done(self, code, btn):
        btn.setEnabled(True)
        btn.setText("▶  Jogar")
        self.log.append(f"\n[Processo encerrado com código {code}]")


class GarrafaAS(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(900, 580)
        self._load_icon()
        self.setStyleSheet(load_stylesheet())
        self._build_ui()
        self._load_bottles()

    def _load_icon(self):
        candidates = [
            "/usr/share/garrafa-as/icon.png",
            str(Path(__file__).parent / "icon.png"),
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

        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setObjectName("sidebar")
        sv = QVBoxLayout(sidebar)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(0)

        logo_widget = QWidget()
        logo_widget.setObjectName("logoArea")
        lv = QVBoxLayout(logo_widget)
        lv.setContentsMargins(12, 16, 12, 16)

        if ICON_PATH.exists():
            pix = QPixmap(str(ICON_PATH)).scaled(
                64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            img_lbl = QLabel()
            img_lbl.setPixmap(pix)
            img_lbl.setAlignment(Qt.AlignCenter)
            lv.addWidget(img_lbl)

        app_title = QLabel(APP_NAME)
        app_title.setAlignment(Qt.AlignCenter)
        app_title.setObjectName("appTitle")
        lv.addWidget(app_title)
        sv.addWidget(logo_widget)

        section_lbl = QLabel("  GARRAFAS")
        section_lbl.setObjectName("sectionLabel")
        sv.addWidget(section_lbl)

        self.bottle_list = QListWidget()
        self.bottle_list.setObjectName("bottleList")
        self.bottle_list.currentRowChanged.connect(self._switch_bottle)
        sv.addWidget(self.bottle_list)

        new_btn = QPushButton("+ Nova Garrafa")
        new_btn.setObjectName("newBottleButton")
        new_btn.clicked.connect(self._add_bottle)
        sv.addWidget(new_btn)

        del_btn = QPushButton("✕ Remover Garrafa")
        del_btn.setObjectName("deleteBottleButton")
        del_btn.clicked.connect(self._delete_bottle)
        sv.addWidget(del_btn)

        root.addWidget(sidebar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("contentArea")

        empty = QLabel("← Selecione ou crie uma Garrafa")
        empty.setAlignment(Qt.AlignCenter)
        empty.setObjectName("emptyState")
        self.stack.addWidget(empty)

        root.addWidget(self.stack)

    def _load_bottles(self):
        self.bottle_list.clear()
        while self.stack.count() > 1:
            w = self.stack.widget(1)
            self.stack.removeWidget(w)
            w.deleteLater()

        for name in load_bottles():
            self.bottle_list.addItem(QListWidgetItem(f"🍶  {name}"))
            self.stack.addWidget(BottlePanel(name, self))

        if self.bottle_list.count() > 0:
            self.bottle_list.setCurrentRow(0)

    def _switch_bottle(self, row):
        self.stack.setCurrentIndex(row + 1)

    def _add_bottle(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Nova Garrafa")
        dlg.setMinimumWidth(320)
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Nome da garrafa:"))
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("ex: Jogos Windows, RPGs...")
        v.addWidget(name_edit)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel)
        ok = QPushButton("Criar")
        ok.setObjectName("primaryButton")
        ok.clicked.connect(dlg.accept)
        btn_row.addWidget(ok)
        v.addLayout(btn_row)

        if not dlg.exec():
            return

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
        reply = QMessageBox.question(
            self, "Remover garrafa",
            f"Remover '{name}' e todos os seus jogos?\n"
            "Os arquivos do prefixo Wine não serão apagados.",
            QMessageBox.Yes | QMessageBox.No
        )
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

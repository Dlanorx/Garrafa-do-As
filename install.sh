#!/bin/bash
# Instalador do Garrafa do AS

set -e

echo "🍶 Instalando Garrafa do AS..."

# Detectar distro
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "$ID"
    else
        echo "unknown"
    fi
}

# Verificar e instalar dependências
install_deps() {
    DISTRO=$(detect_distro)

    if ! command -v python3 &> /dev/null; then
        echo "❌ Python3 não encontrado."
        case "$DISTRO" in
            arch|manjaro|endeavouros)
                echo "   Instale com: sudo pacman -S python" ;;
            ubuntu|debian|linuxmint|pop)
                echo "   Instale com: sudo apt install python3" ;;
            fedora)
                echo "   Instale com: sudo dnf install python3" ;;
            opensuse*)
                echo "   Instale com: sudo zypper install python3" ;;
            *)
                echo "   Instale o Python 3 pelo gerenciador de pacotes da sua distro." ;;
        esac
        exit 1
    fi

    if ! python3 -c "import PySide6" &> /dev/null; then
        echo "❌ PySide6 não encontrado."
        case "$DISTRO" in
            arch|manjaro|endeavouros)
                echo "   Instale com: sudo pacman -S pyside6" ;;
            ubuntu|debian|linuxmint|pop)
                echo "   Instale com: sudo apt install python3-pyside6.qtwidgets"
                echo "   Ou via pip:  pip install PySide6" ;;
            fedora)
                echo "   Instale com: sudo dnf install python3-pyside6"
                echo "   Ou via pip:  pip install PySide6" ;;
            *)
                echo "   Instale com: pip install PySide6" ;;
        esac
        exit 1
    fi
}

install_deps

# Instalar arquivos
echo "📦 Copiando arquivos..."
sudo mkdir -p /usr/share/garrafa-as
sudo install -Dm755 garrafa_as.py /usr/share/garrafa-as/garrafa_as.py
sudo install -Dm644 style.qss /usr/share/garrafa-as/style.qss
sudo install -Dm644 icon.png /usr/share/garrafa-as/icon.png
sudo install -Dm644 garrafa-as.desktop /usr/share/applications/garrafa-as.desktop

# Atualizar menu
if command -v kbuildsycoca6 &> /dev/null; then
    kbuildsycoca6 2>/dev/null
elif command -v update-desktop-database &> /dev/null; then
    sudo update-desktop-database /usr/share/applications
fi

echo ""
echo "✅ Garrafa do AS instalado com sucesso!"
echo "   Abra pelo menu de aplicativos ou execute:"
echo "   python3 /usr/share/garrafa-as/garrafa_as.py"

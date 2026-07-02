#!/bin/bash
# Instalador do Garrafa do AS

set -e

echo "🍶 Instalando Garrafa do AS..."

# Verificar dependências
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 não encontrado. Instale com: sudo pacman -S python"
    exit 1
fi

if ! python3 -c "import PySide6" &> /dev/null; then
    echo "❌ PySide6 não encontrado. Instale com: sudo pacman -S pyside6"
    exit 1
fi

# Instalar
sudo mkdir -p /usr/share/garrafa-as
sudo install -Dm755 garrafa_as.py /usr/share/garrafa-as/garrafa_as.py
sudo install -Dm644 icon.png /usr/share/garrafa-as/icon.png
sudo install -Dm644 garrafa-as.desktop /usr/share/applications/garrafa-as.desktop

# Atualizar menu KDE
if command -v kbuildsycoca6 &> /dev/null; then
    kbuildsycoca6 2>/dev/null
fi

echo "✅ Instalado com sucesso!"
echo "   Procure 'Garrafa do AS' no menu de aplicativos."

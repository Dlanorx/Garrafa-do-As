# Garrafa-do-As
Launcher de jogos para linux que usa o proton (steam) para rodar jogos. Ele detecta automaticamente o proton da steam e usa para executar os jogos que você adicionar para jogar no launcher. 
O que é
O Garrafa do AS é um launcher de jogos para Linux que usa o Proton (da Steam) para rodar executáveis Windows (.exe) sem precisar do Windows. Funciona de forma parecida com o Bottles e o Lutris, mas de forma mais simples.
Como funciona
O app localiza automaticamente o Proton instalado via Steam e usa ele para executar qualquer .exe. Por baixo dos panos, é o mesmo mecanismo que o Steam usa internamente — só que exposto para qualquer executável.
Requisitos
Linux (testado no Arch Linux com KDE Plasma Wayland)
Steam instalada (nativa ou Flatpak) com pelo menos um Proton instalado
Python 3
PySide6
Instalação

# 1. Instalar dependências (Arch Linux)
sudo pacman -S python pyside6

# 2. Clonar o repositório
git clone https://github.com/Dlanorx/garrafa-as
cd garrafa-as

# 3. Rodar o instalador
bash install.sh

Como usar
Abra o app pelo menu do KDE
Crie uma Garrafa (ambiente separado por categoria, ex: "RPGs", "FPS")
Dentro da garrafa, clique em + Adicionar Jogo
Selecione o .exe do jogo
O app detecta o Proton automaticamente
Clique em ▶ Jogar
Recursos
Detecta automaticamente todas as versões do Proton instaladas
Suporte a Steam nativa e Flatpak
DXVK e Esync ativados por padrão para melhor performance
Prefixo Wine separado por jogo
Tema escuro com ícone personalizado
Log de execução em tempo real
Compatibilidade de jogos
Consulte o ProtonDB para ver se seu jogo funciona bem com Proton antes de tentar.
Licença
MIT — veja o arquivo LICENSE
Autor
Dlanorx

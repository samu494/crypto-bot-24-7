import sys
import os
import subprocess


def setup():
    print("=== Installation Crypto Daily Bot ===\n")

    if sys.version_info < (3, 8):
        print("Python 3.8+ requis. Version actuelle:", sys.version)
        return

    print("1. Creation de l'environnement virtuel...")
    subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)

    venv_pip = os.path.join("venv", "Scripts", "pip.exe")
    if not os.path.exists(venv_pip):
        venv_pip = os.path.join("venv", "bin", "pip")

    print("2. Installation des dependances...")
    subprocess.run([venv_pip, "install", "-r", "requirements.txt"], check=True)

    if not os.path.exists(".env"):
        print("\n3. Creation du fichier .env...")
        with open(".env.example", "r") as f:
            content = f.read()
        with open(".env", "w") as f:
            f.write(content)
        print("   Fichier .env cree. Remplis TELEGRAM_BOT_TOKEN.")
    else:
        print("\n3. Fichier .env existant detecte.")

    print("\n=== Installation terminee ===")
    print("\nEtapes suivantes:")
    print("1. Ouvre Telegram, cherche @BotFather")
    print("2. Envoie /newbot et suis les instructions")
    print("3. Copie le token et colle-le dans .env")
    print("4. Envoie un message a ton bot")
    print("5. Lance: python get_chat_id.py (pour recuperer ton CHAT_ID)")
    print("6. Ajoute le CHAT_ID dans .env")
    print("7. Lance le bot: python bot.py")


if __name__ == "__main__":
    setup()

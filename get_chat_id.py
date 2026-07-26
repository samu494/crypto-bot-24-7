import requests
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    print("Erreur: TELEGRAM_BOT_TOKEN non defini dans .env")
    exit(1)

print("Envoie un message a ton bot sur Telegram, puis appuie Entree ici.")
input()

url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
resp = requests.get(url).json()

if not resp.get("result"):
    print("Aucune update recue. Envoie d'abord un message au bot sur Telegram.")
    exit(1)

for update in resp["result"]:
    msg = update.get("message", {})
    chat = msg.get("chat", {})
    if chat:
        print(f"Chat ID: {chat['id']}")
        print(f"Nom: {chat.get('first_name', '')} {chat.get('last_name', '')}")
        print(f"Username: @{chat.get('username', 'N/A')}")
        print("---")

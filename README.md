# LifeCity Bot

Bot Telegram avec 3 commandes basees sur des APIs externes :

- `/alldl <url>` (ou `/dl`) - Telecharge une video Facebook/TikTok/Instagram/YouTube
- `/gem <prompt>` - Genere ou edite une image avec l'IA (repondre a une photo pour l'editer)
- `/pinterest <recherche>` (ou `/pin`) - Recherche des images sur Pinterest, avec pagination

## Installation locale

```bash
pip install -r requirements.txt
export BOT_TOKEN=ton_token_telegram
python main.py
```

## Deploiement sur Render

1. Cree un nouveau "Background Worker" (pas "Web Service", ce bot n'ouvre pas de port).
2. Connecte ce repo GitHub.
3. Dans les variables d'environnement du service, ajoute :
   - `BOT_TOKEN` = ton token Telegram (recupere via @BotFather)
4. Deploie. Le build utilisera le Dockerfile fourni.

## Notes

- L'URL de l'API Pinterest (`egret-driving-cattle.ngrok-free.app`) est une URL ngrok temporaire.
  Si elle ne repond plus, remplace-la dans `handlers/pinterest.py`.
- Le token du bot n'est jamais ecrit en dur dans le code : toujours via la variable d'environnement `BOT_TOKEN`.
- 

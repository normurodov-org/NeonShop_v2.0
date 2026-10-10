FROM node:20-slim

# Python ham kerak (bot.py)
RUN apt-get update && apt-get install -y python3 python3-pip python3-venv && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Node deps
COPY package.json package-lock.json* ./
RUN npm install

# Python deps
COPY requirements.txt .
RUN python3 -m venv /app/.venv && /app/.venv/bin/pip install --no-cache-dir -r requirements.txt

# Kod va build
COPY . .

# Python sintaksisini TEKSHIRISH — Railway'dagi Python 3.11 bilan mosligini
# oldindan aniqlaydi (3.12+ xususiyatlari, masalan f-string ichida backslash,
# bu yerda build paytida xato beradi va bot ishlamaydi).
RUN /app/.venv/bin/python -c "import ast; [ast.parse(open(f, encoding='utf-8').read()) for f in ('bot.py', 'premium_emoji.py')]; print('Python syntax OK')"

RUN npm run build

ENV NODE_ENV=production
ENV PORT=3000
EXPOSE 3000

# Ikkalasi ham bir container'da: bot (Telegram polling) + Node (WebApp/API)
CMD ["bash", "-c", "/app/.venv/bin/python bot.py & exec node_modules/.bin/tsx server.ts"]

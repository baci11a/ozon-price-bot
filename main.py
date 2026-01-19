import asyncio
import aiosqlite
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Ваш TOKEN от BotFather
TOKEN = '8091992295:AAFmrr1BEO05rPmr8GPn1zgFJ6rCL0aRx_k'
bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

DB_FILE = 'prices.db'

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS watches (
                user_id INTEGER,
                product_url TEXT,
                threshold REAL,
                last_price REAL,
                PRIMARY KEY (user_id, product_url)
            )
        ''')
        await db.commit()

def get_ozon_price(url: str) -> float:
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        price_elem = soup.find('span', {'data-auto': 'product-price-current'}) or soup.select_one('[data-auto="product-price-current"]')
        if price_elem:
            price = float(price_elem.text.replace(' ₽', '').replace(' ', '').strip())
            return price
        return 0.0
    except:
        return 0.0

async def check_prices():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT user_id, product_url, threshold, last_price FROM watches') as cursor:
            rows = await cursor.fetchall()
        for row in rows:
            user_id, url, thresh, last_p = row
            curr_p = get_ozon_price(url)
            if curr_p > 0 and curr_p < thresh and (last_p == 0 or curr_p < last_p):
                await bot.send_message(user_id, f"🔔 Цена упала! {url} : {curr_p}₽ < {thresh}₽")
            await db.execute('UPDATE watches SET last_price = ? WHERE user_id = ? AND product_url = ?', (curr_p, user_id, url))
            await db.commit()
    await asyncio.sleep(1800)  # 30 мин

@dp.message(Command('start'))
async def start(msg: Message):
    await msg.reply("Привет! Отправь /add <ссылка_на_ozon> <порог_в_руб> (пример: /add https://www.ozon.ru/product/123 5000)")

@dp.message(Command('add'))
async def add(msg: Message):
    parts = msg.text.split()
    if len(parts) != 3:
        return await msg.reply("Формат: /add https://ozon.ru/product/... 5000")
    url, thresh = parts[1], float(parts[2])
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT OR REPLACE INTO watches (user_id, product_url, threshold, last_price) VALUES (?, ?, ?, 0)', (msg.from_user.id, url, thresh))
        await db.commit()
    await msg.reply(f"Добавлено: {url} порог {thresh}₽")

@dp.message(Command('list'))
async def list_watches(msg: Message):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT product_url, threshold FROM watches WHERE user_id = ?', (msg.from_user.id,)) as cursor:
            rows = await cursor.fetchall()
    if rows:
        text = '\n'.join([f"{u}: {t}₽" for u, t in rows])
        await msg.reply(f"Ваши товары:\n{text}")
    else:
        await msg.reply("Нет товаров")

async def main():
    await init_db()
    asyncio.create_task(check_prices())  # Фоновая проверка
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

import asyncio
import sqlite3
import logging
import aiohttp
import time
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import ChatJoinRequest

# --- НАСТРОЙКИ ---
TOKEN = "8650626213:AAGz1X7y6SyihDqoNNWBuDkP_7JHHjfIUYE"  
CHAT_ID = -1003704181629     

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("editors_bot.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            tt_link TEXT,
            followers TEXT,
            bio TEXT,
            avatar TEXT
        )
    """)
    conn.commit()
    conn.close()

# --- ПАРСЕР TIKTOK ---
async def get_tiktok_data(identifier: str):
    # Очистка ника от мусора
    clean_username = identifier.replace("https://www.tiktok.com/", "").replace("@", "").replace("!reg", "").strip().split("/")[0].split("?")[0]
    if not clean_username: return None

    api_url = "https://www.tikwm.com/api/user/info"
    params = {'unique_id': clean_username}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'}
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(api_url, params=params, timeout=10) as response:
                if response.status == 200:
                    res = await response.json()
                    if res.get("code") == 0:
                        data = res.get("data", {})
                        u = data.get("user", {})
                        s = data.get("stats", {})
                        return {
                            "followers": f"{s.get('followerCount', 0):,}".replace(",", " "),
                            "bio": u.get("signature", "Пусто"),
                            "avatar": u.get("avatarLarger", "https://i.pravatar.cc/150"),
                            "username": u.get("uniqueId")
                        }
    except: pass
    return None

# --- ХЕНДЛЕРЫ ---

# Регистрация через чат (!reg ник)
@dp.message(F.text.lower().startswith("!reg"))
async def cmd_reg(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("❌ Напиши команду и ник через пробел, например: ` !reg mytiktok `", parse_mode="Markdown")

    input_data = args[1]
    wait_msg = await message.answer("⏳ Ищу твой TikTok...")
    
    data = await get_tiktok_data(input_data)

    if not data:
        return await wait_msg.edit_text("❌ Аккаунт не найден. Проверь правильность написания ника.")

    conn = sqlite3.connect("editors_bot.db")
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?)",
                (message.from_user.id, message.from_user.username or message.from_user.first_name, 
                 f"https://tiktok.com/@{data['username']}", data['followers'], data['bio'], data['avatar']))
    conn.commit()
    conn.close()

    await wait_msg.edit_text(f"✅ ** Успешно! **\nПрофиль @{data['username']} привязан к твоему телеграмму.\nТеперь можно использовать ` !stats `")

# Статистика (!stats)
@dp.message(F.text.lower().startswith("!stats") | F.text.lower().startswith("!статс"))
async def show_stats(message: types.Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    
    conn = sqlite3.connect("editors_bot.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (target.id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return await message.answer(f"❌ {target.first_name} еще не привязал TikTok (команда ` !reg ник `).")

    _, tg_username, tt_link, followers, bio, avatar = row
    caption = (
        f"📊 **СТАТИСТИКА ЭДИТОРА**\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 ** Телеграмм: ** @{tg_username}\n"
        f"📈 ** Подписчики: ** {followers}\n"
        f"📝 ** BIO: ** {bio}\n\n"
        f"🔗 [Открыть профиль]({tt_link})"
    )

    try:
        await bot.send_photo(message.chat.id, photo=avatar, caption=caption, parse_mode="Markdown")
    except:
        await message.answer(caption, parse_mode="Markdown")

# Обработка заявок в чат
@dp.chat_join_request()
async def handle_join_request(update: ChatJoinRequest):
    try:
        await bot.send_message(update.from_user.id, "👋 Привет! Чтобы зайти в чат, скинь ссылку на свой TikTok.")
    except: pass

# Обработка личных сообщений (для новых участников)
@dp.message(F.chat.type == "private")
async def handle_private(message: types.Message):
    if message.text.startswith("/") or message.text.startswith("!"): return
    
    msg = await message.answer("⏳ Проверяю аккаунт...")
    data = await get_tiktok_data(message.text)

    if not data:
        return await msg.edit_text("❌ Аккаунт не найден.")

    conn = sqlite3.connect("editors_bot.db")
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?)",
                (message.from_user.id, message.from_user.username or "Editor", f"https://tiktok.com/@{data['username']}", data['followers'], data['bio'], data['avatar']))
    conn.commit()
    conn.close()

    try:
        await bot.approve_chat_join_request(CHAT_ID, message.from_user.id)
        await msg.edit_text(f"✅ Профиль @{data['username']} привязан! Заявка одобрена.")
    except:
        await msg.edit_text(f"✅ Профиль @{data['username']} привязан!")

# --- ЗАПУСК ---
async def main():
    init_db()
    print("Бот запущен и готов к работе в группе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
        except Exception as e:
            print(f"⚠️ Ошибка сети: {e}. Перезапуск через 10 сек...")
            time.sleep(10)


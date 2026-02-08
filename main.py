import asyncio
import logging
import aiohttp
import io
import re
import textwrap
from urllib.parse import urlparse, urlunparse
from PIL import Image, ImageDraw, ImageFont, ImageOps
from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
import json
import os
from datetime import datetime

BOT_TOKEN = ""
YANDEX_API_KEY = ""
YANDEX_FOLDER_ID = ""

ADMIN_USERNAME = "NovoseItsevvv"

REP_FILE = "reputation.json"
# Инициализируем единую переменную reputation_data
if os.path.exists(REP_FILE):
    with open(REP_FILE, "r") as f:
        reputation_data = json.load(f)
        # Если файл старый, конвертируем его в новый формат
        if "chats" not in reputation_data:
            reputation_data = {"chats": reputation_data, "limits": {}}
else:
    reputation_data = {"chats": {}, "limits": {}}

def save_rep():
    with open(REP_FILE, "w") as f:
        json.dump(reputation_data, f)


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
message_cache = {}

layout_map = {
    "q": "й", "w": "ц", "e": "у", "r": "к", "t": "е", "y": "н", "u": "г", "i": "ш", "o": "щ", "p": "з", "[": "х",
    "]": "ъ",
    "a": "ф", "s": "ы", "d": "в", "f": "а", "g": "п", "h": "р", "j": "о", "k": "л", "l": "д", ";": "ж", "'": "э",
    "z": "я", "x": "ч", "c": "с", "v": "м", "b": "и", "n": "т", "m": "ь",
    "Q": "Й", "W": "Ц", "E": "У", "R": "К", "T": "Е", "Y": "Н", "U": "Г", "I": "Ш", "O": "Щ", "P": "З", "{": "Х",
    "}": "Ъ",
    "A": "Ф", "S": "Ы", "D": "В", "F": "А", "G": "П", "H": "Р", "J": "О", "K": "Л", "L": "Д", ":": "Ж", "\"": "Э",
    "Z": "Я", "X": "Ч", "C": "С", "V": "М", "B": "И", "N": "Т", "M": "Ь",
    ",": "б", ".": "ю", "/": ".", "&": ","
}


def get_font(size):
    font_names = ["arial.ttf", "DejaVuSans.ttf", "FreeSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except:
            continue
    return ImageFont.load_default()


async def stt_recognize(audio_data):
    url = f"https://stt.api.cloud.yandex.net/speech/v1/stt:recognize?folderId={YANDEX_FOLDER_ID}&lang=auto"
    headers = {"Authorization": f"Api-Key {YANDEX_API_KEY}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=audio_data) as resp:
                data = await resp.json()
                return data.get("result")
    except:
        return None


async def is_gibberish(text):
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {"Authorization": f"Api-Key {YANDEX_API_KEY}"}
    payload = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite",
        "completionOptions": {"stream": False, "temperature": 0, "maxTokens": "10"},
        "messages": [
            {"role": "system",
             "text": "Если текст выглядит как абракадабра из-за забытой раскладки (например, 'ghbdtn'), ответь только словом ДА. Если это осмысленный английский текст, ответь НЕТ."},
            {"role": "user", "text": text}
        ]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                result = data['result']['alternatives'][0]['message']['text'].strip().upper()
                return "ДА" in result
    except Exception as e:
        logging.error(f"Ошибка LLM: {e}")
        return True


@dp.message(Command("cs"))
async def cmd_summarize(message: types.Message):
    # Проверяем аргументы (кол-во сообщений)
    args = message.text.split()
    count = 20  # По умолчанию 20
    if len(args) > 1 and args[1].isdigit():
        count = min(max(int(args[1]), 5), 50)  # Ограничим от 5 до 50 сообщений

    cid_str = str(message.chat.id)

    # Берем сообщения из логов, которые мы и так сохраняем в main_handler
    if cid_str not in reputation_data.get("logs", {}) or not reputation_data["logs"][cid_str]["messages"]:
        return await message.reply("∅ Пока нечего пересказывать.")

    history = reputation_data["logs"][cid_str]["messages"][-count:]
    formatted_history = "\n".join([f"{m['user']}: {m['text']}" for m in history])

    # Запрос к YandexGPT
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {"Authorization": f"Api-Key {YANDEX_API_KEY}"}
    payload = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite",
        "completionOptions": {"stream": False, "temperature": 0.5, "maxTokens": "500"},
        "messages": [
            {"role": "system",
             "text": "Ты — полезный ассистент. Сделай краткий и остроумный пересказ переписки пользователей. Выдели главное."},
            {"role": "user", "text": f"Перескажи эти сообщения:\n{formatted_history}"}
        ]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                summary = data['result']['alternatives'][0]['message']['text']
                await message.answer(f"📝 **Краткий пересказ ({len(history)} соо):**\n\n{summary}",
                                     parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Ошибка суммаризации: {e}")
        await message.answer("❌ Не удалось собрать мысли в кучу. Попробуй позже.")

@dp.message(Command("zero"))
async def cmd_zero(message: types.Message):
    if message.from_user.username != "NovoseItsevvv":
        return await message.reply("⛔ У вас нет прав на эту команду.")

    if not message.reply_to_message:
        return await message.reply("⚠️ Ответьте на сообщение пользователя, которого хотите обнулить.")

    target_id = str(message.reply_to_message.from_user.id)
    cid_str = str(message.chat.id)

    if cid_str in reputation_data["chats"] and target_id in reputation_data["chats"][cid_str]:
        reputation_data["chats"][cid_str][target_id] = 0
        save_rep()
        try:
            await bot.set_chat_administrator_custom_title(message.chat.id, int(target_id), "Репа: 0")
        except:
            pass
        await message.answer(f"✅ Репутация {message.reply_to_message.from_user.first_name} обнулена.")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.chat.type == 'private':
        welcome_text = (
            f"👋 Привет, {message.from_user.first_name}!\n\n"
            "Я - ModerDuck - многофункциональный бот. Вот что я умею:\n"
            "• 🎤 Расшифровываю голосовые сообщения\n"
            "• 🖼 Делаю стикеры из сообщений (команда /w)\n"
            "• ⌨️ Исправляю забытую раскладку\n"
            "• ⭐ Веду рейтинг репутации в чатах\n"
        )
        await message.answer(welcome_text)


@dp.message(F.new_chat_members)
async def welcome_new_member(message: types.Message):
    for new_user in message.new_chat_members:
        bot_obj = await bot.get_me()

        if new_user.id == bot_obj.id:
            await message.answer(
                "🚀 Всем привет, я - ModerDuck и моя задача - навести здесь порядок.\n"
            )
        else:
            await message.answer(f"Добро пожаловать, {new_user.first_name}! 🤗")


@dp.message(Command("st"))
async def show_stats(message: types.Message):
    cid = str(message.chat.id)
    # Используем правильный путь к данным
    if cid not in reputation_data["chats"] or not reputation_data["chats"][cid]:
        return await message.answer("🏆 В этом чате пока нет героев.")

    sorted_rep = sorted(reputation_data["chats"][cid].items(), key=lambda x: x[1], reverse=True)[:10]

    # Переходим на HTML форматирование для надежности
    text = "<b>🏆 Рейтинг репутации:</b>\n\n"
    for i, (uid, score) in enumerate(sorted_rep, 1):
        try:
            member = await bot.get_chat_member(message.chat.id, int(uid))
            # Экранируем имя, чтобы символы в нем не ломали верстку
            name = member.user.first_name.replace("<", "&lt;").replace(">", "&gt;")
        except:
            name = f"ID: {uid}"
        text += f"{i}. {name} — <b>{score}</b> ⭐\n"

    # Указываем parse_mode="HTML"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("call"))
async def call_admins(message: types.Message):
    if message.chat.type not in ['group', 'supergroup']: return
    args = message.text.split(maxsplit=1)
    custom_message = args[1] if len(args) > 1 else "Общий сбор!"
    try:
        admins = await bot.get_chat_administrators(message.chat.id)
        calls = [f"[{a.user.first_name}](tg://user?id={a.user.id})" for a in admins if not a.user.is_bot]
        if calls: await message.answer(f"📢 **{custom_message}**\n\n" + ", ".join(calls), parse_mode="Markdown")
    except:
        pass

    @dp.message(Command("logs"))
    async def cmd_logs(message: types.Message):
        if message.from_user.username != ADMIN_USERNAME:
            return await message.reply("⛔ Доступ только для администратора.")

        builder = InlineKeyboardBuilder()
        # Берем логи из нашей базы
        logs = reputation_data.get("logs", {})

        if not logs:
            return await message.answer("📁 Логов пока нет. Бот должен сначала увидеть сообщения в чатах.")

        for chat_id, data in logs.items():
            title = data.get("title", f"ID: {chat_id}")
            builder.button(text=f"💬 {title}", callback_data=f"view_{chat_id}")

        builder.adjust(1)
        await message.answer("📂 Выберите чат для чтения логов:", reply_markup=builder.as_markup())

    @dp.callback_query(F.data.startswith("view_"))
    async def show_chat_history(callback: types.CallbackQuery):
        chat_id = callback.data.split("_")[1]
        chat_data = reputation_data.get("logs", {}).get(chat_id)

        if not chat_data or not chat_data["messages"]:
            return await callback.answer("Сообщений нет.")

        text = f"📜 **Логи чата: {chat_data['title']}**\n\n"
        for m in chat_data["messages"][-15:]:  # Показываем последние 15
            text += f"🕒 `{m['time']}` **{m['user']}**: {m['text']}\n"

        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Обновить", callback_data=f"view_{chat_id}")
        builder.button(text="⬅️ Назад", callback_data="back_to_list")

        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())

    @dp.callback_query(F.data == "back_to_list")
    async def back_to_list(callback: types.CallbackQuery):
        await callback.message.delete()
        await cmd_logs(callback.message)


@dp.message(F.text.startswith("/w"))
async def make_sticker(message: types.Message):
    if not message.reply_to_message:
        return await message.reply("⚠️ Ответь на сообщение!")

    args = message.text.split()
    count = int(args[0][2:]) if len(args[0]) > 2 and args[0][2:].isdigit() else \
        (int(args[1]) if len(args) > 1 and args[1].isdigit() else 1)
    count = max(1, min(count, 10))

    cid = message.chat.id
    target_id = message.reply_to_message.message_id
    all_msgs = message_cache.get(cid, [])
    idx = next((i for i, m in enumerate(all_msgs) if m.message_id == target_id), None)
    msgs = all_msgs[idx: idx + count] if idx is not None else [message.reply_to_message]

    f_name, f_text = get_font(24), get_font(26)
    elements, total_h, last_uid = [], 40, None

    for m in msgs:
        name = m.from_user.first_name if m.from_user else "Unknown"
        uid = m.from_user.id if m.from_user else None
        text = m.text or m.caption or ""

        # Обработка медиа
        media_img = None
        media_h = 0
        file_id = None

        if m.photo:
            file_id = m.photo[-1].file_id
        elif m.sticker:
            file_id = m.sticker.file_id
        elif m.animation:
            file_id = m.animation.thumb.file_id if m.animation.thumb else m.animation.file_id
        elif m.video:
            file_id = m.video.thumb.file_id if m.video.thumb else None

        if file_id:
            try:
                f = await bot.get_file(file_id)
                b = await bot.download_file(f.file_path)
                media_img = Image.open(b).convert("RGBA")
                # Пропорциональное изменение размера медиа под ширину баббла
                max_media_w = 300
                w_percent = (max_media_w / float(media_img.size[0]))
                media_h = int((float(media_img.size[1]) * float(w_percent)))
                media_img = media_img.resize((max_media_w, media_h), Image.LANCZOS)
            except:
                media_img = None

        is_same = (uid == last_uid and uid is not None)
        wrapped = textwrap.fill(text, width=35) if text else ""

        tmp_draw = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
        tw, th = 0, 0
        if wrapped:
            bbox = tmp_draw.multiline_textbbox((0, 0), wrapped, font=f_text, spacing=8)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        b_w = max(tw + 60, (340 if media_img else 200))
        if not is_same:
            nw = tmp_draw.textbbox((0, 0), name, font=f_name)[2]
            b_w = max(b_w, nw + 60)
            b_h = th + media_h + 90 + (15 if media_img and wrapped else 0)
        else:
            b_h = th + media_h + 45 + (15 if media_img and wrapped else 0)

        elements.append({
            "name": name, "text": wrapped, "uid": uid,
            "is_same": is_same, "h": b_h, "w": b_w, "media": media_img
        })
        total_h += b_h + (5 if is_same else 20)
        last_uid = uid

    img = Image.new('RGBA', (600, int(total_h)), (0, 0, 0, 0))
    draw, y_off = ImageDraw.Draw(img), 20

    for el in elements:
        x_start = 100
        if el['is_same']: y_off -= 10

        draw.rounded_rectangle([x_start, y_off, x_start + el['w'], y_off + el['h']], radius=22, fill=(30, 41, 59))

        # Аватарка
        if not el['is_same'] and el['uid']:
            try:
                p = await bot.get_user_profile_photos(el['uid'], limit=1)
                if p.total_count > 0:
                    f = await bot.get_file(p.photos[0][-1].file_id)
                    b = await bot.download_file(f.file_path)
                    av = ImageOps.fit(Image.open(b).convert("RGBA"), (70, 70), Image.LANCZOS)
                    mask = Image.new('L', (70, 70), 0)
                    ImageDraw.Draw(mask).ellipse((0, 0, 70, 70), fill=255)
                    av.putalpha(mask)
                    img.paste(av, (15, int(y_off)), av)
            except:
                pass

        curr_y = y_off + 12
        if not el['is_same']:
            draw.text((x_start + 25, curr_y), el['name'], font=f_name, fill=(100, 180, 255))
            curr_y += 35

        if el['media']:
            img.paste(el['media'], (x_start + 25, int(curr_y)), el['media'])
            curr_y += el['media'].size[1] + 10

        if el['text']:
            draw.multiline_text((x_start + 25, curr_y), el['text'], font=f_text, fill=(255, 255, 255), spacing=6)

        y_off += el['h'] + 15

    out = io.BytesIO()
    img.save(out, format='WEBP')
    out.seek(0)
    await message.answer_sticker(types.BufferedInputFile(out.read(), filename="sticker.webp"))

@dp.message(F.text == "/p")
async def add_to_pack(message: types.Message):
    if not message.reply_to_message or not message.reply_to_message.sticker:
        return await message.reply("⚠️ Ответь на стикер командой /p")

    user_id = message.from_user.id
    bot_obj = await bot.get_me()

    if message.chat.type == 'private':
        owner_id = str(user_id)
        pack_label = "personal"
        pack_title = f"Моя личная папка: {message.from_user.first_name}"
    else:
        owner_id = str(message.chat.id).replace("-", "c")
        pack_label = "group"
        pack_title = f"Папка чата: {message.chat.title or 'Без названия'}"

    pack_name = f"{pack_label}_{owner_id}_by_{bot_obj.username.lower()}"

    target = message.reply_to_message.sticker
    try:
        file = await bot.get_file(target.file_id)
        data = await bot.download_file(file.file_path)
        img = Image.open(data).convert("RGBA")
        img.thumbnail((512, 512))

        out = io.BytesIO()
        img.save(out, format='WEBP')
        out.seek(0)

        stk = types.InputSticker(
            sticker=types.BufferedInputFile(out.read(), filename="s.webp"),
            emoji_list=[target.emoji or "⭐"],
            format="static"
        )

        try:
            await bot.add_sticker_to_set(user_id=user_id, name=pack_name, sticker=stk)
            await message.reply(f"✅ Добавлено! \nhttps://t.me/addstickers/{pack_name}")
        except TelegramBadRequest as e:
            if "STICKERSET_INVALID" in str(e):
                await bot.create_new_sticker_set(
                    user_id=user_id,
                    name=pack_name,
                    title=pack_title,
                    stickers=[stk],
                    sticker_format="static"
                )
                await message.answer(f"🎉 Пакет создан! \nhttps://t.me/addstickers/{pack_name}")
            else:
                await message.reply(f"❌ Ошибка Telegram: {e}")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


@dp.message(F.voice)
async def handle_voice(message: types.Message):
    file = await bot.get_file(message.voice.file_id)
    content = await bot.download_file(file.file_path)
    text = await stt_recognize(content.read())
    if text: await message.reply(f"🎤 **Распознано:**\n{text}", parse_mode="Markdown")


@dp.message()
async def main_handler(message: types.Message):
    # Данные сообщения
    text = message.text or message.caption or ""
    cid = message.chat.id
    cid_str = str(cid)
    uid_str = str(message.from_user.id) if message.from_user else "0"


    # Кэш для стикеров (/w)
    if cid not in message_cache: message_cache[cid] = []
    message_cache[cid].append(message)
    if len(message_cache[cid]) > 100: message_cache[cid].pop(0)

    if not message.from_user or message.from_user.is_bot: return

    # Логика репутации (твоя оригинальная)
    triggers = ["+", "красава", "имба", "база", "респект", "лайк", "спс", "спасибо"]
    if message.reply_to_message and any(t in text.lower().strip() for t in triggers):
        # ... (тут твой код репутации без изменений) ...
        target = message.reply_to_message.from_user
        if target.id == message.from_user.id: return
        now_ts = datetime.now().timestamp()
        limit_key = f"{cid_str}_{uid_str}"
        try:
            last_action_ts = float(reputation_data["limits"].get(limit_key, 0))
        except:
            last_action_ts = 0.0
        if now_ts - last_action_ts < 5400:
            rem = int((5400 - (now_ts - last_action_ts)) // 60)
            return await message.reply(f"⏳ Репу можно через {rem} мин.")
        reputation_data["limits"][limit_key] = now_ts
        if cid_str not in reputation_data["chats"]: reputation_data["chats"][cid_str] = {}
        t_uid = str(target.id)
        reputation_data["chats"][cid_str][t_uid] = reputation_data["chats"][cid_str].get(t_uid, 0) + 1
        save_rep()
        score = reputation_data["chats"][cid_str][t_uid]
        try:
            await bot.set_chat_administrator_custom_title(cid, target.id, f"⭐ Репа: {score}")
        except:
            pass
        await message.answer(f"📈 {target.first_name}, твоя репутация: **{score}**")
        return

    # Раскладка (твоя оригинальная)
    if not text: return
    has_cyrillic = any('а' <= c.lower() <= 'я' for c in text)
    if not has_cyrillic and not text.startswith(('/', '@', 'http')) and not message.reply_to_message and len(text) > 3:
        if await is_gibberish(text):
            conv = "".join(layout_map.get(c, c) for c in text)
            if conv.lower() != text.lower():
                await message.reply(f"🇷🇺 **Перевод:** `{conv}`", parse_mode="Markdown")
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
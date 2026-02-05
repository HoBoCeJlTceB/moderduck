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


BOT_TOKEN = ""
YANDEX_API_KEY = ""
YANDEX_FOLDER_ID = ""



REP_FILE = "reputation.json"
if os.path.exists(REP_FILE):
    with open(REP_FILE, "r") as f: reputation = json.load(f)
else:
    reputation = {}

def save_rep():
    with open(REP_FILE, "w") as f: json.dump(reputation, f)


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
        "messages": [
            {"role": "system",
             "text": "Если текст выглядит как абракадабра из-за раскладки (ghbdtn), ответь ДА. Иначе НЕТ."},
            {"role": "user", "text": text}
        ]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                res = await resp.json()
                return "ДА" in res['result']['alternatives'][0]['message']['text'].upper()
    except:
        return False


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
    if cid not in reputation or not reputation[cid]:
        return await message.answer("🏆 В этом чате пока нет героев.")

    sorted_rep = sorted(reputation[cid].items(), key=lambda x: x[1], reverse=True)[:10]

    text = "🏆 **Рейтинг репутации:**\n\n"
    for i, (uid, score) in enumerate(sorted_rep, 1):
        try:
            member = await bot.get_chat_member(message.chat.id, int(uid))
            name = member.user.first_name
        except:
            name = f"ID: {uid}"
        text += f"{i}. {name} — **{score}** ⭐\n"

    await message.answer(text, parse_mode="Markdown")

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


@dp.message(F.text.startswith("/w"))
async def make_sticker(message: types.Message):
    if not message.reply_to_message:
        return await message.reply("⚠️ Ответь на сообщение!")
    cid, target_id = message.chat.id, message.reply_to_message.message_id
    args = message.text.split()
    count = min(int(args[1]), 10) if len(args) > 1 and args[1].isdigit() else 1

    all_msgs = message_cache.get(cid, [])
    sorted_cache = sorted(all_msgs, key=lambda x: x.message_id)
    idx = next((i for i, m in enumerate(sorted_cache) if m.message_id == target_id), None)
    msgs = sorted_cache[idx: idx + count] if idx is not None else [message.reply_to_message]

    f_name, f_text = get_font(26), get_font(28)
    elements, total_h, last_uid = [], 40, None

    for m in msgs:
        if m.forward_origin:
            origin = m.forward_origin
            if origin.type == "user":
                name, uid = origin.sender_user.first_name, origin.sender_user.id
            elif origin.type == "hidden_user":
                name, uid = origin.sender_user_name, None
            elif origin.type in ["chat", "channel"]:
                name, uid = origin.chat.title, None
            else:
                name, uid = m.from_user.first_name, m.from_user.id
        else:
            name, uid = m.from_user.first_name, m.from_user.id

        display_name = name
        if uid and cid in reputation and uid in reputation[cid]:
            rep_count = reputation[cid][uid]
            display_name = f"{name} ({rep_count})"

        text = m.text or m.caption or " "
        is_same = (uid == last_uid) if uid is not None else False
        wrapped = textwrap.fill(text, width=28)
        tmp_draw = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
        tw, th = tmp_draw.multiline_textbbox((0, 0), wrapped, font=f_text, spacing=10)[2:]
        b_w = max(tw + 70, 220)

        if not is_same:
            nw = tmp_draw.textbbox((0, 0), display_name, font=f_name)[2]  # Используем display_name
            b_w, b_h = max(b_w, nw + 70), th + 90
        else:
            b_h = th + 55

        elements.append({"name": display_name, "text": wrapped, "uid": uid, "is_same": is_same, "h": b_h, "w": b_w})
        total_h += b_h + (10 if is_same else 25)
        last_uid = uid

    img = Image.new('RGBA', (600, int(total_h)), (0, 0, 0, 0))
    draw, y_off = ImageDraw.Draw(img), 20
    for el in elements:
        x_start = 110
        if el['is_same']: y_off -= 15
        draw.rounded_rectangle([x_start, y_off, x_start + el['w'], y_off + el['h']], radius=22, fill=(28, 28, 30))

        if not el['is_same'] and el['uid']:
            try:
                photos = await bot.get_user_profile_photos(el['uid'], limit=1)
                if photos.total_count > 0:
                    f = await bot.get_file(photos.photos[0][-1].file_id)
                    b = await bot.download_file(f.file_path)
                    av = ImageOps.fit(Image.open(b).convert("RGBA"), (80, 80), Image.LANCZOS)
                    mask = Image.new('L', (80, 80), 0)
                    ImageDraw.Draw(mask).ellipse((0, 0, 80, 80), fill=255)
                    av.putalpha(mask)
                    img.paste(av, (15, int(y_off)), av)
            except:
                pass

        if not el['is_same']:
            draw.text((x_start + 30, y_off + 12), el['name'], font=f_name, fill=(71, 201, 170))
            txt_y = y_off + 48
        else:
            txt_y = y_off + 18

        draw.multiline_text((x_start + 30, txt_y), el['text'], font=f_text, fill=(255, 255, 255), spacing=8)
        y_off += el['h'] + 20

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
    cid = message.chat.id
    cid_str = str(cid)
    if cid not in message_cache: message_cache[cid] = []
    message_cache[cid].append(message)
    if len(message_cache[cid]) > 100: message_cache[cid].pop(0)

    if message.text:
        if message.reply_to_message and message.reply_to_message.from_user:
            triggers = ["+", "красава", "имба", "база", "респект", "лайк", "спс"]
            if any(t in message.text.lower().strip() for t in triggers):
                target = message.reply_to_message.from_user

                if target.id == message.from_user.id:
                    return
                if cid_str not in reputation: reputation[cid_str] = {}
                user_id_str = str(target.id)
                reputation[cid_str][user_id_str] = reputation[cid_str].get(user_id_str, 0) + 1
                save_rep()
                new_score = reputation[cid_str][user_id_str]
                try:
                    await bot.promote_chat_member(
                        chat_id=cid,
                        user_id=target.id,
                        can_manage_chat=True
                    )

                    await bot.set_chat_administrator_custom_title(
                        chat_id=cid,
                        user_id=target.id,
                        custom_title=f" Репа: {new_score}"
                    )
                except Exception as e:
                    logging.error(f"Ошибка титула: {e}")

                await message.answer(f"📈 {target.first_name}, твоя репутация: **{new_score}**")
                return

        if not any('а' <= c.lower() <= 'я' for c in message.text) and not message.text.startswith(('/', '@')):
            clean = re.sub(r'[^\w\s.,!?\-]', '', message.text).strip()
            if clean and not clean.isdigit() and await is_gibberish(clean):
                conv = "".join(layout_map.get(c, c) for c in message.text)
                await message.reply(f"🇷🇺 **Перевод:**\n`{conv}`", parse_mode="Markdown")
                return

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    asyncio.run(main())

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    LabeledPrice
)
from telegram.ext import (
    ApplicationBuilder, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler,
    ConversationHandler, CommandHandler,
    PreCheckoutQueryHandler
)
from deep_translator import GoogleTranslator
import uuid
import json
import os
from datetime import datetime

TOKEN = "8175823615:AAEsX3F7JQUpN_A-6bsk-mzX4CKdb4253JM"
PROVIDER_TOKEN = "YOUR_PROVIDER_TOKEN"

ASK_TITLE, ASK_DESCRIPTION, ASK_PRICE, ASK_IMAGES, ASK_FILE, ASK_TAGS = range(6)
ASK_FREE_TITLE, ASK_FREE_DESCRIPTION, ASK_FREE_IMAGES, ASK_FREE_FILE, ASK_FREE_LINKS, ASK_FREE_TAGS = range(6, 12)

CHANNEL_ID = "@BlenderForge"
REVIEWS_CHANNEL_ID = -1002740649693
REVIEWS_CHANNEL_URL = "https://t.me/BlenderForgeReviews"
BOT_USERNAME = "my_cool_shop_bot"
YOUR_ADMIN_ID = 123456789  # Замініть на ваш Telegram ID
YOUR_ADMIN_USERNAME = "Samurai22_1"  # Замініть на ваш username

PRODUCTS_FILE = "products.json"

# Глобальный словарь для хранения товаров и сообщений
PRODUCTS = {}
FREE_MESSAGES = {}

def save_products():
    """Зберігає товари у файл"""
    try:
        with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(PRODUCTS, f, ensure_ascii=False, indent=2)
        print(f"Збережено {len(PRODUCTS)} товарів")
    except Exception as e:
        print(f"Помилка збереження: {e}")

def load_products():
    """Завантажує товари з файлу"""
    global PRODUCTS
    try:
        if os.path.exists(PRODUCTS_FILE):
            with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                PRODUCTS = json.load(f)
                print(f"Завантажено {len(PRODUCTS)} товарів")
        else:
            print("Файл товарів не знайдено, створюється новий")
    except Exception as e:
        print(f"Помилка завантаження: {e}")
        PRODUCTS = {}

def add_translation(text: str) -> str:
    try:
        translated = GoogleTranslator(source='auto', target='en').translate(text)
        return f"{text}\n\n_{translated}_"
    except Exception:
        return text

def escape_markdown(text):
    """Экранирование специальных символов для MarkdownV2"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def parse_links(text):
    """Парсинг посилань у форматі 'Текст - URL'"""
    if not text:
        return []
    
    links = []
    lines = text.strip().split('\n')
    
    for line in lines:
        if ' - ' in line:
            parts = line.split(' - ', 1)
            if len(parts) == 2:
                title = parts[0].strip()
                url = parts[1].strip()
                if title and url:
                    links.append((title, url))
    
    return links

# Функція для обробки старих посилань
async def handle_old_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє запити на старі товари, яких немає в пам'яті"""
    await update.message.reply_text(
        add_translation(
            "❗ Цей товар більше недоступний або було видалено.\n"
            "Перегляньте актуальні товари в каналі або зверніться до адміністратора."
        ),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Перейти до каналу", url="https://t.me/BlenderForge")],
            [InlineKeyboardButton("✉️ Зв'язатися з адміном", url=f"https://t.me/{YOUR_ADMIN_USERNAME}")]
        ])
    )

# ----------------- Приветствие -----------------
async def reply_hello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💸 Створити платне повідомлення / Create Paid Message", callback_data="create_paid")],
        [InlineKeyboardButton("📝 Створити звичайне повідомлення / Create Free Message", callback_data="create_free")]
    ]
    await update.message.reply_text(
        add_translation("Привіт! Що хочеш створити?"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ----------------- Создание товара -----------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(add_translation("📌 Крок 1: Введи назву товару"))
    return ASK_TITLE

async def ask_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text
    await update.message.reply_text(add_translation("✏️ Крок 2: Опиши товар"))
    return ASK_DESCRIPTION

async def ask_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text
    await update.message.reply_text(add_translation("💰 Крок 3: Вкажи ціну у зірках (наприклад: 50)"))
    return ASK_PRICE

async def ask_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text)
        context.user_data["price"] = price
        context.user_data["images"] = []  # Инициализируем список для фото
        await update.message.reply_text(add_translation("🖼 Крок 4: Надішли зображення (можна кілька). Коли закінчиш — напиши /skip"))
        return ASK_IMAGES
    except ValueError:
        await update.message.reply_text(add_translation("❗ Введи число. Спробуй ще раз."))
        return ASK_PRICE

async def ask_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1] if update.message.photo else None
    if photo:
        context.user_data["images"].append(photo.file_id)
        await update.message.reply_text(add_translation("✅ Фото додано. Надішли ще або /skip"))
    return ASK_IMAGES

async def skip_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(add_translation("📦 Крок 5: Надішли файл, який отримає покупець"))
    return ASK_FILE

async def ask_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document:
        await update.message.reply_text(add_translation("❗ Надішли файл, а не текст."))
        return ASK_FILE
    context.user_data["file_id"] = document.file_id
    await update.message.reply_text(add_translation("🏷 Крок 6: Введи хештеги для товару (або /skip)"))
    return ASK_TAGS

async def ask_tags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tags"] = update.message.text
    await send_preview(update, context)
    return ConversationHandler.END

async def skip_tags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tags"] = ""
    await send_preview(update, context)
    return ConversationHandler.END

# ----------------- Создание бесплатного сообщения -----------------
async def button_free_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["images"] = []
    await update.callback_query.message.reply_text(add_translation("📌 Крок 1: Введи заголовок повідомлення"))
    return ASK_FREE_TITLE

async def ask_free_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text
    await update.message.reply_text(add_translation("✏️ Крок 2: Опиши повідомлення"))
    return ASK_FREE_DESCRIPTION

async def ask_free_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text
    await update.message.reply_text(add_translation("🖼 Крок 3: Надішли фото (можна кілька). Коли закінчиш — напиши /skip"))
    return ASK_FREE_IMAGES

async def ask_free_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1] if update.message.photo else None
    if photo:
        context.user_data["images"].append(photo.file_id)
        await update.message.reply_text(add_translation("✅ Фото додано. Надішли ще або /skip"))
    return ASK_FREE_IMAGES

async def skip_free_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(add_translation("📦 Крок 4: Надішли файл (опціонально) або /skip"))
    return ASK_FREE_FILE

async def ask_free_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if document:
        context.user_data["file_id"] = document.file_id
    else:
        context.user_data["file_id"] = None
    await update.message.reply_text(add_translation("🔗 Крок 5: Додай посилання у форматі:\nНазва кнопки - https://example.com\nІнша кнопка - https://site.com\n\nАбо напиши /skip"))
    return ASK_FREE_LINKS

async def skip_free_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["file_id"] = None
    await update.message.reply_text(add_translation("🔗 Крок 5: Додай посилання у форматі:\nНазва кнопки - https://example.com\nІнша кнопка - https://site.com\n\nАбо напиши /skip"))
    return ASK_FREE_LINKS

async def ask_free_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["links"] = update.message.text
    await update.message.reply_text(add_translation("🏷 Крок 6: Введи хештеги або /skip"))
    return ASK_FREE_TAGS

async def skip_free_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["links"] = ""
    await update.message.reply_text(add_translation("🏷 Крок 6: Введи хештеги або /skip"))
    return ASK_FREE_TAGS

async def ask_free_tags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tags"] = update.message.text
    await send_free_preview(update, context)
    return ConversationHandler.END

async def skip_free_tags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tags"] = ""
    await send_free_preview(update, context)
    return ConversationHandler.END

# ----------------- Предварительный просмотр бесплатного сообщения -----------------
async def send_free_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = context.user_data["title"]
    description = context.user_data["description"]
    tags = context.user_data.get("tags", "")
    images = context.user_data.get("images", [])
    file_id = context.user_data.get("file_id")
    links_text = context.user_data.get("links", "")

    message_key = f"free_{uuid.uuid4().hex[:8]}"
    FREE_MESSAGES[message_key] = {
        "title": title,
        "description": description,
        "tags": tags,
        "images": images,
        "file_id": file_id,
        "links": links_text
    }

    context.user_data["current_free_key"] = message_key

    # Экранируем текст для MarkdownV2
    escaped_title = escape_markdown(title)
    escaped_desc = escape_markdown(description)
    escaped_tags = escape_markdown(tags) if tags else ""

    message_text = f"⭐ *{escaped_title}*\n{escaped_desc}"
    if escaped_tags:
        message_text += f"\n\n{escaped_tags}"

    # Добавляем английский перевод
    try:
        translated_title = GoogleTranslator(source='auto', target='en').translate(title)
        translated_desc = GoogleTranslator(source='auto', target='en').translate(description)
        message_text += f"\n\n_{escape_markdown(translated_title)}_\n_{escape_markdown(translated_desc)}_"
    except:
        pass

    # Создаем кнопки из посилань
    custom_keyboard = []
    links = parse_links(links_text)
    
    for link_title, link_url in links:
        custom_keyboard.append([InlineKeyboardButton(link_title, url=link_url)])

    # Отправка фото/текста
    if images:
        if custom_keyboard:
            await update.effective_chat.send_photo(
                photo=images[0], 
                caption=message_text, 
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(custom_keyboard)
            )
        else:
            await update.effective_chat.send_photo(
                photo=images[0], 
                caption=message_text, 
                parse_mode="MarkdownV2"
            )
        for img in images[1:]:
            await update.effective_chat.send_photo(photo=img)
    else:
        if custom_keyboard:
            await update.effective_chat.send_message(
                text=message_text, 
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(custom_keyboard)
            )
        else:
            await update.effective_chat.send_message(
                text=message_text, 
                parse_mode="MarkdownV2"
            )

    if file_id:
        await update.effective_chat.send_document(document=file_id)

    # Кнопки для публикации
    confirm_keyboard = [[
        InlineKeyboardButton("✅ Так / Yes", callback_data=f"post_free:{message_key}"),
        InlineKeyboardButton("❌ Ні / No", callback_data="cancel_free_post")
    ]]
    await update.effective_chat.send_message(
        add_translation("📢 Хочеш запостити це повідомлення у канал?"),
        reply_markup=InlineKeyboardMarkup(confirm_keyboard)
    )

# ----------------- Публикация бесплатного сообщения в канал -----------------
async def confirm_free_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Получаем ключ из callback_data
    data = query.data  # "post_free:free_XXXXXX"
    free_key = data.split(":")[1] if ":" in data else None

    if not free_key or free_key not in FREE_MESSAGES:
        await query.message.reply_text(add_translation("❗ Немає повідомлення для публікації."))
        return

    msg_data = FREE_MESSAGES[free_key]

    # Подготавливаем текст для публикации
    escaped_title = escape_markdown(msg_data['title'])
    escaped_desc = escape_markdown(msg_data['description'])
    escaped_tags = escape_markdown(msg_data['tags']) if msg_data['tags'] else ""

    channel_text = f"⭐ *{escaped_title}*\n{escaped_desc}"
    if escaped_tags:
        channel_text += f"\n\n{escaped_tags}"

    # Добавляем английский перевод
    try:
        translated_title = GoogleTranslator(source='auto', target='en').translate(msg_data['title'])
        translated_desc = GoogleTranslator(source='auto', target='en').translate(msg_data['description'])
        channel_text += f"\n\n_{escape_markdown(translated_title)}_\n_{escape_markdown(translated_desc)}_"
    except:
        pass

    # Создаем кнопки из посилань
    custom_keyboard = []
    links = parse_links(msg_data.get('links', ''))
    
    for link_title, link_url in links:
        custom_keyboard.append([InlineKeyboardButton(link_title, url=link_url)])

    # Отправка в канал
    try:
        if msg_data["images"]:
            if custom_keyboard:
                await context.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=msg_data["images"][0],
                    caption=channel_text,
                    parse_mode="MarkdownV2",
                    reply_markup=InlineKeyboardMarkup(custom_keyboard)
                )
            else:
                await context.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=msg_data["images"][0],
                    caption=channel_text,
                    parse_mode="MarkdownV2"
                )
            for img in msg_data["images"][1:]:
                await context.bot.send_photo(chat_id=CHANNEL_ID, photo=img)
        else:
            if custom_keyboard:
                await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=channel_text,
                    parse_mode="MarkdownV2",
                    reply_markup=InlineKeyboardMarkup(custom_keyboard)
                )
            else:
                await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=channel_text,
                    parse_mode="MarkdownV2"
                )

        if msg_data["file_id"]:
            await context.bot.send_document(chat_id=CHANNEL_ID, document=msg_data["file_id"])

        await query.message.edit_text(add_translation("✅ Опубліковано у каналі!"))

    except Exception as e:
        await query.message.edit_text(add_translation(f"❗ Помилка при публікації: {str(e)}"))

    # Удаляем из памяти
    if free_key in FREE_MESSAGES:
        del FREE_MESSAGES[free_key]

async def cancel_free_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    message_key = context.user_data.get("current_free_key")
    if message_key and message_key in FREE_MESSAGES:
        del FREE_MESSAGES[message_key]

    await query.message.edit_text(add_translation("❌ Публікацію скасовано."))

# ----------------- Предварительный просмотр платного товара -----------------
async def send_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = context.user_data["title"]
    description = context.user_data["description"]
    price = context.user_data["price"]
    tags = context.user_data.get("tags", "")
    images = context.user_data.get("images", [])
    file_id = context.user_data["file_id"]

    # Генерируем уникальный ключ для товара
    product_key = f"product_{uuid.uuid4().hex[:8]}"
    
    # Сохраняем товар в глобальном словаре с датой создания
    PRODUCTS[product_key] = {
        "title": title,
        "description": description,
        "price": price,
        "file_id": file_id,
        "images": images,
        "tags": tags,
        "created_at": str(datetime.now())
    }
    
    # ВАЖЛИВО: Зберігаємо у файл
    save_products()

    # Экранируем текст для MarkdownV2
    escaped_title = escape_markdown(title)
    escaped_desc = escape_markdown(description)
    escaped_tags = escape_markdown(tags) if tags else ""

    message_text = f"⭐ *{escaped_title}*\n{escaped_desc}\n\n*Ціна:* {price} ⭐\nPrice: {price} ⭐"
    if escaped_tags:
        message_text += f"\n\n{escaped_tags}"
    message_text += "\n⬇️⬇️⬇️"

    # Добавляем английский перевод
    try:
        translated_title = GoogleTranslator(source='auto', target='en').translate(title)
        translated_desc = GoogleTranslator(source='auto', target='en').translate(description)
        message_text = f"⭐ *{escaped_title}*\n{escaped_desc}\n\n*Ціна:* {price} ⭐\nPrice: {price} ⭐\n\n_{escape_markdown(translated_title)}_\n_{escape_markdown(translated_desc)}_"
        if escaped_tags:
            message_text += f"\n\n{escaped_tags}"
        message_text += "\n⬇️⬇️⬇️"
    except:
        pass

    keyboard = [
        [InlineKeyboardButton("💳 Придбати / Buy", url=f"https://t.me/{BOT_USERNAME}?start={product_key}")],
        [InlineKeyboardButton("ℹ️ Як купити? / How to buy?", callback_data="how_to_buy")],
        [InlineKeyboardButton("📝 Відгуки / Reviews", url=REVIEWS_CHANNEL_URL)]
    ]

    # Отправляем первое изображение с подписью или текстовое сообщение
    if images:
        msg = await update.effective_chat.send_photo(
            photo=images[0],
            caption=message_text,
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        # Отправляем остальные изображения без подписи
        for img in images[1:]:
            await update.effective_chat.send_photo(photo=img)
    else:
        msg = await update.effective_chat.send_message(
            text=message_text,
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    context.user_data["preview_message_id"] = msg.message_id
    context.user_data["current_product_key"] = product_key
    context.user_data["preview_text"] = message_text
    context.user_data["preview_keyboard"] = keyboard

    confirm_keyboard = [[
        InlineKeyboardButton("✅ Так / Yes", callback_data="post_to_channel"),
        InlineKeyboardButton("❌ Ні / No", callback_data="cancel_post")
    ]]
    await update.effective_chat.send_message(
        add_translation("📢 Хочеш запостити цей товар у канал?"),
        reply_markup=InlineKeyboardMarkup(confirm_keyboard)
    )

# ----------------- Публикация в канал -----------------
async def confirm_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_key = context.user_data.get("current_product_key")
    if not product_key or product_key not in PRODUCTS:
        await query.message.reply_text(add_translation("❗ Немає товару для публікації."))
        return

    product = PRODUCTS[product_key]
    message_text = context.user_data["preview_text"]
    keyboard = context.user_data["preview_keyboard"]

    try:
        if product.get("images"):  # Проверяем наличие изображений
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=product["images"][0],
                caption=message_text,
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            # Отправляем остальные изображения
            for img in product["images"][1:]:
                await context.bot.send_photo(chat_id=CHANNEL_ID, photo=img)
        else:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=message_text,
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        await query.message.edit_text(add_translation("✅ Опубліковано у каналі!"))
    except Exception as e:
        await query.message.edit_text(add_translation(f"❗ Помилка при публікації: {str(e)}"))

# ----------------- Отмена -----------------
async def cancel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Удаляем товар из глобального словаря
    product_key = context.user_data.get("current_product_key")
    if product_key and product_key in PRODUCTS:
        del PRODUCTS[product_key]
        save_products()  # Оновлюємо файл
    
    preview_id = context.user_data.get("preview_message_id")
    if preview_id:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=preview_id)
        except:
            pass
    await query.message.edit_text(add_translation("❌ Публікацію скасовано."))

# ----------------- Инструкция -----------------
async def how_to_buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text=add_translation(
            "ℹ️ Інструкція з купівлі:\n"
            "1. Натисни кнопку «Придбати»\n"
            "2. Оплати товар через Telegram Payments\n"
            "3. Отримай файл відразу після оплати ✅"
        )
    )

# ----------------- Оплата и отзывы -----------------
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args and len(args) > 0:
        product_key = args[0]
        
        # Перевіряємо чи існує товар
        if product_key in PRODUCTS:
            product = PRODUCTS[product_key]
            prices = [LabeledPrice(label=product["title"], amount=product["price"])]
            
            context.user_data["pending_payment_key"] = product_key

            await context.bot.send_invoice(
                chat_id=update.effective_chat.id,
                title=product["title"],
                description=product["description"],
                payload=product_key,
                provider_token=PROVIDER_TOKEN,
                currency="XTR",
                prices=prices,
                start_parameter=product_key
            )
        else:
            # Товар не знайдено - обробляємо як старий пост
            await handle_old_product(update, context)
    else:
        # Звичайний start без параметрів
        await update.message.reply_text(
            add_translation("👋 Привіт! Напиши 'привіт' щоб почати роботу з ботом."),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Перейти до каналу", url="https://t.me/BlenderForge")]
            ])
        )

async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    product = PRODUCTS.get(payload)
    
    if not product:
        await update.message.reply_text(add_translation("❗ Немає файлу для надсилання."))
        return

    await update.message.reply_text(add_translation("✅ Оплата успішна! Ось твій файл:"))
    await update.message.reply_document(document=product["file_id"])

    context.user_data["awaiting_review"] = True
    await update.message.reply_text(add_translation("✍️ Напишіть відгук про товар:"))

async def ask_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_review"):
        return

    text = update.message.text
    user = update.message.from_user

    await context.bot.send_message(
        chat_id=REVIEWS_CHANNEL_ID,
        text=add_translation(f"💬 Відгук від @{user.username or user.id}:\n\n{text}")
    )

    await update.message.reply_text(add_translation("✅ Дякуємо за твій відгук!"))
    context.user_data["awaiting_review"] = False

# Команда для адміністратора
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для адміністратора для керування товарами"""
    if update.effective_user.id != YOUR_ADMIN_ID:
        return
    
    products_count = len(PRODUCTS)
    await update.message.reply_text(
        f"🔧 Адмін панель:\n"
        f"📦 Всього товарів: {products_count}\n"
        f"💾 Файл: {PRODUCTS_FILE}\n\n"
        f"Команди:\n"
        f"/products - показати всі товари\n"
        f"/clear_old - очистити товари старше 30 днів"
    )

# Показати всі товари (тільки для адміна)
async def products_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показує список всіх товарів"""
    if update.effective_user.id != YOUR_ADMIN_ID:
        return
    
    if not PRODUCTS:
        await update.message.reply_text("Немає товарів")
        return
    
    products_list = []
    for key, product in PRODUCTS.items():
        created_at = product.get('created_at', 'Невідомо')
        products_list.append(
            f"🔹 {product['title']}\n"
            f"   ID: {key}\n"
            f"   Ціна: {product['price']} ⭐\n"
            f"   Створено: {created_at[:10] if created_at != 'Невідомо' else created_at}\n"
        )
    
    message = f"📦 Всі товари ({len(products_list)}):\n\n" + "\n".join(products_list)
    
    # Розбиваємо на частини якщо повідомлення занадто довге
    if len(message) > 4000:
        for i in range(0, len(message), 4000):
            await update.message.reply_text(message[i:i+4000])
    else:
        await update.message.reply_text(message)

# ----------------- Запуск -----------------
# Завантажуємо товари при старті
load_products()

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^привіт$"), reply_hello))

# Обработчики для бесплатных сообщений
app.add_handler(ConversationHandler(
    entry_points=[CallbackQueryHandler(button_free_handler, pattern="create_free")],
    states={
        ASK_FREE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_free_title)],
        ASK_FREE_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_free_description)],
        ASK_FREE_IMAGES: [MessageHandler(filters.PHOTO, ask_free_images), CommandHandler("skip", skip_free_images)],
        ASK_FREE_FILE: [MessageHandler(filters.Document.ALL, ask_free_file), CommandHandler("skip", skip_free_file)],
        ASK_FREE_LINKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_free_links), CommandHandler("skip", skip_free_links)],
        ASK_FREE_TAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_free_tags), CommandHandler("skip", skip_free_tags)],
    },
    fallbacks=[CommandHandler("cancel", cancel_post_handler)],
    allow_reentry=True,
    per_chat=True
))

# Обработчики для платных товаров
app.add_handler(ConversationHandler(
    entry_points=[CallbackQueryHandler(button_handler, pattern="create_paid")],
    states={
        ASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_title)],
        ASK_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_description)],
        ASK_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_price)],
        ASK_IMAGES: [MessageHandler(filters.PHOTO, ask_images), CommandHandler("skip", skip_images)],
        ASK_FILE: [MessageHandler(filters.Document.ALL, ask_file)],
        ASK_TAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_tags), CommandHandler("skip", skip_tags)],
    },
    fallbacks=[CommandHandler("cancel", cancel_post_handler)],
    allow_reentry=True,
    per_chat=True
))

# Основные обработчики
app.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
app.add_handler(CommandHandler("start", start_handler))

# Адмін команди
app.add_handler(CommandHandler("admin", admin_command))
app.add_handler(CommandHandler("products", products_command))

# Обработчики кнопок
app.add_handler(CallbackQueryHandler(confirm_free_post_handler, pattern=r"^post_free:"))
app.add_handler(CallbackQueryHandler(cancel_free_post_handler, pattern="cancel_free_post"))
app.add_handler(CallbackQueryHandler(confirm_post_handler, pattern="post_to_channel"))
app.add_handler(CallbackQueryHandler(cancel_post_handler, pattern="cancel_post"))
app.add_handler(CallbackQueryHandler(how_to_buy_handler, pattern="how_to_buy"))

# Обработчик отзывов (должен быть последним)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ask_review))

print("🚀 Бот запущений...")
print(f"📦 Завантажено товарів: {len(PRODUCTS)}")
app.run_polling()

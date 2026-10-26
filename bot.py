"""
Демо-бот для маникюрного салона "Nail Studio" (мастер Анастасия, работа на дому).

Возможности:
- главное меню: услуги и цены, запись, контакты;
- запись через пошаговый диалог (FSM): имя -> услуга -> дата/время;
- отправка заявки владельцу в отдельный чат (OWNER_CHAT_ID);
- логирование ошибок в файл errors.log.
"""

import asyncio
import logging
import os
import sys
from html import escape

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ErrorEvent,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Настройки
# ---------------------------------------------------------------------------

# Загружаем переменные окружения из файла .env (если он есть)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")

# Файл для логов ошибок лежит рядом со скриптом
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "errors.log")

# Список услуг салона: название -> цена в рублях
SERVICES = {
    "Маникюр классический": 1500,
    "Покрытие гель-лак": 2000,
    "Наращивание": 3000,
}

# Тексты кнопок главного меню
BTN_SERVICES = "💅 Услуги и цены"
BTN_BOOK = "📅 Записаться"
BTN_CONTACTS = "📞 Контакты"
BTN_CANCEL = "❌ Отмена"


# ---------------------------------------------------------------------------
# Логирование
# ---------------------------------------------------------------------------

def setup_logging() -> None:
    """Информационные сообщения выводим в консоль, ошибки дополнительно пишем в файл."""
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(console_handler)
    root.addHandler(file_handler)


logger = logging.getLogger("nail_studio_bot")


# ---------------------------------------------------------------------------
# Клавиатуры
# ---------------------------------------------------------------------------

def main_menu_kb() -> ReplyKeyboardMarkup:
    """Главное меню бота."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SERVICES)],
            [KeyboardButton(text=BTN_BOOK), KeyboardButton(text=BTN_CONTACTS)],
        ],
        resize_keyboard=True,
    )


def services_kb() -> ReplyKeyboardMarkup:
    """Клавиатура выбора услуги при записи."""
    rows = [[KeyboardButton(text=name)] for name in SERVICES]
    rows.append([KeyboardButton(text=BTN_CANCEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    """Клавиатура с одной кнопкой отмены (во время диалога записи)."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
    )


# ---------------------------------------------------------------------------
# Состояния диалога записи (FSM)
# ---------------------------------------------------------------------------

class Booking(StatesGroup):
    name = State()       # ждём имя клиента
    service = State()    # ждём выбор услуги
    datetime = State()   # ждём удобную дату и время


router = Router()


# ---------------------------------------------------------------------------
# Общие команды и главное меню
# ---------------------------------------------------------------------------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Приветствие и показ главного меню."""
    await state.clear()
    name = escape(message.from_user.first_name or "")
    await message.answer(
        f"Здравствуйте, {name}! 👋\n\n"
        "Добро пожаловать в <b>Nail Studio</b> — уютный маникюрный кабинет "
        "мастера Алины.\n\nВыберите, что вас интересует:",
        reply_markup=main_menu_kb(),
    )


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    """Служебная команда: показывает ID текущего чата (нужно для OWNER_CHAT_ID)."""
    await message.answer(f"ID этого чата: <code>{message.chat.id}</code>")


@router.message(StateFilter("*"), F.text == BTN_CANCEL)
@router.message(StateFilter("*"), Command("cancel"))
async def cancel_booking(message: Message, state: FSMContext) -> None:
    """Отмена записи на любом шаге диалога."""
    await state.clear()
    await message.answer("Запись отменена.", reply_markup=main_menu_kb())


@router.message(F.text == BTN_SERVICES)
async def show_services(message: Message) -> None:
    """Список услуг с ценами."""
    lines = [f"• {name} — <b>{price}₽</b>" for name, price in SERVICES.items()]
    await message.answer(
        "💅 <b>Услуги и цены</b>\n\n" + "\n".join(lines) +
        "\n\nЧтобы записаться, нажмите «📅 Записаться».",
        reply_markup=main_menu_kb(),
    )


@router.message(F.text == BTN_CONTACTS)
async def show_contacts(message: Message) -> None:
    """Контактная информация (демо-данные)."""
    await message.answer(
        "📞 <b>Контакты</b>\n\n"
        "Мастер: Анастасия\n"
        "Телефон: +7 (900) 000-00-00\n"
        "Адрес: работаю на дому, точный адрес сообщу при подтверждении записи\n"
        "Время работы: ежедневно с 10:00 до 20:00",
        reply_markup=main_menu_kb(),
    )


# ---------------------------------------------------------------------------
# Диалог записи
# ---------------------------------------------------------------------------

@router.message(F.text == BTN_BOOK)
async def booking_start(message: Message, state: FSMContext) -> None:
    """Шаг 1: спрашиваем имя."""
    await state.set_state(Booking.name)
    await message.answer("Как вас зовут?", reply_markup=cancel_kb())


@router.message(Booking.name, F.text)
async def booking_name(message: Message, state: FSMContext) -> None:
    """Шаг 2: сохраняем имя и предлагаем выбрать услугу."""
    await state.update_data(name=message.text.strip())
    await state.set_state(Booking.service)
    await message.answer("Выберите услугу:", reply_markup=services_kb())


@router.message(Booking.service, F.text.in_(SERVICES.keys()))
async def booking_service(message: Message, state: FSMContext) -> None:
    """Шаг 3: сохраняем услугу и спрашиваем дату/время."""
    await state.update_data(service=message.text)
    await state.set_state(Booking.datetime)
    await message.answer(
        "Укажите удобную дату и время (например: 15 ноября, 14:00):",
        reply_markup=cancel_kb(),
    )


@router.message(Booking.service)
async def booking_service_invalid(message: Message) -> None:
    """Пользователь ввёл что-то кроме кнопки с услугой."""
    await message.answer(
        "Пожалуйста, выберите услугу с помощью кнопок ниже.",
        reply_markup=services_kb(),
    )


@router.message(Booking.datetime, F.text)
async def booking_datetime(message: Message, state: FSMContext, bot: Bot) -> None:
    """Финал: отправляем заявку владельцу и подтверждаем клиенту."""
    data = await state.update_data(datetime=message.text.strip())
    await state.clear()

    name = escape(data["name"])
    service = escape(data["service"])
    when = escape(data["datetime"])
    price = SERVICES[data["service"]]

    user = message.from_user
    username = f"@{user.username}" if user.username else "не указан"

    # Структурированное сообщение для владельца
    owner_text = (
        "🆕 <b>Новая заявка на запись</b>\n\n"
        f"👤 Имя: {name}\n"
        f"💅 Услуга: {service} ({price}₽)\n"
        f"📅 Дата/время: {when}\n\n"
        f"Telegram: {escape(username)}\n"
        f"ID пользователя: <code>{user.id}</code>\n"
        f'<a href="tg://user?id={user.id}">Открыть профиль</a>'
    )

    try:
        await bot.send_message(OWNER_CHAT_ID, owner_text)
    except Exception:
        # Ошибка уйдёт в errors.log; клиенту всё равно показываем подтверждение
        logger.exception("Не удалось отправить заявку владельцу (OWNER_CHAT_ID=%s)", OWNER_CHAT_ID)

    await message.answer(
        f"Спасибо, {name}! Заявка на {service} на {when} принята. "
        "Анастасия свяжется с вами для подтверждения.",
        reply_markup=main_menu_kb(),
    )


@router.message(StateFilter(Booking.name, Booking.datetime))
async def booking_text_expected(message: Message) -> None:
    """В диалоге ожидается текст, а пришло что-то другое (стикер, фото и т.п.)."""
    await message.answer("Пожалуйста, отправьте ответ текстом.")


# ---------------------------------------------------------------------------
# Прочее
# ---------------------------------------------------------------------------

@router.message()
async def fallback(message: Message) -> None:
    """Любое неизвестное сообщение — возвращаем в главное меню."""
    await message.answer(
        "Не совсем поняла вас 🙂 Воспользуйтесь кнопками меню.",
        reply_markup=main_menu_kb(),
    )


@router.errors()
async def error_handler(event: ErrorEvent) -> bool:
    """Глобальный обработчик необработанных ошибок — пишет их в errors.log."""
    logger.error("Ошибка при обработке апдейта: %r", event.exception, exc_info=event.exception)
    return True


# ---------------------------------------------------------------------------
# Запуск
# ---------------------------------------------------------------------------

async def main() -> None:
    setup_logging()

    if not BOT_TOKEN:
        logger.error("Не задана переменная окружения BOT_TOKEN")
        sys.exit(1)
    if not OWNER_CHAT_ID:
        # Бот всё равно запускается, чтобы можно было узнать свой ID командой /myid
        logger.warning(
            "Не задана переменная OWNER_CHAT_ID — заявки не будут доставляться владельцу. "
            "Отправьте боту /myid, чтобы узнать ID чата."
        )

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger("nail_studio_bot").info("Бот остановлен")

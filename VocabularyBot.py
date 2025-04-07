import logging
import os
import random

from dotenv import load_dotenv

import BaseModel
from DatabaseManeger import DatabaseManager

# Проверка зависимостей
try:
    import psycopg2
    from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, text, Index
    from sqlalchemy.orm import sessionmaker, declarative_base, relationship, close_all_sessions
    from sqlalchemy.exc import SQLAlchemyError
except ImportError as e:
    print("Ошибка: Не установлены необходимые зависимости. Установите их командой:")
    print("pip install psycopg2-binary sqlalchemy python-dotenv python-telegram-bot")
    raise

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, \
    KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

# Настройка логгирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# ==================== ОСНОВНОЙ КЛАСС БОТА ====================
class VocabularyBot:
    def __init__(self):
        self.db = DatabaseManager()
        self.db.initialize_words()

        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ValueError("Токен бота не найден в переменных окружения!")

        self.application = Application.builder().token(token).build()
        self._register_handlers()

    def _register_handlers(self):
        """Регистрация обработчиков команд"""
        handlers = [
            CommandHandler("start", self.start),
            CommandHandler("add", self.add_word),
            CommandHandler("remove", self.remove_word),
            CommandHandler("quiz", self.quiz),
            CommandHandler("list", self.list_words),
            CommandHandler("stats", self.show_stats),
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message),
            CallbackQueryHandler(self.handle_button_click)
        ]
        for handler in handlers:
            self.application.add_handler(handler)

    # ==================== ОСНОВНЫЕ КОМАНДЫ ====================
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start"""
        try:
            await update.message.reply_text(
                "👋 Привет! Я бот для изучения английских слов.\n\n"
                "Основные команды:\n"
                "/add - добавить новое слово\n"
                "/remove - удалить слово\n"
                "/quiz - начать викторину\n"
                "/list - показать все слова\n"
                "/stats - показать прогресс\n\n"
                "Используй кнопки ниже для быстрого доступа:",
                reply_markup=self._get_main_menu()
            )
        except Exception as e:
            logger.error(f"Ошибка в команде start: {e}")

    def _get_main_menu(self):
        """Создает главное меню с кнопками"""
        return ReplyKeyboardMarkup([
            [KeyboardButton("➕ Добавить слово"), KeyboardButton("🗑️ Удалить слово")],
            [KeyboardButton("📋 Список слов"), KeyboardButton("📊 Статистика")],
            [KeyboardButton("🎯 Викторина"), KeyboardButton("❌ Скрыть клавиатуру")]
        ], resize_keyboard=True)

    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает статистику изучения"""
        user_id = update.effective_user.id
        with self.db.get_session() as session:
            try:
                # Получаем общее количество слов пользователя
                total_words = session.query(BaseModel.UserWord).filter_by(user_id=user_id).count()

                # Получаем количество изученных слов
                learned_words = session.query(BaseModel.UserWord).filter_by(
                    user_id=user_id,
                    passed_word=True
                ).count()

                # Получаем количество новых слов за последнюю неделю
                # (здесь нужна доработка с датами)

                await update.message.reply_text(
                    f"📊 Ваша статистика:\n\n"
                    f"• Всего слов: {total_words}\n"
                    f"• Изучено: {learned_words}\n"
                    f"• Прогресс: {round(learned_words / max(total_words, 1) * 100)}%\n\n"
                    f"Продолжайте в том же духе! 💪",
                    reply_markup=self._get_main_menu()
                )

            except Exception as e:
                logger.error(f"Ошибка при получении статистики: {e}")
                await update.message.reply_text(
                    "⚠️ Не удалось получить статистику. Попробуйте позже.",
                    reply_markup=self._get_main_menu()
                )

    # ==================== РАБОТА СО СЛОВАМИ ====================
    async def add_word(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавление нового слова в словарь"""
        if not context.args:
            await update.message.reply_text(
                "📝 Введите слово и перевод через пробел:\n"
                "Пример: <code>яблоко apple</code>",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("Отмена")]],
                    resize_keyboard=True
                )
            )
            return

        try:
            if len(context.args) < 2:
                await update.message.reply_text("❌ Нужно ввести оба слова: на русском и английском!")
                return

            ru_word, en_word = context.args[0].lower(), context.args[1].lower()
            user_id = update.effective_user.id

            with self.db.get_session() as session:
                # Проверяем существование слова
                word = session.query(BaseModel.Word).filter_by(
                    target_word=ru_word,
                    translate_word=en_word
                ).first()

                if not word:
                    word = BaseModel.Word(target_word=ru_word, translate_word=en_word)
                    session.add(word)
                    session.commit()

                # Проверяем, есть ли уже связь с пользователем
                user_word = session.query(BaseModel.UserWord).filter_by(
                    user_id=user_id,
                    word_id=word.id
                ).first()

                if not user_word:
                    user_word = BaseModel.UserWord(
                        user_id=user_id,
                        word_id=word.id,
                        passed_word=False
                    )
                    session.add(user_word)
                    session.commit()

                await update.message.reply_text(
                    f"✅ Слово <b>{ru_word}</b> - <b>{en_word}</b> успешно добавлено!",
                    parse_mode="HTML",
                    reply_markup=self._get_main_menu()
                )

        except Exception as e:
            logger.error(f"Ошибка при добавлении слова: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка. Проверьте формат ввода и попробуйте еще раз.",
                reply_markup=self._get_main_menu()
            )

    async def remove_word(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаление слова из словаря пользователя"""
        if not context.args:
            await update.message.reply_text(
                "🗑 Введите слово, которое хотите удалить:",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("Отмена")]],
                    resize_keyboard=True
                )
            )
            return

        try:
            word_to_remove = context.args[0].lower()
            user_id = update.effective_user.id

            with self.db.get_session() as session:
                word = session.query(BaseModel.Word).filter_by(target_word=word_to_remove).first()

                if not word:
                    await update.message.reply_text("❌ Слово не найдено!")
                    return

                # Удаляем из user_words
                session.query(BaseModel.UserWord).filter_by(
                    user_id=user_id,
                    word_id=word.id
                ).delete()

                # Добавляем в игнорируемые
                if not session.query(BaseModel.IgnoreWord).filter_by(
                        user_id=user_id,
                        word_id=word.id
                ).first():
                    ignore_word = BaseModel.IgnoreWord(user_id=user_id, word_id=word.id)
                    session.add(ignore_word)

                session.commit()

                await update.message.reply_text(
                    f"🗑 Слово <b>{word_to_remove}</b> удалено из вашего словаря!",
                    parse_mode="HTML",
                    reply_markup=self._get_main_menu()
                )

        except Exception as e:
            logger.error(f"Ошибка при удалении слова: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при удалении слова",
                reply_markup=self._get_main_menu()
            )

    async def list_words(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список слов пользователя с пагинацией"""
        user_id = update.effective_user.id
        page = int(context.args[0]) if context.args and context.args[0].isdigit() else 1
        page_size = 10

        with self.db.get_session() as session:
            try:
                # Получаем общее количество слов
                total_words = session.query(BaseModel.UserWord).filter_by(user_id=user_id).count()
                if not total_words:
                    await update.message.reply_text(
                        "📭 Ваш словарь пуст! Добавьте слова через /add",
                        reply_markup=self._get_main_menu()
                    )
                    return

                # Вычисляем общее количество страниц
                total_pages = (total_words + page_size - 1) // page_size
                page = max(1, min(page, total_pages))

                # Получаем слова для текущей страницы
                words = session.query(BaseModel.Word).join(BaseModel.UserWord).filter(
                    BaseModel.UserWord.user_id == user_id
                ).order_by(BaseModel.Word.target_word).offset((page - 1) * page_size).limit(page_size).all()

                # Формируем сообщение
                word_list = "\n".join(
                    f"• {word.target_word} - {word.translate_word}" +
                    (" ✅" if session.query(BaseModel.UserWord).filter_by(
                        user_id=user_id,
                        word_id=word.id,
                        passed_word=True
                    ).first() else "")
                    for word in words
                )

                # Создаем клавиатуру пагинации
                pagination = []
                if page > 1:
                    pagination.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page_{page - 1}"))
                if page < total_pages:
                    pagination.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"page_{page + 1}"))

                reply_markup = InlineKeyboardMarkup([pagination]) if pagination else None

                await update.message.reply_text(
                    f"📖 Ваши слова (стр. {page}/{total_pages}):\n\n{word_list}",
                    reply_markup=reply_markup
                )

            except Exception as e:
                logger.error(f"Ошибка при получении списка слов: {e}")
                await update.message.reply_text(
                    "❌ Произошла ошибка при получении списка слов",
                    reply_markup=self._get_main_menu()
                )

    # ==================== ВИКТОРИНА ====================
    async def quiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запуск викторины с проверкой на None"""
        try:
            # Получаем объект сообщения
            message = update.message or (update.callback_query.message if update.callback_query else None)
            if not message:
                logger.error("Не удалось получить объект сообщения")
                return

            user_id = update.effective_user.id
            with self.db.get_session() as session:
                # Получаем слова пользователя
                user_words = session.query(BaseModel.Word).join(BaseModel.UserWord).filter(
                    BaseModel.UserWord.user_id == user_id,
                    BaseModel.UserWord.passed_word == False
                ).all()

                # Получаем случайные слова из основной таблицы
                added_words_ids = [w.id for w in user_words]
                all_words = session.query(BaseModel.Word).filter(
                    ~BaseModel.Word.id.in_(added_words_ids) if added_words_ids else True
                ).order_by(text("RANDOM()")).limit(5).all()

                words = user_words + all_words
                if not words:
                    await message.reply_text(
                        "Ваш словарь пуст! Добавьте слова через /add",
                        reply_markup=self._get_main_menu()
                    )
                    return

                word = random.choice(words)
                correct_answer = word.translate_word

                # Получаем варианты ответов
                wrong_answers = session.execute(
                    text("""
                    SELECT translate_word 
                    FROM words 
                    WHERE translate_word != :correct 
                    GROUP BY translate_word
                    ORDER BY RANDOM() 
                    LIMIT 3
                    """).bindparams(correct=correct_answer)
                ).fetchall()

                options = [t[0] for t in wrong_answers] + [correct_answer]
                random.shuffle(options)

                # Сохраняем данные для проверки
                context.user_data['quiz'] = {
                    'correct_answer': correct_answer,
                    'word_id': word.id,
                    'is_user_word': word in user_words
                }

                keyboard = [
                    [InlineKeyboardButton(opt, callback_data=f"quiz_{opt}")]
                    for opt in options
                ]

                await message.reply_text(
                    f"Как переводится слово '{word.target_word}'?",
                    reply_markup=InlineKeyboardMarkup(keyboard))

        except Exception as e:
            logger.error(f"Ошибка при запуске викторины: {e}")
            if update.message:  # Дополнительная проверка
                await update.message.reply_text(
                    "❌ Ошибка при запуске викторины",
                    reply_markup=self._get_main_menu()
                )

    async def handle_button_click(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий кнопок с проверкой на None"""
        try:
            query = update.callback_query
            if not query or not query.message:
                logger.error("Не удалось получить callback_query или message")
                return

            await query.answer()

            message = query.message
            if not message:
                logger.error("Не удалось получить объект сообщения")
                return

            if query.data.startswith("quiz_"):
                # Обработка ответа
                user_answer = query.data[5:]
                quiz_data = context.user_data.get('quiz', {})
                correct_answer = quiz_data.get('correct_answer')

                if user_answer == correct_answer:
                    response = f"✅ Правильно! {correct_answer} - верный ответ!"
                else:
                    response = f"❌ Неверно! Правильный ответ: {correct_answer}"

                await query.edit_message_text(response)

                # Предлагаем продолжить
                keyboard = [[InlineKeyboardButton("➡️ Продолжить", callback_data="continue_quiz")]]
                await message.reply_text(
                    "Продолжить викторину?",
                    reply_markup=InlineKeyboardMarkup(keyboard))

            elif query.data == "continue_quiz":
                await self.quiz(update, context)

        except Exception as e:
            logger.error(f"Ошибка в обработчике кнопок: {e}")
            if update.callback_query and update.callback_query.message:
                await update.callback_query.message.reply_text(
                    "⚠️ Произошла ошибка, попробуйте снова",
                    reply_markup=self._get_main_menu()
                )
    # ==================== ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ ====================
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        text = update.message.text

        if text == "➕ Добавить слово":
            await update.message.reply_text(
                "Введите слово и перевод через пробел (например: <code>яблоко apple</code>)",
                parse_mode="HTML"
            )
        elif text == "🗑️ Удалить слово":
            await update.message.reply_text("Введите слово, которое хотите удалить:")
        elif text == "📋 Список слов":
            await self.list_words(update, context)
        elif text == "📊 Статистика":
            await self.show_stats(update, context)
        elif text == "🎯 Викторина":
            await self.quiz(update, context)
        elif text == "❌ Скрыть клавиатуру":
            await update.message.reply_text(
                "Клавиатура скрыта. Напишите /start для её возврата.",
                reply_markup=ReplyKeyboardRemove()
            )
        elif text == "Отмена":
            await update.message.reply_text(
                "✖️ Действие отменено",
                reply_markup=self._get_main_menu()
            )
        else:
            # Попытка автоматически определить, хочет ли пользователь добавить слово
            if len(text.split()) >= 2:
                context.args = text.split()
                await self.add_word(update, context)
            else:
                await update.message.reply_text(
                    "Я не понимаю эту команду. Используйте меню или команды.",
                    reply_markup=self._get_main_menu()
                )

    def run(self):
        """Запуск бота"""
        try:
            logger.info("Запуск бота...")
            self.application.run_polling()
        except Exception as e:
            logger.critical(f"Фатальная ошибка: {e}")
        finally:
            close_all_sessions()
            self.db.engine.dispose()
            logger.info("Бот остановлен")


# ==================== ЗАПУСК ПРИЛОЖЕНИЯ ====================
if __name__ == "__main__":
    try:
        bot = VocabularyBot()
        bot.run()
    except Exception as e:
        logger.critical(f"Не удалось запустить бота: {e}")
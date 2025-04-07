import logging
import os

from dotenv import load_dotenv

from BaseModel import Word

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

# Настройка логгирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()


# ==================== КЛАСС ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ ====================
class DatabaseManager:
    def __init__(self):
        self.engine = self._create_engine()
        self.Session = sessionmaker(bind=self.engine)

    def _create_engine(self):
        """Создание подключения к PostgreSQL"""
        try:
            db_user = os.getenv('POSTGRES_USER', 'postgres')
            db_password = os.getenv('POSTGRES_PASSWORD', '')
            db_host = os.getenv('POSTGRES_HOST', 'localhost')
            db_port = os.getenv('POSTGRES_PORT', '5432')
            db_name = os.getenv('POSTGRES_DB', 'vocabulary')

            connection_string = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            engine = create_engine(
                connection_string,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                connect_args={"connect_timeout": 5}
            )

            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            logger.info("Успешное подключение к PostgreSQL")
            return engine

        except SQLAlchemyError as e:
            logger.error(f"Ошибка подключения к PostgreSQL: {e}")
            raise RuntimeError(f"Не удалось подключиться к базе данных. Проверьте параметры подключения.")

    def get_session(self):
        """Возвращает новую сессию для работы с БД"""
        return self.Session()

    def initialize_words(self):
        """Инициализация начального набора слов"""
        with self.get_session() as session:
            try:
                if not session.query(Word).count():
                    initial_words = [
                        ("красный", "red"), ("синий", "blue"), ("зеленый", "green"),
                        ("желтый", "yellow"), ("черный", "black"), ("белый", "white"),
                        ("я", "I"), ("ты", "you"), ("он", "he"), ("она", "she")
                    ]
                    for ru, en in initial_words:
                        if not session.query(Word).filter_by(target_word=ru, translate_word=en).first():
                            session.add(Word(target_word=ru, translate_word=en))
                    session.commit()
                    logger.info("Добавлены начальные слова")
            except Exception as e:
                session.rollback()
                logger.error(f"Ошибка инициализации слов: {e}")
                raise

import logging

from dotenv import load_dotenv

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

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()



# ==================== МОДЕЛИ БАЗЫ ДАННЫХ ====================
Base = declarative_base()


class Word(Base):
    __tablename__ = 'words'
    id = Column(Integer, primary_key=True)
    target_word = Column(String(255), nullable=False)  # Слово на русском
    translate_word = Column(String(255), nullable=False)  # Перевод на английский
    user_words = relationship("UserWord", backref="word")
    ignore_words = relationship("IgnoreWord", backref="word")


class UserWord(Base):
    __tablename__ = 'user_words'
    __table_args__ = (
        Index('idx_user_word', 'user_id', 'word_id', unique=True),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    word_id = Column(Integer, ForeignKey('words.id'), nullable=False)
    passed_word = Column(Boolean, default=False, nullable=False)  # Флаг изучения слова


class IgnoreWord(Base):
    __tablename__ = 'ignore_words'
    __table_args__ = (
        Index('idx_ignore_word', 'user_id', 'word_id', unique=True),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    word_id = Column(Integer, ForeignKey('words.id'), nullable=False)
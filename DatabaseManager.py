import os




Base = declarative_base()

class Word(Base):
    __tablename__ = 'words'
    id = Column(Integer, primary_key=True)
    target_word = Column(String(255), nullable=False)
    translate_word = Column(String(255), nullable=False)
    user_words = relationship("UserWord", backref="word")
    ignore_words = relationship("IgnoreWord", backref="word")

class UserWord(Base):
    __tablename__ = 'user_words'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    word_id = Column(Integer, ForeignKey('words.id'), nullable=False)
    passed_word = Column(Boolean, default=False, nullable=False)

class IgnoreWord(Base):
    __tablename__ = 'ignore_words'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    word_id = Column(Integer, ForeignKey('words.id'), nullable=False)

class AnotherWord(Base):
    __tablename__ = 'another_words'
    id = Column(Integer, primary_key=True)
    other_word = Column(String(255), nullable=False)

# Инициализация базы данных
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///vocabulary.db')
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
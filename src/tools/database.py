from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, DECIMAL, Enum
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
import enum

DATABASE_URL = "sqlite:///finance_bot_sqlalchemy.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class TransactionType(enum.Enum):
    RECEITA = "receita"
    DESPESA = "despesa"

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(String(500))
    date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
class Category(Base):
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    

class Budget(Base):
    __tablename__ = 'budgets'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    category = Column(String(100), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    month = Column(String(10), nullable=False)

def init_database():
    """Criar todas as tabelas no banco de dados"""
    try:
        Base.metadata.create_all(engine)
        print("✅ Banco de dados criado com sucesso!")
        return True
    except Exception as e:
        print(f"❌ Erro ao criar banco: {e}")
        return False

def get_session():
    """Obter nova sessão do banco"""
    return Session()

class Database:
    def __init__(self):
        self.engine = engine
        self.SessionLocal = sessionmaker(bind=engine)
    
    def get_session(self):
        return self.SessionLocal()
    
    def init_database(self):
        return init_database()

if __name__ == "__main__":
    init_database()

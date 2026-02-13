from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, DECIMAL, CheckConstraint, Enum
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
import enum


# Engine - Fácil de mudar para outros bancos
DATABASE_URL = "sqlite:///finance_bot_sqlalchemy.db"
# Para mudar para PostgreSQL: "postgresql://user:password@localhost/dbname"
# Para MySQL: "mysql+pymysql://user:password@localhost/dbname"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

Base = declarative_base()

class TransactionType(enum.Enum):
    RECEITA = "receita"
    DESPESA = "despesa"

# Modelos ORM
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
    
    # O Enum já garante a validação dos valores

class Category(Base):
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    
    # Check constraint para garantir que type seja 'DESPESA' ou 'RECEITA'
    __table_args__ = (
        CheckConstraint("type IN ('DESPESA', 'RECEITA')", name='check_category_type'),
    ) 
 
class Budget(Base):
    __tablename__ = 'budgets'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    category = Column(String(100), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    month = Column(String(10), nullable=False)

# Função de inicialização
def init_database():
    """Criar todas as tabelas no banco de dados"""
    try:
        Base.metadata.create_all(engine)
        print("✅ Banco de dados criado com sucesso!")
        return True
    except Exception as e:
        print(f"❌ Erro ao criar banco: {e}")
        return False

# Função para obter sessão
def get_session():
    """Obter nova sessão do banco"""
    return Session()

# Classe Database para compatibilidade
class Database:
    def __init__(self):
        self.engine = engine
        self.SessionLocal = sessionmaker(bind=engine)
    
    def get_session(self):
        return self.SessionLocal()
    
    def init_database(self):
        return init_database()

# Criar banco ao importar
if __name__ == "__main__":
    init_database()
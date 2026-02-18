
from telegram import Update
from telegram.ext import ContextTypes
from tools.database import get_session, Transaction, TransactionType
from datetime import date

async def add_transaction(user_id: int, trans_type: str, amount: float, category: str, description: str = ""):
    """ Função que adiciona uma transação ao banco de dados """
    session = get_session()
    try:
        # Converter string para enum
        if trans_type == "receita":
            trans_type_enum = TransactionType.RECEITA
        elif trans_type == "despesa":
            trans_type_enum = TransactionType.DESPESA
        else:
            return f"❌ Tipo de transação inválido: {trans_type}"
        
        transaction = Transaction(
            user_id=user_id,
            type=trans_type_enum,
            amount=amount,
            category=category,
            description=description,
            date=date.today()
        )
        session.add(transaction)
        session.commit()
        
        emoji = "💰" if trans_type == "receita" else "💸"
        return f"{emoji} {trans_type.title()} de R${amount:.2f} em '{category}' registrada com sucesso!"
    except Exception as e:
        session.rollback()
        return f"❌ Erro ao registrar transação: {str(e)}"
    finally:
        session.close()



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


async def adicionar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ Função que interage com o usuário para adicionar uma transação ao banco de dados """
    user_id = update.effective_user.id
    
    if len(context.args) < 3:
        await update.message.reply_text(
            "❌ Formato incorreto!\n\n"
            "Use: /adicionar <tipo> <valor> <categoria>\n"
            "Exemplo: /adicionar despesa 50.00 alimentação"
        )
        return
    
    trans_type = context.args[0].lower()
    if trans_type not in ['receita', 'despesa']:
        await update.message.reply_text("❌ Tipo deve ser 'receita' ou 'despesa'")
        return
    
    try:
        amount = float(context.args[1].replace(',', '.'))
        category = ' '.join(context.args[2:])
        
        result = await add_transaction(user_id, trans_type, amount, category)
        await update.message.reply_text(result)
        
    except ValueError:
        await update.message.reply_text("❌ Valor inválido! Use um número como 50.00")

from telegram import Update
from telegram.ext import ContextTypes
from tools.database import get_session, Transaction, TransactionType
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


async def get_user_transactions(user_id: int, limit: int = 10):
    session = get_session()
    try:
        transactions = session.query(Transaction).filter(
            Transaction.user_id == user_id
        ).order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit).all()
        
        return [
            {
                'id': t.id,
                'type': 'receita' if t.type == TransactionType.RECEITA else 'despesa',
                'amount': float(t.amount),
                'category': t.category,
                'date': t.date.strftime('%Y-%m-%d'),
                'description': t.description
            }
            for t in transactions
        ]
    except Exception as e:
        print(f"Erro ao buscar transações: {e}")
        return []
    finally:
        session.close()

async def excluir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if len(context.args) == 0:
        transactions = await get_user_transactions(user_id, 10)
        
        if not transactions:
            await update.message.reply_text("📊 Nenhuma transação encontrada.")
            return

        message = "📝 *Últimas 10 Transações*\n\n"
        
        for trans in transactions:
            emoji = "💰" if trans['type'] == "receita" else "💸"
            message += f"{emoji} *#{trans['id']}* R${trans['amount']:.2f} - {trans['category']}\n"
            message += f"   📅 {trans['date']}\n"
            if trans['description']:
                message += f"   📝 {trans['description']}\n"
            message += "\n"
        
        message += "💡 Use /excluir <id> para excluir uma transação"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "❌ Formato incorreto!\n\n"
            "Use: /excluir <id>\n"
            "Exemplo: /excluir 5\n\n"
            "💡 Para ver os IDs: /excluir (sem argumentos) ou /recentes"
        )
        return
    
    try:
        transaction_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID deve ser um número!")
        return
    
    session = get_session()
    try:
        transaction = session.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id
        ).first()
        
        if not transaction:
            await update.message.reply_text("❌ Transação não encontrada!")
            return
        
        # Confirmação antes de excluir
        keyboard = [
            [
                InlineKeyboardButton("✅ Sim, excluir", callback_data=f"confirm_delete_{transaction_id}"),
                InlineKeyboardButton("❌ Cancelar", callback_data=f"cancel_delete_{transaction_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        emoji = "💰" if transaction.type == TransactionType.RECEITA else "💸"
        type_str = "receita" if transaction.type == TransactionType.RECEITA else "despesa"
        await update.message.reply_text(
            f"⚠️ Tem certeza que deseja excluir?\n\n"
            f"{emoji} {type_str.title()}: R${transaction.amount:.2f}\n"
            f"📁 Categoria: {transaction.category}\n"
            f"📅 Data: {transaction.date}\n\n"
            f"ID: #{transaction.id}",
            reply_markup=reply_markup
        )
    except Exception as e:
        session.rollback()
        print(f"Erro ao excluir transação: {e}")
    finally:
        session.close()

from telegram import Update
from telegram.ext import ContextTypes
from tools.database import get_session, Transaction, TransactionType
from datetime import date

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    session = get_session()
    try:
        from sqlalchemy import func
        
        results = session.query(
            Transaction.type,
            func.sum(Transaction.amount).label('total')
        ).filter(
            Transaction.user_id == user_id,
            Transaction.date >= date.today().replace(day=1)
        ).group_by(Transaction.type).all()
        
        receitas = 0
        despesas = 0
        
        for trans_type, total in results:
            if trans_type == TransactionType.RECEITA:
                receitas = float(total)
            elif trans_type == TransactionType.DESPESA:
                despesas = float(total)
        
        saldo_atual = receitas - despesas
        
        message = f"💳 *Saldo do Mês*\n\n"
        message += f"💰 Receitas: R${receitas:.2f}\n"
        message += f"💸 Despesas: R${despesas:.2f}\n"
        message += f"💵 *Saldo: R${saldo_atual:.2f}*\n\n"
        
        if saldo_atual < 0:
            message += "⚠️ Atenção: Você está com saldo negativo este mês!"
        elif saldo_atual > 0:
            message += "✅ Ótimo: Seu saldo está positivo!"
        else:
            message += "📊 Seu saldo está zerado este mês."
        
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        print(f"Erro ao buscar saldo: {e}")
    finally:
        session.close()

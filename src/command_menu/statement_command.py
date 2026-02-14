from telegram import Update
from telegram.ext import ContextTypes
from tools.database import get_session, Transaction, TransactionType
from datetime import datetime, date
import calendar

async def get_user_transactions(user_id: int):
    """
    Busca as transações do usuário do mês e ano corrente.
    """
    session = get_session()
    try:
        # Obter data atual
        today = date.today()
        current_year = today.year
        current_month = today.month
        
        # Calcular o último dia do mês corrente
        last_day_of_month = calendar.monthrange(current_year, current_month)[1]
        
        # Filtrar transações do mês e ano corrente
        transactions = session.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.date >= date(current_year, current_month, 1),
            Transaction.date <= date(current_year, current_month, last_day_of_month)
        ).order_by(Transaction.date.desc(), Transaction.id.desc()).all()
        
        return [
            {
                'id': t.id,
                'type': 'receita' if t.type == TransactionType.RECEITA else 'despesa',
                'amount': float(t.amount),
                'category': t.category,
                'date': t.date.strftime('%d/%m/%Y'),
                'description': t.description
            }
            for t in transactions
        ]
    except Exception as e:
        print(f"Erro ao buscar transações: {e}")
        return []
    finally:
        session.close()

async def extrato(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Exibe o extrato do usuário com as transações do mês corrente.
    """
    user_id = update.effective_user.id
    transactions = await get_user_transactions(user_id)
    
    if not transactions:
        await update.message.reply_text(
            "📋 *Extrato do Mês*\n\n"
            "Nenhuma transação encontrada para este mês.\n\n"
            "Use /adicionar para registrar suas transações!"
        )
        return
    
    # Calcular totais
    total_receitas = sum(t['amount'] for t in transactions if t['type'] == 'receita')
    total_despesas = sum(t['amount'] for t in transactions if t['type'] == 'despesa')
    saldo = total_receitas - total_despesas
    
    # Formatar mensagem
    message = "📋 *Extrato do Mês*\n\n"
    
    # Adicionar resumo
    message += f"💰 *Receitas:* R$ {total_receitas:.2f}\n"
    message += f"💸 *Despesas:* R$ {total_despesas:.2f}\n"
    message += f"📊 *Saldo:* R$ {saldo:.2f}\n\n"
    
    # Adicionar transações
    message += "*Transações:*\n"
    for trans in transactions:
        emoji = "💰" if trans['type'] == 'receita' else "💸"
        desc = f" - {trans['description']}" if trans['description'] else ""
        message += f"{emoji} {trans['date']} - {trans['category']}: R$ {trans['amount']:.2f}{desc}\n"
    
    await update.message.reply_text(message)

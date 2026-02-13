from telegram import Update
from telegram.ext import ContextTypes
from tools.database import get_session, Transaction, TransactionType
from datetime import date

async def relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Gera um relatório com as transações do mês atual.
    """
    user_id = update.effective_user.id

    session = get_session()
    try:
        from sqlalchemy import func

        results = session.query(
            Transaction.category,
            Transaction.type,
            func.sum(Transaction.amount).label('total'),
            func.count(Transaction.id).label('count')
        ).filter(
            Transaction.user_id == user_id,
            Transaction.date >= date.today().replace(day=1)
        ).group_by(Transaction.category, Transaction.type).order_by(func.sum(Transaction.amount).desc()).all()

        if not results:
            await update.message.reply_text("📊 Nenhuma transação encontrada este mês.")
            return

        message = f"📊 *Relatório do Mês*\n\n"

        receitas_por_categoria = {}
        despesas_por_categoria = {}
        total_receitas = 0
        total_despesas = 0

        for category, trans_type, total, count in results:
            total = float(total)
            if trans_type == TransactionType.RECEITA:
                receitas_por_categoria[category] = {'total': total, 'count': count}
                total_receitas += total
            else:
                despesas_por_categoria[category] = {'total': total, 'count': count}
                total_despesas += total

        if receitas_por_categoria:
            message += "💰 *Receitas:*\n"
            for category, data in receitas_por_categoria.items():
                message += f"  • {category}: R${data['total']:.2f}\n"
            message += f"  • *Total Receitas: R${total_receitas:.2f}*\n\n"

        if despesas_por_categoria:
            message += "💸 *Despesas:*\n"
            for category, data in despesas_por_categoria.items():
                message += f"  • {category}: R${data['total']:.2f}\n"
            message += f"  • *Total Despesas: R${total_despesas:.2f}*\n\n"

        saldo = total_receitas - total_despesas
        message += f"💵 *Saldo Líquido: R${saldo:.2f}*"

        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        print(f"Erro ao buscar relatório: {e}")
    finally:
        session.close()

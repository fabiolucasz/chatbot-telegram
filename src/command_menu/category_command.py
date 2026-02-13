from telegram import Update
from telegram.ext import ContextTypes
from tools.database import get_session, Category, TransactionType


async def categorias(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Exibe as categorias de receitas e despesas do usuário.
    """
    user_id = update.effective_user.id
    
    session = get_session()
    try:
        categories = session.query(Category).filter(
            Category.user_id == user_id
        ).order_by(Category.type, Category.name).all()
        
        if not categories:
            await update.message.reply_text("Nenhuma categoria encontrada.")
            return
        
        message = "📁 *Suas Categorias*\n\n"
        
        receitas = []
        despesas = []
        
        for cat in categories:
            if cat.type == TransactionType.RECEITA:
                receitas.append(cat.name)
            else:
                despesas.append(cat.name)
        
        if receitas:
            message += "💰 *Receitas:*\n"
            for cat in receitas:
                message += f"  • {cat}\n"
            message += "\n"
        
        if despesas:
            message += "💸 *Despesas:*\n"
            for cat in despesas:
                message += f"  • {cat}\n"
            message += "\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        print(f"Erro ao buscar categorias: {e}")
    finally:
        session.close()

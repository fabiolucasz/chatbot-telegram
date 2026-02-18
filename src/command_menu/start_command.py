
from tools.database import get_session, Category, TransactionType
from telegram import Update
from telegram.ext import ContextTypes


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ 
    Função que é chamada quando o usuário executa o comando /start
    """
    user_id = update.effective_user.id
    
    # Add default categories for new users using SQLAlchemy
    session = get_session()
    try:
        default_expense_categories = ["alimentação", "transporte", "moradia", "lazer", "saúde", "educação", "outros"]
        default_income_categories = ["salário", "freelancer", "investimentos", "outros"]
        
        for cat in default_expense_categories:
            category = Category(user_id=user_id, name=cat, type=TransactionType.DESPESA)
            session.merge(category)  # Usar merge para evitar duplicatas
        
        for cat in default_income_categories:
            category = Category(user_id=user_id, name=cat, type=TransactionType.RECEITA)
            session.merge(category)  # Usar merge para evitar duplicatas
        
        session.commit()
        
        await update.message.reply_text(
            f"👋 Olá {update.effective_user.first_name}!\n\n"
            "Sou seu assistente financeiro pessoal!\n\n"
            "💡 *Mensagens inteligentes:*\n"
            "'gastei 50 reais com alimentação - almoço no trabalho'\n"
            "'recebi 1000 de salário - pagamento mensal'\n"
            "'comprei material de escritório por 150 reais'\n"
            "'paguei aluguel de 800 - apartamento'\n"
            "'ganhei 500 freelancer - projeto website'\n\n"
            
            "📌 Comandos disponíveis:\n"
            "/saldo - Ver seu saldo atual\n"
            "/relatorio - Ver relatório do mês\n"
            "/categorias - Listar categorias\n"
            "/metas - Gerenciar metas financeiras\n"
            "/excluir - Excluir transação\n"
            "/extrato - Ver extrato\n\n"
            
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao configurar categorias: {str(e)}")
    finally:
        session.close()
from telegram import Update
from telegram.ext import ContextTypes

async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ Função que interage com o usuário para mostrar ajuda '/ajuda' """
    
    message = "🤖 *Ajuda do Bot Financeiro*\n\n"
    message += "📌 *Comandos:*\n"
    message += "/start - Iniciar o bot\n"
    message += "/adicionar <tipo> <valor> <categoria> - Adicionar transação\n"
    message += "/editar <id> [valor] [categoria] - Editar transação (ou /editar para ver últimos 10)\n"
    message += "/excluir <id> - Excluir transação\n"
    message += "/recentes - Listar transações recentes\n"
    message += "/saldo - Ver saldo do mês\n"
    message += "/relatorio - Relatório detalhado\n"
    message += "/categorias - Listar categorias\n"
    message += "/metas - Metas financeiras\n"
    message += "/ajuda - Esta ajuda\n\n"
    message += "💡 *Mensagens inteligentes:*\n"
    message += "'gastei 50 reais com alimentação - almoço no trabalho'\n"
    message += "'recebi 1000 de salário - pagamento mensal'\n"
    message += "'comprei material de escritório por 150 reais'\n"
    message += "'paguei aluguel de 800 - apartamento'\n"
    message += "'ganhei 500 freelancer - projeto website'\n\n"
    message += "🔧 *Gerenciamento:*\n"
    message += "Use /recentes para ver os IDs das transações\n"
    message += "Use /editar <id> para modificar\n"
    message += "Use /excluir <id> para remover"

    await update.message.reply_text(message, parse_mode='Markdown')

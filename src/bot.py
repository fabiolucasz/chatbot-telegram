import os
import re
from datetime import date
from typing import Optional, Dict
from dotenv import load_dotenv
from telegram import Update
from command_menu.start_command import start
from command_menu.add_command import adicionar, add_transaction
from command_menu.balance_command import saldo
from command_menu.help_command import ajuda
from command_menu.delete_command import excluir
from command_menu.edit_command import editar
from command_menu.category_command import categorias
from command_menu.goal_command import metas
from command_menu.report_command import relatorio
from command_menu.statement_command import extrato

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from photo_handler import handle_photo, handle_document, nf_callback_handler
from tools.database import get_session, Transaction, Category, TransactionType, Budget, init_database

# Load environment variables
load_dotenv()

# Get bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize database
init_database()
# Funções usando SQLAlchemy

def parse_financial_message(text: str) -> Optional[Dict]:
    text = text.lower()
    
    # Patterns for expense messages - mais flexíveis para capturar descrição
    expense_patterns = [
        r'gastei\s+r?\$?\s*(\d+(?:[.,]\d+)?)\s*(?:reais?\s*)?(?:com|em|para|de|do|da)?\s*([\w\s]+)(?:\s*[-:]\s*(.+))?',
        r'despesa\s+(\d+(?:[.,]\d+)?)\s*([\w\s]+)(?:\s*[-:]\s*(.+))?',
        r'paguei\s+r?\$?\s*(\d+(?:[.,]\d+)?)\s*(?:reais?\s*)?(?:com|em|para|de|do|da)?\s*([\w\s]+)(?:\s*[-:]\s*(.+))?',
        r'comprei\s+([\w\s]+?)\s*por\s+r?\$?\s*(\d+(?:[.,]\d+)?)\s*(?:reais?)?',
        r'pago\s+([\w\s]+?)\s*de\s+r?\$?\s*(\d+(?:[.,]\d+)?)\s*(?:reais?)?'
    ]
    
    # Pattern for income messages - mais flexíveis para capturar descrição
    income_patterns = [
        r'recebi\s+r?\$?\s*(\d+(?:[.,]\d+)?)\s*(?:reais?\s*)?(?:de|do|da)?\s*([\w\s]+)(?:\s*[-:]\s*(.+))?',
        r'renda\s+(\d+(?:[.,]\d+)?)\s*([\w\s]+)(?:\s*[-:]\s*(.+))?',
        r'ganhei\s+r?\$?\s*(\d+(?:[.,]\d+)?)\s*(?:reais?\s*)?(?:com|em)?\s*([\w\s]+)(?:\s*[-:]\s*(.+))?',
        r'depositei\s+r?\$?\s*(\d+(?:[.,]\d+)?)\s*(?:reais?\s*)?(?:na|em)?\s*([\w\s]+)(?:\s*[-:]\s*(.+))?',
        r'entraram\s+r?\$?\s*(\d+(?:[.,]\d+)?)\s*(?:reais?\s*)?(?:na|em)?\s*([\w\s]+)(?:\s*[-:]\s*(.+))?'
    ]
    
    # Verificar patterns de despesa
    for pattern in expense_patterns:
        match = re.search(pattern, text)
        if match:
            # Para patterns "comprei" e "pago", a ordem é diferente
            if 'comprei' in pattern or 'pago' in pattern:
                category = match.group(1).strip()
                amount = float(match.group(2).replace(',', '.'))
                description = f'compra por {amount}' if 'comprei' in pattern else f'pagamento de {amount}'
            else:
                amount = float(match.group(1).replace(',', '.'))
                category = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else ''
                description = match.group(3).strip() if len(match.groups()) > 2 and match.group(3) else ''
            
            if category:
                return {'type': 'despesa', 'amount': amount, 'category': category, 'description': description}
    
    # Verificar patterns de receita
    for pattern in income_patterns:
        match = re.search(pattern, text)
        if match:
            amount = float(match.group(1).replace(',', '.'))
            category = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else ''
            description = match.group(3).strip() if len(match.groups()) > 2 and match.group(3) else ''
            
            if category:
                return {'type': 'receita', 'amount': amount, 'category': category, 'description': description}
    
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_id = update.effective_user.id
    
    # Try to parse as financial message
    parsed = parse_financial_message(text)
    
    if parsed:
        description = parsed.get('description', '')
        result = await add_transaction(user_id, parsed['type'], parsed['amount'], parsed['category'], description)
        await update.message.reply_text(result)
    else:
        await update.message.reply_text(
            "❌ Não entendi sua mensagem.\n\n"
            "Tente algo como:\n"
            "'gastei 50 reais com alimentação'\n"
            "'recebi 1000 de salário'\n\n"
            "Ou use /ajuda para ver todos os comandos."
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks for delete confirmation and NF processing"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    if data.startswith("confirm_delete_"):
        transaction_id = int(data.split("_")[2])
        
        success = await delete_transaction(user_id, transaction_id)
        
        if success:
            # Buscar transação para mostrar mensagem
            session = get_session()
            try:
                transaction = session.query(Transaction).filter(
                    Transaction.id == transaction_id,
                    Transaction.user_id == user_id
                ).first()
                
                if transaction:
                    emoji = "💰" if transaction.type == TransactionType.RECEITA else "💸"
                    type_str = "receita" if transaction.type == TransactionType.RECEITA else "despesa"
                    await query.edit_message_text(
                        f"✅ {emoji} Transação #{transaction_id} excluída com sucesso!\n\n"
                        f"{type_str.title()}: R${transaction.amount:.2f} em {transaction.category}"
                    )
                else:
                    await query.edit_message_text("❌ Transação não encontrada!")
            except Exception as e:
                print(f"Erro ao buscar transação para exclusão: {e}")
            finally:
                session.close()
        else:
            await query.edit_message_text("❌ Falha ao excluir transação!")
        
    elif data.startswith("cancel_delete_"):
        await query.edit_message_text("❌ Exclusão cancelada.")


app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("adicionar", adicionar))
app.add_handler(CommandHandler("editar", editar))
app.add_handler(CommandHandler("excluir", excluir))
app.add_handler(CommandHandler("saldo", saldo))
app.add_handler(CommandHandler("relatorio", relatorio))
app.add_handler(CommandHandler("categorias", categorias))
app.add_handler(CommandHandler("metas", metas))
app.add_handler(CommandHandler("extrato", extrato))
app.add_handler(CommandHandler("ajuda", ajuda))

app.add_handler(CallbackQueryHandler(button_callback, pattern="^(confirm_delete_|cancel_delete_)"))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
app.add_handler(CallbackQueryHandler(nf_callback_handler, pattern=r'^(add_all_nf|cancel_nf)$'))

print("🤖 Bot financeiro iniciado!")
app.run_polling()
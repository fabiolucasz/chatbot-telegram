import os
import sqlite3
import re
from datetime import datetime, date
from decimal import Decimal
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters


# Load environment variables
load_dotenv()

# Get bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_NAME = "finance_bot.db"


def init_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('receita', 'despesa')),
            amount DECIMAL(10,2) NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('receita', 'despesa')),
            UNIQUE(user_id, name)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            month TEXT NOT NULL,
            UNIQUE(user_id, category, month)
        )
    """)
    
    conn.commit()
    conn.close()

init_database()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    # Add default categories for new users
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    default_expense_categories = ["alimentação", "transporte", "moradia", "lazer", "saúde", "educação", "outros"]
    default_income_categories = ["salário", "freelancer", "investimentos", "outros"]
    
    for cat in default_expense_categories:
        cursor.execute("INSERT OR IGNORE INTO categories (user_id, name, type) VALUES (?, ?, ?)", 
                      (user_id, cat, "despesa"))
    
    for cat in default_income_categories:
        cursor.execute("INSERT OR IGNORE INTO categories (user_id, name, type) VALUES (?, ?, ?)", 
                      (user_id, cat, "receita"))
    
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"👋 Olá {update.effective_user.first_name}!\n\n"
        "Sou seu assistente financeiro pessoal!\n\n"
        "📌 Comandos disponíveis:\n"
        "/adicionar <tipo> <valor> <categoria> - Adicionar transação\n"
        "/saldo - Ver seu saldo atual\n"
        "/relatorio - Ver relatório do mês\n"
        "/categorias - Listar categorias\n"
        "/metas - Gerenciar metas financeiras\n\n"
        "💡 Você também pode enviar mensagens como:\n"
        "'gastei 50 reais com alimentação'\n"
        "'recebi 1000 de salário'"
    )

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Hello {update.effective_user.first_name}')

def parse_financial_message(text: str):
    text = text.lower().strip()
    
    # Pattern for expense messages
    expense_patterns = [
        r'gastei\s+r?\$?\s*(\d+(?:[.,]\d+)?)\s*(?:reais?\s*)?(?:com|em|para)?\s*([\w\s]+)',
        r'despesa\s+(\d+(?:[.,]\d+)?)\s*([\w\s]+)',
        r'paguei\s+r?\$?\s*(\d+(?:[.,]\d+)?)\s*(?:reais?\s*)?(?:com|em|para)?\s*([\w\s]+)'
    ]
    
    # Pattern for income messages
    income_patterns = [
        r'recebi\s+r?\$?\s*(\d+(?:[.,]\d+)?)\s*(?:reais?\s*)?(?:de|do|da)?\s*([\w\s]+)',
        r'renda\s+(\d+(?:[.,]\d+)?)\s*([\w\s]+)',
        r'ganhei\s+r?\$?\s*(\d+(?:[.,]\d+)?)\s*(?:reais?\s*)?(?:com|em)?\s*([\w\s]+)'
    ]
    
    for pattern in expense_patterns:
        match = re.search(pattern, text)
        if match:
            amount = float(match.group(1).replace(',', '.'))
            category = match.group(2).strip()
            return {'type': 'despesa', 'amount': amount, 'category': category}
    
    for pattern in income_patterns:
        match = re.search(pattern, text)
        if match:
            amount = float(match.group(1).replace(',', '.'))
            category = match.group(2).strip()
            return {'type': 'receita', 'amount': amount, 'category': category}
    
    return None

async def add_transaction(user_id: int, trans_type: str, amount: float, category: str, description: str = ""):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Check if category exists, if not add it
    cursor.execute("SELECT id FROM categories WHERE user_id = ? AND name = ? AND type = ?", 
                   (user_id, category, trans_type))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO categories (user_id, name, type) VALUES (?, ?, ?)", 
                       (user_id, category, trans_type))
    
    # Insert transaction
    cursor.execute("""
        INSERT INTO transactions (user_id, type, amount, category, description, date)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, trans_type, amount, category, description, date.today()))
    
    conn.commit()
    conn.close()
    
    emoji = "💰" if trans_type == "receita" else "💸"
    return f"{emoji} {trans_type.title()} de R${amount:.2f} em '{category}' registrada com sucesso!"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_id = update.effective_user.id
    
    # Try to parse as financial message
    parsed = parse_financial_message(text)
    
    if parsed:
        result = await add_transaction(user_id, parsed['type'], parsed['amount'], parsed['category'])
        await update.message.reply_text(result)
    else:
        await update.message.reply_text(
            "❌ Não entendi sua mensagem.\n\n"
            "Tente algo como:\n"
            "'gastei 50 reais com alimentação'\n"
            "'recebi 1000 de salário'\n\n"
            "Ou use /ajuda para ver todos os comandos."
        )

async def adicionar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            type,
            SUM(amount) as total
        FROM transactions 
        WHERE user_id = ? AND date >= date('now', 'start of month')
        GROUP BY type
    """, (user_id,))
    
    results = cursor.fetchall()
    conn.close()
    
    receitas = 0
    despesas = 0
    
    for trans_type, total in results:
        if trans_type == 'receita':
            receitas = float(total)
        elif trans_type == 'despesa':
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

async def relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            category,
            type,
            SUM(amount) as total,
            COUNT(*) as count
        FROM transactions 
        WHERE user_id = ? AND date >= date('now', 'start of month')
        GROUP BY category, type
        ORDER BY total DESC
    """, (user_id,))
    
    results = cursor.fetchall()
    conn.close()
    
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
        if trans_type == 'receita':
            receitas_por_categoria[category] = total
            total_receitas += total
        else:
            despesas_por_categoria[category] = total
            total_despesas += total
    
    if receitas_por_categoria:
        message += "💰 *Receitas:*\n"
        for category, total in receitas_por_categoria.items():
            message += f"  • {category}: R${total:.2f}\n"
        message += f"  • *Total Receitas: R${total_receitas:.2f}*\n\n"
    
    if despesas_por_categoria:
        message += "💸 *Despesas:*\n"
        for category, total in despesas_por_categoria.items():
            message += f"  • {category}: R${total:.2f}\n"
        message += f"  • *Total Despesas: R${total_despesas:.2f}*\n\n"
    
    saldo = total_receitas - total_despesas
    message += f"💵 *Saldo Líquido: R${saldo:.2f}*"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def categorias(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name, type FROM categories 
        WHERE user_id = ? 
        ORDER BY type, name
    """, (user_id,))
    
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        await update.message.reply_text("Nenhuma categoria encontrada.")
        return
    
    message = "📁 *Suas Categorias*\n\n"
    
    receitas = []
    despesas = []
    
    for name, trans_type in results:
        if trans_type == 'receita':
            receitas.append(name)
        else:
            despesas.append(name)
    
    if receitas:
        message += "💰 *Receitas:*\n"
        for cat in receitas:
            message += f"  • {cat}\n"
        message += "\n"
    
    if despesas:
        message += "💸 *Despesas:*\n"
        for cat in despesas:
            message += f"  • {cat}\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def metas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎯 *Metas Financeiras*\n\n"
        "Esta funcionalidade está em desenvolvimento!\n\n"
        "Em breve você poderá:\n"
        "• Definir metas de economia\n"
        "• Acompanhar progresso\n"
        "• Receber alertas"
    )

async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = "🤖 *Ajuda do Bot Financeiro*\n\n"
    message += "📌 *Comandos:*\n"
    message += "/start - Iniciar o bot\n"
    message += "/adicionar <tipo> <valor> <categoria> - Adicionar transação\n"
    message += "/saldo - Ver saldo do mês\n"
    message += "/relatorio - Relatório detalhado\n"
    message += "/categorias - Listar categorias\n"
    message += "/metas - Metas financeiras\n"
    message += "/ajuda - Esta ajuda\n\n"
    message += "💡 *Mensagens inteligentes:*\n"
    message += "'gastei 50 reais com alimentação'\n"
    message += "'recebi 1000 de salário'\n"
    message += "'paguei 200 de aluguel'\n"
    message += "'ganhei 500 freelancer'"
    
    await update.message.reply_text(message, parse_mode='Markdown')

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("hello", hello))
app.add_handler(CommandHandler("adicionar", adicionar))
app.add_handler(CommandHandler("saldo", saldo))
app.add_handler(CommandHandler("relatorio", relatorio))
app.add_handler(CommandHandler("categorias", categorias))
app.add_handler(CommandHandler("metas", metas))
app.add_handler(CommandHandler("ajuda", ajuda))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🤖 Bot financeiro iniciado!")
app.run_polling()
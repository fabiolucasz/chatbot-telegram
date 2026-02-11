import os
import sqlite3
import re
from datetime import datetime, date
from decimal import Decimal
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler


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
        "/metas - Gerenciar metas financeiras\n"
        "/excluir - Excluir transação\n"
        "/recentes - Ver últimas transações\n\n"
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

async def editar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    # Se não fornecer argumentos, mostra últimos 10 registros
    if len(context.args) == 0:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, type, amount, category, date, description
            FROM transactions 
            WHERE user_id = ? 
            ORDER BY date DESC, id DESC 
            LIMIT 10
        """, (user_id,))
        
        transactions = cursor.fetchall()
        conn.close()
        
        if not transactions:
            await update.message.reply_text("📊 Nenhuma transação encontrada.")
            return
        
        message = "📝 *Últimas 10 Transações*\n\n"
        
        for trans_id, trans_type, amount, category, trans_date, description in transactions:
            emoji = "💰" if trans_type == "receita" else "💸"
            message += f"{emoji} *#{trans_id}* R${amount:.2f} - {category}\n"
            message += f"   📅 {trans_date}\n"
            if description:
                message += f"   📝 {description}\n"
            message += "\n"
        
        message += "💡 Use /editar <id> para ver detalhes ou editar"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(
            "❌ Formato incorreto!\n\n"
            "Use: /editar <id> [novo_valor] [nova_categoria]\n"
            "Exemplo: /editar 5 75.00 transporte\n"
            "Ou apenas: /editar (para ver últimos 10)"
        )
        return
    
    try:
        transaction_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID deve ser um número!")
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Verifica se a transação existe e pertence ao usuário
    cursor.execute("""
        SELECT id, type, amount, category, description, date
        FROM transactions 
        WHERE id = ? AND user_id = ?
    """, (transaction_id, user_id))
    
    transaction = cursor.fetchone()
    if not transaction:
        conn.close()
        await update.message.reply_text("❌ Transação não encontrada!")
        return
    
    trans_id, trans_type, amount, category, description, trans_date = transaction
    
    # Se só tem o ID, mostra os detalhes
    if len(context.args) == 1:
        message = f"📝 *Transação #{trans_id}*\n\n"
        message += f"💰 Tipo: {trans_type.title()}\n"
        message += f"💵 Valor: R${amount:.2f}\n"
        message += f"📁 Categoria: {category}\n"
        message += f"📅 Data: {trans_date}\n"
        if description:
            message += f"📝 Descrição: {description}\n"
        message += f"\n💡 Para editar: /editar {trans_id} <novo_valor> <nova_categoria>"
        
        conn.close()
        await update.message.reply_text(message, parse_mode='Markdown')
        return
    
    # Tenta editar
    try:
        new_amount = float(context.args[1].replace(',', '.'))
        new_category = ' '.join(context.args[2:]) if len(context.args) > 2 else category
        
        cursor.execute("""
            UPDATE transactions 
            SET amount = ?, category = ?, description = ?
            WHERE id = ? AND user_id = ?
        """, (new_amount, new_category, description, transaction_id, user_id))
        
        conn.commit()
        conn.close()
        
        emoji = "💰" if trans_type == "receita" else "💸"
        await update.message.reply_text(
            f"✅ {emoji} Transação #{trans_id} atualizada!\n\n"
            f"Valor: R${amount:.2f} → R${new_amount:.2f}\n"
            f"Categoria: {category} → {new_category}"
        )
        
    except (ValueError, IndexError):
        conn.close()
        await update.message.reply_text(
            "❌ Formato incorreto!\n\n"
            "Use: /editar <id> <novo_valor> <nova_categoria>\n"
            "Exemplo: /editar 5 75.00 transporte"
        )

async def excluir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if len(context.args) == 0:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, type, amount, category, date, description
            FROM transactions 
            WHERE user_id = ? 
            ORDER BY date DESC, id DESC 
            LIMIT 10
        """, (user_id,))
        
        transactions = cursor.fetchall()
        conn.close()

        if not transactions:
            await update.message.reply_text("📊 Nenhuma transação encontrada.")
            return

        message = "📝 *Últimas 10 Transações*\n\n"
        
        for trans_id, trans_type, amount, category, trans_date, description in transactions:
            emoji = "💰" if trans_type == "receita" else "💸"
            message += f"{emoji} *#{trans_id}* R${amount:.2f} - {category}\n"
            message += f"   📅 {trans_date}\n"
            if description:
                message += f"   📝 {description}\n"
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
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Verifica se a transação existe e pertence ao usuário
    cursor.execute("""
        SELECT id, type, amount, category, date
        FROM transactions 
        WHERE id = ? AND user_id = ?
    """, (transaction_id, user_id))
    
    transaction = cursor.fetchone()
    if not transaction:
        conn.close()
        await update.message.reply_text("❌ Transação não encontrada!")
        return
    
    trans_id, trans_type, amount, category, trans_date = transaction
    
    # Confirmação antes de excluir
    keyboard = [
        [
            InlineKeyboardButton("✅ Sim, excluir", callback_data=f"confirm_delete_{trans_id}"),
            InlineKeyboardButton("❌ Cancelar", callback_data=f"cancel_delete_{trans_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    emoji = "💰" if trans_type == "receita" else "💸"
    await update.message.reply_text(
        f"⚠️ Tem certeza que deseja excluir?\n\n"
        f"{emoji} {trans_type.title()}: R${amount:.2f}\n"
        f"📁 Categoria: {category}\n"
        f"📅 Data: {trans_date}\n\n"
        f"ID: #{trans_id}",
        reply_markup=reply_markup
    )
    
    conn.close()

async def recentes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, type, amount, category, date, description
        FROM transactions 
        WHERE user_id = ? 
        ORDER BY date DESC, id DESC 
        LIMIT 15
    """, (user_id,))
    
    transactions = cursor.fetchall()
    conn.close()
    
    if not transactions:
        await update.message.reply_text("📊 Nenhuma transação encontrada.")
        return
    
    message = "📋 *Transações Recentes*\n\n"
    
    for trans_id, trans_type, amount, category, trans_date, description in transactions:
        emoji = "💰" if trans_type == "receita" else "💸"
        message += f"{emoji} *#{trans_id}* {trans_type.title()}: R${amount:.2f}\n"
        message += f"   📁 {category} 📅 {trans_date}\n"
        if description:
            message += f"   📝 {description}\n"
        message += "\n"
    
    message += "💡 Use /editar <id> ou /excluir <id> para modificar"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks for delete confirmation"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    if data.startswith("confirm_delete_"):
        transaction_id = int(data.split("_")[2])
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Verifica se a transação existe e pertence ao usuário
        cursor.execute("""
            SELECT id, type, amount, category
            FROM transactions 
            WHERE id = ? AND user_id = ?
        """, (transaction_id, user_id))
        
        transaction = cursor.fetchone()
        if transaction:
            trans_id, trans_type, amount, category = transaction
            
            cursor.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", 
                          (transaction_id, user_id))
            conn.commit()
            
            emoji = "💰" if trans_type == "receita" else "💸"
            await query.edit_message_text(
                f"✅ {emoji} Transação #{trans_id} excluída com sucesso!\n\n"
                f"{trans_type.title()}: R${amount:.2f} em {category}"
            )
        else:
            await query.edit_message_text("❌ Transação não encontrada!")
        
        conn.close()
        
    elif data.startswith("cancel_delete_"):
        await query.edit_message_text("❌ Exclusão cancelada.")

async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    message += "'gastei 50 reais com alimentação'\n"
    message += "'recebi 1000 de salário'\n"
    message += "'paguei 200 de aluguel'\n"
    message += "'ganhei 500 freelancer'\n\n"
    message += "🔧 *Gerenciamento:*\n"
    message += "Use /recentes para ver os IDs das transações\n"
    message += "Use /editar <id> para modificar\n"
    message += "Use /excluir <id> para remover"
    
    await update.message.reply_text(message, parse_mode='Markdown')

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("hello", hello))
app.add_handler(CommandHandler("adicionar", adicionar))
app.add_handler(CommandHandler("editar", editar))
app.add_handler(CommandHandler("excluir", excluir))
app.add_handler(CommandHandler("recentes", recentes))
app.add_handler(CommandHandler("saldo", saldo))
app.add_handler(CommandHandler("relatorio", relatorio))
app.add_handler(CommandHandler("categorias", categorias))
app.add_handler(CommandHandler("metas", metas))
app.add_handler(CommandHandler("ajuda", ajuda))

# Handler para botões de callback
app.add_handler(CallbackQueryHandler(button_callback, pattern="^(confirm_delete_|cancel_delete_)"))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🤖 Bot financeiro iniciado!")
app.run_polling()
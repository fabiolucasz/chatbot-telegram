import os
import re
from datetime import datetime, date
from decimal import Decimal
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
async def add_transaction(user_id: int, trans_type: str, amount: float, category: str, description: str = ""):
    session = get_session()
    try:
        # Converter string para enum
        if trans_type == "receita":
            trans_type_enum = TransactionType.RECEITA
        elif trans_type == "despesa":
            trans_type_enum = TransactionType.DESPESA
        else:
            return f"❌ Tipo de transação inválido: {trans_type}"
        
        transaction = Transaction(
            user_id=user_id,
            type=trans_type_enum,
            amount=amount,
            category=category,
            description=description,
            date=date.today()
        )
        session.add(transaction)
        session.commit()
        
        emoji = "💰" if trans_type == "receita" else "💸"
        return f"{emoji} {trans_type.title()} de R${amount:.2f} em '{category}' registrada com sucesso!"
    except Exception as e:
        session.rollback()
        return f"❌ Erro ao registrar transação: {str(e)}"
    finally:
        session.close()

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

async def get_monthly_summary(user_id: int):
    session = get_session()
    try:
        from sqlalchemy import func
        
        results = session.query(
            Transaction.type,
            func.sum(Transaction.amount).label('total'),
            func.count(Transaction.id).label('count')
        ).filter(
            Transaction.user_id == user_id,
            Transaction.date >= date.today().replace(day=1)
        ).group_by(Transaction.type).all()
        
        summary = {'receitas': 0, 'despesas': 0, 'receitas_count': 0, 'despesas_count': 0}
        
        for trans_type, total, count in results:
            if trans_type == 'receita':
                summary['receitas'] = float(total)
                summary['receitas_count'] = count
            elif trans_type == 'despesa':
                summary['despesas'] = float(total)
                summary['despesas_count'] = count
        
        summary['saldo'] = summary['receitas'] - summary['despesas']
        return summary
    except Exception as e:
        print(f"Erro ao buscar resumo: {e}")
        return {'receitas': 0, 'despesas': 0, 'saldo': 0}
    finally:
        session.close()

async def get_monthly_report(user_id: int):
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
        
        report = {'receitas': {}, 'despesas': {}}
        
        for category, trans_type, total, count in results:
            total = float(total)
            if trans_type == 'receita':
                report['receitas'][category] = {'total': total, 'count': count}
            else:
                report['despesas'][category] = {'total': total, 'count': count}
        
        return report
    except Exception as e:
        print(f"Erro ao buscar relatório: {e}")
        return {'receitas': {}, 'despesas': {}}
    finally:
        session.close()

async def get_user_categories(user_id: int):
    session = get_session()
    try:
        categories = session.query(Category).filter(
            Category.user_id == user_id
        ).order_by(Category.type, Category.name).all()
        
        result = {'receitas': [], 'despesas': []}
        
        for cat in categories:
            if cat.type == 'receita':
                result['receitas'].append(cat.name)
            else:
                result['despesas'].append(cat.name)
        
        return result
    except Exception as e:
        print(f"Erro ao buscar categorias: {e}")
        return {'receitas': [], 'despesas': []}
    finally:
        session.close()

async def delete_transaction(user_id: int, transaction_id: int):
    session = get_session()
    try:
        transaction = session.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id
        ).first()
        
        if transaction:
            session.delete(transaction)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        print(f"Erro ao excluir transação: {e}")
        return False
    finally:
        session.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao configurar categorias: {str(e)}")
    finally:
        session.close()
    
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
        r'gastei\s+r?\$?\s*(\d+(?:[.,]\d+)?)\s*(?:reais?\s*)?(?:com|em|para|de|do|da)?\s*([\w\s]+)',
        r'despesa\s+(\d+(?:[.,]\d+)?)\s*([\w\s]+)',
        r'paguei\s+r?\$?\s*(\d+(?:[.,]\d+)?)\s*(?:reais?\s*)?(?:com|em|para|de|do|da)?\s*([\w\s]+)'
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

async def relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

async def categorias(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    
    session = get_session()
    try:
        transaction = session.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id
        ).first()
        
        if not transaction:
            await update.message.reply_text("❌ Transação não encontrada!")
            return
        
        # Se só tem o ID, mostra os detalhes
        if len(context.args) == 1:
            type_str = "receita" if transaction.type == TransactionType.RECEITA else "despesa"
            message = f"📝 *Transação #{transaction.id}*\n\n"
            message += f"💰 Tipo: {type_str.title()}\n"
            message += f"💵 Valor: R${transaction.amount:.2f}\n"
            message += f"📁 Categoria: {transaction.category}\n"
            message += f"📅 Data: {transaction.date}\n"
            if transaction.description:
                message += f"📝 Descrição: {transaction.description}\n"
            message += f"\n💡 Para editar: /editar {transaction.id} <novo_valor> <nova_categoria>"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            return
        
        # Tenta editar
        try:
            new_amount = float(context.args[1].replace(',', '.'))
            new_category = ' '.join(context.args[2:]) if len(context.args) > 2 else transaction.category
            description = transaction.description  # Mantém a descrição original
            
            transaction.amount = new_amount
            transaction.category = new_category
            
            session.commit()
            
            emoji = "💰" if transaction.type == TransactionType.RECEITA else "💸"
            await update.message.reply_text(
                f"✅ {emoji} Transação #{transaction.id} atualizada!\n\n"
                f"Valor: R${transaction.amount:.2f} → R${new_amount:.2f}\n"
                f"Categoria: {transaction.category} → {new_category}"
            )
        
        except (ValueError, IndexError):
            await update.message.reply_text(
                "❌ Formato incorreto!\n\n"
                "Use: /editar <id> <novo_valor> <nova_categoria>\n"
                "Exemplo: /editar 5 75.00 transporte"
            )
    except Exception as e:
        session.rollback()
        print(f"Erro ao editar transação: {e}")
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

async def recentes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    transactions = await get_user_transactions(user_id, 15)
    
    if not transactions:
        await update.message.reply_text("📊 Nenhuma transação encontrada.")
        return
    
    message = "📋 *Transações Recentes*\n\n"
    
    for trans in transactions:
        emoji = "💰" if trans['type'] == "receita" else "💸"
        message += f"{emoji} *#{trans['id']}* {trans['type'].title()}: R${trans['amount']:.2f}\n"
        message += f"   📁 {trans['category']} 📅 {trans['date']}\n"
        if trans['description']:
            message += f"   📝 {trans['description']}\n"
        message += "\n"
    
    message += "💡 Use /editar <id> ou /excluir <id> para modificar"
    
    await update.message.reply_text(message, parse_mode='Markdown')

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

async def metas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎯 *Metas Financeiras*\n\n"
        "Esta funcionalidade está em desenvolvimento!\n\n"
        "Em breve você poderá:\n"
        "• Definir metas de economia\n"
        "• Acompanhar progresso\n"
        "• Receber alertas"
    )

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

app.add_handler(CallbackQueryHandler(button_callback, pattern="^(confirm_delete_|cancel_delete_)"))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
app.add_handler(CallbackQueryHandler(nf_callback_handler, pattern=r'^(add_all_nf|cancel_nf)$'))

print("🤖 Bot financeiro iniciado!")
app.run_polling()
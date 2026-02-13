from telegram import Update
from telegram.ext import ContextTypes
from tools.database import get_session, Transaction, TransactionType

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

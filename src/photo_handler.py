import os
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from read_qrcode import ReadQrcode
from tools.database import get_session, Category, TransactionType
from command_menu.add_command import add_transaction

# Instância do leitor de QR Code
qr_reader = ReadQrcode()

def get_user_expense_categories(user_id: int):
    """Obtém as categorias de despesa do usuário sem duplicatas"""
    session = get_session()
    try:
        categories = session.query(Category).filter(
            Category.user_id == user_id,
            Category.type == TransactionType.DESPESA
        ).distinct().all()
        # Remover duplicatas e ordenar
        unique_categories = list(set(cat.name for cat in categories))
        unique_categories.sort()
        return unique_categories
    except Exception as e:
        print(f"Erro ao buscar categorias: {e}")
        return ["outros"]  # Categoria padrão
    finally:
        session.close()

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para quando usuário envia uma foto"""
    user_id = update.effective_user.id
    
    try:
        # Baixar a foto para um arquivo temporário
        photo_file = await update.message.photo[-1].get_file()
        
        # Criar arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            await photo_file.download_to_drive(temp_file.name)
            temp_path = temp_file.name
        
        # Processar a imagem com o ReadQrcode
        qr_reader.image_name = temp_path
        qr_reader.image_folder = os.path.dirname(temp_path)
        
        # Extrair dados da nota fiscal
        result_data = qr_reader.extract_nf_data(temp_path)
        
        # Limpar arquivo temporário
        os.unlink(temp_path)
        
        if result_data:
            # Enviar resumo com seleção de categoria
            await send_nf_summary(update, result_data, context)
        else:
            await update.message.reply_text(
                "❌ Não foi possível ler a nota fiscal.\n\n"
                "💡 Verifique se:\n"
                "• A foto está nítida\n"
                "• O QR Code está visível\n"
                "• A nota fiscal é válida"
            )
            
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao processar a imagem: {str(e)}")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para quando usuário envia um documento (imagem)"""
    user_id = update.effective_user.id
    
    try:
        # Verificar se é uma imagem
        document = update.message.document
        
        if not document.mime_type.startswith('image/'):
            await update.message.reply_text("❌ Por favor, envie apenas arquivos de imagem (JPG, PNG).")
            return
        
        # Baixar o documento
        doc_file = await document.get_file()
        
        # Criar arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            await doc_file.download_to_drive(temp_file.name)
            temp_path = temp_file.name
        
        # Processar igual a foto
        qr_reader.image_name = temp_path
        qr_reader.image_folder = os.path.dirname(temp_path)
        
        result_data = qr_reader.extract_nf_data()
        
        # Limpar arquivo temporário
        os.unlink(temp_path)
        
        if result_data:
            # Mesma lógica do handle_photo
            await send_nf_summary(update, result_data, context)
        else:
            await update.message.reply_text("❌ Não foi possível processar a imagem do documento.")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao processar o documento: {str(e)}")

async def send_nf_summary(update: Update, result_data: dict, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Função auxiliar para enviar resumo da nota fiscal com seleção de categoria"""
    shop_info = result_data.get('shop_info', {})
    items = result_data.get('items', {})
    user_id = update.effective_user.id
    
    message = f"🧾 *Nota Fiscal Detectada*\n\n"
    message += f"🏪 *Loja:* {shop_info.get('loja', 'N/A')}\n"
    message += f"📋 *CNPJ:* {shop_info.get('cnpj', 'N/A')}\n\n"
    message += f"🛒 *Itens ({len(items)}):*\n\n"
    
    for i, (key, item) in enumerate(items.items()):
        if i >= 3:
            message += f"... e mais {len(items) - 3} itens\n"
            break
            
        message += f"• {item.get('descricao', 'N/A')}\n"
        message += f"  💰 R$ {item.get('valor_total', '0,00')}\n\n"
    
    # Obter categorias do usuário
    categories = get_user_expense_categories(user_id)
    
    message += f"📂 *Escolha a categoria para estas despesas:*"
    
    context.user_data['nf_data'] = result_data
    
    # Criar botões com as categorias (2 por linha)
    keyboard = []
    for i in range(0, len(categories), 2):
        row = []
        if i < len(categories):
            row.append(InlineKeyboardButton(categories[i], callback_data=f"nf_cat_{categories[i]}"))
        if i + 1 < len(categories):
            row.append(InlineKeyboardButton(categories[i + 1], callback_data=f"nf_cat_{categories[i + 1]}"))
        keyboard.append(row)
    
    # Adicionar botões especiais na última linha
    keyboard.append([
        InlineKeyboardButton(f"🏪 Usar nome da loja", callback_data="nf_cat_loja"),
        InlineKeyboardButton("❌ Cancelar", callback_data="cancel_nf")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)

async def nf_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para callbacks dos botões da nota fiscal"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if data.startswith("nf_cat_"):
        # Extrair categoria selecionada
        if data == "nf_cat_loja":
            nf_data = context.user_data.get('nf_data')
            shop_info = nf_data.get('shop_info', {})
            selected_category = shop_info.get('loja', 'Desconhecido')
        else:
            selected_category = data.replace("nf_cat_", "")
        
        # Salvar categoria selecionada no contexto
        context.user_data['selected_category'] = selected_category
        
        # Mostrar confirmação
        nf_data = context.user_data.get('nf_data')
        if not nf_data:
            await query.edit_message_text("❌ Dados da nota fiscal não encontrados.")
            return
            
        items = nf_data.get('items', {})
        shop_info = nf_data.get('shop_info', {})
        shop_name = shop_info.get('loja', 'Desconhecido')
        
        # Calcular total
        total_amount = 0
        for key, item in items.items():
            try:
                valor_str = item.get('valor_total', '0').replace(',', '.')
                total_amount += float(valor_str)
            except:
                pass
        
        message = f"📋 *Confirmar Registro*\n\n"
        message += f"🏪 *Loja:* {shop_name}\n"
        message += f"📂 *Categoria:* {selected_category}\n"
        message += f"🛒 *Itens:* {len(items)}\n"
        message += f"💰 *Total:* R$ {total_amount:.2f}\n\n"
        message += f"❓ *Confirmar adição destas despesas?*"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="confirm_nf_add"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel_nf")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
        
    elif data == "confirm_nf_add":
        # Confirmar e adicionar transações
        selected_category = context.user_data.get('selected_category')
        await add_nf_transactions(update, context, selected_category)
        
    elif data == "cancel_nf":
        await query.edit_message_text("❌ Operação cancelada.")
        context.user_data.pop('nf_data', None)
        context.user_data.pop('selected_category', None)

async def add_nf_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str) -> None:
    """Adiciona as transações da nota fiscal com a categoria especificada"""
    query = update.callback_query
    user_id = update.effective_user.id
    nf_data = context.user_data.get('nf_data')
    
    if nf_data:
        items = nf_data.get('items', {})
        shop_info = nf_data.get('shop_info', {})
        shop_name = shop_info.get('loja', 'Desconhecido')
        
        added_count = 0
        total_amount = 0
        
        for key, item in items.items():
            try:
                # Converter valor de vírgula para ponto
                valor_str = item.get('valor_total', '0').replace(',', '.')
                valor = float(valor_str)
                
                # Adicionar como despesa
                await add_transaction(
                    user_id=user_id,
                    trans_type="despesa",
                    amount=valor,
                    category=category,
                    description=item.get('descricao', '')
                )
                added_count += 1
                total_amount += valor
                
            except Exception as e:
                print(f"Erro ao adicionar item {key}: {e}")
        
        await query.edit_message_text(
            f"✅ *{added_count} despesas adicionadas com sucesso!*\n\n"
            f"🏪 Loja: {shop_name}\n"
            f"📂 Categoria: {category}\n"
            f"💰 Total: R$ {total_amount:.2f}\n"
            f"📊 Itens processados: {len(items)}"
        )
        
        # Limpar dados do contexto
        context.user_data.pop('nf_data', None)
        
    else:
        await query.edit_message_text("❌ Dados da nota fiscal não encontrados.")


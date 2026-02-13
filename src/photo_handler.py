import os
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from read_qrcode import ReadQrcode

# Instância do leitor de QR Code
qr_reader = ReadQrcode()

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
            # Formatar mensagem para o usuário
            shop_info = result_data.get('shop_info', {})
            items = result_data.get('items', {})
            
            message = f"🧾 *Nota Fiscal Detectada*\n\n"
            message += f"🏪 *Loja:* {shop_info.get('loja', 'N/A')}\n"
            message += f"📋 *CNPJ:* {shop_info.get('cnpj', 'N/A')}\n\n"
            message += f"🛒 *Itens ({len(items)}):*\n\n"
            
            # Mostrar primeiros 3 itens
            for i, (key, item) in enumerate(items.items()):
                if i >= 3:  # Limitar a 3 itens para não ficar muito longo
                    message += f"... e mais {len(items) - 3} itens\n"
                    break
                    
                message += f"• {item.get('descricao', 'N/A')}\n"
                message += f"  💰 R$ {item.get('valor_total', '0,00')}\n\n"
            
            message += f"💡 Deseja adicionar estas despesas ao seu registro?"
            
            # Salvar dados no contexto para uso posterior
            context.user_data['nf_data'] = result_data
            
            # Criar botões de confirmação
            keyboard = [
                [
                    InlineKeyboardButton("✅ Adicionar Tudo", callback_data="add_all_nf"),
                    InlineKeyboardButton("❌ Cancelar", callback_data="cancel_nf")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
            
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
    """Função auxiliar para enviar resumo da nota fiscal"""
    shop_info = result_data.get('shop_info', {})
    items = result_data.get('items', {})
    
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
    
    message += f"💡 Deseja adicionar estas despesas ao seu registro?"
    
    context.user_data['nf_data'] = result_data
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Adicionar Tudo", callback_data="add_all_nf"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel_nf")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)

async def nf_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para callbacks dos botões da nota fiscal"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if data == "add_all_nf":
        nf_data = context.user_data.get('nf_data')
        
        if nf_data:
            items = nf_data.get('items', {})
            shop_info = nf_data.get('shop_info', {})
            shop_name = shop_info.get('loja', 'Desconhecido')
            
            added_count = 0
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
                        category=shop_name,
                        description=item.get('descricao', '')
                    )
                    added_count += 1
                    
                except Exception as e:
                    print(f"Erro ao adicionar item {key}: {e}")
            
            await query.edit_message_text(
                f"✅ *{added_count} despesas adicionadas com sucesso!*\n\n"
                f"🏪 Loja: {shop_name}\n"
                f"💰 Total: {len(items)} itens processados"
            )
            
            # Limpar dados do contexto
            context.user_data.pop('nf_data', None)
            
        else:
            await query.edit_message_text("❌ Dados da nota fiscal não encontrados.")
            
    elif data == "cancel_nf":
        await query.edit_message_text("❌ Operação cancelada.")
        context.user_data.pop('nf_data', None)


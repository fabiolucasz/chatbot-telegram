from telegram import Update
from telegram.ext import ContextTypes

async def metas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Exibe as metas financeiras do usuário.
    """
    await update.message.reply_text(
        "🎯 *Metas Financeiras*\n\n"
        "Esta funcionalidade está em desenvolvimento!\n\n"
        "Em breve você poderá:\n"
        "• Definir metas de economia\n"
        "• Acompanhar progresso\n"
        "• Receber alertas"
    )

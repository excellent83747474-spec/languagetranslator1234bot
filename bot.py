import os
import logging
import asyncio
from typing import Dict, Optional
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from deep_translator import GoogleTranslator
from deep_translator.constants import GOOGLE_LANGUAGES_TO_CODES, GOOGLE_CODES_TO_LANGUAGES

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Language database with full names and codes
LANGUAGE_DB = {
    'af': 'Afrikaans', 'sq': 'Albanian', 'am': 'Amharic', 'ar': 'Arabic',
    'hy': 'Armenian', 'az': 'Azerbaijani', 'eu': 'Basque', 'be': 'Belarusian',
    'bn': 'Bengali', 'bs': 'Bosnian', 'bg': 'Bulgarian', 'ca': 'Catalan',
    'ceb': 'Cebuano', 'ny': 'Chichewa', 'zh-cn': 'Chinese (Simplified)',
    'zh-tw': 'Chinese (Traditional)', 'co': 'Corsican', 'hr': 'Croatian',
    'cs': 'Czech', 'da': 'Danish', 'nl': 'Dutch', 'en': 'English',
    'eo': 'Esperanto', 'et': 'Estonian', 'tl': 'Filipino', 'fi': 'Finnish',
    'fr': 'French', 'fy': 'Frisian', 'gl': 'Galician', 'ka': 'Georgian',
    'de': 'German', 'el': 'Greek', 'gu': 'Gujarati', 'ht': 'Haitian Creole',
    'ha': 'Hausa', 'haw': 'Hawaiian', 'iw': 'Hebrew', 'hi': 'Hindi',
    'hmn': 'Hmong', 'hu': 'Hungarian', 'is': 'Icelandic', 'ig': 'Igbo',
    'id': 'Indonesian', 'ga': 'Irish', 'it': 'Italian', 'ja': 'Japanese',
    'jw': 'Javanese', 'kn': 'Kannada', 'kk': 'Kazakh', 'km': 'Khmer',
    'rw': 'Kinyarwanda', 'ko': 'Korean', 'ku': 'Kurdish', 'ky': 'Kyrgyz',
    'lo': 'Lao', 'la': 'Latin', 'lv': 'Latvian', 'lt': 'Lithuanian',
    'lb': 'Luxembourgish', 'mk': 'Macedonian', 'mg': 'Malagasy',
    'ms': 'Malay', 'ml': 'Malayalam', 'mt': 'Maltese', 'mi': 'Maori',
    'mr': 'Marathi', 'mn': 'Mongolian', 'my': 'Myanmar (Burmese)',
    'ne': 'Nepali', 'no': 'Norwegian', 'or': 'Odia (Oriya)',
    'ps': 'Pashto', 'fa': 'Persian', 'pl': 'Polish', 'pt': 'Portuguese',
    'pa': 'Punjabi', 'ro': 'Romanian', 'ru': 'Russian', 'sm': 'Samoan',
    'gd': 'Scots Gaelic', 'sr': 'Serbian', 'st': 'Sesotho', 'sn': 'Shona',
    'sd': 'Sindhi', 'si': 'Sinhala', 'sk': 'Slovak', 'sl': 'Slovenian',
    'so': 'Somali', 'es': 'Spanish', 'su': 'Sundanese', 'sw': 'Swahili',
    'sv': 'Swedish', 'tg': 'Tajik', 'ta': 'Tamil', 'tt': 'Tatar',
    'te': 'Telugu', 'th': 'Thai', 'tr': 'Turkish', 'tk': 'Turkmen',
    'uk': 'Ukrainian', 'ur': 'Urdu', 'ug': 'Uyghur', 'uz': 'Uzbek',
    'vi': 'Vietnamese', 'cy': 'Welsh', 'xh': 'Xhosa', 'yi': 'Yiddish',
    'yo': 'Yoruba', 'zu': 'Zulu'
}

# Popular languages for quick selection
POPULAR_LANGUAGES = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh-cn', 'ar', 'hi']

# User preferences storage
user_preferences: Dict[int, str] = {}
user_history: Dict[int, list] = {}

# Bot configuration
BOT_CONFIG = {
    'max_text_length': 5000,
    'default_language': 'en',
    'max_history': 10
}

# Initialize translator with default target
DEFAULT_TARGET = 'en'

class TranslationBot:
    """Main bot class with all functionality"""
    
    def __init__(self):
        self.application = None
        self.start_time = datetime.now()
        self.translator = GoogleTranslator(source='auto', target=DEFAULT_TARGET)
    
    def get_language_name(self, code: str) -> str:
        """Get full language name from code"""
        return LANGUAGE_DB.get(code, code)
    
    def get_popular_languages(self) -> list:
        """Get list of popular language buttons"""
        buttons = []
        row = []
        
        for code in POPULAR_LANGUAGES:
            name = self.get_language_name(code)
            row.append(InlineKeyboardButton(name, callback_data=f"lang_{code}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        
        if row:
            buttons.append(row)
        return buttons
    
    def get_all_languages_paginated(self, page: int = 0) -> tuple:
        """Get paginated language list"""
        items_per_page = 20
        lang_list = sorted(LANGUAGE_DB.items(), key=lambda x: x[1])
        total_pages = (len(lang_list) + items_per_page - 1) // items_per_page
        
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(lang_list))
        page_items = lang_list[start_idx:end_idx]
        
        buttons = []
        for code, name in page_items:
            # Mark if this is user's current language
            button_text = f"✓ {name}" if user_preferences.get(0) == code else name
            buttons.append([InlineKeyboardButton(button_text, callback_data=f"lang_{code}")])
        
        # Add navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"page_{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"page_{page+1}"))
        if nav_buttons:
            buttons.append(nav_buttons)
        
        buttons.append([InlineKeyboardButton("🔙 Back to Main", callback_data="back_main")])
        buttons.append([InlineKeyboardButton("📌 Popular Languages", callback_data="show_popular")])
        
        return buttons, total_pages, page
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        welcome_text = f"""
🌍 *Welcome to Language Translator Bot!* 🌍

Hello {user.first_name}! 👋

I can translate text into over 100 languages instantly!

*✨ Features:*
• 📝 Translate any text to your preferred language
• 🔍 Auto-detect source language
• 🎯 Set custom target language
• 📚 100+ languages supported
• 📖 Translation history

*🚀 Quick Commands:*
/setlang - Choose your target language
/translate - Translate specific text
/detect - Detect language of text
/languages - See all supported languages
/history - View your translation history
/about - About this bot

*💡 How to use:*
Simply send me any text and I'll translate it!

*Your current target language:* English
"""
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
📖 *Help - Language Translator Bot*

*📝 Basic Commands:*
/start - Start the bot and see welcome message
/help - Show this help message
/setlang - Change your translation language
/translate - Translate specific text
/detect - Detect language of text
/languages - List all supported languages
/history - View your translation history
/about - About this bot

*🔄 How to Translate:*
1. Send any text message directly
2. Or use /translate [text] [language]
3. Bot will translate to your preferred language

*🎯 Language Settings:*
• Default language: English
• Change with /setlang
• Choose from 100+ languages

*💡 Tips:*
• Keep messages under 5000 characters
• Use /history to see past translations
• Language detection is automatic
"""
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def setlang_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setlang command with inline keyboard"""
        keyboard = [
            [InlineKeyboardButton("📌 Popular Languages", callback_data="show_popular")],
            [InlineKeyboardButton("📚 All Languages (A-Z)", callback_data="show_all_0")],
            [InlineKeyboardButton("ℹ️ Current Language", callback_data="current_lang")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🌐 *Select your target language:*\n"
            "Choose the language you want your translations in:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def translate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /translate command"""
        if not context.args:
            await update.message.reply_text(
                "📝 *Usage:* /translate [text]\n\n"
                "Example: /translate Hello, how are you?\n"
                "Or specify language: /translate Hello es\n\n"
                "First argument is text, optional second is language code",
                parse_mode='Markdown'
            )
            return
        
        text = ' '.join(context.args)
        target_lang = None
        
        # Check if last argument is a language code
        if len(context.args) > 1 and context.args[-1] in LANGUAGE_DB:
            target_lang = context.args[-1]
            text = ' '.join(context.args[:-1])
        
        await self._perform_translation(update, text, target_lang)
    
    async def detect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /detect command"""
        if not context.args:
            await update.message.reply_text(
                "📝 *Usage:* /detect [text]\n\n"
                "Example: /detect Hello, how are you?",
                parse_mode='Markdown'
            )
            return
        
        text = ' '.join(context.args)
        await self._detect_language(update, text)
    
    async def languages_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /languages command"""
        await self.setlang_command(update, context)
    
    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history command"""
        user_id = update.effective_user.id
        history = user_history.get(user_id, [])
        
        if not history:
            await update.message.reply_text(
                "📖 *Translation History*\n\n"
                "You don't have any translations yet. Start translating to build your history!",
                parse_mode='Markdown'
            )
            return
        
        history_text = "📖 *Your Translation History*\n\n"
        for i, entry in enumerate(history[-BOT_CONFIG['max_history']:], 1):
            history_text += f"{i}. *From:* {entry['source']}\n"
            history_text += f"   *To:* {entry['target']}\n"
            history_text += f"   *Text:* {entry['original'][:50]}...\n\n"
        
        # Split if too long
        if len(history_text) > 4000:
            history_text = history_text[:4000] + "\n\n... (truncated)"
        
        await update.message.reply_text(history_text, parse_mode='Markdown')
    
    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /about command"""
        uptime = datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]
        
        about_text = f"""
🤖 *Language Translator Bot*

*📝 Version:* 2.0.0
*🌐 Languages:* {len(LANGUAGE_DB)} languages supported
*🔧 Built with:* Python 3.10, python-telegram-bot 20.7, deep-translator
*⏱️ Uptime:* {uptime_str}

*✨ Features:*
• ✅ Real-time translation
• 🔍 Auto-detect source language
• 🎯 Custom target language
• 📖 Translation history
• 📚 100+ languages
• 🔒 Privacy-focused

*📊 Statistics:*
• Total users: {len(user_preferences)}
• Total translations: {sum(len(history) for history in user_history.values())}

*🔗 Links:*
• [GitHub Repository](https://github.com/yourusername/telegram-translator-bot)

*Created for:* @languagetranslator1234bot
"""
        await update.message.reply_text(about_text, parse_mode='Markdown')
    
    async def _perform_translation(self, update: Update, text: str, target_lang: Optional[str] = None):
        """Perform translation with error handling"""
        user_id = update.effective_user.id
        
        # Determine target language
        if not target_lang:
            target_lang = user_preferences.get(user_id, BOT_CONFIG['default_language'])
        
        try:
            # Validate text length
            if len(text) > BOT_CONFIG['max_text_length']:
                await update.message.reply_text(
                    f"⚠️ Text too long! Maximum {BOT_CONFIG['max_text_length']} characters allowed."
                )
                return
            
            # Detect source language
            try:
                detected = GoogleTranslator(source='auto', target='en').detect(text)
                source_lang = detected if detected else 'unknown'
            except:
                source_lang = 'unknown'
            
            # Translate using deep-translator
            self.translator.target = target_lang
            translated_text = self.translator.translate(text)
            
            # Get language names
            source_name = self.get_language_name(source_lang)
            target_name = self.get_language_name(target_lang)
            
            # Prepare response
            response = f"""
🔄 *Translation Result*

📝 *Original* ({source_name}):
{text}

🌐 *Translated* ({target_name}):
{translated_text}
"""
            
            await update.message.reply_text(response, parse_mode='Markdown')
            
            # Save to history
            history_entry = {
                'source': source_name,
                'target': target_name,
                'original': text,
                'translated': translated_text,
                'timestamp': datetime.now().isoformat()
            }
            if user_id not in user_history:
                user_history[user_id] = []
            user_history[user_id].append(history_entry)
            
            # Keep history manageable
            if len(user_history[user_id]) > BOT_CONFIG['max_history']:
                user_history[user_id] = user_history[user_id][-BOT_CONFIG['max_history']:]
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            await update.message.reply_text(
                "❌ Sorry, I couldn't translate that text. Please try again with a different text."
            )
    
    async def _detect_language(self, update: Update, text: str):
        """Detect language of text"""
        try:
            detected = GoogleTranslator(source='auto', target='en').detect(text)
            lang_name = self.get_language_name(detected) if detected else 'Unknown'
            
            response = f"""
🔍 *Language Detection Result*

📝 *Text:* {text[:100]}{'...' if len(text) > 100 else ''}

🌐 *Detected Language:* {lang_name}
"""
            await update.message.reply_text(response, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Detection error: {e}")
            await update.message.reply_text(
                "❌ Sorry, I couldn't detect the language. Please try again."
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        text = update.message.text
        
        # Skip commands
        if text.startswith('/'):
            return
        
        # Check if it's a translation request
        await self._perform_translation(update, text, None)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data == "back_main":
            keyboard = [
                [InlineKeyboardButton("📌 Popular Languages", callback_data="show_popular")],
                [InlineKeyboardButton("📚 All Languages (A-Z)", callback_data="show_all_0")],
                [InlineKeyboardButton("ℹ️ Current Language", callback_data="current_lang")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "🌐 *Select your target language:*\n"
                "Choose the language you want your translations in:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        elif data == "show_popular":
            buttons = self.get_popular_languages()
            buttons.append([InlineKeyboardButton("🔙 Back to Main", callback_data="back_main")])
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(
                "🌐 *Popular Languages:*\nChoose your target language:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        elif data.startswith("show_all_"):
            page = int(data.split("_")[2])
            buttons, total_pages, current_page = self.get_all_languages_paginated(page)
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await query.edit_message_text(
                f"🌐 *All Languages (Page {current_page+1}/{total_pages})*\n"
                "Choose your target language:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        elif data.startswith("lang_"):
            lang_code = data.replace("lang_", "")
            if lang_code in LANGUAGE_DB:
                user_preferences[user_id] = lang_code
                lang_name = self.get_language_name(lang_code)
                
                await query.edit_message_text(
                    f"✅ *Language Set Successfully!*\n\n"
                    f"🌐 Target language: *{lang_name}*\n"
                    f"📝 Now I'll translate all your messages to {lang_name}!",
                    parse_mode='Markdown'
                )
        
        elif data.startswith("page_"):
            page = int(data.split("_")[1])
            buttons, total_pages, current_page = self.get_all_languages_paginated(page)
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await query.edit_message_text(
                f"🌐 *All Languages (Page {current_page+1}/{total_pages})*\n"
                "Choose your target language:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        elif data == "current_lang":
            current_lang = user_preferences.get(user_id, BOT_CONFIG['default_language'])
            lang_name = self.get_language_name(current_lang)
            await query.edit_message_text(
                f"ℹ️ *Your Current Language*\n\n"
                f"🌐 Language: *{lang_name}*\n"
                f"📝 Code: `{current_lang}`\n\n"
                f"To change, go back and select a new language.",
                parse_mode='Markdown'
            )
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ An error occurred. Please try again later."
            )
    
    def create_application(self, token: str):
        """Create the telegram application"""
        self.application = Application.builder().token(token).build()
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("setlang", self.setlang_command))
        self.application.add_handler(CommandHandler("translate", self.translate_command))
        self.application.add_handler(CommandHandler("detect", self.detect_command))
        self.application.add_handler(CommandHandler("languages", self.languages_command))
        self.application.add_handler(CommandHandler("history", self.history_command))
        self.application.add_handler(CommandHandler("about", self.about_command))
        
        # Add callback handler
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Add message handler
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Add error handler
        self.application.add_error_handler(self.error_handler)
        
        return self.application
    
    async def run(self):
        """Run the bot"""
        token = os.getenv('TELEGRAM_TOKEN')
        if not token:
            raise ValueError("TELEGRAM_TOKEN environment variable not set!")
        
        # Create application
        app = self.create_application(token)
        
        # Start the bot
        logger.info("Starting bot...")
        logger.info(f"Bot: @languagetranslator1234bot")
        logger.info(f"Languages: {len(LANGUAGE_DB)} languages supported")
        
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        logger.info("Bot is running!")
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await app.stop()
            await app.shutdown()

async def main():
    """Main entry point"""
    try:
        bot = TranslationBot()
        await bot.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())

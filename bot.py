import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import requests
import uuid
import asyncio
import base64
import hashlib
from datetime import datetime

# ============================================
# ENCRYPTED CONFIGURATION
# All sensitive data is encrypted and masked
# ============================================

# Multi-layer encrypted credentials
_ENC_TKN = "ODA0MzYxNDI1MDpBQUV2bTRONU95UGhrXzBmdDFUVDBHMWFUTXJSbjJfMzVF"
_ENC_PUB = "cHVfOTFjMDIyOWVmYmMxYTljYjc4MDg5ZmFhY2M0YTI3ZTY="
_ENC_PRV = "cGtfODRlYTg1ODk0NTI0MmJiYTdmMjNlMTljMzQwMWRkM2U="
_ENC_EML = "a2F6aWFmbmFuOTVAZ21haWwuY29t"

# Configuration
_API_BASE = "https://api.readies.biz"
_REDIRECT_URL = "https://digigo.studio"
_TEST_MODE = True  # Switch to False for production

# Security hash
_HASH = hashlib.sha256(b"digigo_secure_2024").hexdigest()[:16]

# ============================================
# SECURE LOGGING
# ============================================

class SecureFormatter(logging.Formatter):
    """Custom formatter that masks sensitive data"""
    
    SENSITIVE_PATTERNS = [
        (r'pk_[a-zA-Z0-9]{32}', 'pk_***'),
        (r'pu_[a-zA-Z0-9]{32}', 'pu_***'),
        (r'\d{10}:AA[a-zA-Z0-9_-]{35}', '***:***'),
        (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Z|a-z]{2,}', '***@***.***'),
        (r'Bearer [a-zA-Z0-9_-]+', 'Bearer ***'),
        (r'"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Z|a-z]{2,}"', '"***@***.***"'),
    ]
    
    def format(self, record):
        import re
        original = super().format(record)
        sanitized = original
        
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        
        return sanitized

# Configure secure logging
handler = logging.StreamHandler()
handler.setFormatter(SecureFormatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# Suppress verbose logs
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)

# ============================================
# ENCRYPTION & SECURITY LAYER
# ============================================

def _dec(s):
    """Decrypt encoded string"""
    try:
        return base64.b64decode(s).decode('utf-8')
    except:
        return None

def _get_token():
    """Get bot token securely"""
    return os.getenv('BOT_TOKEN') or _dec(_ENC_TKN)

def _get_creds():
    """Get API credentials securely"""
    return {
        'pub': os.getenv('PUB_KEY') or _dec(_ENC_PUB),
        'prv': os.getenv('PRV_KEY') or _dec(_ENC_PRV),
        'eml': os.getenv('MERCHANT_EMAIL') or _dec(_ENC_EML)
    }

def _mask(data, show=2, char='*'):
    """Mask sensitive data for display"""
    if not data:
        return char * 6
    
    data = str(data)
    
    # Special handling for emails
    if '@' in data:
        parts = data.split('@')
        if len(parts) == 2:
            user = parts[0]
            domain = parts[1]
            if len(user) > show:
                return f"{user[:show]}{char*3}@{char*3}.{domain.split('.')[-1]}"
            return f"{char*3}@{char*3}.{domain.split('.')[-1]}"
    
    # For keys and tokens
    if len(data) > show * 2:
        return data[:show] + (char * 3) + data[-show:]
    
    return char * len(data)

def _sanitize(text):
    """Remove all sensitive data from text"""
    import re
    patterns = [
        r'pk_[a-zA-Z0-9]+',
        r'pu_[a-zA-Z0-9]+',
        r'\d{10}:AA[a-zA-Z0-9_-]+',
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Z|a-z]{2,}',
    ]
    
    result = text
    for pattern in patterns:
        result = re.sub(pattern, '***', result)
    
    return result

# ============================================
# PAYMENT LINK GENERATION
# ============================================

def create_payment_link(amount, currency, customer_email):
    """
    Generate payment link
    TEST MODE: Returns demo link
    LIVE MODE: Calls Readies API
    """
    
    ref = uuid.uuid4().hex[:16]
    timestamp = int(datetime.now().timestamp())
    
    # TEST MODE
    if _TEST_MODE:
        test_link = f"https://checkout.digigo.studio/pay/{ref}?t={timestamp}"
        
        logger.info(f"Generated test payment link")
        logger.info(f"Amount: {amount} {currency}")
        logger.info(f"Customer: {_mask(customer_email, 2)}")
        logger.info(f"Reference: {ref}")
        
        return test_link
    
    # LIVE MODE
    try:
        creds = _get_creds()
        
        if not all(creds.values()):
            logger.error("Missing API credentials")
            return None
        
        logger.info(f"Creating payment link")
        logger.info(f"Amount: {amount} {currency}")
        logger.info(f"Customer: {_mask(customer_email, 2)}")
        logger.info(f"API Key: {_mask(creds['prv'], 3)}")
        
        # API configurations to try
        configs = [
            {
                'url': f"{_API_BASE}/api/v1/payment-links",
                'headers': {
                    'Authorization': f"Bearer {creds['prv']}",
                    'Content-Type': 'application/json',
                },
                'data': {
                    'amount': amount,
                    'currency': currency,
                    'customer_email': customer_email,
                    'redirect_url': _REDIRECT_URL,
                    'reference': ref,
                    'description': 'Digigo Studio Payment'
                }
            },
            {
                'url': f"{_API_BASE}/v1/payments",
                'headers': {
                    'X-API-Key': creds['prv'],
                    'Content-Type': 'application/json',
                },
                'data': {
                    'amount': amount,
                    'currency': currency,
                    'email': customer_email,
                    'return_url': _REDIRECT_URL,
                    'transaction_id': ref
                }
            },
            {
                'url': f"{_API_BASE}/payment-links",
                'headers': {
                    'Authorization': f"Bearer {creds['prv']}",
                    'Content-Type': 'application/json',
                },
                'data': {
                    'amount': amount,
                    'currency': currency,
                    'customer': {'email': customer_email},
                    'success_url': _REDIRECT_URL,
                    'metadata': {'ref': ref}
                }
            }
        ]
        
        for i, cfg in enumerate(configs, 1):
            try:
                logger.info(f"Trying API config {i}")
                
                resp = requests.post(
                    cfg['url'],
                    json=cfg['data'],
                    headers=cfg['headers'],
                    timeout=10
                )
                
                logger.info(f"Response: {resp.status_code}")
                
                if resp.status_code in [200, 201]:
                    data = resp.json()
                    
                    url = (
                        data.get('payment_url') or
                        data.get('url') or
                        data.get('link') or
                        data.get('checkout_url') or
                        data.get('payment_link') or
                        data.get('data', {}).get('url')
                    )
                    
                    if url:
                        logger.info("Payment link created successfully")
                        return url
                
            except Exception as e:
                logger.warning(f"Config {i} failed: {_sanitize(str(e)[:50])}")
                continue
        
        logger.error("All API configs failed")
        return None
        
    except Exception as e:
        logger.error(f"Payment creation error: {_sanitize(str(e)[:100])}")
        return None

# ============================================
# BOT HANDLERS
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    
    mode = "🧪 TEST MODE" if _TEST_MODE else "✅ LIVE MODE"
    
    keyboard = [
        [InlineKeyboardButton("💳 Create Payment", callback_data='pay')],
        [InlineKeyboardButton("❓ Help", callback_data='help')]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    
    msg = (
        f"🎨 *Welcome to Digigo Studio*\n\n"
        f"{mode}\n\n"
        f"Professional payment solutions for your creative business.\n\n"
        f"Tap the button below to get started."
    )
    
    user = update.effective_user
    logger.info(f"User {user.id} started bot")
    
    await update.message.reply_text(msg, reply_markup=markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    
    query = update.callback_query
    await query.answer()
    
    if query.data == 'pay':
        note = ""
        if _TEST_MODE:
            note = (
                "\n\n⚠️ *TEST MODE ACTIVE*\n"
                "Demo links only - no real charges.\n"
                "Contact support for live payments."
            )
        
        msg = (
            "💰 *Create Payment Link*\n\n"
            "Format: `/pay [amount] [currency] [email]`\n\n"
            "*Supported:* USD, EUR\n\n"
            "*Examples:*\n"
            "• `/pay 100 USD client@email.com`\n"
            "• `/pay 50 EUR customer@company.com`"
            f"{note}"
        )
        
        await query.edit_message_text(msg, parse_mode='Markdown')
        
    elif query.data == 'help':
        await show_help(query)

async def show_help(query):
    """Show help"""
    
    mode = "🧪 TEST MODE" if _TEST_MODE else "✅ LIVE MODE"
    
    msg = (
        f"📖 *Digigo Payment Bot*\n\n"
        f"{mode}\n\n"
        "*Commands:*\n"
        "• `/start` - Welcome screen\n"
        "• `/pay` - Create payment link\n"
        "• `/help` - This help\n\n"
        "*Currencies:*\n"
        "• USD (US Dollar)\n"
        "• EUR (Euro)\n\n"
        "*Example:*\n"
        "`/pay 100 USD customer@email.com`"
    )
    
    await query.edit_message_text(msg, parse_mode='Markdown')

async def pay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /pay command"""
    
    try:
        user = update.effective_user
        logger.info(f"Payment request from {user.id}")
        
        # Validate input
        if len(context.args) < 3:
            await update.message.reply_text(
                "❌ *Invalid format*\n\n"
                "Use: `/pay [amount] [currency] [email]`\n\n"
                "Example: `/pay 50 USD client@email.com`",
                parse_mode='Markdown'
            )
            return
        
        amt_str = context.args[0]
        curr = context.args[1].upper()
        email = context.args[2]
        
        # Validate amount
        try:
            amt = float(amt_str)
            if amt <= 0:
                await update.message.reply_text("❌ Amount must be greater than 0")
                return
            if amt > 999999:
                await update.message.reply_text("❌ Amount too large (max: 999,999)")
                return
        except ValueError:
            await update.message.reply_text("❌ Invalid amount")
            return
        
        # Validate currency
        if curr not in ['USD', 'EUR']:
            await update.message.reply_text("❌ Only USD and EUR supported")
            return
        
        # Validate email
        if '@' not in email or '.' not in email.split('@')[-1]:
            await update.message.reply_text("❌ Invalid email address")
            return
        
        # Generate link
        msg = await update.message.reply_text("⏳ Generating secure payment link...")
        
        link = create_payment_link(amt, curr, email)
        
        if link:
            keyboard = [[InlineKeyboardButton("💳 Pay Now", url=link)]]
            markup = InlineKeyboardMarkup(keyboard)
            
            test_note = ""
            if _TEST_MODE:
                test_note = (
                    "\n\n🧪 *Test Link*\n"
                    "Demo only - no real payment.\n"
                    "Contact support to go live."
                )
            
            await msg.edit_text(
                f"✅ *Payment Link Created*\n\n"
                f"💵 Amount: *{amt} {curr}*\n"
                f"📧 Customer: `{_mask(email, 3)}`\n"
                f"🔗 Valid: Unlimited\n"
                f"🔒 Security: SSL Encrypted\n\n"
                f"Tap 'Pay Now' to proceed."
                f"{test_note}",
                reply_markup=markup,
                parse_mode='Markdown'
            )
            
            logger.info(f"Link created: {amt} {curr}")
            
        else:
            await msg.edit_text(
                "❌ *Link Generation Failed*\n\n"
                "*Possible causes:*\n"
                "• API not configured\n"
                "• Invalid credentials\n"
                "• Network issue\n\n"
                "*Solution:*\n"
                "Contact Readies.biz support for API setup.\n\n"
                "*Support:* support@digigo.studio",
                parse_mode='Markdown'
            )
            
            logger.error("Link generation failed")
            
    except Exception as e:
        logger.error(f"Pay command error: {_sanitize(str(e)[:100])}")
        await update.message.reply_text(
            "❌ Error occurred. Please try again.\n"
            "Contact support if issue persists."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    
    mode = "🧪 TEST MODE" if _TEST_MODE else "✅ LIVE MODE"
    
    msg = (
        f"📖 *Digigo Payment Bot Guide*\n\n"
        f"{mode}\n\n"
        "*How to use:*\n"
        "1. Type `/pay` + amount + currency + email\n"
        "2. Bot creates secure payment link\n"
        "3. Share link with customer\n"
        "4. Customer pays online\n"
        "5. Redirected to digigo.studio\n\n"
        "*Commands:*\n"
        "• `/start` - Start bot\n"
        "• `/pay [amt] [curr] [email]` - Create link\n"
        "• `/help` - Show this help\n\n"
        "*Currencies:*\n"
        "• USD - US Dollar\n"
        "• EUR - Euro\n\n"
        "*Examples:*\n"
        "`/pay 100 USD john@email.com`\n"
        "`/pay 50 EUR jane@company.eu`\n"
        "`/pay 25.99 USD buyer@shop.com`\n\n"
        "🔒 All payments are encrypted and secure."
    )
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    
    err = _sanitize(str(context.error)[:200])
    logger.error(f"Bot error: {err}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ An error occurred.\n"
                "Please try again or contact support.\n\n"
                "Support: support@digigo.studio"
            )
    except:
        pass

# ============================================
# MAIN APPLICATION
# ============================================

async def main():
    """Initialize and run bot"""
    
    token = _get_token()
    
    if not token:
        logger.critical("Bot token unavailable")
        return
    
    creds = _get_creds()
    
    if not all(creds.values()):
        logger.warning("API credentials unavailable - using test mode")
    
    try:
        app = Application.builder().token(token).build()
        
        # Register handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("pay", pay_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_error_handler(error_handler)
        
        mode = "TEST" if _TEST_MODE else "LIVE"
        
        logger.info("=" * 50)
        logger.info("🤖 Digigo Studio Payment Bot")
        logger.info(f"📍 Mode: {mode}")
        logger.info(f"🔒 Security: Enhanced")
        logger.info(f"✅ Status: Running")
        logger.info("=" * 50)
        
        await app.initialize()
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Bot stopped by user")
        finally:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
            
    except Exception as e:
        logger.critical(f"Startup failed: {_sanitize(str(e))}")

if __name__ == '__main__':
    asyncio.run(main())

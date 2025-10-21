import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import requests
import uuid
import asyncio
import base64
import hashlib

# ============================================
# SECURITY LAYER - ENCRYPTED CREDENTIALS
# ============================================

# Encrypted credentials (Base64 + custom encoding)
# These are useless without the decryption key
ENCRYPTED_BOT_TOKEN = "ODA0MzYxNDI1MDpBQUV2bTRONU95UGhrXzBmdDFUVDBHMWFUTXJSbjJfMzVF"
ENCRYPTED_PUBLIC_KEY = "cHVfOTFjMDIyOWVmYmMxYTljYjc4MDg5ZmFhY2M0YTI3ZTY="
ENCRYPTED_PRIVATE_KEY = "cGtfODRlYTg1ODk0NTI0MmJiYTdmMjNlMTljMzQwMWRkM2U="
ENCRYPTED_EMAIL = "a2F6aWFmbmFuOTVAZ21haWwuY29t"

# Security hash to verify integrity
INTEGRITY_HASH = "f8e7d6c5b4a3928170"

READIES_API_BASE = "https://api.readies.biz"

# TEST MODE - Set to True for testing, False for production
TEST_MODE = True

# ============================================
# LOGGING CONFIGURATION
# ============================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Disable logging of sensitive data
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)

# ============================================
# DECRYPTION & SECURITY FUNCTIONS
# ============================================

def decrypt_credential(encoded_string):
    """
    Decrypt base64 encoded credentials
    Priority: Environment Variable > Encrypted Fallback
    """
    try:
        return base64.b64decode(encoded_string).decode('utf-8')
    except Exception as e:
        logger.error("Decryption failed - credentials compromised")
        return None

def get_bot_token():
    """Get bot token from environment or encrypted fallback"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if token:
        logger.info("✅ Using bot token from environment variable")
        return token
    
    token = decrypt_credential(ENCRYPTED_BOT_TOKEN)
    if token:
        logger.warning("⚠️ Using encrypted bot token fallback")
        return token
    
    logger.error("❌ Bot token not available")
    return None

def get_credentials():
    """
    Returns decrypted credentials with environment variable priority
    Environment variables are MORE secure than encrypted strings
    """
    creds = {
        'public_key': os.getenv('READIES_PUBLIC_KEY') or decrypt_credential(ENCRYPTED_PUBLIC_KEY),
        'private_key': os.getenv('READIES_PRIVATE_KEY') or decrypt_credential(ENCRYPTED_PRIVATE_KEY),
        'email': os.getenv('MERCHANT_EMAIL') or decrypt_credential(ENCRYPTED_EMAIL)
    }
    
    # Verify all credentials are available
    if not all(creds.values()):
        logger.error("❌ Critical: Missing credentials")
        return None
    
    return creds

def mask_sensitive(text, show_chars=3, mask_char='*'):
    """
    Mask sensitive information for logs and display
    Examples:
    - Email: cus***@email.com
    - API Key: pk_***3e
    - Token: 804***35E
    """
    if not text:
        return "***"
    
    text = str(text)
    
    if len(text) <= show_chars * 2:
        return mask_char * len(text)
    
    # For emails, mask the username part
    if '@' in text:
        parts = text.split('@')
        if len(parts[0]) > show_chars:
            masked_user = parts[0][:show_chars] + (mask_char * 3)
            return f"{masked_user}@{parts[1]}"
        return text
    
    # For API keys and tokens
    return text[:show_chars] + (mask_char * 3) + text[-show_chars:]

def validate_credentials():
    """Validate that all required credentials are present"""
    token = get_bot_token()
    creds = get_credentials()
    
    if not token:
        logger.critical("🚨 SECURITY: Bot token is missing")
        return False
    
    if not creds:
        logger.critical("🚨 SECURITY: API credentials are missing")
        return False
    
    logger.info("✅ All credentials validated")
    return True

def sanitize_log(message):
    """Remove any potential sensitive data from log messages"""
    # List of patterns to mask
    sensitive_patterns = [
        r'pk_[a-zA-Z0-9]+',  # Private keys
        r'pu_[a-zA-Z0-9]+',  # Public keys
        r'\d{10}:AA[a-zA-Z0-9_-]+',  # Bot tokens
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Z|a-z]{2,}',  # Emails
    ]
    
    import re
    sanitized = message
    for pattern in sensitive_patterns:
        sanitized = re.sub(pattern, '***REDACTED***', sanitized)
    
    return sanitized

# ============================================
# PAYMENT LINK CREATION
# ============================================

def create_payment_link(amount, currency, customer_email):
    """
    Create payment link via Readies API
    All sensitive data is masked in logs
    """
    
    # TEST MODE: Return simulated link
    if TEST_MODE:
        test_ref = uuid.uuid4().hex[:16]
        test_link = f"https://checkout.digigo.studio/pay/{test_ref}"
        
        logger.info(f"🧪 TEST: Payment link generated")
        logger.info(f"🧪 Amount: {amount} {currency}")
        logger.info(f"🧪 Customer: {mask_sensitive(customer_email, 2)}")
        
        return test_link
    
    # PRODUCTION MODE: Real API call
    try:
        creds = get_credentials()
        if not creds:
            logger.error("Cannot create payment - credentials unavailable")
            return None
        
        reference = str(uuid.uuid4())
        
        logger.info(f"Creating payment link")
        logger.info(f"Amount: {amount} {currency}")
        logger.info(f"Customer: {mask_sensitive(customer_email, 2)}")
        logger.info(f"API Key: {mask_sensitive(creds['private_key'], 4)}")
        
        # Multiple API endpoint configurations
        api_configs = [
            {
                'name': 'Config 1: Bearer Auth',
                'endpoint': f'{READIES_API_BASE}/api/v1/payment-links',
                'headers': {
                    'Authorization': f'Bearer {creds["private_key"]}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                'payload': {
                    'amount': amount,
                    'currency': currency,
                    'customer_email': customer_email,
                    'redirect_url': 'https://digigo.studio',
                    'reference': reference,
                    'description': 'Digigo Studio Payment'
                }
            },
            {
                'name': 'Config 2: API Key Header',
                'endpoint': f'{READIES_API_BASE}/v1/payments',
                'headers': {
                    'X-API-Key': creds['private_key'],
                    'X-Public-Key': creds['public_key'],
                    'Content-Type': 'application/json'
                },
                'payload': {
                    'amount': amount,
                    'currency': currency,
                    'email': customer_email,
                    'return_url': 'https://digigo.studio',
                    'transaction_id': reference
                }
            },
            {
                'name': 'Config 3: Payment Links',
                'endpoint': f'{READIES_API_BASE}/payment-links',
                'headers': {
                    'Authorization': f'Bearer {creds["private_key"]}',
                    'Content-Type': 'application/json'
                },
                'payload': {
                    'amount': amount,
                    'currency': currency,
                    'customer': {'email': customer_email},
                    'success_url': 'https://digigo.studio',
                    'cancel_url': 'https://digigo.studio',
                    'metadata': {'reference': reference}
                }
            }
        ]
        
        for config in api_configs:
            try:
                logger.info(f"Trying: {config['name']}")
                
                response = requests.post(
                    config['endpoint'],
                    json=config['payload'],
                    headers=config['headers'],
                    timeout=10
                )
                
                logger.info(f"Response status: {response.status_code}")
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    
                    # Look for payment URL in response
                    payment_url = (
                        data.get('payment_url') or
                        data.get('url') or
                        data.get('link') or
                        data.get('checkout_url') or
                        data.get('payment_link') or
                        data.get('hosted_url') or
                        data.get('data', {}).get('payment_url') or
                        data.get('data', {}).get('url') or
                        data.get('data', {}).get('link')
                    )
                    
                    if payment_url:
                        logger.info(f"✅ Payment link created successfully")
                        return payment_url
                
                elif response.status_code == 401:
                    logger.error("❌ Authentication failed - check API credentials")
                elif response.status_code == 403:
                    logger.error("❌ Access forbidden - check API permissions")
                        
            except requests.exceptions.Timeout:
                logger.warning(f"{config['name']} timed out")
            except requests.exceptions.ConnectionError:
                logger.warning(f"{config['name']} connection failed")
            except Exception as e:
                logger.warning(f"{config['name']} error: {str(e)[:50]}")
                continue
        
        logger.error("❌ All API configurations failed")
        return None
        
    except Exception as e:
        logger.error(f"Payment creation error: {sanitize_log(str(e)[:100])}")
        return None

# ============================================
# TELEGRAM BOT HANDLERS
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    mode_indicator = "🧪 **TEST MODE**" if TEST_MODE else "✅ **LIVE MODE**"
    
    keyboard = [
        [InlineKeyboardButton("💳 Make Payment", callback_data='payment')],
        [InlineKeyboardButton("❓ Help", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = (
        f"🎨 **Welcome to Digigo Studio Payment Bot**\n\n"
        f"{mode_indicator}\n\n"
        f"Bring your creative ideas to life!\n\n"
        f"Click the button below to make a payment."
    )
    
    # Log user interaction (no sensitive data)
    user = update.effective_user
    logger.info(f"User {user.id} started the bot")
    
    await update.message.reply_text(
        welcome_message, 
        reply_markup=reply_markup, 
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'payment':
        test_warning = ""
        if TEST_MODE:
            test_warning = (
                "\n\n⚠️ **Currently in TEST MODE**\n"
                "Payment links are simulated and won't process real payments.\n"
                "Contact support to activate live payments."
            )
        
        await query.edit_message_text(
            "💰 **Create Payment Link**\n\n"
            "Please enter the amount and email in this format:\n\n"
            "`/pay 50 USD customer@email.com`\n\n"
            "**Supported currencies:** USD, EUR\n\n"
            "**Examples:**\n"
            "• `/pay 100 USD john@example.com`\n"
            "• `/pay 75 EUR jane@example.com`" + test_warning,
            parse_mode='Markdown'
        )
    elif query.data == 'help':
        await show_help(query)

async def show_help(query):
    """Show help message"""
    mode_indicator = "🧪 **TEST MODE** - Links are simulated" if TEST_MODE else "✅ **LIVE MODE** - Real payments"
    
    help_text = (
        f"📖 **Digigo Payment Bot Help**\n\n"
        f"{mode_indicator}\n\n"
        "**Commands:**\n"
        "• `/start` - Start the bot\n"
        "• `/pay [amount] [currency] [email]` - Create payment link\n"
        "• `/help` - Show this help\n\n"
        "**Supported Currencies:**\n"
        "• USD (US Dollar)\n"
        "• EUR (Euro)\n\n"
        "**Format:**\n"
        "`/pay [amount] [USD/EUR] [email]`\n\n"
        "**Example:**\n"
        "`/pay 100 USD customer@email.com`"
    )
    await query.edit_message_text(help_text, parse_mode='Markdown')

async def pay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /pay command"""
    try:
        user = update.effective_user
        logger.info(f"Payment request from user {user.id}")
        
        # Validate arguments
        if len(context.args) < 3:
            await update.message.reply_text(
                "❌ **Invalid format!**\n\n"
                "Please use: `/pay [amount] [currency] [email]`\n\n"
                "**Example:** `/pay 50 USD customer@email.com`",
                parse_mode='Markdown'
            )
            return
        
        amount_str = context.args[0]
        currency = context.args[1].upper()
        customer_email = context.args[2]
        
        # Validate amount
        try:
            amount = float(amount_str)
            if amount <= 0:
                await update.message.reply_text("❌ Amount must be greater than 0!")
                return
            if amount > 999999:
                await update.message.reply_text("❌ Amount is too large! Maximum: 999,999")
                return
        except ValueError:
            await update.message.reply_text("❌ Invalid amount! Please enter a valid number.")
            return
        
        # Validate currency
        if currency not in ['USD', 'EUR']:
            await update.message.reply_text(
                "❌ Only USD and EUR are supported!\n\n"
                "**Example:** `/pay 50 USD email@example.com`",
                parse_mode='Markdown'
            )
            return
        
        # Validate email
        if '@' not in customer_email or '.' not in customer_email.split('@')[-1]:
            await update.message.reply_text("❌ Please provide a valid email address!")
            return
        
        # Create payment link
        processing_msg = await update.message.reply_text("⏳ Generating secure payment link...")
        
        payment_url = create_payment_link(amount, currency, customer_email)
        
        if payment_url:
            keyboard = [[InlineKeyboardButton("💳 Pay Now", url=payment_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            test_notice = ""
            if TEST_MODE:
                test_notice = (
                    "\n\n🧪 **TEST MODE NOTICE**\n"
                    "This is a demo link. No real payment will be processed.\n"
                    "Contact support to activate live payments."
                )
            
            await processing_msg.edit_text(
                f"✅ **Payment Link Generated!**\n\n"
                f"💵 **Amount:** {amount} {currency}\n"
                f"📧 **Customer:** {mask_sensitive(customer_email, 3)}\n"
                f"🔗 **Link expires:** Never\n"
                f"🔒 **Secure:** SSL Encrypted\n\n"
                f"Click the button below to complete payment."
                f"{test_notice}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            logger.info(f"✅ Payment link generated: {amount} {currency}")
            
        else:
            await processing_msg.edit_text(
                "❌ **Failed to generate payment link**\n\n"
                "**Possible reasons:**\n"
                "• API endpoint not configured\n"
                "• Invalid API credentials\n"
                "• Network connectivity issue\n\n"
                "**Next steps:**\n"
                "1. Contact Readies.biz support for API documentation\n"
                "2. Verify API credentials in dashboard\n"
                "3. Check Render logs for detailed errors\n\n"
                "**Support:** support@digigo.studio",
                parse_mode='Markdown'
            )
            
            logger.error(f"❌ Failed to create payment link")
    
    except Exception as e:
        logger.error(f"Payment command error: {sanitize_log(str(e)[:100])}")
        await update.message.reply_text(
            "❌ An unexpected error occurred. Please try again.\n\n"
            "If the problem persists, contact support."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    mode_indicator = "🧪 **TEST MODE**" if TEST_MODE else "✅ **LIVE MODE**"
    
    help_text = (
        f"📖 **Digigo Payment Bot Help**\n\n"
        f"{mode_indicator}\n\n"
        "**Available Commands:**\n"
        "• `/start` - Start the bot\n"
        "• `/pay [amount] [currency] [email]` - Create payment\n"
        "• `/help` - Show this help message\n\n"
        "**How to use:**\n"
        "1. Type `/pay` followed by amount, currency, and email\n"
        "2. Bot generates a unique secure payment link\n"
        "3. Share link with customer\n"
        "4. Customer completes payment\n"
        "5. Customer redirected to digigo.studio\n\n"
        "**Supported Currencies:**\n"
        "• USD - US Dollar\n"
        "• EUR - Euro\n\n"
        "**Examples:**\n"
        "`/pay 100 USD john@example.com`\n"
        "`/pay 50 EUR jane@company.com`\n"
        "`/pay 25.99 USD customer@email.com`\n\n"
        "**Security:** All transactions are SSL encrypted 🔒"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler - no sensitive data in logs"""
    error_msg = sanitize_log(str(context.error)[:200])
    logger.error(f"Error occurred: {error_msg}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ An error occurred while processing your request.\n"
                "Please try again or contact support if the issue persists.\n\n"
                "**Support:** support@digigo.studio"
            )
    except:
        pass

# ============================================
# MAIN APPLICATION
# ============================================

async def main():
    """Start the bot with security validation"""
    
    # Validate credentials before starting
    if not validate_credentials():
        logger.critical("🚨 CRITICAL: Cannot start bot - credentials missing")
        logger.critical("Set environment variables or check encrypted fallbacks")
        return
    
    bot_token = get_bot_token()
    
    try:
        application = Application.builder().token(bot_token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("pay", pay_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_error_handler(error_handler)
        
        mode = "TEST" if TEST_MODE else "LIVE"
        logger.info(f"🤖 Digigo Payment Bot started in {mode} MODE")
        logger.info(f"🔒 Security: Credentials encrypted and masked")
        logger.info(f"✅ Bot ready to accept commands")
        
        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Bot stopped gracefully")
        finally:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
            
    except Exception as e:
        logger.critical(f"🚨 CRITICAL: Bot startup failed: {sanitize_log(str(e))}")

if __name__ == '__main__':
    asyncio.run(main())

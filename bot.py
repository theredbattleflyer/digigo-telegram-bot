import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import requests
import uuid
import asyncio

# Configuration
TELEGRAM_BOT_TOKEN = "8043614250:AAEvm4N5OyPhk_0fTt1TT0G1aTMrRn2_35E"
READIES_PUBLIC_KEY = "pu_91c0229efbc1a9cb78089faacc4a27e6"
READIES_PRIVATE_KEY = "pk_84ea858945242bba7f23e19c3401dd3e"
READIES_API_BASE = "https://api.readies.biz"
MERCHANT_EMAIL = "kaziafnan95@gmail.com"

# Currency conversion API (free)
EXCHANGE_API = "https://api.exchangerate-api.com/v4/latest/USD"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get exchange rates
def get_exchange_rates():
    try:
        response = requests.get(EXCHANGE_API, timeout=5)
        data = response.json()
        return {
            'USD': 1,
            'EUR': data['rates']['EUR']
        }
    except Exception as e:
        logger.warning(f"Exchange rate fetch failed: {e}. Using fallback.")
        return {'USD': 1, 'EUR': 0.92}  # Fallback rates

# Create payment link
def create_payment_link(amount, currency, customer_email):
    try:
        headers = {
            'Authorization': f'Bearer {READIES_PRIVATE_KEY}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Generate unique reference
        reference = str(uuid.uuid4())
        
        payload = {
            'amount': amount,
            'currency': currency,
            'customer_email': customer_email,
            'redirect_url': 'https://digigo.studio',
            'merchant_name': 'Digigo Studio',
            'reference': reference,
            'description': 'Digigo Studio Payment',
            'public_key': READIES_PUBLIC_KEY
        }
        
        logger.info(f"Creating payment link for {amount} {currency}")
        
        # Try different endpoint patterns
        endpoints_to_try = [
            f'{READIES_API_BASE}/v1/payment-links',
            f'{READIES_API_BASE}/api/v1/payment-links',
            f'{READIES_API_BASE}/payment-links',
            f'{READIES_API_BASE}/v1/payments',
            f'{READIES_API_BASE}/api/payments',
            f'{READIES_API_BASE}/payments/create'
        ]
        
        for endpoint in endpoints_to_try:
            try:
                logger.info(f"Trying endpoint: {endpoint}")
                response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
                
                logger.info(f"Response status: {response.status_code}")
                logger.info(f"Response body: {response.text[:200]}")
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    # Look for payment link in various possible response fields
                    payment_url = (
                        data.get('payment_url') or 
                        data.get('url') or 
                        data.get('link') or 
                        data.get('checkout_url') or
                        data.get('payment_link') or
                        data.get('data', {}).get('payment_url') or
                        data.get('data', {}).get('url')
                    )
                    
                    if payment_url:
                        logger.info(f"Payment link created successfully: {payment_url}")
                        return payment_url
                        
            except requests.exceptions.RequestException as e:
                logger.warning(f"Endpoint {endpoint} failed: {e}")
                continue
        
        logger.error("All endpoints failed")
        return None
        
    except Exception as e:
        logger.error(f"Payment link creation error: {e}", exc_info=True)
        return None

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💳 Make Payment", callback_data='payment')],
        [InlineKeyboardButton("❓ Help", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = (
        "🎨 *Welcome to Digigo Studio Payment Bot*\n\n"
        "Bring your creative ideas to life!\n\n"
        "Click the button below to make a payment."
    )
    
    await update.message.reply_text(
        welcome_message, 
        reply_markup=reply_markup, 
        parse_mode='Markdown'
    )

# Handle payment button
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'payment':
        await query.edit_message_text(
            "💰 *Create Payment Link*\n\n"
            "Please enter the amount and your email in this format:\n\n"
            "`/pay 50 USD your@email.com`\n\n"
            "*Supported currencies:* USD, EUR\n\n"
            "*Examples:*\n"
            "• `/pay 100 USD john@example.com`\n"
            "• `/pay 75 EUR jane@example.com`",
            parse_mode='Markdown'
        )
    elif query.data == 'help':
        await show_help(query)

async def show_help(query):
    help_text = (
        "📖 *How to Use Digigo Payment Bot*\n\n"
        "*Commands:*\n"
        "• `/start` - Start the bot\n"
        "• `/pay [amount] [currency] [email]` - Create payment link\n"
        "• `/help` - Show this help message\n\n"
        "*Supported Currencies:*\n"
        "• USD (US Dollar)\n"
        "• EUR (Euro)\n\n"
        "*Payment Instructions:*\n"
        "1. Use the `/pay` command with amount, currency, and email\n"
        "2. Get your unique payment link\n"
        "3. Click 'Pay Now' to complete payment\n"
        "4. After payment, you'll be redirected to Digigo Studio\n\n"
        "*Example:*\n"
        "`/pay 100 USD john@example.com`"
    )
    await query.edit_message_text(help_text, parse_mode='Markdown')

# Handle payment command
async def pay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) < 3:
            await update.message.reply_text(
                "❌ *Invalid format!*\n\n"
                "Please use: `/pay [amount] [currency] [email]`\n\n"
                "*Example:*\n"
                "`/pay 50 USD your@email.com`",
                parse_mode='Markdown'
            )
            return
        
        # Parse arguments
        amount_str = context.args[0]
        currency = context.args[1].upper()
        customer_email = context.args[2]
        
        # Validate amount
        try:
            amount = float(amount_str)
            if amount <= 0:
                await update.message.reply_text("❌ Amount must be greater than 0!")
                return
        except ValueError:
            await update.message.reply_text("❌ Invalid amount! Please enter a valid number.")
            return
        
        # Validate currency
        if currency not in ['USD', 'EUR']:
            await update.message.reply_text(
                "❌ Only USD and EUR are supported!\n\n"
                "Example: `/pay 50 USD your@email.com`",
                parse_mode='Markdown'
            )
            return
        
        # Validate email
        if '@' not in customer_email or '.' not in customer_email:
            await update.message.reply_text("❌ Please provide a valid email address!")
            return
        
        # Send processing message
        processing_msg = await update.message.reply_text("⏳ Generating your payment link...")
        
        # Create payment link
        payment_url = create_payment_link(amount, currency, customer_email)
        
        if payment_url:
            keyboard = [[InlineKeyboardButton("💳 Pay Now", url=payment_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await processing_msg.edit_text(
                f"✅ *Payment Link Generated!*\n\n"
                f"💵 *Amount:* {amount} {currency}\n"
                f"📧 *Email:* {customer_email}\n\n"
                f"Click the button below to complete your payment.\n"
                f"After payment, you'll be redirected to Digigo Studio.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await processing_msg.edit_text(
                "❌ *Failed to generate payment link*\n\n"
                "This could be due to:\n"
                "• API configuration issue\n"
                "• Invalid credentials\n"
                "• Network error\n\n"
                "Please contact support: kaziafnan95@gmail.com"
            )
    
    except Exception as e:
        logger.error(f"Payment command error: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ An unexpected error occurred. Please try again or contact support."
        )

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *How to Use Digigo Payment Bot*\n\n"
        "*Commands:*\n"
        "• `/start` - Start the bot\n"
        "• `/pay [amount] [currency] [email]` - Create payment link\n"
        "• `/help` - Show this help message\n\n"
        "*Supported Currencies:*\n"
        "• USD (US Dollar)\n"
        "• EUR (Euro)\n\n"
        "*Payment Instructions:*\n"
        "1. Use the `/pay` command with amount, currency, and email\n"
        "2. Get your unique payment link\n"
        "3. Click 'Pay Now' to complete payment\n"
        "4. After payment, you'll be redirected to Digigo Studio\n\n"
        "*Examples:*\n"
        "`/pay 100 USD john@example.com`\n"
        "`/pay 75 EUR jane@example.com`"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)

# Main function
async def main():
    """Start the bot."""
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("pay", pay_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("🤖 Digigo Payment Bot started successfully!")
    logger.info(f"Bot is running in polling mode...")
    
    # Run the bot until stopped
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    # Keep the bot running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    asyncio.run(main())

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import requests
import uuid

# Configuration
TELEGRAM_BOT_TOKEN = "8043614250:AAEvm4N5OyPhk_0fTt1TT0G1aTMrRn2_35E"
READIES_PUBLIC_KEY = "pu_91c0229efbc1a9cb78089faacc4a27e6"
READIES_PRIVATE_KEY = "pk_84ea858945242bba7f23e19c3401dd3e"
READIES_API_BASE = "https://api.readies.biz"
MERCHANT_EMAIL = "kaziafnan95@gmail.com"

# Currency conversion API (free)
EXCHANGE_API = "https://api.exchangerate-api.com/v4/latest/USD"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get exchange rates
def get_exchange_rates():
    try:
        response = requests.get(EXCHANGE_API)
        data = response.json()
        return {
            'USD': 1,
            'EUR': data['rates']['EUR']
        }
    except:
        return {'USD': 1, 'EUR': 0.92}  # Fallback rates

# Create payment link
def create_payment_link(amount, currency, customer_email):
    try:
        headers = {
            'Authorization': f'Bearer {READIES_PRIVATE_KEY}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'amount': amount,
            'currency': currency,
            'customer_email': customer_email,
            'redirect_url': 'https://digigo.studio',
            'merchant_name': 'Digigo Studio',
            'reference': str(uuid.uuid4()),
            'description': 'Digigo Studio Payment'
        }
        
        # Try different endpoint patterns
        endpoints_to_try = [
            f'{READIES_API_BASE}/v1/payment-links',
            f'{READIES_API_BASE}/api/v1/payment-links',
            f'{READIES_API_BASE}/payment-links',
            f'{READIES_API_BASE}/v1/payments'
        ]
        
        for endpoint in endpoints_to_try:
            try:
                response = requests.post(endpoint, json=payload, headers=headers)
                if response.status_code in [200, 201]:
                    data = response.json()
                    # Look for payment link in various possible response fields
                    payment_url = data.get('payment_url') or data.get('url') or data.get('link') or data.get('checkout_url')
                    if payment_url:
                        return payment_url
            except:
                continue
        
        return None
    except Exception as e:
        logger.error(f"Payment link creation error: {e}")
        return None

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💳 Make Payment", callback_data='payment')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = """
🎨 **Welcome to Digigo Studio Payment Bot**

Bring your creative ideas to life!

Click the button below to make a payment.
    """
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')

# Handle payment button
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'payment':
        await query.edit_message_text(
            "Please enter the amount and your email in this format:\n\n"
            "`/pay 50 USD your@email.com`\n\n"
            "Supported currencies: USD, EUR",
            parse_mode='Markdown'
        )

# Handle payment command
async def pay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) < 3:
            await update.message.reply_text(
                "❌ Invalid format!\n\n"
                "Please use: `/pay 50 USD your@email.com`",
                parse_mode='Markdown'
            )
            return
        
        amount = float(context.args[0])
        currency = context.args[1].upper()
        customer_email = context.args[2]
        
        if currency not in ['USD', 'EUR']:
            await update.message.reply_text("❌ Only USD and EUR are supported!")
            return
        
        if '@' not in customer_email:
            await update.message.reply_text("❌ Please provide a valid email address!")
            return
        
        await update.message.reply_text("⏳ Generating your payment link...")
        
        # Create payment link
        payment_url = create_payment_link(amount, currency, customer_email)
        
        if payment_url:
            keyboard = [[InlineKeyboardButton("💳 Pay Now", url=payment_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ **Payment Link Generated!**\n\n"
                f"Amount: {amount} {currency}\n"
                f"Email: {customer_email}\n\n"
                f"Click the button below to complete your payment:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "❌ Failed to generate payment link.\n\n"
                "Please contact support or try again later."
            )
    
    except ValueError:
        await update.message.reply_text("❌ Invalid amount! Please enter a valid number.")
    except Exception as e:
        logger.error(f"Payment command error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📖 **How to Use Digigo Payment Bot**

1. Click "Make Payment" button or use commands below
2. Enter payment details in this format:
   `/pay 50 USD your@email.com`

**Commands:**
/start - Start the bot
/pay [amount] [currency] [email] - Create payment link
/help - Show this help message

**Supported Currencies:**
• USD (US Dollar)
• EUR (Euro)

**Example:**
`/pay 100 USD john@example.com`
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

# Main function
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("pay", pay_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("Bot started successfully!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

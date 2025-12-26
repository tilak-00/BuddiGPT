from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

GEMINI_KEY = "API_KEY"
BOT_TOKEN = "Bot_Token"

client = genai.Client(api_key=GEMINI_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 BuddiGPT Free AI Bot Ready!\n\n"
        "Use:\n"
        "/ask your question\n\n"
        "Supports: Chat, Q/A, Coding\n"
        "Images & Videos are disabled (billing required)"
    )

def choose_model(prompt: str):
    prompt_lower = prompt.lower()

    long_question = len(prompt) > 200
    complex_keywords = [
        "analysis", "explain", "detailed", "research",
        "compare", "advanced", "why", "how", "long answer",
        "code review", "optimize", "architecture"
    ]

    if long_question or any(k in prompt_lower for k in complex_keywords):
        return "models/gemini-2.5-pro"   # smarter
    return "models/gemini-2.5-flash"     # fast

async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if context.args:
        prompt = " ".join(context.args)
    else:
        prompt = update.message.text

    if not prompt:
        await update.message.reply_text("Please type a question 🙂")
        return

    model_name = choose_model(prompt)

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
    except Exception as e:
        # fallback to flash if pro fails / billing / quota
        response = client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=prompt
        )

    reply = response.text

    for i in range(0, len(reply), 4000):
        await update.message.reply_text(reply[i:i+4000])



app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ask", ask))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ask))


print("🤖 BuddiGPT Free AI Bot Running...")
app.run_polling()

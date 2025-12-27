from telegram.constants import ChatAction
import asyncio
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

GEMINI_KEY = "API_KEY"
GROQ_KEY = "API_KEY"
BOT_TOKEN = "Bot_Token"

client = genai.Client(api_key=GEMINI_KEY)
groq_client = Groq(api_key=GROQ_KEY)

bot_messages = {}
user_memory = {}

FALLBACK_MODELS = [
    "models/gemini-2.5-pro",
    "models/gemini-2.5-flash",
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-lite",
    "models/gemini-flash-latest",
    "models/gemini-pro-latest"
]


# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 BuddiGPT Free AI Bot!\n\n"
        "Use:\n"
        "/ask your question\n"
        "Or just type normally\n\n"
        "Supports: Chat, Q/A, Coding 🔥"
    )


# ================== MODEL PICK ==================
def choose_model(prompt: str):
    prompt_lower = prompt.lower()

    long_question = len(prompt) > 200
    complex_keywords = [
        "analysis", "explain", "detailed", "research",
        "compare", "advanced", "why", "how", "long answer",
        "code review", "optimize", "architecture"
    ]

    if long_question or any(k in prompt_lower for k in complex_keywords):
        return "models/gemini-2.5-pro"
    return "models/gemini-2.5-flash"


# ================== ASK FUNCTION ==================
async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id

    # -------- PROMPT --------
    if context.args:
        prompt = " ".join(context.args)
    else:
        prompt = update.message.text

    if not prompt:
        await update.message.reply_text("Please type something 🙂")
        return

    # -------- MEMORY --------
    if user_id not in user_memory:
        user_memory[user_id] = []

    user_memory[user_id].append({
        "role": "user",
        "parts": [{"text": prompt}]
    })

    if len(user_memory[user_id]) > 20:
        user_memory[user_id] = user_memory[user_id][-20:]

    # -------- MODEL LIST --------
    models_to_try = [
        choose_model(prompt),
        *FALLBACK_MODELS
    ]

    # -------- TYPING --------
    stop_typing = asyncio.Event()

    async def typing_loop():
        while not stop_typing.is_set():
            try:
                await context.bot.send_chat_action(
                    chat_id=chat_id,
                    action=ChatAction.TYPING
                )
            except:
                pass
            await asyncio.sleep(3)

    typing_task = asyncio.create_task(typing_loop())
    response_text = None
    errors = genai.errors

    # ================== 1️⃣ TRY GEMINI ==================
    try:
        for model in models_to_try:
            try:
                gemini_res = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model,
                    contents=user_memory[user_id]
                )
                response_text = gemini_res.text
                print("Using Gemini:", model)
                break
            except errors.ClientError as e:
                if "429" in str(e):
                    print(f"[LIMIT] {model} exhausted → next")
                    continue
                elif "404" in str(e):
                    print(f"[NOT FOUND] skipping {model}")
                    continue
                else:
                    raise

        # ================== 2️⃣ TRY GROQ ==================
        if not response_text:
            print("Switching to Groq...")

            GROQ_MODELS = [
                "llama-3.3-70b-versatile",    # best quality
                "llama-3.1-8b-instant",       # very fast
                "llama-3.1-70b-versatile-v2"  # backup
            ]

            for groq_model in GROQ_MODELS:
                try:
                    groq_res = await asyncio.to_thread(
                        groq_client.chat.completions.create,
                        model=groq_model,
                        messages=[
                            {"role": "system", "content": "You are BuddiGPT helpful assistant"},
                            *[
                                {
                                    "role": "user" if m["role"] == "user" else "assistant",
                                    "content": m["parts"][0]["text"]
                                }
                                for m in user_memory[user_id]
                            ]
                        ]
                    )

                    response_text = groq_res.choices[0].message.content
                    print("Using Groq:", groq_model)
                    break

                except Exception as e:
                    print(f"GROQ Model failed: {groq_model} → {e}")
                    continue

    finally:
        stop_typing.set()
        try:
            await typing_task
        except:
            pass

    # -------- IF NOTHING WORKED --------
    if not response_text:
        await update.message.reply_text(
            "⚠️ All AI providers are busy.\nPlease try again later."
        )
        return

    reply = response_text

    # -------- SAVE MEMORY --------
    user_memory[user_id].append({
        "role": "model",
        "parts": [{"text": reply}]
    })

    # -------- SEND CHUNKS --------
    for i in range(0, len(reply), 4000):
        msg = await update.message.reply_text(reply[i:i + 4000])
        bot_messages.setdefault(user_id, []).append(msg.message_id)


# ================= INTRO =================
async def intro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*Welcome to BuddiGPT 🤖*\n\n"
        "I can help you with:\n"
        "• Q/A\n"
        "• Coding\n"
        "• Study Help\n"
        "• Smart Chat\n\n"
        "Just ask me!"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ================= HELP =================
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🆘 *Help Menu*\n\n"
        "`/start` – Start bot\n"
        "`/intro` – What I can do\n"
        "`/ask question` – Ask anything\n"
        "`/reset` – Clear memory\n"
        "Or just type normally 😊"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ================= RESET =================
async def reset(update: Update, context):
    user_id = update.message.from_user.id

    user_memory.pop(user_id, None)

    if user_id in bot_messages:
        for msg_id in bot_messages[user_id]:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=msg_id)
            except:
                pass
        bot_messages[user_id] = []

    await update.message.reply_text("🧹 Memory cleared!")


# ================= RUN BOT =================
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("intro", intro))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(CommandHandler("reset", reset))
app.add_handler(CommandHandler("ask", ask))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ask))

print("🤖 BuddiGPT — Running with Gemini + Groq...")
app.run_polling()


print("🤖 BuddiGPT Free AI Bot Running...")
app.run_polling()


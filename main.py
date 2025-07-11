import os
import img2pdf
from PyPDF2 import PdfMerger
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from keep_alive import keep_alive

user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome!\n\nCommands:\n"
        "/setinsert - Send image for Page 1\n"
        "/setcover - Send image for thumbnail\n"
        "/setname <filename.pdf> - Rename final file\n"
        "\nSend your PDF after setup."
    )

async def set_insert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data.setdefault(update.effective_user.id, {})['waiting_for'] = 'insert'
    await update.message.reply_text("📸 Send the image to insert as Page 1")

async def set_cover_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data.setdefault(update.effective_user.id, {})['waiting_for'] = 'cover'
    await update.message.reply_text("📸 Send the image for thumbnail")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    waiting = user_data.get(user_id, {}).get("waiting_for")

    photo = await update.message.photo[-1].get_file()
    file_path = f"{user_id}_{waiting}.jpg"
    await photo.download_to_drive(file_path)
    user_data[user_id][waiting] = file_path
    user_data[user_id]["waiting_for"] = None
    await update.message.reply_text(f"✅ {waiting.capitalize()} image saved!")

async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Use: /setname yourfilename.pdf")
        return
    name = " ".join(context.args)
    if not name.endswith(".pdf"):
        name += ".pdf"
    user_data.setdefault(update.effective_user.id, {})["filename"] = name
    await update.message.reply_text(f"✅ File will be named: {name}")

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_data.get(user_id, {})

    insert_img = data.get("insert")
    filename = data.get("filename", "Edited_File.pdf")

    if not insert_img:
        await update.message.reply_text("❌ Use /setinsert to set Page 1 image first")
        return

    file = update.message.document
    if file.file_size > 200 * 1024 * 1024:
        await update.message.reply_text("❌ File too big! Max 200MB allowed.")
        return

    await update.message.reply_text("🔄 Processing...")

    try:
        doc_file = await file.get_file()
        await doc_file.download_to_drive("original.pdf")

        # Step 1: Convert image to PDF
        with open("insert_page.pdf", "wb") as f:
            f.write(img2pdf.convert(insert_img))

        # Step 2: Merge image + original PDF
        merger = PdfMerger()
        merger.append("insert_page.pdf")
        merger.append("original.pdf")
        merger.write(filename)
        merger.close()

        # Step 3: Send file
        with open(filename, "rb") as f:
            if "cover" in data:
                with open(data["cover"], "rb") as t:
                    await update.message.reply_document(document=f, filename=filename, thumbnail=t)
            else:
                await update.message.reply_document(document=f, filename=filename)

        # Clean up
        for file in ["original.pdf", "insert_page.pdf", filename]:
            if os.path.exists(file):
                os.remove(file)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

def main():
    keep_alive()
    token = os.getenv("TOKEN")
    if not token:
        print("❌ Error: Set TOKEN in .env")
        return

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setinsert", set_insert_command))
    app.add_handler(CommandHandler("setcover", set_cover_command))
    app.add_handler(CommandHandler("setname", set_name))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    print("🤖 Bot started.")
    app.run_polling()

if __name__ == "__main__":
    main()

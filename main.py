import os
import requests
import fitz  # PyMuPDF
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from keep_alive import keep_alive

user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome!\n\nCommands:\n"
        "/setinsert - Send image for Page 1\n"
        "/setcover - Send image for thumbnail\n"
        "/setname <filename.pdf> - Set output file name\n"
        "Now send me a PDF!"
    )

async def set_insert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data.setdefault(update.effective_user.id, {})['waiting'] = 'insert'
    await update.message.reply_text("📥 Now send image to insert on Page 1.")

async def set_cover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data.setdefault(update.effective_user.id, {})['waiting'] = 'cover'
    await update.message.reply_text("🖼️ Now send image for Telegram thumbnail.")

async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Example: /setname myfile.pdf")
        return
    name = " ".join(context.args)
    if not name.endswith(".pdf"):
        name += ".pdf"
    user_data.setdefault(update.effective_user.id, {})['filename'] = name
    await update.message.reply_text(f"✅ File name set to: {name}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    waiting = user_data.get(user_id, {}).get("waiting")

    if waiting not in ['insert', 'cover']:
        await update.message.reply_text("❗ Use /setinsert or /setcover first.")
        return

    photo = await update.message.photo[-1].get_file()
    path = f"{user_id}_{waiting}.jpg"
    await photo.download_to_drive(path)
    user_data[user_id][waiting] = path
    user_data[user_id]['waiting'] = None
    await update.message.reply_text(f"✅ Saved {waiting} image!")

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_data.get(user_id, {})
    insert_path = data.get("insert")
    cover_path = data.get("cover")
    output_name = data.get("filename", "Edited_File.pdf")

    if not insert_path:
        await update.message.reply_text("❌ Please set insert image with /setinsert")
        return

    try:
        file = update.message.document
        if file.file_size > 200 * 1024 * 1024:
            await update.message.reply_text("❌ File too large. Max: 200MB.")
            return

        await update.message.reply_text("🔧 Processing PDF...")

        tg_file = await file.get_file()
        await tg_file.download_to_drive("input.pdf")

        # Open PDF and create new with image as first page
        original = fitz.open("input.pdf")
        new_pdf = fitz.open()
        img_page = new_pdf.new_page(width=595, height=842)
        img_page.insert_image(fitz.Rect(0, 0, 595, 842), filename=insert_path)
        new_pdf.insert_pdf(original)
        new_pdf.save(output_name)
        new_pdf.close()
        original.close()

        # Send the file or upload to file.io if too big
        if os.path.getsize(output_name) > 48 * 1024 * 1024:
            await update.message.reply_text("📤 Uploading to file.io (file too big)...")
            with open(output_name, 'rb') as f:
                res = requests.post("https://file.io", files={"file": f})
            link = res.json().get("link")
            await update.message.reply_text(f"✅ File uploaded: {link}")
        else:
            with open(output_name, 'rb') as f:
                if cover_path and os.path.exists(cover_path):
                    with open(cover_path, 'rb') as thumb:
                        await update.message.reply_document(document=f, filename=output_name, thumbnail=thumb)
                else:
                    await update.message.reply_document(document=f, filename=output_name)

        os.remove("input.pdf")
        os.remove(output_name)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

def main():
    keep_alive()
    token = os.getenv("TOKEN")
    if not token:
        print("❌ TOKEN env variable missing")
        return

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setinsert", set_insert))
    app.add_handler(CommandHandler("setcover", set_cover))
    app.add_handler(CommandHandler("setname", set_name))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.run_polling()

if __name__ == '__main__':
    main()

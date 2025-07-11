import os
import requests
try:
    import fitz  # PyMuPDF
except ImportError:
    import pymupdf as fitz  # fallback if renamed
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from keep_alive import keep_alive

user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome!\n\nCommands:\n"
        "/setinsert - Then send an image to insert on Page 1\n"
        "/setcover - Then send an image for Telegram preview\n"
        "/setname <filename.pdf> - Set file name\n"
        "\nAfter setting up, send me a PDF to process!"
    )

async def set_insert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data.setdefault(update.effective_user.id, {})['waiting_for'] = 'insert'
    await update.message.reply_text("📸 Now send me the image to insert on Page 1")

async def set_cover_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data.setdefault(update.effective_user.id, {})['waiting_for'] = 'cover'
    await update.message.reply_text("📸 Now send me the thumbnail image for Telegram preview")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_data.get(user_id, {})
    waiting_for = data.get('waiting_for')
    
    if waiting_for == 'insert':
        photo = await update.message.photo[-1].get_file()
        path = f"{user_id}_insert.jpg"
        await photo.download_to_drive(path)
        user_data[user_id]['insert'] = path
        user_data[user_id]['waiting_for'] = None
        await update.message.reply_text("✅ Insert image for Page 1 saved!")
    
    elif waiting_for == 'cover':
        photo = await update.message.photo[-1].get_file()
        path = f"{user_id}_cover.jpg"
        await photo.download_to_drive(path)
        user_data[user_id]['cover'] = path
        user_data[user_id]['waiting_for'] = None
        await update.message.reply_text("✅ Thumbnail image saved!")
    
    else:
        await update.message.reply_text("❌ Please use /setinsert or /setcover first to specify what this image is for")

async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Please provide a filename. Example: /setname myfile.pdf")
        return
    
    name = " ".join(context.args)
    if not name.endswith(".pdf"):
        name += ".pdf"
    user_data.setdefault(update.effective_user.id, {})['filename'] = name
    await update.message.reply_text(f"✅ File name set to: {name}")

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_data.get(user_id, {})

    insert_path = data.get("insert")
    filename = data.get("filename", "Edited_File.pdf")
    thumbnail = data.get("cover")

    if not insert_path:
        await update.message.reply_text("❌ Please set insert image first using /setinsert")
        return

    try:
        await update.message.reply_text("🔄 Processing PDF...")
        
        pdf_file = await update.message.document.get_file()
        await pdf_file.download_to_drive("input.pdf")
        
        # Open the original PDF
        base_pdf = fitz.open("input.pdf")

        # Create a new PDF with the image as first page
        insert_pdf = fitz.open()
        img_page = insert_pdf.new_page(width=595, height=842)
        img_rect = fitz.Rect(0, 0, 595, 842)
        img_page.insert_image(img_rect, filename=insert_path)

        # Insert all pages from the original PDF after the image page
        insert_pdf.insert_pdf(base_pdf)

        output_name = filename
        insert_pdf.save(output_name)
        insert_pdf.close()
        base_pdf.close()

        # Upload to file.io (for >50MB bypass)
        try:
            with open(output_name, 'rb') as f:
                res = requests.post("https://file.io", files={"file": f})

            if res.status_code == 200:
                link = res.json().get("link")
                await update.message.reply_text(
                    f"✅ PDF processed successfully!\n\n📎 [Download PDF]({link})",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("❌ Upload failed. Please try again.")

        except Exception as e:
            await update.message.reply_text(f"❌ Error during upload: `{e}`", parse_mode="Markdown")

        # Clean up files
        for file_path in ["input.pdf", output_name, insert_path, thumbnail]:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

    except Exception as e:
        await update.message.reply_text(f"❌ Error processing PDF: `{e}`", parse_mode="Markdown")


def main():
    keep_alive()  # Flask alive service for Replit or hosting
    
    token = os.getenv("TOKEN")
    if not token:
        print("❌ Error: TOKEN environment variable not set!")
        return
    
    try:
        application = Application.builder().token(token).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("setinsert", set_insert_command))
        application.add_handler(CommandHandler("setcover", set_cover_command))
        application.add_handler(CommandHandler("setname", set_name))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

        print("🤖 Bot starting...")
        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        print(f"❌ Error starting bot: {e}")


if __name__ == '__main__':
    main()

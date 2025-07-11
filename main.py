uimport os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from keep_alive import keep_alive
from PyPDF2 import PdfMerger
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to the Lightweight PDF Bot!\n\n"
        "Commands:\n"
        "/setinsert - Send image for Page 1\n"
        "/setcover - Send image for Telegram thumbnail\n"
        "/setname <filename.pdf> - Set output PDF name\n"
        "Then send any PDF file to process!"
    )

async def set_insert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data.setdefault(update.effective_user.id, {})['waiting_for'] = 'insert'
    await update.message.reply_text("📸 Send image for Page 1")

async def set_cover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data.setdefault(update.effective_user.id, {})['waiting_for'] = 'cover'
    await update.message.reply_text("🖼️ Send image for thumbnail")

async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Use like: /setname myfile.pdf")
        return
    filename = " ".join(context.args)
    if not filename.endswith(".pdf"):
        filename += ".pdf"
    user_data.setdefault(update.effective_user.id, {})['filename'] = filename
    await update.message.reply_text(f"✅ File name set to: {filename}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    purpose = user_data.setdefault(user_id, {}).get('waiting_for')
    photo_file = await update.message.photo[-1].get_file()
    file_path = f"{user_id}_{purpose}.jpg"
    await photo_file.download_to_drive(file_path)
    user_data[user_id][purpose] = file_path
    user_data[user_id]['waiting_for'] = None
    await update.message.reply_text(f"✅ {purpose.capitalize()} image saved.")

def image_to_pdf(img_path, output_path):
    img = Image.open(img_path).convert("RGB")
    img.save(output_path, "PDF", resolution=100.0)

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_data.get(user_id, {})
    insert_img = data.get('insert')
    output_name = data.get('filename', 'Edited_File.pdf')
    thumbnail = data.get('cover')

    if not insert_img:
        await update.message.reply_text("❌ Use /setinsert first.")
        return

    await update.message.reply_text("🔄 Processing PDF...")

    file = await update.message.document.get_file()
    await file.download_to_drive("original.pdf")

    # Convert insert image to PDF
    image_to_pdf(insert_img, "first_page.pdf")

    # Merge using PyPDF2
    merger = PdfMerger()
    merger.append("first_page.pdf")
    merger.append("original.pdf")
    merger.write(output_name)
    merger.close()

    # Send PDF
    import requests

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
    await update.message.reply_text(f"❌ Error: `{e}`", parse_mode="Markdown")
    # Cleanup
    for file in ['original.pdf', 'first_page.pdf', output_name]:
        if os.path.exists(file):
            os.remove(file)

    await update.message.reply_text("✅ Done!")

def main():
    keep_alive()
    token = "8048849948:AAE1tRpgfAOSWW-6c4gN2GEwnw7ADLChYEs"
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setinsert", set_insert))
    app.add_handler(CommandHandler("setcover", set_cover))
    app.add_handler(CommandHandler("setname", set_name))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    print("🤖 Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()

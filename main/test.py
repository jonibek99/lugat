import pandas as pd
import random
import os
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# CSV fayl nomi
CSV_FILE = 'vocabulary.csv'

# Bot tokenini bu yerga yozing
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # <<< BU YERGA TOKEN NI YOZING!

# Inglizcha-O'zbekcha lug'at
DICTIONARY = {
    'apple': 'olma', 'book': 'kitob', 'cat': 'mushuk', 'dog': 'it',
    'house': 'uy', 'car': 'mashina', 'water': 'suv', 'hello': 'salom',
    'goodbye': 'xayr', 'thank': 'rahmat', 'yes': 'ha', 'no': "yo'q",
    'man': 'erkak', 'woman': 'ayol', 'child': 'bola', 'school': 'maktab',
    'teacher': "o'qituvchi", 'student': "o'quvchi", 'friend': "do'st",
    'family': 'oilа', 'work': 'ish', 'time': 'vaqt', 'day': 'kun',
    'night': 'tun', 'city': 'shahar', 'country': 'davlat', 'world': 'dunyo',
    'life': 'hayot', 'love': 'sevgi', 'home': 'uy', 'room': 'xona',
    'table': 'stol', 'chair': 'stul', 'door': 'eshik', 'window': 'deraza',
    'pen': 'ruchka', 'paper': "qog'oz", 'computer': 'kompyuter',
    'phone': 'telefon', 'money': 'pul', 'market': 'bozor', 'road': "yo'l",
    'street': "ko'cha", 'park': 'park', 'tree': 'daraxt', 'flower': 'gul',
    'sun': 'quyosh', 'moon': 'oy', 'star': 'yulduz', 'sky': 'osmon',
    'earth': 'yer', 'fire': 'olov', 'air': 'havo', 'rain': "yomg'ir",
    'snow': 'qor', 'hot': 'issiq', 'cold': 'sovuq', 'big': 'katta',
    'small': 'kichik', 'good': 'yaxshi', 'bad': 'yomon', 'happy': 'baxtli',
    'sad': 'qayguli', 'beautiful': 'chiroyli', 'rich': 'boy',
    'strong': 'kuchli', 'fast': 'tez', 'slow': 'sekin', 'old': 'qari',
    'young': 'yosh', 'new': 'yangi', 'right': "o'ng", 'left': 'chap',
    'morning': 'ertalab', 'evening': 'kechqurun', 'bread': 'non',
    'rice': 'guruch', 'meat': "go'sht", 'fish': 'baliq', 'egg': 'tuxum',
    'milk': 'sut', 'tea': 'choy', 'coffee': 'qahva', 'sugar': 'shakar',
    'salt': 'tuz', 'red': 'qizil', 'blue': "ko'k", 'green': 'yashil',
    'yellow': 'sariq', 'black': 'qora', 'white': 'oq',
    'i': 'men', 'you': 'siz', 'he': 'u', 'she': 'u', 'it': 'u',
    'we': 'biz', 'they': 'ular', 'my': 'mening', 'your': 'sizning',
    'his': 'uning', 'her': 'uning', 'our': 'bizning', 'their': 'ularning',
    'one': 'bir', 'two': 'ikki', 'three': 'uch', 'four': "to'rt",
    'five': 'besh', 'six': 'olti', 'seven': 'yetti', 'eight': 'sakkiz',
    'nine': "to'qqiz", 'ten': "o'n"
}

# Foydalanuvchi ma'lumotlarini saqlash
user_data = {}

# Asosiy CSV faylni yuklash
def load_vocabulary():
    try:
        if os.path.exists(CSV_FILE):
            df = pd.read_csv(CSV_FILE)
        else:
            df = pd.DataFrame(columns=['word', 'translation', 'example', 'added_date'])
            df.to_csv(CSV_FILE, index=False)
        return df
    except:
        return pd.DataFrame(columns=['word', 'translation', 'example', 'added_date'])

# So'z qo'shish
def add_word(word, translation="", example=""):
    df = load_vocabulary()
    
    word_lower = word.lower().strip()
    
    # So'z mavjudligini tekshirish
    if not df.empty and word_lower in df['word'].str.lower().values:
        return False, "Bu so'z allaqachon mavjud"
    
    # Avtomatik tarjima
    if not translation:
        translation = DICTIONARY.get(word_lower, "")
        if not translation:
            # Agar lug'atda yo'q bo'lsa, kiritilishini so'rash
            return False, "not_found"
    
    # Misol yaratish
    if not example:
        example = f"I use {word} every day."
    
    new_word = pd.DataFrame({
        'word': [word],
        'translation': [translation],
        'example': [example],
        'added_date': [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    })
    
    df = pd.concat([df, new_word], ignore_index=True)
    df.to_csv(CSV_FILE, index=False)
    
    return True, "✅ So'z qo'shildi!"

# So'zni o'chirish
def delete_word(word):
    df = load_vocabulary()
    
    word_lower = word.lower().strip()
    
    if df.empty or word_lower not in df['word'].str.lower().values:
        return False, "So'z topilmadi"
    
    df = df[df['word'].str.lower() != word_lower]
    df.to_csv(CSV_FILE, index=False)
    
    return True, "✅ So'z o'chirildi!"

# /start komandasi
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    user_data[user_id] = {
        'mode': 'menu',
        'words': [],
        'current_index': 0,
        'correct_answers': 0
    }
    
    keyboard = [
        [InlineKeyboardButton("📚 10 ta so'z yodlash", callback_data='learn_10')],
        [InlineKeyboardButton("📚 20 ta so'z yodlash", callback_data='learn_20')],
        [InlineKeyboardButton("📝 Test topshirish", callback_data='test')],
        [InlineKeyboardButton("➕ So'z qo'shish", callback_data='add')],
        [InlineKeyboardButton("🗑️ So'z o'chirish", callback_data='delete')],
        [InlineKeyboardButton("📊 Statistika", callback_data='stats')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🇺🇿 Assalomu alaykum! Inglizcha so'zlar yodlash botiga xush kelibsiz!\n\n"
        "Botdan foydalanish:\n"
        "1. So'z qo'shish: 'apple' yoki 'apple, olma, I eat apple'\n"
        "2. So'z yodlash: 10/20 ta so'z\n"
        "3. Test: bilimingizni tekshiring\n\n"
        "Quyidagilardan birini tanlang:",
        reply_markup=reply_markup
    )

# Xabarlarni qayta ishlash
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_data:
        await start_command(update, context)
        return
    
    text = update.message.text.strip()
    
    if text == '/start':
        await start_command(update, context)
    else:
        # So'z qo'shish
        await add_word_from_message(update, context, text)

# So'z qo'shish
async def add_word_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    try:
        if ',' in text:
            # Format: word, translation, example
            parts = [part.strip() for part in text.split(',', 2)]
            
            if len(parts) >= 2:
                word = parts[0]
                translation = parts[1]
                example = parts[2] if len(parts) > 2 else ""
                
                success, message = add_word(word, translation, example)
                
                if success:
                    await update.message.reply_text(f"✅ So'z qo'shildi!\nInglizcha: {word}\nTarjima: {translation}")
                else:
                    await update.message.reply_text(f"❌ {message}")
            else:
                await update.message.reply_text("❌ Format noto'g'ri. Misol: apple, olma, I eat apple")
        
        else:
            # Faqat so'z
            word = text.strip()
            
            if word:
                success, message = add_word(word)
                
                if success:
                    df = load_vocabulary()
                    translation = df[df['word'].str.lower() == word.lower()]['translation'].values[0]
                    await update.message.reply_text(f"✅ So'z qo'shildi!\nInglizcha: {word}\nTarjima: {translation}")
                elif message == "not_found":
                    await update.message.reply_text(
                        f"❌ '{word}' so'zi lug'atda topilmadi.\n"
                        f"Iltimos, tarjimasini ham kiriting:\n"
                        f"<code>{word}, tarjima, misol</code>",
                        parse_mode='HTML'
                    )
                else:
                    await update.message.reply_text(f"❌ {message}")
            else:
                await update.message.reply_text("❌ Iltimos, so'z kiriting")
    
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")

# Callback query handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    try:
        if data == 'learn_10':
            await start_learning(query, 10)
        elif data == 'learn_20':
            await start_learning(query, 20)
        elif data == 'test':
            await start_test(query)
        elif data == 'add':
            await show_add_menu(query)
        elif data == 'delete':
            await show_delete_menu(query)
        elif data == 'stats':
            await show_stats(query)
        elif data == 'menu':
            await show_main_menu(query)
        elif data == 'next_word':
            await show_next_word(query)
        elif data.startswith('delete_'):
            word = data.replace('delete_', '')
            await delete_word_action(query, word)
        elif data.startswith('answer_'):
            await check_answer(query, data)
        else:
            await query.edit_message_text("❌ Noma'lum buyruq")
    
    except Exception as e:
        print(f"Xatolik: {e}")
        await query.edit_message_text("❌ Xatolik yuz berdi")

# Asosiy menyu
async def show_main_menu(query):
    keyboard = [
        [InlineKeyboardButton("📚 10 ta so'z yodlash", callback_data='learn_10')],
        [InlineKeyboardButton("📚 20 ta so'z yodlash", callback_data='learn_20')],
        [InlineKeyboardButton("📝 Test topshirish", callback_data='test')],
        [InlineKeyboardButton("➕ So'z qo'shish", callback_data='add')],
        [InlineKeyboardButton("🗑️ So'z o'chirish", callback_data='delete')],
        [InlineKeyboardButton("📊 Statistika", callback_data='stats')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🏠 Asosiy menyu\n\n"
        "Quyidagilardan birini tanlang:",
        reply_markup=reply_markup
    )

# So'z qo'shish menyusi
async def show_add_menu(query):
    keyboard = [
        [InlineKeyboardButton("🏠 Asosiy menyu", callback_data='menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "➕ So'z qo'shish\n\n"
        "Quyidagi formatlardan birida yozing:\n\n"
        "1. Faqat so'z (avtomatik tarjima):\n"
        "   <code>apple</code>\n\n"
        "2. To'liq format:\n"
        "   <code>apple, olma, I eat an apple</code>\n\n"
        "Endi so'zni yozing:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

# So'z o'chirish menyusi
async def show_delete_menu(query):
    df = load_vocabulary()
    
    if df.empty:
        keyboard = [[InlineKeyboardButton("🏠 Asosiy menyu", callback_data='menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ Lug'at bo'sh", reply_markup=reply_markup)
        return
    
    # So'zlarni 5 ta guruhga ajratish
    words = df['word'].tolist()
    keyboard = []
    
    for i in range(0, min(20, len(words)), 4):
        row = []
        for j in range(4):
            if i + j < len(words):
                word = words[i + j]
                row.append(InlineKeyboardButton(word, callback_data=f'delete_{word}'))
        if row:
            keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🏠 Asosiy menyu", callback_data='menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🗑️ O'chirmoqchi bo'lgan so'zingizni tanlang:",
        reply_markup=reply_markup
    )

# So'zni o'chirish amali
async def delete_word_action(query, word):
    success, message = delete_word(word)
    
    keyboard = [[InlineKeyboardButton("🏠 Asosiy menyu", callback_data='menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(f"{message}", reply_markup=reply_markup)

# Statistika
async def show_stats(query):
    df = load_vocabulary()
    
    total_words = len(df)
    
    text = f"📊 Statistika\n\n"
    text += f"📚 Jami so'zlar: {total_words} ta\n\n"
    
    if total_words > 0:
        text += "Oxirgi 10 ta so'z:\n"
        recent_words = df.tail(10)
        for i, row in recent_words.iterrows():
            text += f"• {row['word']} - {row['translation']}\n"
    
    keyboard = [[InlineKeyboardButton("🏠 Asosiy menyu", callback_data='menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

# Yodlashni boshlash
async def start_learning(query, count):
    df = load_vocabulary()
    
    if df.empty:
        keyboard = [[InlineKeyboardButton("🏠 Asosiy menyu", callback_data='menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ Lug'at bo'sh. Avval so'z qo'shing.", reply_markup=reply_markup)
        return
    
    if len(df) < count:
        count = len(df)
    
    words = df.sample(n=count).to_dict('records')
    user_id = query.from_user.id
    
    if user_id not in user_data:
        user_data[user_id] = {}
    
    user_data[user_id]['words'] = words
    user_data[user_id]['current_index'] = 0
    user_data[user_id]['mode'] = 'learning'
    
    await show_word(query, user_id)

# So'zni ko'rsatish
async def show_word(query, user_id):
    words = user_data[user_id]['words']
    current_index = user_data[user_id]['current_index']
    
    if current_index < len(words):
        word = words[current_index]
        
        text = f"📖 So'z {current_index + 1}/{len(words)}\n\n"
        text += f"<b>Inglizcha:</b> {word['word']}\n"
        text += f"<b>Tarjima:</b> {word['translation']}\n"
        if word['example']:
            text += f"<b>Misol:</b> {word['example']}\n"
        
        keyboard = [[InlineKeyboardButton("✅ Keyingi so'z", callback_data='next_word')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # Yakun
        text = f"🎉 Tabriklayman! {len(words)} ta so'zni yodladingiz!\n\n"
        text += "Yana yodlash yoki test topshirishni xohlaysizmi?"
        
        keyboard = [
            [InlineKeyboardButton("📚 Yana yodlash", callback_data='learn_10')],
            [InlineKeyboardButton("📝 Test topshirish", callback_data='test')],
            [InlineKeyboardButton("🏠 Asosiy menyu", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)

# Keyingi so'z
async def show_next_word(query):
    user_id = query.from_user.id
    
    if user_id not in user_data:
        await show_main_menu(query)
        return
    
    user_data[user_id]['current_index'] += 1
    await show_word(query, user_id)

# Testni boshlash
async def start_test(query):
    df = load_vocabulary()
    
    if len(df) < 4:
        keyboard = [[InlineKeyboardButton("🏠 Asosiy menyu", callback_data='menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ Test uchun kamida 4 ta so'z kerak.", reply_markup=reply_markup)
        return
    
    count = min(10, len(df))
    test_words = df.sample(n=count).to_dict('records')
    user_id = query.from_user.id
    
    if user_id not in user_data:
        user_data[user_id] = {}
    
    user_data[user_id]['test_words'] = test_words
    user_data[user_id]['current_index'] = 0
    user_data[user_id]['correct_answers'] = 0
    user_data[user_id]['mode'] = 'test'
    
    await show_test_question(query, user_id)

# Test savolini ko'rsatish
async def show_test_question(query, user_id):
    test_words = user_data[user_id]['test_words']
    current_index = user_data[user_id]['current_index']
    
    if current_index < len(test_words):
        word = test_words[current_index]
        
        # Variantlarni tanlash
        df = load_vocabulary()
        correct_answer = word['translation']
        
        # Noto'g'ri variantlar
        wrong_answers = df[df['word'] != word['word']].sample(n=3)['translation'].tolist()
        
        # Agar yetarli variant bo'lmasa
        if len(wrong_answers) < 3:
            wrong_answers += ["Noto'g'ri 1", "Noto'g'ri 2", "Noto'g'ri 3"][:3-len(wrong_answers)]
        
        # Barcha variantlar
        all_answers = [correct_answer] + wrong_answers[:3]
        random.shuffle(all_answers)
        
        # Tugmalar
        keyboard = []
        for i, answer in enumerate(all_answers):
            is_correct = 1 if answer == correct_answer else 0
            keyboard.append([InlineKeyboardButton(
                answer,
                callback_data=f'answer_{i}_{is_correct}'
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"❓ Test savoli {current_index + 1}/{len(test_words)}\n\n"
        text += f"<b>'{word['word']}'</b> so'zining tarjimasi?\n"
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # Test yakunlandi
        correct = user_data[user_id]['correct_answers']
        total = len(test_words)
        percentage = (correct / total * 100) if total > 0 else 0
        
        text = f"📊 Test yakunlandi!\n\n"
        text += f"✅ To'g'ri javoblar: {correct}/{total}\n"
        text += f"📈 Natija: {percentage:.1f}%\n\n"
        
        if percentage == 100:
            text += "🎉 Ajoyib! Hammasi to'g'ri!"
        elif percentage >= 70:
            text += "👍 Yaxshi natija!"
        elif percentage >= 50:
            text += "👌 O'rtacha natija"
        else:
            text += "💪 Qaytadan urinib ko'ring!"
        
        keyboard = [
            [InlineKeyboardButton("📚 Yana yodlash", callback_data='learn_10')],
            [InlineKeyboardButton("📝 Yana test", callback_data='test')],
            [InlineKeyboardButton("🏠 Asosiy menyu", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)

# Javobni tekshirish
async def check_answer(query, data):
    user_id = query.from_user.id
    
    if user_id not in user_data:
        await show_main_menu(query)
        return
    
    try:
        _, _, is_correct = data.split('_')
        is_correct = bool(int(is_correct))
    except:
        await query.edit_message_text("❌ Xatolik yuz berdi")
        return
    
    if is_correct:
        user_data[user_id]['correct_answers'] += 1
        message = "✅ To'g'ri!"
    else:
        # To'g'ri javobni ko'rsatish
        current_index = user_data[user_id]['current_index']
        test_words = user_data[user_id]['test_words']
        if current_index < len(test_words):
            correct_answer = test_words[current_index]['translation']
            message = f"❌ Noto'g'ri!\nTo'g'ri javob: {correct_answer}"
        else:
            message = "❌ Noto'g'ri!"
    
    user_data[user_id]['current_index'] += 1
    
    # Natijani ko'rsatish va keyingi savolga o'tish
    await query.edit_message_text(message)
    await show_test_question(query, user_id)

# Asosiy funksiya
def main():
    # Token tekshirish
    if BOT_TOKEN == "Y7823631570:AAHUvls6hRK8AtXrJHq_iTPupOi8U5q6L70":
        print("❌ ERROR: Bot tokenini kiritmadingiz!")
        print("BOT_TOKEN o'zgaruvchisiga o'z tokeningizni yozing")
        return
    
    # Application yaratish
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Botni ishga tushurish
    print("✅ Bot ishga tushdi...")
    print("📝 Ishlatish: apple yoki apple, olma, I eat apple")
    print("📚 Yodlash: 10/20 ta so'z")
    print("📝 Test: bilimingizni tekshiring")
    print("🔴 To'xtatish: Ctrl+C")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
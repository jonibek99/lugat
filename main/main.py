import pandas as pd
import random
import os
import json
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# CSV fayl nomi
CSV_FILE = 'vocabulary.csv'
USER_WORDS_FILE = 'user_vocabulary_{}.json'

# Foydalanuvchi ma'lumotlarini saqlash
user_data = {}

# MyMemory Translate API funksiyasi
def translate_word_my_memory(word, source_lang='en', target_lang='uz'):
    """
    MyMemory API orqali so'z tarjima qilish
    """
    try:
        url = f"https://api.mymemory.translated.net/get"
        params = {
            'q': word,
            'langpair': f'{source_lang}|{target_lang}'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data['responseStatus'] == 200:
                translation = data['responseData']['translatedText']
                # Agar tarjima bir nechta bo'lsa, birinchisini olamiz
                if ';' in translation:
                    translation = translation.split(';')[0].strip()
                if '(' in translation:
                    translation = translation.split('(')[0].strip()
                return translation
        return None
    except Exception as e:
        print(f"Tarjima qilishda xato: {e}")
        return None

# Google Translate API (alternativa)
def translate_word_google(word, source_lang='en', target_lang='uz'):
    """
    Google Translate API (bepul va oson)
    """
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            'client': 'gtx',
            'sl': source_lang,
            'tl': target_lang,
            'dt': 't',
            'q': word
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # Google Translate javobi kompleks struktura
            # Birinchi elementda tarjimalar listi bor
            if data and len(data) > 0 and data[0]:
                translations = data[0]
                if translations and len(translations) > 0:
                    translation = translations[0][0]
                    return translation
        return None
    except Exception as e:
        print(f"Google Translate xatosi: {e}")
        return None

# Tarjima funksiyasi (ikkala API dan foydalanadi)
def translate_word(word, source_lang='en', target_lang='uz'):
    """
    So'zni tarjima qilish - birinchi Google Translate, keyin MyMemory
    """
    # Avval Google Translate dan urinib ko'ramiz
    translation = translate_word_google(word, source_lang, target_lang)
    
    # Agar Google Translate ishlamasa, MyMemory dan foydalanamiz
    if not translation or translation == word:
        translation = translate_word_my_memory(word, source_lang, target_lang)
    
    # Agar ikkalasi ham ishlamasa, oddiy lug'atdan foydalanamiz
    if not translation or translation == word:
        translation = get_translation_from_dict(word)
    
    return translation

# Kichik lug'at (zaxira sifatida)
def get_translation_from_dict(word):
    """
    Kichik lug'atdan tarjima qidirish
    """
    simple_dict = {
        'apple': 'olma',
        'book': 'kitob',
        'cat': 'mushuk',
        'dog': 'it',
        'house': 'uy',
        'car': 'mashina',
        'water': 'suv',
        'hello': 'salom',
        'goodbye': 'xayr',
        'thank you': 'rahmat',
        'yes': 'ha',
        'no': "yo'q",
        'man': 'erkak',
        'woman': 'ayol',
        'child': 'bola',
        'school': 'maktab',
        'teacher': "o'qituvchi",
        'student': "o'quvchi",
        'friend': "do'st",
        'family': 'oilа',
        'work': 'ish',
        'time': 'vaqt'
    }
    
    word_lower = word.lower().strip()
    return simple_dict.get(word_lower, None)

# Asosiy CSV faylni yuklash
def load_vocabulary():
    if os.path.exists(CSV_FILE):
        try:
            df = pd.read_csv(CSV_FILE)
            if df.empty:
                return pd.DataFrame(columns=['word', 'translation', 'example', 'added_date'])
            return df
        except Exception as e:
            print(f"CSV faylni o'qishda xato: {e}")
            return pd.DataFrame(columns=['word', 'translation', 'example', 'added_date'])
    else:
        # Bo'sh dataframe yaratish
        df = pd.DataFrame(columns=['word', 'translation', 'example', 'added_date'])
        df.to_csv(CSV_FILE, index=False)
        return df

# Foydalanuvchi lug'atini yuklash (JSON formatida)
def load_user_vocabulary(user_id):
    user_file = USER_WORDS_FILE.format(user_id)
    
    if os.path.exists(user_file):
        try:
            with open(user_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # JSON dan DataFrame ga o'tkazish
            words = []
            for word_data in data.get('words', []):
                words.append({
                    'word': word_data.get('word', ''),
                    'translation': word_data.get('translation', ''),
                    'example': word_data.get('example', ''),
                    'learned': word_data.get('learned', False),
                    'deleted': word_data.get('deleted', False),
                    'seen_count': word_data.get('seen_count', 0),
                    'correct_count': word_data.get('correct_count', 0),
                    'last_seen': word_data.get('last_seen'),
                    'added_date': word_data.get('added_date')
                })
            
            return pd.DataFrame(words)
        except Exception as e:
            print(f"Foydalanuvchi faylini o'qishda xato: {e}")
    
    # Yangi foydalanuvchi uchun asosiy lug'atdan nusxa olish
    main_df = load_vocabulary()
    
    if main_df.empty:
        words = []
    else:
        # Asosiy lug'atdan so'zlarni olish
        words = []
        for _, row in main_df.iterrows():
            words.append({
                'word': row['word'],
                'translation': row['translation'],
                'example': row.get('example', ''),
                'learned': False,
                'deleted': False,
                'seen_count': 0,
                'correct_count': 0,
                'last_seen': None,
                'added_date': row.get('added_date', datetime.now().isoformat())
            })
    
    # Yangi foydalanuvchi faylini yaratish
    save_user_vocabulary(user_id, pd.DataFrame(words))
    return pd.DataFrame(words)

# Foydalanuvchi lug'atini saqlash (JSON formatida)
def save_user_vocabulary(user_id, df):
    user_file = USER_WORDS_FILE.format(user_id)
    
    try:
        # DataFrame dan JSON ga o'tkazish
        words = []
        for _, row in df.iterrows():
            words.append({
                'word': str(row['word']),
                'translation': str(row['translation']),
                'example': str(row.get('example', '')),
                'learned': bool(row.get('learned', False)),
                'deleted': bool(row.get('deleted', False)),
                'seen_count': int(row.get('seen_count', 0)),
                'correct_count': int(row.get('correct_count', 0)),
                'last_seen': row.get('last_seen'),
                'added_date': row.get('added_date', datetime.now().isoformat())
            })
        
        user_vocab = {
            'user_id': user_id,
            'updated_at': datetime.now().isoformat(),
            'words': words
        }
        
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(user_vocab, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"Foydalanuvchi faylini saqlashda xato: {e}")

# So'z qo'shish (asosiy lug'atga)
def add_word_to_vocabulary(word, translation="", example=""):
    df = load_vocabulary()
    
    # So'z allaqachon mavjudligini tekshirish
    if not df.empty and word.lower() in df['word'].str.lower().values:
        return False, "Bu so'z allaqachon mavjud"
    
    # Agar tarjima berilmagan bo'lsa, avtomatik tarjima qilish
    if not translation:
        translation = translate_word(word)
        if not translation:
            return False, "Tarjima topilmadi. Iltimos, tarjimasini ham kiriting."
    
    # Masalan yaratish
    if not example:
        example = f"I use {word} every day." if word else ""
    
    new_word = pd.DataFrame({
        'word': [word],
        'translation': [translation],
        'example': [example],
        'added_date': [datetime.now().isoformat()]
    })
    
    if df.empty:
        df = new_word
    else:
        df = pd.concat([df, new_word], ignore_index=True)
    
    df.to_csv(CSV_FILE, index=False)
    
    # Barcha foydalanuvchilar fayllarini yangilash
    for filename in os.listdir('.'):
        if filename.startswith('user_vocabulary_') and filename.endswith('.json'):
            try:
                user_id = filename.replace('user_vocabulary_', '').replace('.json', '')
                user_df = load_user_vocabulary(user_id)
                
                if word.lower() not in user_df['word'].str.lower().values:
                    new_user_word = pd.DataFrame({
                        'word': [word],
                        'translation': [translation],
                        'example': [example],
                        'learned': [False],
                        'deleted': [False],
                        'seen_count': [0],
                        'correct_count': [0],
                        'last_seen': [None],
                        'added_date': [datetime.now().isoformat()]
                    })
                    user_df = pd.concat([user_df, new_user_word], ignore_index=True)
                    save_user_vocabulary(user_id, user_df)
                    
            except Exception as e:
                print(f"Foydalanuvchi faylini yangilashda xato: {e}")
    
    return True, "So'z muvaffaqiyatli qo'shildi"

# Avtomatik so'z qo'shish (foydalanuvchi faqat so'zni kiritadi)
async def auto_add_word(word, user_id):
    """
    Foydalanuvchi so'z kiritganda avtomatik tarjima qilish va qo'shish
    """
    # So'zni tozalash
    word = word.strip()
    
    if not word:
        return False, "So'z kiritilmadi"
    
    # Avtomatik tarjima qilish
    translation = translate_word(word)
    
    if not translation:
        # Tarjima topilmasa, foydalanuvchidan so'rash
        return False, "tarjima_topilmadi"
    
    # CSV ga qo'shish
    success, message = add_word_to_vocabulary(word, translation)
    
    if success:
        return True, f"✅ '{word}' so'zi avtomatik qo'shildi!\nTarjima: {translation}"
    else:
        return False, message

# So'zni o'chirish (faqat foydalanuvchi uchun)
def delete_word_for_user(user_id, word):
    user_df = load_user_vocabulary(user_id)
    
    if user_df.empty:
        return False
    
    word_lower = word.lower()
    if word_lower in user_df['word'].str.lower().values:
        user_df.loc[user_df['word'].str.lower() == word_lower, 'deleted'] = True
        save_user_vocabulary(user_id, user_df)
        return True
    return False

# /start komandasi
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Foydalanuvchi ma'lumotlarini ishga tushirish
    user_data[user_id] = {
        'learning_mode': False,
        'test_mode': False,
        'words_to_learn': [],
        'test_words': [],
        'current_word_index': 0,
        'correct_answers': 0,
        'awaiting_word': False,
        'auto_add_mode': True  # Avtomatik qo'shish rejimi
    }
    
    # Foydalanuvchi lug'at faylini yaratish (agar mavjud bo'lmasa)
    load_user_vocabulary(user_id)
    
    keyboard = [
        [InlineKeyboardButton("📚 10 ta so'z yodlash", callback_data='learn_10')],
        [InlineKeyboardButton("📚 20 ta so'z yodlash", callback_data='learn_20')],
        [InlineKeyboardButton("📝 Test topshirish", callback_data='test')],
        [InlineKeyboardButton("➕ So'z qo'shish", callback_data='add_word')],
        [InlineKeyboardButton("⚡ Avtomatik qo'shish", callback_data='auto_add')],
        [InlineKeyboardButton("🗑️ So'z o'chirish", callback_data='delete_word')],
        [InlineKeyboardButton("📊 Mening statistikam", callback_data='stats')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🇺🇿 Assalomu alaykum! Inglizcha so'zlar yodlash botiga xush kelibsiz!\n"
        "🇬🇧 Welcome to the English vocabulary learning bot!\n\n"
        "⚡ <b>Yangi imkoniyat:</b> Faqat inglizcha so'z yozing, bot avtomatik tarjima qilib qo'shadi!\n"
        "   Masalan: <code>apple</code> yozing → bot <code>olma</code> deb tarjima qiladi\n\n"
        "Quyidagi tugmalardan birini tanlang:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

# Avtomatik qo'shish rejimini yoqish
async def enable_auto_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data[user_id]['auto_add_mode'] = True
    user_data[user_id]['awaiting_word'] = True
    
    text = "⚡ <b>Avtomatik qo'shish rejimi yoqildi!</b>\n\n"
    text += "Endi faqat inglizcha so'z yozing, men avtomatik tarjima qilib CSV faylga saqlayman.\n\n"
    text += "Misol uchun:\n"
    text += "• <code>apple</code>\n"
    text += "• <code>computer</code>\n"
    text += "• <code>beautiful</code>\n\n"
    text += "Yoki an'anaviy usulda qo'shish uchun: <code>apple, olma, I eat an apple</code>"
    
    keyboard = [[InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

# An'anaviy so'z qo'shish funksiyasi
async def add_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data[user_id]['awaiting_word'] = True
    user_data[user_id]['auto_add_mode'] = False  # An'anaviy rejim
    
    text = "📝 <b>An'anaviy usulda so'z qo'shish</b>\n\n"
    text += "Quyidagi formatda yuboring:\n"
    text += "<code>so'z, tarjima, misol (ixtiyoriy)</code>\n\n"
    text += "Misol uchun:\n"
    text += "<code>apple, olma, I eat an apple every day</code>\n\n"
    text += "Yoki faqat so'z yozib, avtomatik tarjima qilish uchun 'Avtomatik qo'shish' tugmasini bosing."
    
    keyboard = [
        [InlineKeyboardButton("⚡ Avtomatik qo'shish", callback_data='auto_add')],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

# Xabarlarni qayta ishlash
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_data:
        user_data[user_id] = {
            'learning_mode': False,
            'test_mode': False,
            'words_to_learn': [],
            'test_words': [],
            'current_word_index': 0,
            'correct_answers': 0,
            'awaiting_word': False,
            'auto_add_mode': True  # Default - avtomatik rejim
        }
    
    text = update.message.text.strip()
    
    # Agar foydalanuvchi so'z qo'shish rejimida bo'lsa
    if user_data[user_id].get('awaiting_word'):
        # Avtomatik rejimda (faqat so'z)
        if user_data[user_id].get('auto_add_mode', True):
            # Faqat so'z kiritilgan (vergulsiz)
            if ',' not in text:
                word = text.strip()
                if word:
                    # So'zni avtomatik qo'shish
                    await update.message.reply_text(f"🔍 '{word}' so'zini tarjima qilyapman...")
                    
                    success, message = await auto_add_word(word, user_id)
                    
                    if success:
                        user_data[user_id]['awaiting_word'] = False
                        
                        keyboard = [
                            [InlineKeyboardButton("⚡ Yana so'z qo'shish", callback_data='auto_add')],
                            [InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await update.message.reply_text(message, reply_markup=reply_markup)
                    elif message == "tarjima_topilmadi":
                        # Tarjima topilmasa, foydalanuvchidan so'rash
                        await update.message.reply_text(
                            f"❌ '{word}' so'zining tarjimasini topa olmadim.\n\n"
                            f"Iltimos, tarjimasini ham kiriting:\n"
                            f"<code>{word}, tarjima, misol (ixtiyoriy)</code>",
                            parse_mode='HTML'
                        )
                        user_data[user_id]['auto_add_mode'] = False
                    else:
                        await update.message.reply_text(f"❌ {message}")
                else:
                    await update.message.reply_text("Iltimos, so'z kiriting.")
            else:
                # Vergul bor - an'anaviy format
                await handle_traditional_format(update, context, text, user_id)
        
        else:
            # An'anaviy rejimda
            await handle_traditional_format(update, context, text, user_id)
    
    else:
        # Agar foydalanuvchi oddiy xabar yuborsa
        if text.lower() in ['/start', 'start', 'меню', 'menu']:
            await start_command(update, context)
        else:
            # Avtomatik rejimni taklif qilish
            keyboard = [
                [InlineKeyboardButton("⚡ Avtomatik qo'shish", callback_data='auto_add')],
                [InlineKeyboardButton("📝 An'anaviy qo'shish", callback_data='add_word')],
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"'{text}' so'zini qo'shmoqchimisiz?\n"
                "Quyidagi usullardan birini tanlang:",
                reply_markup=reply_markup
            )

# An'anaviy formatni qayta ishlash
async def handle_traditional_format(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, user_id: int):
    try:
        # Matnni ajratish
        parts = [part.strip() for part in text.split(',')]
        
        if len(parts) >= 2:
            word = parts[0]
            translation = parts[1]
            example = parts[2] if len(parts) > 2 else ""
            
            # CSV ga qo'shish
            success, message = add_word_to_vocabulary(word, translation, example)
            
            user_data[user_id]['awaiting_word'] = False
            
            if success:
                response = f"✅ {message}:\n\n"
                response += f"<b>Inglizcha:</b> {word}\n"
                response += f"<b>Tarjima:</b> {translation}\n"
                if example:
                    response += f"<b>Misol:</b> {example}\n"
            else:
                response = f"❌ {message}"
            
            keyboard = [
                [InlineKeyboardButton("➕ Yana so'z qo'shish", callback_data='add_word')],
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(response, reply_markup=reply_markup, parse_mode='HTML')
            
        else:
            await update.message.reply_text(
                "❌ Noto'g'ri format. Iltimos, formatga rioya qiling:\n"
                "<code>so'z, tarjima, misol (ixtiyoriy)</code>\n\n"
                "Misol: <code>apple, olma, I eat an apple</code>",
                parse_mode='HTML'
            )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Xatolik yuz berdi: {str(e)}\n\n"
            "Iltimos, qayta urinib ko'ring."
        )

# Callback query handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    try:
        if data == 'learn_10':
            await start_learning(update, context, 10)
        elif data == 'learn_20':
            await start_learning(update, context, 20)
        elif data == 'test':
            await start_test(update, context)
        elif data == 'add_word':
            await add_word_command(update, context)
        elif data == 'auto_add':
            await enable_auto_add(update, context)
        elif data == 'delete_word':
            await delete_word_menu(update, context)
        elif data == 'menu':
            await start_command(update, context)
        elif data == 'stats':
            await show_stats(update, context)
        else:
            await query.edit_message_text("Noma'lum buyruq. Iltimos, /start buyrug'ini yuboring.")
    except Exception as e:
        print(f"Xatolik: {e}")
        await query.edit_message_text(
            f"Xatolik yuz berdi: {str(e)}\n\n"
            "Iltimos, /start buyrug'ini qayta yuboring."
        )

# Qolgan funksiyalar (o'xshash, lekin qisqartirilgan)
async def start_learning(update: Update, context: ContextTypes.DEFAULT_TYPE, count: int):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in user_data:
        await query.edit_message_text("Xatolik! Iltimos, /start buyrug'ini qayta yuboring.")
        return
    
    # Foydalanuvchi lug'atini yuklash
    user_df = load_user_vocabulary(user_id)
    
    if user_df.empty:
        await query.edit_message_text("Sizda hali so'zlar mavjud emas. Avval so'z qo'shing.")
        return
    
    # O'chirilmagan so'zlarni hisoblash
    available_words = user_df[~user_df['deleted']]
    
    if len(available_words) < count:
        await query.edit_message_text(
            f"Kechirasiz, sizda faqat {len(available_words)} ta so'z mavjud. "
            f"Iltimos, avval yangi so'zlar qo'shing."
        )
        return
    
    # Tasodifiy so'zlarni tanlash
    if len(available_words) <= count:
        words_to_learn = available_words.to_dict('records')
    else:
        words_to_learn = available_words.sample(n=count).to_dict('records')
    
    user_data[user_id]['learning_mode'] = True
    user_data[user_id]['test_mode'] = False
    user_data[user_id]['words_to_learn'] = words_to_learn
    user_data[user_id]['current_word_index'] = 0
    
    # Birinchi so'zni ko'rsatish
    await show_next_word(update, context)

async def show_next_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in user_data:
        await query.edit_message_text("Xatolik! Iltimos, /start buyrug'ini qayta yuboring.")
        return
    
    user_info = user_data[user_id]
    current_index = user_info['current_word_index']
    words = user_info['words_to_learn']
    
    if current_index < len(words):
        word = words[current_index]
        
        text = f"📖 So'z {current_index + 1}/{len(words)}:\n\n"
        text += f"<b>Inglizcha:</b> {word.get('word', '')}\n"
        text += f"<b>Tarjima:</b> {word.get('translation', '')}\n"
        if word.get('example'):
            text += f"<b>Misol:</b> {word['example']}\n"
        
        keyboard = [
            [InlineKeyboardButton("✅ Tushundim (Keyingisi)", callback_data='next_word')],
            [InlineKeyboardButton("🗑️ Bu so'zni o'chirish", callback_data=f"delete_current_{word['word']}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # Yodlash yakunlandi
        text = f"🎉 Tabriklayman! Siz {len(words)} ta so'zni yodladingiz!\n"
        
        keyboard = [
            [InlineKeyboardButton("📝 Test topshirish", callback_data='test')],
            [InlineKeyboardButton("📚 Yana so'z yodlash", callback_data='learn_10')],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)

# Qolgan funksiyalar (o'xshash, lekin soddalashtirilgan)
async def delete_word_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_df = load_user_vocabulary(user_id)
    
    if user_df.empty:
        await query.edit_message_text("Sizda hali so'zlar mavjud emas.")
        return
    
    text = "🗑️ O'chirmoqchi bo'lgan so'zingizni tanlang:\n\n"
    
    # So'zlarni guruhlarga ajratish
    available_words = user_df[~user_df['deleted']].head(15)
    keyboard = []
    
    for _, row in available_words.iterrows():
        keyboard.append([InlineKeyboardButton(
            f"{row['word']} - {row['translation']}",
            callback_data=f"delete_select_{row['word']}"
        )])
    
    keyboard.append([InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def delete_word(update: Update, context: ContextTypes.DEFAULT_TYPE, word_to_delete):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if delete_word_for_user(user_id, word_to_delete):
        text = f"✅ '{word_to_delete}' so'zi o'chirildi!"
        
        keyboard = [[InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await query.edit_message_text("❌ So'z topilmadi.")

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_df = load_user_vocabulary(user_id)
    
    if user_df.empty:
        await query.edit_message_text("📊 Sizda hali so'zlar mavjud emas.")
        return
    
    total_words = len(user_df)
    learned_words = len(user_df[user_df['learned'] == True]) if 'learned' in user_df.columns else 0
    deleted_words = len(user_df[user_df['deleted'] == True]) if 'deleted' in user_df.columns else 0
    
    text = f"📊 Shaxsiy statistika:\n\n"
    text += f"📚 Jami so'zlar: {total_words} ta\n"
    text += f"✅ O'rgangan so'zlar: {learned_words} ta\n"
    text += f"🗑️ O'chirilgan so'zlar: {deleted_words} ta\n"
    
    # Oxirgi 5 ta qo'shilgan so'zlar
    if 'added_date' in user_df.columns:
        recent_words = user_df.sort_values('added_date', ascending=False).head(5)
        if len(recent_words) > 0:
            text += f"\n🆕 Oxirgi qo'shilgan so'zlar:\n"
            for _, row in recent_words.iterrows():
                text += f"• {row['word']} - {row['translation']}\n"
    
    keyboard = [[InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

# Test funksiyalari (qisqartirilgan)
async def start_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in user_data:
        await query.edit_message_text("Xatolik! Iltimos, /start buyrug'ini qayta yuboring.")
        return
    
    user_df = load_user_vocabulary(user_id)
    
    if len(user_df) < 4:
        await query.edit_message_text("Test uchun kamida 4 ta so'z kerak.")
        return
    
    test_words = user_df.sample(n=min(10, len(user_df))).to_dict('records')
    
    user_data[user_id]['test_mode'] = True
    user_data[user_id]['test_words'] = test_words
    user_data[user_id]['current_word_index'] = 0
    user_data[user_id]['correct_answers'] = 0
    
    # Birinchi test savolini ko'rsatish
    await show_next_test_question(update, context)

async def show_next_test_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in user_data:
        await query.edit_message_text("Xatolik! Iltimos, /start buyrug'ini qayta yuboring.")
        return
    
    user_info = user_data[user_id]
    current_index = user_info['current_word_index']
    test_words = user_info['test_words']
    
    if current_index < len(test_words):
        current_word = test_words[current_index]
        
        # 4 ta variant yaratish
        options = [current_word['translation']]
        
        # Qolgan 3 ta noto'g'ri variant
        user_df = load_user_vocabulary(user_id)
        other_words = user_df[user_df['word'] != current_word['word']]
        if len(other_words) >= 3:
            wrong_options = other_words.sample(n=3)['translation'].tolist()
        else:
            wrong_options = ["Noto'g'ri 1", "Noto'g'ri 2", "Noto'g'ri 3"]
        
        options.extend(wrong_options)
        random.shuffle(options)
        
        # Tugmalar
        keyboard = []
        for i, option in enumerate(options):
            is_correct = 1 if option == current_word['translation'] else 0
            keyboard.append([InlineKeyboardButton(
                option, 
                callback_data=f"answer_{i}_{is_correct}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"❓ Test {current_index + 1}/{len(test_words)}:\n\n"
        text += f"<b>'{current_word['word']}'</b> so'zining tarjimasi?\n"
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # Test yakunlandi
        correct = user_data[user_id]['correct_answers']
        total = len(test_words)
        
        text = f"📊 Test yakunlandi!\n"
        text += f"✅ To'g'ri javoblar: {correct}/{total}\n"
        text += f"📈 Natija: {correct/total*100:.1f}%\n"
        
        keyboard = [
            [InlineKeyboardButton("📚 Yana yodlash", callback_data='learn_10')],
            [InlineKeyboardButton("📝 Yana test", callback_data='test')],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)

async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in user_data:
        await query.edit_message_text("Xatolik! Iltimos, /start buyrug'ini qayta yuboring.")
        return
    
    try:
        _, _, is_correct = data.split('_')
        is_correct = bool(int(is_correct))
    except:
        await query.edit_message_text("Xatolik yuz berdi.")
        return
    
    if is_correct:
        user_data[user_id]['correct_answers'] += 1
        message = "✅ To'g'ri!"
    else:
        message = "❌ Noto'g'ri!"
    
    user_data[user_id]['current_word_index'] += 1
    
    await query.edit_message_text(message)
    await show_next_test_question(update, context)

# Asosiy funksiya
def main():
    # Bot tokenini o'rnating
    TOKEN = "7823631570:AAHUvls6hRK8AtXrJHq_iTPupOi8U5q6L70"
    
    # Application yaratish
    application = Application.builder().token(TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Botni ishga tushurish
    print("⚡ Bot ishga tushdi...")
    print("📝 Endi faqat so'z yozing (masalan: apple)")
    print("🤖 Bot avtomatik tarjima qilib CSV ga saqlaydi")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
import pandas as pd
import random
import os
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# CSV fayl nomi
CSV_FILE = 'vocabulary2.csv'
USER_WORDS_FILE = 'user_vocabulary2_{}.json'  # JSON formatida saqlaymiz

# Foydalanuvchi ma'lumotlarini saqlash
user_data = {}

# Asosiy CSV faylni yuklash
def load_vocabulary():
    if os.path.exists(CSV_FILE):
        try:
            df = pd.read_csv(CSV_FILE)
            if df.empty:
                return pd.DataFrame(columns=['word', 'translation', 'example'])
            # Takrorlanishlarni olib tashlash
            df = df.drop_duplicates(subset=['word'], keep='first')
            return df
        except Exception as e:
            print(f"CSV faylni o'qishda xato: {e}")
            return pd.DataFrame(columns=['word', 'translation', 'example'])
    else:
        # Bo'sh dataframe yaratish
        df = pd.DataFrame(columns=['word', 'translation', 'example'])
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
                    'last_seen': word_data.get('last_seen')
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
                'last_seen': None
            })
    
    # Yangi foydalanuvchi faylini yaratish
    user_vocab = {
        'user_id': user_id,
        'created_at': datetime.now().isoformat(),
        'words': words
    }
    
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
                'last_seen': row.get('last_seen')
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
def add_word_to_vocabulary(word, translation, example=""):
    df = load_vocabulary()
    
    # So'z allaqachon mavjudligini tekshirish
    if not df.empty and word in df['word'].values:
        return False  # So'z allaqachon mavjud
    
    new_word = pd.DataFrame({
        'word': [word],
        'translation': [translation],
        'example': [example]
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
                
                if word not in user_df['word'].values:
                    new_user_word = pd.DataFrame({
                        'word': [word],
                        'translation': [translation],
                        'example': [example],
                        'learned': [False],
                        'deleted': [False],
                        'seen_count': [0],
                        'correct_count': [0],
                        'last_seen': [None]
                    })
                    user_df = pd.concat([user_df, new_user_word], ignore_index=True)
                    save_user_vocabulary(user_id, user_df)
                    
            except Exception as e:
                print(f"Foydalanuvchi faylini yangilashda xato: {e}")
    
    return True

# So'zni o'chirish (faqat foydalanuvchi uchun)
def delete_word_for_user(user_id, word):
    user_df = load_user_vocabulary(user_id)
    
    if user_df.empty:
        return False
    
    if word in user_df['word'].values:
        user_df.loc[user_df['word'] == word, 'deleted'] = True
        save_user_vocabulary(user_id, user_df)
        return True
    return False

# Yodlash uchun so'zlarni tanlash (takrorlanmas)
def get_unique_words_for_learning(user_id, count=10):
    user_df = load_user_vocabulary(user_id)
    
    if user_df.empty:
        return []
    
    # O'chirilmagan va kam ko'rilgan so'zlarni tanlash
    available_words = user_df[
        (~user_df['deleted']) & 
        (~user_df['learned'])
    ]
    
    if available_words.empty:
        return []
    
    # Kam ko'rilgan so'zlarni ustun qo'yish
    available_words = available_words.sort_values(['seen_count', 'last_seen'], na_position='first')
    
    # Agar kerakli son yetmasa, barcha so'zlardan tanlash
    if len(available_words) < count:
        all_words = user_df[~user_df['deleted']]
        if len(all_words) < count:
            return all_words.sample(n=min(count, len(all_words))).to_dict('records')
        return all_words.sample(n=count).to_dict('records')
    
    # Eng kam ko'rilgan 'count' ta so'zni tanlash
    return available_words.head(count).to_dict('records')

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
        'awaiting_word': False
    }
    
    # Foydalanuvchi lug'at faylini yaratish (agar mavjud bo'lmasa)
    load_user_vocabulary(user_id)
    
    keyboard = [
        [InlineKeyboardButton("📚 10 ta so'z yodlash", callback_data='learn_10')],
        [InlineKeyboardButton("📚 20 ta so'z yodlash", callback_data='learn_20')],
        [InlineKeyboardButton("📝 Test topshirish", callback_data='test')],
        [InlineKeyboardButton("➕ So'z qo'shish", callback_data='add_word')],
        [InlineKeyboardButton("🗑️ So'z o'chirish", callback_data='delete_word')],
        [InlineKeyboardButton("📊 Mening statistikam", callback_data='stats')],
        [InlineKeyboardButton("🔄 So'zlarni yangilash", callback_data='refresh')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🇺🇿 Assalomu alaykum! Inglizcha so'zlar yodlash botiga xush kelibsiz!\n"
        "🇬🇧 Welcome to the English vocabulary learning bot!\n\n"
        "Sizga yoqmaydigan so'zlarni o'chirishingiz mumkin.\n"
        "Har bir so'z faqat bir marta ko'rsatiladi!\n\n"
        "Quyidagi tugmalardan birini tanlang:",
        reply_markup=reply_markup
    )

# So'z qo'shish funksiyasi
async def add_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data[user_id]['awaiting_word'] = True
    
    text = "📝 Yangi so'z qo'shish uchun quyidagi formatda yuboring:\n\n"
    text += "<code>so'z, tarjima, misol (ixtiyoriy)</code>\n\n"
    text += "Misol uchun:\n"
    text += "<code>apple, olma, I eat an apple every day</code>\n\n"
    text += "Eslatma: Agar so'z allaqachon mavjud bo'lsa, qo'shilmaydi."
    
    keyboard = [[InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

# So'zni qabul qilish va saqlash
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
            'awaiting_word': False
        }
    
    # Agar foydalanuvchi so'z qo'shish rejimida bo'lsa
    if user_data[user_id].get('awaiting_word'):
        text = update.message.text.strip()
        
        try:
            # Matnni ajratish
            parts = [part.strip() for part in text.split(',')]
            
            if len(parts) >= 2:
                word = parts[0]
                translation = parts[1]
                example = parts[2] if len(parts) > 2 else ""
                
                # CSV ga qo'shish
                success = add_word_to_vocabulary(word, translation, example)
                
                if success:
                    response = f"✅ So'z muvaffaqiyatli qo'shildi:\n\n"
                    response += f"<b>Inglizcha:</b> {word}\n"
                    response += f"<b>Tarjima:</b> {translation}\n"
                    if example:
                        response += f"<b>Misol:</b> {example}\n"
                    
                    # Foydalanuvchi lug'atini yangilash
                    user_df = load_user_vocabulary(user_id)
                    if word not in user_df['word'].values:
                        new_user_word = pd.DataFrame({
                            'word': [word],
                            'translation': [translation],
                            'example': [example],
                            'learned': [False],
                            'deleted': [False],
                            'seen_count': [0],
                            'correct_count': [0],
                            'last_seen': [None]
                        })
                        user_df = pd.concat([user_df, new_user_word], ignore_index=True)
                        save_user_vocabulary(user_id, user_df)
                else:
                    response = f"ℹ️ '{word}' so'zi allaqachon lug'atda mavjud."
                
                user_data[user_id]['awaiting_word'] = False
                
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
    else:
        # Agar foydalanuvchi so'z kiritayotgan bo'lsa, lekin rejimda emas
        await update.message.reply_text(
            "Iltimos, avval 'So'z qo'shish' tugmasini bosing yoki /start buyrug'ini yuboring."
        )

# So'z yodlashni boshlash
async def start_learning(update: Update, context: ContextTypes.DEFAULT_TYPE, count: int):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Foydalanuvchi ma'lumotlarini tekshirish
    if user_id not in user_data:
        await query.edit_message_text("Xatolik! Iltimos, /start buyrug'ini qayta yuboring.")
        return
    
    user_df = load_user_vocabulary(user_id)
    
    # O'chirilmagan so'zlarni hisoblash
    available_words = user_df[~user_df['deleted']]
    
    if len(available_words) < count:
        await query.edit_message_text(
            f"Kechirasiz, sizda faqat {len(available_words)} ta so'z mavjud. "
            f"Iltimos, avval yangi so'zlar qo'shing."
        )
        return
    
    # Takrorlanmas so'zlarni tanlash
    words_to_learn = get_unique_words_for_learning(user_id, count)
    
    if not words_to_learn:
        await query.edit_message_text("Yangi yodlash uchun so'zlar topilmadi! Yangi so'zlar qo'shing.")
        return
    
    user_data[user_id]['learning_mode'] = True
    user_data[user_id]['test_mode'] = False
    user_data[user_id]['words_to_learn'] = words_to_learn
    user_data[user_id]['current_word_index'] = 0
    
    # Birinchi so'zni ko'rsatish
    await show_next_word(update, context)

# Keyingi so'zni ko'rsatish
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
        
        # Ko'rilgan sonini yangilash
        user_df = load_user_vocabulary(user_id)
        if not user_df.empty:
            mask = user_df['word'] == word['word']
            if mask.any():
                user_df.loc[mask, 'seen_count'] = user_df.loc[mask, 'seen_count'] + 1
                user_df.loc[mask, 'last_seen'] = datetime.now().isoformat()
                save_user_vocabulary(user_id, user_df)
        
        text = f"📖 So'z {current_index + 1}/{len(words)}:\n\n"
        text += f"<b>Inglizcha:</b> {word.get('word', '')}\n"
        text += f"<b>Tarjima:</b> {word.get('translation', '')}\n"
        if word.get('example'):
            text += f"<b>Misol:</b> {word['example']}\n"
        
        # Qoshimcha tugmalar
        keyboard = [
            [InlineKeyboardButton("✅ Tushundim (Keyingisi)", callback_data='next_word')],
            [InlineKeyboardButton("🗑️ Bu so'zni o'chirish", callback_data=f"delete_current_{word['word']}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # Yodlash yakunlandi
        text = f"🎉 Tabriklayman! Siz {len(words)} ta so'zni yodladingiz!\n\n"
        text += "Bu so'zlar endi 'o'rgangan' deb belgilandi."
        
        # O'rgangan so'zlarni belgilash
        user_df = load_user_vocabulary(user_id)
        for word in words:
            mask = user_df['word'] == word['word']
            if mask.any():
                user_df.loc[mask, 'learned'] = True
        save_user_vocabulary(user_id, user_df)
        
        keyboard = [
            [InlineKeyboardButton("📝 Test topshirish", callback_data='test')],
            [InlineKeyboardButton("📚 Yana so'z yodlash", callback_data='learn_10')],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)

# So'zni o'chirish menyusi
async def delete_word_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_df = load_user_vocabulary(user_id)
    
    if user_df.empty:
        await query.edit_message_text("Sizda hali so'zlar mavjud emas. Avval so'z qo'shing.")
        return
    
    # O'chirilmagan so'zlarni olish
    available_words = user_df[~user_df['deleted']]
    
    if len(available_words) == 0:
        await query.edit_message_text(
            "Hamma so'zlaringiz o'chirilgan! Yangi so'zlar qo'shing."
        )
        return
    
    text = "🗑️ O'chirmoqchi bo'lgan so'zingizni tanlang:\n\n"
    
    # So'zlarni guruhlarga ajratish (har bir guruh 3 ta so'z)
    words_list = available_words.head(15).to_dict('records')  # Faqat birinchi 15 tasi
    keyboard = []
    
    for i in range(0, len(words_list), 3):
        row = []
        for j in range(3):
            if i + j < len(words_list):
                word = words_list[i + j]
                row.append(InlineKeyboardButton(
                    word['word'], 
                    callback_data=f"delete_select_{word['word']}"
                ))
        if row:
            keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

# So'zni o'chirish
async def delete_word(update: Update, context: ContextTypes.DEFAULT_TYPE, word_to_delete):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if delete_word_for_user(user_id, word_to_delete):
        text = f"✅ '{word_to_delete}' so'zi o'chirildi!\n\n"
        
        # Agar hozir yodlash rejimida bo'lsa
        if user_id in user_data and user_data[user_id].get('learning_mode'):
            current_index = user_data[user_id]['current_word_index']
            words = user_data[user_id]['words_to_learn']
            
            # O'chirilgan so'zni ro'yxatdan o'chirish
            words = [w for w in words if w['word'] != word_to_delete]
            user_data[user_id]['words_to_learn'] = words
            
            # Agar ro'yxat bo'sh bo'lsa
            if not words:
                text += "Hamma so'zlar o'chirildi. Bosh menyuga qaytamiz."
                keyboard = [[InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text, reply_markup=reply_markup)
                return
            
            # Agar joriy indeks ro'yxatdan tashqarida bo'lsa
            if current_index >= len(words):
                user_data[user_id]['current_word_index'] = len(words) - 1
            
            text += "Keyingi so'zga o'tamiz..."
            await query.edit_message_text(text)
            await show_next_word(update, context)
        else:
            keyboard = [[InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await query.edit_message_text("❌ So'z topilmadi yoki allaqachon o'chirilgan.")

# Test uchun so'zlarni tanlash
def get_words_for_test(user_id, count=10):
    user_df = load_user_vocabulary(user_id)
    
    if user_df.empty:
        return []
    
    # O'chirilmagan va ko'rilgan so'zlarni tanlash
    test_words = user_df[
        (~user_df['deleted']) & 
        (user_df['seen_count'] > 0)
    ]
    
    if test_words.empty:
        return []
    
    # Tasodifiy tanlash
    if len(test_words) < count:
        return test_words.sample(n=min(count, len(test_words))).to_dict('records')
    
    return test_words.sample(n=count).to_dict('records')

# Testni boshlash
async def start_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in user_data:
        await query.edit_message_text("Xatolik! Iltimos, /start buyrug'ini qayta yuboring.")
        return
    
    test_words = get_words_for_test(user_id, 10)
    
    if len(test_words) < 4:
        await query.edit_message_text(
            "Kechirasiz, test uchun kamida 4 ta so'z kerak. "
            "Iltimos, avval so'z yodlash orqali kamida 4 ta so'zni ko'rib chiqing."
        )
        return
    
    user_data[user_id]['learning_mode'] = False
    user_data[user_id]['test_mode'] = True
    user_data[user_id]['current_word_index'] = 0
    user_data[user_id]['correct_answers'] = 0
    user_data[user_id]['test_words'] = test_words
    
    # Birinchi test savolini ko'rsatish
    await show_next_test_question(update, context)

# Keyingi test savolini ko'rsatish
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
        user_df = load_user_vocabulary(user_id)
        
        # Noto'g'ri variantlar (o'chirilmagan so'zlardan)
        available_words = user_df[
            (~user_df['deleted']) & 
            (user_df['word'] != current_word['word'])
        ]
        
        # Agar yetarli so'z bo'lmasa
        if len(available_words) < 3:
            # Barcha so'zlardan (o'zini hisobga olmaganda)
            all_words = user_df[user_df['word'] != current_word['word']]
            if len(all_words) >= 3:
                wrong_answers = all_words.sample(n=min(3, len(all_words)))['translation'].tolist()
            else:
                # Agar yetarli so'z bo'lmasa, boshqa tarjimalar yaratish
                wrong_answers = ["Noto'g'ri 1", "Noto'g'ri 2", "Noto'g'ri 3"]
        else:
            wrong_answers = available_words.sample(n=3)['translation'].tolist()
        
        # Barcha variantlar
        all_answers = [current_word['translation']] + wrong_answers
        random.shuffle(all_answers)
        
        # Tugmalar yaratish
        keyboard = []
        for i, answer in enumerate(all_answers):
            callback_data = f"answer_{i}_{1 if answer == current_word['translation'] else 0}"
            keyboard.append([InlineKeyboardButton(answer, callback_data=callback_data)])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"❓ Test savoli {current_index + 1}/{len(test_words)}:\n\n"
        text += f"<b>'{current_word['word']}'</b> so'zining tarjimasini toping:\n"
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # Test yakunlandi
        await finish_test(update, context)

# Test natijalarini hisoblash va ko'rsatish
async def finish_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in user_data:
        await query.edit_message_text("Xatolik! Iltimos, /start buyrug'ini qayta yuboring.")
        return
    
    user_info = user_data[user_id]
    correct = user_info['correct_answers']
    total = len(user_info['test_words'])
    
    text = f"📊 Test yakunlandi!\n\n"
    text += f"✅ To'g'ri javoblar: {correct}/{total}\n"
    text += f"📈 Natija: {correct/total*100:.1f}%\n\n"
    
    # To'g'ri javoblar sonini yangilash
    user_df = load_user_vocabulary(user_id)
    for word in user_info['test_words']:
        mask = user_df['word'] == word['word']
        if mask.any():
            user_df.loc[mask, 'correct_count'] = user_df.loc[mask, 'correct_count'] + 1
    save_user_vocabulary(user_id, user_df)
    
    if correct == total:
        text += "🎉 Ajoyib! Barcha javoblaringiz to'g'ri!"
    elif correct >= total * 0.7:
        text += "👍 Yaxshi natija!"
    else:
        text += "💪 Qaytadan urinib ko'ring!"
    
    keyboard = [
        [InlineKeyboardButton("📚 Yangi so'zlar yodlash", callback_data='learn_10')],
        [InlineKeyboardButton("📝 Yana test topshirish", callback_data='test')],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

# Test javobini tekshirish
async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in user_data:
        await query.edit_message_text("Xatolik! Iltimos, /start buyrug'ini qayta yuboring.")
        return
    
    try:
        _, answer_index, is_correct = data.split('_')
        is_correct = bool(int(is_correct))
    except:
        await query.edit_message_text("Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")
        return
    
    user_info = user_data[user_id]
    
    if is_correct:
        user_info['correct_answers'] += 1
        message = "✅ To'g'ri!"
    else:
        current_index = user_info['current_word_index']
        if current_index < len(user_info['test_words']):
            current_word = user_info['test_words'][current_index]
            message = f"❌ Noto'g'ri!\nTo'g'ri javob: {current_word.get('translation', '')}"
        else:
            message = "❌ Noto'g'ri!"
    
    user_info['current_word_index'] += 1
    
    # Natijani ko'rsatish va keyingi savolga o'tish
    await query.edit_message_text(message)
    await show_next_test_question(update, context)

# Statistikani ko'rsatish
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_df = load_user_vocabulary(user_id)
    
    if user_df.empty:
        await query.edit_message_text("📊 Sizda hali so'zlar mavjud emas. Avval so'z qo'shing.")
        return
    
    total_words = len(user_df)
    learned_words = len(user_df[user_df['learned'] == True]) if 'learned' in user_df.columns else 0
    deleted_words = len(user_df[user_df['deleted'] == True]) if 'deleted' in user_df.columns else 0
    active_words = len(user_df[~user_df['deleted']]) if 'deleted' in user_df.columns else total_words
    
    text = f"📊 Shaxsiy statistika:\n\n"
    text += f"📚 Jami so'zlar: {total_words} ta\n"
    text += f"✅ O'rgangan so'zlar: {learned_words} ta\n"
    text += f"🗑️ O'chirilgan so'zlar: {deleted_words} ta\n"
    text += f"📖 Faol so'zlar: {active_words} ta\n\n"
    
    if active_words > 0 and 'seen_count' in user_df.columns:
        # Eng ko'p ko'rilgan so'zlar
        active_df = user_df[~user_df['deleted']]
        if len(active_df) > 0:
            top_seen = active_df.nlargest(5, 'seen_count')
            if len(top_seen) > 0:
                text += "👀 Eng ko'p ko'rilgan so'zlar:\n"
                for _, row in top_seen.iterrows():
                    text += f"• {row['word']} - {row['seen_count']} marta\n"
            
            text += "\n"
            
            # Eng kam ko'rilgan so'zlar
            least_seen = active_df[active_df['seen_count'] > 0].nsmallest(3, 'seen_count')
            if len(least_seen) > 0:
                text += "📝 Yana ko'rib chiqish kerak:\n"
                for _, row in least_seen.iterrows():
                    text += f"• {row['word']} - {row['seen_count']} marta\n"
    
    keyboard = [
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

# So'zlarni yangilash
async def refresh_vocabulary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    main_df = load_vocabulary()
    user_df = load_user_vocabulary(user_id)
    
    if main_df.empty:
        await query.edit_message_text("Asosiy lug'at bo'sh. Avval so'z qo'shing.")
        return
    
    # Yangi so'zlarni aniqlash
    if user_df.empty:
        new_words = main_df
    else:
        new_words = main_df[~main_df['word'].isin(user_df['word'])]
    
    if len(new_words) == 0:
        await query.edit_message_text("✅ Sizning lug'atingiz allaqachon yangilangan. Yangi so'zlar yo'q.")
        return
    
    # Yangi so'zlarni qo'shish
    for _, row in new_words.iterrows():
        new_user_word = pd.DataFrame({
            'word': [row['word']],
            'translation': [row['translation']],
            'example': [row.get('example', '')],
            'learned': [False],
            'deleted': [False],
            'seen_count': [0],
            'correct_count': [0],
            'last_seen': [None]
        })
        user_df = pd.concat([user_df, new_user_word], ignore_index=True)
    
    save_user_vocabulary(user_id, user_df)
    
    text = f"✅ Lug'atingiz yangilandi!\n\n"
    text += f"📥 Yangi qo'shilgan so'zlar: {len(new_words)} ta\n\n"
    if len(new_words) <= 10:
        text += "Yangi so'zlar:\n"
        for i, (_, row) in enumerate(new_words.iterrows()):
            text += f"{i+1}. {row['word']} - {row['translation']}\n"
    else:
        text += "Birinchi 10 ta yangi so'z:\n"
        for i, (_, row) in enumerate(new_words.head(10).iterrows()):
            text += f"{i+1}. {row['word']} - {row['translation']}\n"
        text += f"\n...va yana {len(new_words) - 10} ta so'z"
    
    keyboard = [[InlineKeyboardButton("🏠 Bosh menyu", callback_data='menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

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
        elif data == 'delete_word':
            await delete_word_menu(update, context)
        elif data == 'next_word':
            user_id = query.from_user.id
            if user_id in user_data:
                user_data[user_id]['current_word_index'] += 1
                await show_next_word(update, context)
            else:
                await query.edit_message_text("Xatolik! Iltimos, /start buyrug'ini qayta yuboring.")
        elif data.startswith('delete_current_'):
            word = data.replace('delete_current_', '')
            await delete_word(update, context, word)
        elif data.startswith('delete_select_'):
            word = data.replace('delete_select_', '')
            await delete_word(update, context, word)
        elif data == 'start_test_after_learn':
            await start_test(update, context)
        elif data == 'menu':
            await start_command(update, context)
        elif data == 'stats':
            await show_stats(update, context)
        elif data == 'refresh':
            await refresh_vocabulary(update, context)
        elif data.startswith('answer_'):
            await check_answer(update, context, data)
        else:
            await query.edit_message_text("Noma'lum buyruq. Iltimos, /start buyrug'ini yuboring.")
    except Exception as e:
        print(f"Xatolik: {e}")
        await query.edit_message_text(
            f"Xatolik yuz berdi: {str(e)}\n\n"
            "Iltimos, /start buyrug'ini qayta yuboring."
        )

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
    print("Bot ishga tushdi...")
    print("Ctrl+C tugmasini bosib to'xtating")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
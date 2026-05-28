#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDP Installer Telegram Bot
Fitur:
- Install RDP dengan pilihan Windows
- Payment Gateway OrKut QRIS
- Sistem Deposit/Saldo User
- Kunci Grup (harus join channel + punya saldo)
"""

import telebot
from telebot import types
import json
import os
import time
import random
import threading
import requests
import qrcode
import io

# ==================== KONFIGURASI ====================
BOT_TOKEN = "7727483936:AAH83Vr4Kdu2em-98dt3EzGvtCu9IPau9KE"
OWNER_ID = 5854017651
DATA_FILE = "bot_data.json"
QRIS_DIR = "qris_images"

# Channel yang harus di-join
CHANNEL_ID = "-1002469926011"
CHANNEL_URL = "https://t.me/lexzytesti"

# Harga install RDP
HARGA_RDP = 1000

# OrKut Payment Config
ORKUT_USERNAME = "senjaxchan"
ORKUT_TOKEN = "1197647:sHVZW9Lc3dQKyTFzY4mx8tuopUOjXEqI"
ORKUT_QRIS_STRING = "00020101021126670016COM.NOBUBANK.WWW01189360050300000879140214358444855597300303UMI51440014ID.CO.QRIS.WWW0215ID20232679764700303UMI5204481253033605802ID5923SENJA X STORE OK11976476008SURABAYA61056011162070703A0163045CFF"
RELAY_URL = "https://ivansia.tech/playall-relay/mutasi.php"
RELAY_TOKEN = "tokentesting123456789"

# ==================== HELPER: QRIS ====================
os.makedirs(QRIS_DIR, exist_ok=True)

def toCRC16(s):
    crc = 0xFFFF
    for ch in s:
        crc ^= ord(ch) << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
    return format(crc & 0xFFFF, '04X')

def make_dynamic_qris(nominal):
    amount = str(int(nominal))
    body = ORKUT_QRIS_STRING[:-4].replace('010211', '010212')
    tag = '5802ID'
    idx = body.index(tag)
    head = body[:idx]
    tail = body[idx + len(tag):]
    import re
    head = re.sub(r'54\d{2}\d+$', '', head)
    amount_tag = '54' + str(len(amount)).zfill(2) + amount
    out = head + amount_tag + tag + tail
    return out + toCRC16(out)

def generate_qris_image(nominal, filename):
    qr_string = make_dynamic_qris(nominal)
    img = qrcode.make(qr_string)
    path = os.path.join(QRIS_DIR, filename)
    img.save(path)
    return path

def check_orkut_payment(amount):
    """Cek mutasi via relay, return True jika nominal ditemukan"""
    try:
        resp = requests.post(RELAY_URL, json={
            "auth_username": ORKUT_USERNAME,
            "auth_token": ORKUT_TOKEN,
            "action": "qris_history"
        }, headers={
            "Authorization": f"Bearer {RELAY_TOKEN}",
            "Content-Type": "application/json"
        }, timeout=60)
        data = resp.json()
        # Extract history array
        history = []
        for key in ['qris_history', 'results', 'data', 'mutasi', 'history']:
            candidate = data.get(key)
            if isinstance(candidate, list):
                history = candidate
                break
            if isinstance(candidate, dict):
                for k2 in ['results', 'data', 'list', 'history']:
                    if isinstance(candidate.get(k2), list):
                        history = candidate[k2]
                        break
            if history:
                break
        # Match nominal
        for item in history:
            if not isinstance(item, dict):
                continue
            for k in ['kredit', 'credit', 'amount', 'jumlah', 'nominal', 'total']:
                val = item.get(k)
                if val is None:
                    continue
                parsed = int(str(val).replace('.', '').replace(',', '').strip() or '0')
                if parsed == amount:
                    return True
        return False
    except:
        return False

# ==================== LOAD/SAVE DATA ====================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {
        "allowed_users": [OWNER_ID],
        "owner_link": "https://t.me/username_owner",
        "channel_link": CHANNEL_URL,
        "users": {}
    }

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_user(data, user_id):
    uid = str(user_id)
    if uid not in data.get("users", {}):
        if "users" not in data:
            data["users"] = {}
        data["users"][uid] = {"balance": 0, "total_install": 0, "banned": False, "install_history": [], "deposit_history": []}
        save_data(data)
    u = data["users"][uid]
    # Migrate old users
    if "banned" not in u: u["banned"] = False
    if "install_history" not in u: u["install_history"] = []
    if "deposit_history" not in u: u["deposit_history"] = []
    return u

def add_balance(data, user_id, amount):
    user = get_user(data, user_id)
    user["balance"] += amount
    save_data(data)

def deduct_balance(data, user_id, amount):
    user = get_user(data, user_id)
    user["balance"] -= amount
    save_data(data)

# ==================== INISIALISASI ====================
bot = telebot.TeleBot(BOT_TOKEN)
data = load_data()
user_os_choice = {}
pending_deposits = {}  # {user_id: {amount, unique, total, created_at}}

WINDOWS_OPTIONS = {
    "1": "Windows Server 2012 R2", "2": "Windows Server 2016",
    "3": "Windows Server 2019", "4": "Windows Server 2022",
    "5": "Windows Server 2025", "6": "Windows 10 SuperLite",
    "7": "Windows 11 SuperLite", "8": "Windows 10 Atlas",
    "9": "Windows 11 Atlas", "10": "Windows 10 Pro",
    "11": "Windows 11 Pro", "12": "Tiny10 23H2", "13": "Tiny11 23H2"
}

# ==================== CEK AKSES ====================
def is_owner(user_id):
    return user_id == OWNER_ID

def is_member(user_id):
    """Cek apakah user sudah join channel"""
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def check_access(message):
    """Cek akses: harus join channel + tidak banned."""
    user_id = message.from_user.id
    if is_owner(user_id):
        return True
    user = get_user(data, user_id)
    if user.get("banned"):
        bot.reply_to(message, "⛔ Akun kamu telah di-banned. Hubungi owner.")
        return False
    if not is_member(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("👥 Join Channel", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Sudah Join", callback_data="cek_join"))
        bot.reply_to(message, "🔒 <b>AKSES DITOLAK</b>\n\nKamu harus join channel dulu untuk menggunakan bot ini.", parse_mode="HTML", reply_markup=markup)
        return False
    return True

def check_access_callback(call):
    """Cek akses untuk callback query"""
    user_id = call.from_user.id
    if is_owner(user_id):
        return True
    user = get_user(data, user_id)
    if user.get("banned"):
        bot.answer_callback_query(call.id, "⛔ Akun kamu di-banned!", show_alert=True)
        return False
    if not is_member(user_id):
        bot.answer_callback_query(call.id, "❌ Join channel dulu!", show_alert=True)
        return False
    return True

# ==================== HANDLER /start ====================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "User"
    
    # Auto register user
    user = get_user(data, user_id)
    
    if not is_member(user_id) and not is_owner(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("👥 Join Channel", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Sudah Join", callback_data="cek_join"))
        bot.send_message(message.chat.id, f"""🔒 <b>SELAMAT DATANG</b>

Untuk menggunakan bot ini, kamu harus:
1. Join channel kami
2. Deposit saldo minimal Rp {HARGA_RDP:,}

Silahkan join channel dulu 👇""", parse_mode="HTML", reply_markup=markup)
        return
    
    show_main_menu(message.chat.id, user_id, user_name)

def show_main_menu(chat_id, user_id, user_name):
    user = get_user(data, user_id)
    balance = user["balance"]
    
    text = f"""🚀 <b>RDP INSTALLER BOT</b>
━━━━━━━━━━━━━━━━━━

📊 <b>PROFILE</b>
<b>ID</b> : <code>{user_id}</code>
<b>NAMA</b> : {user_name}
<b>SALDO</b> : Rp {balance:,}

💰 <b>HARGA INSTALL RDP</b> : Rp {HARGA_RDP:,}

📊 <b>INFO</b>
<b>PROVIDER</b> : DigitalOcean / Vultr
<b>RAM</b> : Minimal 2GB
<b>OS VPS</b> : Ubuntu 22/20 - Debian 11/12
━━━━━━━━━━━━━━━━━━"""

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("🖥 Install RDP", callback_data="install_rdp"))
    markup.add(
        types.InlineKeyboardButton("💳 Deposit", callback_data="deposit_menu"),
        types.InlineKeyboardButton("💰 Saldo", callback_data="cek_saldo")
    )
    markup.add(
        types.InlineKeyboardButton("📋 Riwayat Install", callback_data="history_install"),
        types.InlineKeyboardButton("📋 Riwayat Deposit", callback_data="history_deposit")
    )
    markup.add(
        types.InlineKeyboardButton("💬 Owner ↗", url=data["owner_link"]),
        types.InlineKeyboardButton("📢 Channel ↗", url=data["channel_link"])
    )
    if is_owner(user_id):
        markup.add(types.InlineKeyboardButton("⚙️ Settings Owner", callback_data="owner_settings"))
    
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

# ==================== CEK JOIN CALLBACK ====================
@bot.callback_query_handler(func=lambda call: call.data == "cek_join")
def cek_join(call):
    if is_member(call.from_user.id) or is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Berhasil! Silahkan /start lagi")
        show_main_menu(call.message.chat.id, call.from_user.id, call.from_user.first_name or "User")
    else:
        bot.answer_callback_query(call.id, "❌ Kamu belum join channel!", show_alert=True)

# ==================== CEK SALDO ====================
@bot.callback_query_handler(func=lambda call: call.data == "cek_saldo")
def cek_saldo(call):
    if not check_access_callback(call):
        return
    user = get_user(data, call.from_user.id)
    bot.answer_callback_query(call.id, f"💰 Saldo kamu: Rp {user['balance']:,}", show_alert=True)

# ==================== DEPOSIT MENU ====================
@bot.callback_query_handler(func=lambda call: call.data == "deposit_menu")
def deposit_menu(call):
    if not check_access_callback(call):
        return
    
    text = """💳 <b>DEPOSIT SALDO</b>
━━━━━━━━━━━━━━━━━━

Pilih nominal deposit:"""

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Rp 15.000", callback_data="depo_15000"),
        types.InlineKeyboardButton("Rp 25.000", callback_data="depo_25000")
    )
    markup.add(
        types.InlineKeyboardButton("Rp 50.000", callback_data="depo_50000"),
        types.InlineKeyboardButton("Rp 100.000", callback_data="depo_100000")
    )
    markup.add(types.InlineKeyboardButton("✏️ Custom Nominal", callback_data="depo_custom"))
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="back_main"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# ==================== PROSES DEPOSIT ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("depo_"))
def process_deposit(call):
    if not check_access_callback(call):
        return
    
    user_id = call.from_user.id
    nominal = int(call.data.replace("depo_", ""))
    unique_code = random.randint(1, 99)
    total = nominal + unique_code
    
    # Simpan pending deposit
    pending_deposits[user_id] = {
        "amount": nominal,
        "unique": unique_code,
        "total": total,
        "created_at": time.time()
    }
    
    # Generate QRIS
    filename = f"depo_{user_id}_{int(time.time())}.png"
    qris_path = generate_qris_image(total, filename)
    
    text = f"""💳 <b>INVOICE DEPOSIT</b>
━━━━━━━━━━━━━━━━━━

💰 Nominal: Rp {nominal:,}
🔢 Kode Unik: +Rp {unique_code}
📌 <b>TOTAL BAYAR: Rp {total:,}</b>

📱 Scan QRIS di bawah untuk bayar
⏳ Expired dalam 60 menit
✅ Pembayaran otomatis terverifikasi (±30 detik)

⚠️ Bayar TEPAT Rp {total:,} agar terdeteksi!"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Cek Pembayaran", callback_data="cek_bayar"))
    markup.add(types.InlineKeyboardButton("❌ Batal", callback_data="back_main"))
    
    # Kirim QRIS image
    with open(qris_path, 'rb') as photo:
        bot.send_photo(call.message.chat.id, photo, caption=text, parse_mode="HTML", reply_markup=markup)
    
    # Hapus pesan lama
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    # Cleanup file
    try:
        os.remove(qris_path)
    except:
        pass
    
    bot.answer_callback_query(call.id)

# ==================== CEK BAYAR MANUAL ====================
@bot.callback_query_handler(func=lambda call: call.data == "cek_bayar")
def cek_bayar(call):
    user_id = call.from_user.id
    deposit = pending_deposits.get(user_id)
    
    if not deposit:
        bot.answer_callback_query(call.id, "❌ Tidak ada deposit pending", show_alert=True)
        return
    
    # Cek expired (1 jam)
    if time.time() - deposit["created_at"] > 3600:
        del pending_deposits[user_id]
        bot.answer_callback_query(call.id, "❌ Deposit expired! Silahkan buat baru", show_alert=True)
        return
    
    if check_orkut_payment(deposit["total"]):
        # Berhasil!
        add_balance(data, user_id, deposit["amount"])
        user = get_user(data, user_id)
        user["deposit_history"].append({"amount": deposit["amount"], "date": time.strftime("%d/%m/%y %H:%M")})
        save_data(data)
        del pending_deposits[user_id]
        bot.answer_callback_query(call.id, f"✅ Deposit Rp {deposit['amount']:,} berhasil! Saldo: Rp {user['balance']:,}", show_alert=True)
        bot.send_message(call.message.chat.id, f"✅ <b>DEPOSIT BERHASIL!</b>\n\n💰 +Rp {deposit['amount']:,}\n💳 Saldo sekarang: Rp {user['balance']:,}", parse_mode="HTML")
        # Notif owner
        try:
            bot.send_message(OWNER_ID, f"💰 <b>DEPOSIT MASUK!</b>\n\n👤 User: <code>{user_id}</code>\n💵 Nominal: Rp {deposit['amount']:,}\n💳 Saldo user: Rp {user['balance']:,}", parse_mode="HTML")
        except: pass
    else:
        bot.answer_callback_query(call.id, "⏳ Pembayaran belum terdeteksi. Coba lagi nanti.", show_alert=True)

# ==================== DEPOSIT CUSTOM ====================
@bot.callback_query_handler(func=lambda call: call.data == "depo_custom")
def depo_custom(call):
    if not check_access_callback(call):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "✏️ Ketik nominal deposit (min 1000):\n\nContoh: <code>5000</code>", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_custom_deposit)

def process_custom_deposit(message):
    try:
        nominal = int(message.text.strip())
        if nominal < 1000:
            bot.reply_to(message, "❌ Minimal deposit Rp 1.000")
            return
        user_id = message.from_user.id
        unique_code = random.randint(1, 99)
        total = nominal + unique_code
        pending_deposits[user_id] = {"amount": nominal, "unique": unique_code, "total": total, "created_at": time.time()}
        filename = f"depo_{user_id}_{int(time.time())}.png"
        qris_path = generate_qris_image(total, filename)
        text = f"💳 <b>INVOICE DEPOSIT</b>\n━━━━━━━━━━━━━━━━━━\n\n💰 Nominal: Rp {nominal:,}\n🔢 Kode Unik: +Rp {unique_code}\n📌 <b>TOTAL BAYAR: Rp {total:,}</b>\n\n⏳ Expired 60 menit\n✅ Auto verifikasi ±30 detik\n⚠️ Bayar TEPAT Rp {total:,}!"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Cek Pembayaran", callback_data="cek_bayar"))
        markup.add(types.InlineKeyboardButton("❌ Batal", callback_data="back_main"))
        with open(qris_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=text, parse_mode="HTML", reply_markup=markup)
        try: os.remove(qris_path)
        except: pass
    except:
        bot.reply_to(message, "❌ Nominal tidak valid. Ketik angka saja.\nContoh: 5000")

# ==================== RIWAYAT INSTALL ====================
@bot.callback_query_handler(func=lambda call: call.data == "history_install")
def history_install(call):
    if not check_access_callback(call):
        return
    user = get_user(data, call.from_user.id)
    history = user.get("install_history", [])
    if not history:
        bot.answer_callback_query(call.id, "📋 Belum ada riwayat install", show_alert=True)
        return
    text = "📋 <b>RIWAYAT INSTALL</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    for i, h in enumerate(history[-10:], 1):
        text += f"{i}. {h.get('os','?')} | {h.get('ip','?')} | {h.get('date','?')}\n"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="back_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# ==================== RIWAYAT DEPOSIT ====================
@bot.callback_query_handler(func=lambda call: call.data == "history_deposit")
def history_deposit(call):
    if not check_access_callback(call):
        return
    user = get_user(data, call.from_user.id)
    history = user.get("deposit_history", [])
    if not history:
        bot.answer_callback_query(call.id, "📋 Belum ada riwayat deposit", show_alert=True)
        return
    text = "📋 <b>RIWAYAT DEPOSIT</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    for i, h in enumerate(history[-10:], 1):
        text += f"{i}. Rp {h.get('amount',0):,} | {h.get('date','?')}\n"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="back_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# ==================== INSTALL RDP MENU ====================
@bot.callback_query_handler(func=lambda call: call.data == "install_rdp")
def install_rdp_menu(call):
    if not check_access_callback(call):
        return
    
    user = get_user(data, call.from_user.id)
    if user["balance"] < HARGA_RDP and not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, f"❌ Saldo tidak cukup! Butuh Rp {HARGA_RDP:,}. Saldo: Rp {user['balance']:,}", show_alert=True)
        return
    
    text = """🖥 <b>Pilih Versi Windows</b>

1   Windows Server 2012 R2
2   Windows Server 2016
3   Windows Server 2019
4   Windows Server 2022
5   Windows Server 2025
6   Windows 10 SuperLite
7   Windows 11 SuperLite
8   Windows 10 Atlas
9   Windows 11 Atlas
10  Windows 10 Pro
11  Windows 11 Pro
12  Tiny10 23H2
13  Tiny11 23H2

Klik tombol OS di bawah 👇"""

    markup = types.InlineKeyboardMarkup(row_width=3)
    for i in range(1, 13, 3):
        row = [types.InlineKeyboardButton(str(j), callback_data=f"win_{j}") for j in range(i, min(i+3, 14))]
        markup.row(*row)
    markup.add(types.InlineKeyboardButton("13", callback_data="win_13"))
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="back_main"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# ==================== PILIH WINDOWS ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("win_"))
def select_windows(call):
    if not check_access_callback(call):
        return
    
    win_num = call.data.replace("win_", "")
    win_name = WINDOWS_OPTIONS.get(win_num, "Unknown")
    user_os_choice[call.from_user.id] = win_num
    
    text = f"""✅ <b>OS Dipilih:</b> {win_name}

Kirim IP dan Password VPS:
<code>/l IP PASSWORD</code>

Contoh: <code>/l 123.456.78.90 password123</code>

💰 Saldo akan dipotong Rp {HARGA_RDP:,} saat install."""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="install_rdp"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
    bot.answer_callback_query(call.id, f"✅ {win_name}")

# ==================== INSTALL COMMAND /l ====================
@bot.message_handler(commands=['l'])
def install_command(message):
    if not check_access(message):
        return
    
    user_id = message.from_user.id
    user = get_user(data, user_id)
    
    # Cek saldo (owner bypass)
    if user["balance"] < HARGA_RDP and not is_owner(user_id):
        bot.reply_to(message, f"❌ Saldo tidak cukup!\n💰 Saldo: Rp {user['balance']:,}\n💵 Harga: Rp {HARGA_RDP:,}\n\nSilahkan deposit dulu.", parse_mode="HTML")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 3:
            raise ValueError
        ip = parts[1]
        password = parts[2]
    except:
        bot.reply_to(message, "❌ Format: /l [IP] [PASSWORD]\nContoh: /l 123.456.78.90 password123")
        return
    
    os_num = user_os_choice.get(user_id)
    if not os_num:
        bot.reply_to(message, "❌ Pilih OS dulu! Klik /start → Install RDP → Pilih OS")
        return
    
    os_name = WINDOWS_OPTIONS.get(os_num, "Unknown")
    
    # Potong saldo (owner tidak dipotong)
    if not is_owner(user_id):
        deduct_balance(data, user_id, HARGA_RDP)
        user["total_install"] = user.get("total_install", 0) + 1
        user["install_history"].append({"os": os_name, "ip": ip, "date": time.strftime("%d/%m/%y %H:%M")})
        save_data(data)
    
    bot.reply_to(message, f"""⏳ <b>Memulai instalasi RDP...</b>

🖥 <b>OS:</b> {os_name}
🌐 <b>IP:</b> <code>{ip}</code>
💰 <b>Saldo dipotong:</b> Rp {HARGA_RDP:,}

Proses 15-30 menit. Notifikasi setelah selesai.""", parse_mode="HTML")
    
    # Notif owner
    try:
        bot.send_message(OWNER_ID, f"🖥 <b>INSTALL BARU!</b>\n\n👤 User: <code>{user_id}</code>\n🌐 IP: <code>{ip}</code>\n💻 OS: {os_name}", parse_mode="HTML")
    except: pass
    
    # Jalankan install di background
    import subprocess
    def run_install():
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "rdp.sh")
        try:
            result = subprocess.run(
                ["bash", script_path, ip, password, os_num],
                capture_output=True, text=True, timeout=1800
            )
            if result.returncode == 0:
                bot.send_message(message.chat.id, f"""✅ <b>INSTALASI SELESAI!</b>

🖥 <b>OS:</b> {os_name}
🌐 <b>RDP:</b> <code>{ip}:3389</code>
👤 <b>User:</b> <code>Administrator</code>
🔑 <b>Pass:</b> <code>P@ssw0rd123</code>

Tunggu 15-30 menit lagi sampai RDP bisa diakses.""", parse_mode="HTML")
            else:
                error_msg = result.stderr[-500:] if result.stderr else "Unknown error"
                bot.send_message(message.chat.id, f"❌ <b>Instalasi gagal!</b>\n\n<code>{error_msg}</code>", parse_mode="HTML")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {str(e)[:200]}")
    
    threading.Thread(target=run_install).start()

# ==================== BACK TO MAIN ====================
@bot.callback_query_handler(func=lambda call: call.data == "back_main")
def back_to_main(call):
    user_id = call.from_user.id
    user_name = call.from_user.first_name or "User"
    user = get_user(data, user_id)
    
    text = f"""🚀 <b>RDP INSTALLER BOT</b>
━━━━━━━━━━━━━━━━━━

📊 <b>PROFILE</b>
<b>ID</b> : <code>{user_id}</code>
<b>NAMA</b> : {user_name}
<b>SALDO</b> : Rp {user['balance']:,}

💰 <b>HARGA INSTALL RDP</b> : Rp {HARGA_RDP:,}
━━━━━━━━━━━━━━━━━━"""

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("🖥 Install RDP", callback_data="install_rdp"))
    markup.add(
        types.InlineKeyboardButton("💳 Deposit", callback_data="deposit_menu"),
        types.InlineKeyboardButton("💰 Saldo", callback_data="cek_saldo")
    )
    markup.add(
        types.InlineKeyboardButton("💬 Owner ↗", url=data["owner_link"]),
        types.InlineKeyboardButton("📢 Channel ↗", url=data["channel_link"])
    )
    if is_owner(user_id):
        markup.add(types.InlineKeyboardButton("⚙️ Settings Owner", callback_data="owner_settings"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
    except:
        bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=markup)

# ==================== OWNER SETTINGS ====================
@bot.callback_query_handler(func=lambda call: call.data == "owner_settings")
def owner_settings(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya owner!")
        return
    
    total_users = len(data.get("users", {}))
    total_balance = sum(u.get("balance", 0) for u in data.get("users", {}).values())
    
    text = f"""⚙️ <b>OWNER SETTINGS</b>
━━━━━━━━━━━━━━━━━━

👥 Total User: {total_users}
💰 Total Saldo User: Rp {total_balance:,}
🔗 Owner: {data["owner_link"]}
📢 Channel: {data["channel_link"]}
💵 Harga RDP: Rp {HARGA_RDP:,}

<b>Commands:</b>
/adduser [id] - Tambah user
/deluser [id] - Hapus user
/addsaldo [id] [nominal] - Tambah saldo user
/ban [id] - Ban user
/unban [id] - Unban user
/broadcast [pesan] - Kirim ke semua user
/setowner [link] - Set link owner
/setchannel [link] - Set link channel
/listuser - Daftar user"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="back_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# ==================== OWNER COMMANDS ====================
@bot.message_handler(commands=['adduser'])
def add_user(message):
    if not is_owner(message.from_user.id):
        return
    try:
        uid = int(message.text.split()[1])
        if uid not in data["allowed_users"]:
            data["allowed_users"].append(uid)
            save_data(data)
        bot.reply_to(message, f"✅ User <code>{uid}</code> ditambahkan!", parse_mode="HTML")
    except:
        bot.reply_to(message, "❌ Format: /adduser [id]")

@bot.message_handler(commands=['deluser'])
def del_user(message):
    if not is_owner(message.from_user.id):
        return
    try:
        uid = int(message.text.split()[1])
        if uid == OWNER_ID:
            bot.reply_to(message, "⚠️ Tidak bisa hapus owner!")
            return
        if uid in data["allowed_users"]:
            data["allowed_users"].remove(uid)
            save_data(data)
        bot.reply_to(message, f"✅ User <code>{uid}</code> dihapus!", parse_mode="HTML")
    except:
        bot.reply_to(message, "❌ Format: /deluser [id]")

@bot.message_handler(commands=['addsaldo'])
def add_saldo_cmd(message):
    if not is_owner(message.from_user.id):
        return
    try:
        parts = message.text.split()
        uid = int(parts[1])
        nominal = int(parts[2])
        add_balance(data, uid, nominal)
        user = get_user(data, uid)
        bot.reply_to(message, f"✅ Saldo user <code>{uid}</code> +Rp {nominal:,}\nSaldo sekarang: Rp {user['balance']:,}", parse_mode="HTML")
    except:
        bot.reply_to(message, "❌ Format: /addsaldo [id] [nominal]")

@bot.message_handler(commands=['setowner'])
def set_owner_link(message):
    if not is_owner(message.from_user.id):
        return
    try:
        link = message.text.split(maxsplit=1)[1]
        data["owner_link"] = link
        save_data(data)
        bot.reply_to(message, f"✅ Owner link: {link}")
    except:
        bot.reply_to(message, "❌ Format: /setowner [link]")

@bot.message_handler(commands=['setchannel'])
def set_channel_link(message):
    if not is_owner(message.from_user.id):
        return
    try:
        link = message.text.split(maxsplit=1)[1]
        data["channel_link"] = link
        save_data(data)
        bot.reply_to(message, f"✅ Channel link: {link}")
    except:
        bot.reply_to(message, "❌ Format: /setchannel [link]")

@bot.message_handler(commands=['listuser'])
def list_users(message):
    if not is_owner(message.from_user.id):
        return
    users_info = ""
    for uid, info in data.get("users", {}).items():
        status = "🚫" if info.get("banned") else "✅"
        users_info += f"{status} <code>{uid}</code> - Rp {info.get('balance', 0):,}\n"
    if not users_info:
        users_info = "Belum ada user"
    bot.reply_to(message, f"👥 <b>Daftar User:</b>\n\n{users_info}", parse_mode="HTML")

@bot.message_handler(commands=['ban'])
def ban_user(message):
    if not is_owner(message.from_user.id):
        return
    try:
        uid = int(message.text.split()[1])
        user = get_user(data, uid)
        user["banned"] = True
        save_data(data)
        bot.reply_to(message, f"🚫 User <code>{uid}</code> telah di-BAN!", parse_mode="HTML")
    except:
        bot.reply_to(message, "❌ Format: /ban [id]")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    if not is_owner(message.from_user.id):
        return
    try:
        uid = int(message.text.split()[1])
        user = get_user(data, uid)
        user["banned"] = False
        save_data(data)
        bot.reply_to(message, f"✅ User <code>{uid}</code> telah di-UNBAN!", parse_mode="HTML")
    except:
        bot.reply_to(message, "❌ Format: /unban [id]")

@bot.message_handler(commands=['broadcast', 'bc'])
def broadcast(message):
    if not is_owner(message.from_user.id):
        return
    try:
        text = message.text.split(maxsplit=1)[1]
    except:
        bot.reply_to(message, "❌ Format: /broadcast [pesan]")
        return
    success = 0
    fail = 0
    for uid in data.get("users", {}).keys():
        try:
            bot.send_message(int(uid), f"📢 <b>BROADCAST</b>\n\n{text}", parse_mode="HTML")
            success += 1
        except:
            fail += 1
    bot.reply_to(message, f"📢 Broadcast selesai!\n✅ Terkirim: {success}\n❌ Gagal: {fail}")

# ==================== AUTO-CHECK PAYMENT (30 detik) ====================
def payment_checker():
    while True:
        time.sleep(30)
        expired = []
        for uid, dep in list(pending_deposits.items()):
            # Expired 1 jam
            if time.time() - dep["created_at"] > 3600:
                expired.append(uid)
                continue
            try:
                if check_orkut_payment(dep["total"]):
                    add_balance(data, uid, dep["amount"])
                    user = get_user(data, uid)
                    user["deposit_history"].append({"amount": dep["amount"], "date": time.strftime("%d/%m/%y %H:%M")})
                    save_data(data)
                    expired.append(uid)
                    try:
                        bot.send_message(uid, f"✅ <b>DEPOSIT BERHASIL!</b>\n\n💰 +Rp {dep['amount']:,}\n💳 Saldo: Rp {user['balance']:,}", parse_mode="HTML")
                    except: pass
                    try:
                        bot.send_message(OWNER_ID, f"💰 <b>DEPOSIT MASUK!</b>\n\n👤 User: <code>{uid}</code>\n💵 Rp {dep['amount']:,}", parse_mode="HTML")
                    except: pass
            except:
                pass
        for uid in expired:
            pending_deposits.pop(uid, None)

# Start payment checker thread
checker_thread = threading.Thread(target=payment_checker, daemon=True)
checker_thread.start()

# ==================== RUN BOT ====================
if __name__ == "__main__":
    print("🤖 Bot RDP berjalan...")
    print(f"💳 Payment: OrKut QRIS")
    print(f"💰 Harga RDP: Rp {HARGA_RDP:,}")
    print(f"📢 Channel: {CHANNEL_URL}")
    bot.infinity_polling()

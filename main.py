from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import string
import random
import os
import json

app = Flask(__name__)

# ================= KONFIGURASI =================
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', "ganti-dengan-secret-key-yang-sangat-kuat-2026")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///licenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ================= MODEL =================
class LicenseKey(db.Model):
    __tablename__ = 'license_keys'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    activated_by = db.Column(db.String(20), nullable=True)
    used_by_chat_id = db.Column(db.BigInteger, nullable=True)
    used_by_username = db.Column(db.String(100), nullable=True)
    used_by_name = db.Column(db.String(100), nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ActivatedUser(db.Model):
    __tablename__ = 'activated_users'
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(100), nullable=True)
    first_name = db.Column(db.String(100), nullable=True)
    activated_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MachineBinding(db.Model):
    __tablename__ = 'machine_bindings'
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.BigInteger, nullable=False)
    ip_address = db.Column(db.String(50), nullable=False)
    activated_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('chat_id', 'ip_address', name='unique_machine'),)

class IvasAccount(db.Model):
    __tablename__ = 'ivas_accounts'
    id = db.Column(db.Integer, primary_key=True)
    owner_chat_id = db.Column(db.BigInteger, nullable=False)
    username = db.Column(db.String(150), nullable=False)
    password = db.Column(db.String(150), nullable=False)
    cookies = db.Column(db.JSON, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime, nullable=True)

    __table_args__ = (db.UniqueConstraint('owner_chat_id', 'username', name='unique_owner_account'),)

# ================= HELPER =================
def generate_key(length=20):
    chars = string.ascii_uppercase + string.digits
    key = ''.join(random.choices(chars, k=length))
    return '-'.join(key[i:i+4] for i in range(0, len(key), 4))

def get_client_ip():
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0]
    return request.remote_addr or "Unknown"

# ================= ROUTES =================
@app.route('/')
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html', 
                         client_ip=get_client_ip(),
                         total_key=LicenseKey.query.count(),
                         used_key=LicenseKey.query.filter_by(is_used=True).count(),
                         total_user=ActivatedUser.query.count(),
                         total_machine=MachineBinding.query.count())

@app.route('/ping')
def ping():
    return "✅ License Manager is Online!"

# ================= LICENSE API =================
@app.route('/api/bot/validate_license', methods=['POST'])
def bot_validate_license():
    data = request.get_json()
    key = data.get('key')
    chat_id = data.get('chat_id')

    if not key or not chat_id:
        return jsonify({"success": False, "message": "Key dan Chat ID wajib dikirim"}), 400

    license = LicenseKey.query.filter_by(key=key.strip()).first()
    if not license:
        return jsonify({"success": False, "message": "Lisensi tidak ditemukan"}), 404

    if license.is_used:
        if license.used_by_chat_id == int(chat_id):
            return jsonify({"success": True, "is_valid": True, "is_used": True, "owner_match": True, "message": "Lisensi valid"})
        else:
            return jsonify({"success": False, "is_valid": False, "message": "Lisensi sudah digunakan oleh Owner lain"}), 403

    return jsonify({"success": True, "is_valid": True, "is_used": False, "message": "Lisensi valid dan siap diaktifkan"})


@app.route('/api/bot/activate_license', methods=['POST'])
def bot_activate_license():
    """Endpoint yang dipanggil bot saat aktivasi pertama"""
    data = request.get_json()
    key = data.get('key')
    chat_id = data.get('chat_id')

    if not key or not chat_id:
        return jsonify({"success": False, "message": "Data tidak lengkap"}), 400

    license = LicenseKey.query.filter_by(key=key.strip()).first()
    if not license or license.is_used:
        return jsonify({"success": False, "message": "Lisensi tidak valid atau sudah digunakan"}), 403

    try:
        license.is_used = True
        license.used_by_chat_id = int(chat_id)
        license.used_at = datetime.utcnow()
        license.activated_by = "bot"

        user = ActivatedUser.query.filter_by(chat_id=int(chat_id)).first()
        if not user:
            user = ActivatedUser(chat_id=int(chat_id))
            db.session.add(user)

        db.session.commit()
        return jsonify({"success": True, "message": "Lisensi berhasil diaktifkan"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/bot/check_owner', methods=['POST'])
def bot_check_owner():
    data = request.get_json()
    chat_id = data.get('chat_id')
    if not chat_id:
        return jsonify({"success": False, "message": "Chat ID tidak boleh kosong"}), 400

    license = LicenseKey.query.filter_by(used_by_chat_id=chat_id, is_used=True).first()
    if license:
        return jsonify({
            "success": True, "registered": True,
            "key": license.key,
            "used_at": license.used_at.strftime('%Y-%m-%d %H:%M:%S') if license.used_at else None
        })
    return jsonify({"success": True, "registered": False})


# ================= IVAS ACCOUNT API =================
@app.route('/api/bot/add_account', methods=['POST', 'GET'])
def bot_add_account():
    if request.method == 'POST':
        data = request.get_json() or request.form.to_dict()
    else:
        data = request.args.to_dict()

    owner_chat_id = data.get('owner_chat_id')
    username = data.get('username')
    password = data.get('password')
    cookies = data.get('cookies')

    if isinstance(cookies, str):
        try:
            cookies = json.loads(cookies)
        except:
            cookies = {}

    if not all([owner_chat_id, username, cookies]):
        return jsonify({"success": False, "message": "Data tidak lengkap"}), 400

    try:
        owner_chat_id = int(owner_chat_id)
        existing = IvasAccount.query.filter_by(owner_chat_id=owner_chat_id, username=username).first()

        if existing:
            existing.password = password or existing.password
            existing.cookies = cookies
            existing.last_used = datetime.utcnow()
            existing.is_active = True
            db.session.commit()
            return jsonify({"success": True, "message": "Akun berhasil diupdate"})

        new_account = IvasAccount(
            owner_chat_id=owner_chat_id,
            username=username,
            password=password or "",
            cookies=cookies,
            is_active=True
        )
        db.session.add(new_account)
        db.session.commit()
        return jsonify({"success": True, "message": "Akun baru berhasil ditambahkan"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/bot/get_accounts', methods=['GET'])
def bot_get_accounts():
    owner_chat_id = request.args.get('owner_chat_id')
    if not owner_chat_id:
        return jsonify({"success": False, "message": "owner_chat_id diperlukan"}), 400

    try:
        accounts = IvasAccount.query.filter_by(
            owner_chat_id=int(owner_chat_id), 
            is_active=True
        ).all()
        
        result = [{
            "username": acc.username,
            "password": acc.password,
            "cookies": acc.cookies
        } for acc in accounts]
        
        return jsonify({"success": True, "accounts": result, "total": len(result)})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/bot/delete_account', methods=['POST', 'GET'])
def bot_delete_account():
    if request.method == 'POST':
        data = request.get_json() or request.form.to_dict()
    else:
        data = request.args.to_dict()

    owner_chat_id = data.get('owner_chat_id')
    username = data.get('username')

    if not owner_chat_id or not username:
        return jsonify({"success": False, "message": "Data tidak lengkap"}), 400

    try:
        account = IvasAccount.query.filter_by(
            owner_chat_id=int(owner_chat_id), 
            username=username
        ).first()

        if not account:
            return jsonify({"success": False, "message": "Akun tidak ditemukan"}), 404

        db.session.delete(account)
        db.session.commit()
        return jsonify({"success": True, "message": f"Akun {username} berhasil dihapus"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/bot/update_cookie', methods=['POST', 'GET'])
def bot_update_cookie():
    if request.method == 'POST':
        data = request.get_json() or request.form.to_dict()
    else:
        data = request.args.to_dict()

    owner_chat_id = data.get('owner_chat_id')
    username = data.get('username')
    cookies = data.get('cookies')

    if isinstance(cookies, str):
        try:
            cookies = json.loads(cookies)
        except:
            pass

    if not all([owner_chat_id, username, cookies]):
        return jsonify({"success": False, "message": "Data tidak lengkap"}), 400

    try:
        account = IvasAccount.query.filter_by(
            owner_chat_id=int(owner_chat_id), 
            username=username
        ).first()

        if not account:
            return jsonify({"success": False, "message": "Akun tidak ditemukan"}), 404

        account.cookies = cookies
        account.last_used = datetime.utcnow()
        db.session.commit()

        return jsonify({"success": True, "message": f"Cookie untuk {username} berhasil diupdate"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


# ================= ADMIN PANEL (DITAMBAHKAN) =================

@app.route('/admin')
def admin():
    status = request.args.get('status', 'all')
    query = LicenseKey.query
    if status == 'active':
        query = query.filter_by(is_used=True)
    elif status == 'inactive':
        query = query.filter_by(is_used=False)
    keys = query.order_by(LicenseKey.created_at.desc()).all()
    return render_template('admin.html', keys=keys, current_status=status, client_ip=get_client_ip())


@app.route('/admin/generate-custom', methods=['GET', 'POST'])
def generate_custom():
    if request.method == 'POST':
        try:
            mode = request.form.get('mode')
            keys = []
            error = None

            if mode == "custom":
                prefix = request.form.get('prefix', '').strip().upper()
                if not prefix:
                    error = "❌ Nama lisensi tidak boleh kosong!"
                elif LicenseKey.query.filter_by(key=prefix).first():
                    error = f"❌ Nama lisensi '<strong>{prefix}</strong>' sudah pernah digunakan!"
                else:
                    db.session.add(LicenseKey(key=prefix, is_used=False))
                    keys.append(prefix)
                    db.session.commit()
            else:
                amount = int(request.form.get('amount', 5))
                if amount > 100: amount = 100
                for _ in range(amount):
                    new_key = generate_key(20)
                    while LicenseKey.query.filter_by(key=new_key).first():
                        new_key = generate_key(20)
                    db.session.add(LicenseKey(key=new_key, is_used=False))
                    keys.append(new_key)
                db.session.commit()

            if error:
                return render_template('generate_custom.html', error=error)
            return render_template('generate_custom.html', keys=keys, success=True, mode=mode)

        except Exception as e:
            return render_template('generate_custom.html', error=f"Terjadi kesalahan: {str(e)}")

    return render_template('generate_custom.html')


@app.route('/admin/delete/key/<int:key_id>', methods=['POST'])
def delete_key(key_id):
    key = LicenseKey.query.get_or_404(key_id)
    if key.is_used and key.used_by_chat_id:
        user = ActivatedUser.query.filter_by(chat_id=key.used_by_chat_id).first()
        if user: db.session.delete(user)
        machines = MachineBinding.query.filter_by(chat_id=key.used_by_chat_id).all()
        for m in machines: db.session.delete(m)
    db.session.delete(key)
    db.session.commit()
    return redirect('/admin')


@app.route('/admin/ivas_accounts')
def admin_ivas_accounts():
    owner_chat_id = request.args.get('owner_chat_id', type=int)
    query = IvasAccount.query.order_by(IvasAccount.added_at.desc())
    
    if owner_chat_id:
        query = query.filter_by(owner_chat_id=owner_chat_id)
    
    accounts = query.all()
    owners = db.session.query(IvasAccount.owner_chat_id).distinct().all()
    owner_list = [o[0] for o in owners]
    
    return render_template('admin_ivas_accounts.html', 
                         accounts=accounts, 
                         owners=owner_list,
                         selected_owner=owner_chat_id)


@app.route('/admin/ivas/delete/<int:account_id>', methods=['POST'])
def admin_delete_ivas_account(account_id):
    account = IvasAccount.query.get_or_404(account_id)
    username = account.username
    owner_id = account.owner_chat_id
    try:
        db.session.delete(account)
        db.session.commit()
        return jsonify({"success": True, "message": f"Akun {username} milik {owner_id} berhasil dihapus"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/admin/delete_all_ivas', methods=['GET', 'POST'])
def admin_delete_all_ivas():
    if request.method == 'POST':
        owner_chat_id = request.form.get('owner_chat_id')
        if owner_chat_id:
            deleted = IvasAccount.query.filter_by(owner_chat_id=int(owner_chat_id)).delete()
            db.session.commit()
            return render_template('admin_delete_ivas.html', 
                                 success=True, 
                                 deleted_count=deleted, 
                                 owner_id=owner_chat_id)
    
    owners = db.session.query(IvasAccount.owner_chat_id).distinct().all()
    owner_list = [o[0] for o in owners]
    return render_template('admin_delete_ivas.html', owners=owner_list)


# ================= INIT DATABASE =================
with app.app_context():
    db.create_all()
    print("✅ Database siap - Semua tabel dibuat")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 License Manager berjalan di port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
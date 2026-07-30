import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = "getsemani_secret_key"

def conectar_banco():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return sqlite3.connect(os.path.join(base_dir, 'getsemani.db'))

def inicializar_banco():
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_transacao TEXT,
            categoria TEXT,
            valor TEXT,
            descricao TEXT,
            numero_serie TEXT,
            data TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patrimonio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_equipamento TEXT,
            numero_serie TEXT,
            valor TEXT,
            data_registo TEXT
        )
    ''')
    conn.commit()
    conn.close()

inicializar_banco()

@app.route('/')
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        senha = request.form.get('senha')
        if usuario == 'admin' and senha == 'admin':
            session['usuario'] = usuario
            return redirect(url_for('index'))
        else:
            flash('Utilizador ou senha incorretos!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))

@app.route('/transacoes', methods=['GET', 'POST'])
def transacoes():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        tipo = request.form.get('tipo_transacao')
        cat = request.form.get('categoria')
        val = request.form.get('valor')
        desc = request.form.get('descricao')
        serie = request.form.get('numero_serie')
        data_hj = datetime.now().strftime('%d/%m/%Y')
        
        conn = conectar_banco()
        cur = conn.cursor()
        cur.execute("INSERT INTO transacoes (tipo_transacao, categoria, valor, descricao, numero_serie, data) VALUES (?, ?, ?, ?, ?, ?)",
                    (tipo, cat, val, desc, serie, data_hj))
        if tipo == 'equipamento' and serie:
            cur.execute("INSERT INTO patrimonio (nome_equipamento, numero_serie, valor, data_registo) VALUES (?, ?, ?, ?)",
                        (cat, serie, val, data_hj))
        conn.commit()
        conn.close()
        flash('Lançamento efetuado com sucesso!', 'success')
        return redirect(url_for('transacoes'))
    return render_template('transacoes.html')

@app.route('/patrimonio')
def patrimonio():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    conn = conectar_banco()
    cur = conn.cursor()
    cur.execute("SELECT * FROM patrimonio")
    bens = cur.fetchall()
    conn.close()
    return render_template('patrimonio.html', bens=bens)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

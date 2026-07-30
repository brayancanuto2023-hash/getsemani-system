import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = "getsemani_secret_secure_key"

def conectar_banco():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'getsemani.db')
    return sqlite3.connect(db_path)

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
    
    # Variáveis seguras para o index.html não dar erro de UndefinedError
    saidas = 0
    entradas = 0
    saldo = 0
    
    return render_template('index.html', saidas=saidas, entradas=entradas, saldo=saldo)

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

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('index'))

@app.route('/transacoes', methods=['GET', 'POST'])
def transacoes():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        tipo_transacao = request.form.get('tipo_transacao')
        categoria = request.form.get('categoria')
        valor = request.form.get('valor')
        descricao = request.form.get('descricao')
        numero_serie = request.form.get('numero_serie')
        data_atual = datetime.now().strftime('%d/%m/%Y')
        
        conn = conectar_banco()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO transacoes (tipo_transacao, categoria, valor, descricao, numero_serie, data)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (tipo_transacao, categoria, valor, descricao, numero_serie, data_atual))
        
        if tipo_transacao == 'equipamento' and numero_serie:
            cursor.execute('''
                INSERT INTO patrimonio (nome_equipamento, numero_serie, valor, data_registo)
                VALUES (?, ?, ?, ?)
            ''', (categoria, numero_serie, valor, data_atual))
            
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
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patrimonio")
    bens = cursor.fetchall()
    conn.close()
    
    return render_template('patrimonio.html', bens=bens)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chave_secreta_getsemani_123')

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def inicializar_banco():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Tabela de Usuários
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                login VARCHAR(50) UNIQUE NOT NULL,
                senha VARCHAR(255) NOT NULL,
                cargo VARCHAR(50) NOT NULL
            );
        ''')

        # Tabela de Transações
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transacoes (
                id SERIAL PRIMARY KEY,
                tipo VARCHAR(50) NOT NULL,
                categoria VARCHAR(100),
                descricao TEXT,
                valor NUMERIC(10, 2) NOT NULL,
                data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        # Garante usuário Administrador padrão
        cursor.execute("SELECT * FROM usuarios WHERE login = 'brayan'")
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO usuarios (nome, login, senha, cargo)
                VALUES ('Brayan', 'brayan', '1234', 'ADMINISTRADOR')
            ''')

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Erro ao inicializar o banco: {e}")

# Executa a criação das tabelas ao iniciar
inicializar_banco()

@app.route('/')
def home():
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_input = request.form.get('login')
        senha_input = request.form.get('senha')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE login = %s AND senha = %s", (login_input, senha_input))
        usuario = cursor.fetchone()
        cursor.close()
        conn.close()

        if usuario:
            session['usuario_id'] = usuario['id']
            session['nome'] = usuario['nome']
            session['cargo_usuario'] = usuario['cargo']
            return redirect(url_for('dashboard'))
        else:
            flash('Login ou senha incorretos!', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Entradas e Saídas do mês
    cursor.execute("SELECT COALESCE(SUM(valor), 0) as total FROM transacoes WHERE tipo IN ('dizimo', 'oferta')")
    entradas = cursor.fetchone()['total']

    cursor.execute("SELECT COALESCE(SUM(valor), 0) as total FROM transacoes WHERE tipo = 'despesa'")
    saidas = cursor.fetchone()['total']

    cursor.close()
    conn.close()

    meta_orcamento = 5000.00  # Exemplo de meta configurada
    cargo_usuario = session.get('cargo_usuario', '')

    return render_template('index.html', entradas=entradas, saidas=saidas, meta_orcamento=meta_orcamento, cargo_usuario=cargo_usuario)

@app.route('/transacoes', methods=['GET', 'POST'])
def transacoes():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        tipo = request.form.get('tipo_transacao')
        categoria = ''
        descricao = ''
        valor = 0.0

        if tipo == 'dizimo':
            membro = request.form.get('dizimo_membro')
            ministerio = request.form.get('dizimo_ministerio')
            categoria = f"Dízimo - {membro}"
            descricao = f"Ministério: {ministerio}"
            valor = float(request.form.get('dizimo_valor') or 0)

        elif tipo == 'oferta':
            culto = request.form.get('oferta_culto')
            categoria = f"Oferta - {culto}"
            descricao = f"Culto: {culto}"
            valor = float(request.form.get('oferta_valor') or 0)

        elif tipo == 'despesa':
            categoria = request.form.get('despesa_categoria')
            descricao = request.form.get('despesa_descricao')
            valor = float(request.form.get('despesa_valor') or 0)

        if valor > 0:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO transacoes (tipo, categoria, descricao, valor) VALUES (%s, %s, %s, %s)",
                (tipo, categoria, descricao, valor)
            )
            conn.commit()
            cursor.close()
            conn.close()
            flash('Lançamento registrado com sucesso!', 'success')
        else:
            flash('Por favor, informe um valor maior que zero.', 'warning')

        return redirect(url_for('transacoes'))

    return render_template('transacoes.html')

if __name__ == '__main__':
    app.run(debug=True)

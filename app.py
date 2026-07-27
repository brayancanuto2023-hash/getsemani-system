import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chave_secreta_getsemani_123')

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_db_connection():
    if not DATABASE_URL:
        return None
    try:
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    except Exception as e:
        print(f"Erro conexao: {e}")
        return None

def inicializar_banco():
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        # Tabela Usuarios
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                login VARCHAR(50) UNIQUE NOT NULL,
                senha VARCHAR(255) NOT NULL,
                cargo VARCHAR(50) NOT NULL
            );
        ''')
        # Tabela Transacoes
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
        # Tabela Patrimonio / Materiais
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patrimonio (
                id SERIAL PRIMARY KEY,
                nome_item VARCHAR(150) NOT NULL,
                quantidade INT NOT NULL DEFAULT 1,
                departamento VARCHAR(100),
                observacao TEXT,
                data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        # Garante Admin Master
        cursor.execute("SELECT id FROM usuarios WHERE login = 'brayan'")
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO usuarios (nome, login, senha, cargo)
                VALUES ('Brayan', 'brayan', '1234', 'ADMINISTRADOR')
            ''')
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Erro init: {e}")

try:
    inicializar_banco()
except Exception as e:
    print(f"Falha init: {e}")

# --- ROTAS ---

@app.route('/')
def home():
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_input = request.form.get('login', '').strip().lower()
        senha_input = request.form.get('senha', '').strip()

        if login_input == 'brayan' and senha_input == '1234':
            session['usuario_id'] = 1
            session['nome'] = 'Brayan'
            session['cargo_usuario'] = 'ADMINISTRADOR'
            return redirect(url_for('dashboard'))

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM usuarios WHERE LOWER(login) = %s AND senha = %s", (login_input, senha_input))
                usuario = cursor.fetchone()
                cursor.close()
                conn.close()
                if usuario:
                    session['usuario_id'] = usuario['id']
                    session['nome'] = usuario['nome']
                    session['cargo_usuario'] = usuario['cargo']
                    return redirect(url_for('dashboard'))
            except Exception as e:
                print(f"Erro login: {e}")

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

    entradas, saidas = 0.0, 0.0
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COALESCE(SUM(valor), 0) as total FROM transacoes WHERE tipo IN ('dizimo', 'oferta', 'entrada')")
            res_e = cursor.fetchone()
            if res_e: entradas = float(res_e['total'])

            cursor.execute("SELECT COALESCE(SUM(valor), 0) as total FROM transacoes WHERE tipo IN ('despesa', 'saida')")
            res_s = cursor.fetchone()
            if res_s: saidas = float(res_s['total'])

            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Erro dash: {e}")

    return render_template('index.html', entradas=entradas, saidas=saidas, meta_orcamento=5000.00, cargo_usuario=session.get('cargo_usuario', 'ADMINISTRADOR'))

@app.route('/transacoes', methods=['GET', 'POST'])
def transacoes():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        tipo = request.form.get('tipo_transacao')
        categoria, descricao, valor = '', '', 0.0

        if tipo in ['dizimo', 'entrada']:
            categoria = request.form.get('categoria', 'Dízimo/Entrada')
            descricao = request.form.get('descricao', '')
            valor = float(request.form.get('valor') or 0)
        elif tipo in ['oferta', 'despesa', 'saida']:
            categoria = request.form.get('categoria', 'Oferta/Saída')
            descricao = request.form.get('descricao', '')
            valor = float(request.form.get('valor') or 0)

        if valor > 0:
            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO transacoes (tipo, categoria, descricao, valor) VALUES (%s, %s, %s, %s)", (tipo, categoria, descricao, valor))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    flash('Lançamento registrado com sucesso!', 'success')
                except Exception as e:
                    flash(f'Erro ao salvar: {e}', 'danger')
        return redirect(url_for('transacoes'))

    return render_template('transacoes.html')

@app.route('/historico')
def historico():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    lista_transacoes = []
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM transacoes ORDER BY data DESC")
            lista_transacoes = cursor.fetchall()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Erro historico: {e}")

    return render_template('historico.html', transacoes=lista_transacoes)

@app.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        nome = request.form.get('nome')
        login_usr = request.form.get('login', '').strip().lower()
        senha = request.form.get('senha')
        cargo = request.form.get('cargo', 'OPERADOR')

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO usuarios (nome, login, senha, cargo) VALUES (%s, %s, %s, %s)", (nome, login_usr, senha, cargo))
                conn.commit()
                cursor.close()
                conn.close()
                flash('Usuário cadastrado!', 'success')
            except Exception as e:
                flash(f'Erro ao criar usuário: {e}', 'danger')
        return redirect(url_for('usuarios'))

    lista_usuarios = []
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome, login, cargo FROM usuarios ORDER BY id DESC")
            lista_usuarios = cursor.fetchall()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Erro usuarios: {e}")

    return render_template('configuracoes.html', usuarios=lista_usuarios)

@app.route('/patrimonio', methods=['GET', 'POST'])
def patrimonio():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        item = request.form.get('nome_item')
        qtd = int(request.form.get('quantidade') or 1)
        depto = request.form.get('departamento', 'Geral')
        obs = request.form.get('observacao', '')

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO patrimonio (nome_item, quantidade, departamento, observacao) VALUES (%s, %s, %s, %s)", (item, qtd, depto, obs))
                conn.commit()
                cursor.close()
                conn.close()
                flash('Material cadastrado!', 'success')
            except Exception as e:
                flash(f'Erro ao salvar patrimonio: {e}', 'danger')
        return redirect(url_for('patrimonio'))

    itens = []
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM patrimonio ORDER BY id DESC")
            itens = cursor.fetchall()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Erro patrimonio: {e}")

    return render_template('patrimonio_pergunta.html', itens=itens)

@app.route('/ministerios', methods=['GET'])
def ministerios():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    busca = request.args.get('busca', '').strip()
    conn = get_db_connection()
    ministerios_lista = []
    if conn:
        try:
            cursor = conn.cursor()
            query = "SELECT descricao AS nome, COUNT(id) AS qtd, COALESCE(SUM(valor), 0) AS total FROM transacoes WHERE tipo IN ('dizimo', 'oferta', 'entrada')"
            params = []
            if busca:
                query += " AND descricao ILIKE %s"
                params.append(f"%{busca}%")
            query += " GROUP BY descricao ORDER BY total DESC;"
            cursor.execute(query, params)
            ministerios_lista = cursor.fetchall()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Erro ministerios: {e}")

    return render_template('ministerios.html', ministerios=ministerios_lista, busca=busca)

if __name__ == '__main__':
    app.run(debug=True)
    @app.route('/dizimistas')
def dizimistas():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    return render_template('dizimistas.html')

import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "getsemani_ecossistema_secret_secure_key"

def conectar_banco():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'getsemani.db')
    return sqlite3.connect(db_path)



def inicializar_banco():
    conn = conectar_banco()
    cursor = conn.cursor()
    
    # 1. Tabela de Usuários (Acessos ilimitados com controle de cargo)
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        nome TEXT, 
        login TEXT UNIQUE, 
        senha TEXT, 
        cargo TEXT)''')
        
    # 2. Tabela de Dízimos (Identificados por Fiel)
    cursor.execute('''CREATE TABLE IF NOT EXISTS dizimos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        fiel TEXT, 
        valor REAL, 
        ministerio TEXT, 
        data TEXT)''')
        
    # 3. Tabela de Ofertas (100% ANÔNIMA)
    cursor.execute('''CREATE TABLE IF NOT EXISTS ofertas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        valor REAL, 
        culto TEXT, 
        data TEXT)''')
        
    # 4. Tabela de Saídas / Despesas (Plano de contas categorizado)
    cursor.execute('''CREATE TABLE IF NOT EXISTS despesas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        categoria TEXT, 
        valor REAL, 
        descricao TEXT, 
        data TEXT)''')
        
    # 5. Tabela de Patrimônio (Com número de série e localização)
    cursor.execute('''CREATE TABLE IF NOT EXISTS patrimonio (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        item TEXT, 
        valor REAL, 
        numero_serie TEXT, 
        localizacao TEXT, 
        nota_fiscal_path TEXT, 
        data_cadastro TEXT)''')

    # Garante que o seu usuário Administrador padrão sempre exista
    cursor.execute("SELECT * FROM usuarios WHERE login = 'brayan'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO usuarios (nome, login, senha, cargo) VALUES (?, ?, ?, ?)",
                       ("Brayan", "brayan", "1234", "ADMINISTRADOR"))
                       
    conn.commit()
    conn.close()

inicializar_banco()

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_input = request.form['login']
        senha_input = request.form['senha']
        
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("SELECT nome, cargo FROM usuarios WHERE login = ? AND senha = ?", (login_input, senha_input))
        usuario = cursor.fetchone()
        conn.close()
        
        if usuario:
            session['usuario_nome'] = usuario[0]
            session['usuario_cargo'] = usuario[1]
            return redirect(url_for('dashboard'))
        else:
            flash("Usuário ou senha incorretos!")
            
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'usuario_nome' not in session:
        return redirect(url_for('login'))
        
    conn = conectar_banco()
    cursor = conn.cursor()
    
    mes_atual = datetime.now().strftime('%Y-%m')
    
    # FLUXO MENSAL (Zera na virada do mês)
    cursor.execute("SELECT SUM(valor) FROM dizimos WHERE data LIKE ?", (f"{mes_atual}%",))
    total_dizimos_mes = cursor.fetchone()[0] or 0.0
    
    cursor.execute("SELECT SUM(valor) FROM ofertas WHERE data LIKE ?", (f"{mes_atual}%",))
    total_ofertas_mes = cursor.fetchone()[0] or 0.0
    
    entradas_mes = total_dizimos_mes + total_ofertas_mes
    
    cursor.execute("SELECT SUM(valor) FROM despesas WHERE data LIKE ?", (f"{mes_atual}%",))
    saidas_mes = cursor.fetchone()[0] or 0.0
    
    # SALDO REAL (Nunca zera)
    cursor.execute("SELECT SUM(valor) FROM dizimos")
    total_dizimos_geral = cursor.fetchone()[0] or 0.0
    
    cursor.execute("SELECT SUM(valor) FROM ofertas")
    total_ofertas_geral = cursor.fetchone()[0] or 0.0
    
    cursor.execute("SELECT SUM(valor) FROM despesas")
    total_despesas_geral = cursor.fetchone()[0] or 0.0
    
    saldo_geral_caixa = (total_dizimos_geral + total_ofertas_geral) - total_despesas_geral
    
    conn.close()
    
    return render_template('index.html', 
                           saldo_caixa=saldo_geral_caixa, 
                           entradas=entradas_mes, 
                           saidas=saidas_mes,
                           cargo_usuario=session.get('usuario_cargo'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/transacoes', methods=['GET', 'POST'])
def transacoes():
    if 'usuario_nome' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        tipo = request.form['tipo_transacao'] # dizimo, oferta ou despesa
        data_atual = datetime.now().strftime('%Y-%m-%d')
        
        conn = conectar_banco()
        cursor = conn.cursor()
        
        if tipo == 'dizimo':
            fiel = request.form['dizimista_nome']
            valor = float(request.form['dizimo_valor'])
            ministerio = request.form['dizimo_ministerio']
            cursor.execute("INSERT INTO dizimos (fiel, valor, ministerio, data) VALUES (?, ?, ?, ?)",
                           (fiel, valor, ministerio, data_atual))
            
        elif tipo == 'oferta':
            valor = float(request.form['oferta_valor'])
            culto = request.form['oferta_culto']
            # Oferta entra 100% anônima na tabela ofertas
            cursor.execute("INSERT INTO ofertas (valor, culto, data) VALUES (?, ?, ?)",
                           (valor, culto, data_atual))
            
        elif tipo == 'despesa':
            categoria = request.form['despesa_categoria'] # Luz, Água, Internet, etc.
            valor = float(request.form['despesa_valor'])
            descricao = request.form['despesa_descricao']
            cursor.execute("INSERT INTO despesas (categoria, valor, descricao, data) VALUES (?, ?, ?, ?)",
                           (categoria, valor, descricao, data_atual))
            
            # Se for categoria de Equipamento/Patrimônio, podemos pegar o ID para o próximo passo
            if categoria == 'Equipamentos/Patrimônio':
                session['ultimo_item_patrimonio'] = {
                    'item': descricao,
                    'valor': valor,
                    'data': data_atual
                }
                conn.commit()
                conn.close()
                # Redireciona direto para a ficha de patrimônio que vamos criar!
                return redirect(url_for('cadastrar_patrimonio'))

        conn.commit()
        conn.close()
        flash("Transação lançada com sucesso!")
        return redirect(url_for('transacoes'))
        
    return render_template('transacoes.html')

@app.route('/patrimonio/novo', methods=['GET', 'POST'])
def cadastrar_patrimonio():
    if 'usuario_nome' not in session:
        return redirect(url_for('login'))
        
    item_dados = session.get('ultimo_item_patrimonio', {'item': '', 'valor': 0.0, 'data': ''})
    
    if request.method == 'POST':
        conn = conectar_banco()
        cursor = conn.cursor()
        
        item = request.form['patrimonio_item']
        valor = float(request.form['patrimonio_valor'])
        num_serie = request.form['patrimonio_serie']
        localizacao = request.form['patrimonio_local']
        nota_fiscal = "caminho/nota_fiscal.jpg" # Upload simplificado por enquanto
        data_cad = item_dados['data']
        
        cursor.execute("INSERT INTO patrimonio (item, valor, numero_serie, localizacao, nota_fiscal_path, data_cadastro) VALUES (?, ?, ?, ?, ?, ?)",
                       (item, valor, num_serie, localizacao, nota_fiscal, data_cad))
        
        conn.commit()
        conn.close()
        session.pop('ultimo_item_patrimonio', None)
        flash("Item registrado no patrimônio da igreja!")
        return redirect(url_for('transacoes'))
        
    return render_template('patrimonio_pergunta.html', item=item_dados)

@app.route('/configuracoes', methods=['GET', 'POST'])
def configuracoes():
    if 'usuario_nome' not in session:
        return redirect(url_for('login'))
        
    conn = conectar_banco()
    cursor = conn.cursor()
    
    # Se o formulário de cadastrar utilizador for enviado
    if request.method == 'POST':
        nome = request.form['novo_nome']
        login_user = request.form['novo_login']
        senha = request.form['nova_senha']
        cargo = request.form['novo_cargo']
        
        try:
            cursor.execute("INSERT INTO usuarios (nome, login, senha, cargo) VALUES (?, ?, ?, ?)",
                           (nome, login_user, senha, cargo))
            conn.commit()
            flash("Novo utilizador cadastrado com sucesso!")
        except sqlite3.IntegrityError:
            flash("Erro: Este login já existe no sistema!")
            
        return redirect(url_for('configuracoes'))
        
    # Puxar todos os utilizadores cadastrados para listar na página
    cursor.execute("SELECT id, nome, login, cargo FROM usuarios")
    lista_usuarios = cursor.fetchall()
    conn.close()
    
    return render_template('configuracoes.html', usuarios=lista_usuarios)

@app.route('/dizimistas')
def dizimistas():
    if 'usuario_nome' not in session:
        return redirect(url_for('login'))
        
    conn = conectar_banco()
    cursor = conn.cursor()
    
    # Puxa a lista de dízimos cadastrados
    cursor.execute("SELECT id, fiel, valor, ministerio, data FROM dizimos ORDER BY data DESC")
    lista_dizimos = cursor.fetchall()
    conn.close()
    
    return render_template('dizimistas.html', dizimos=lista_dizimos, cargo_usuario=session.get('usuario_cargo'))

@app.route('/ministerios')
def ministerios():
    if 'usuario_nome' not in session:
        return redirect(url_for('login'))
        
    conn = conectar_banco()
    cursor = conn.cursor()
    
    # Agrupa o total de dízimos arrecadados por cada ministério
    cursor.execute("SELECT ministerio, SUM(valor), COUNT(id) FROM dizimos GROUP BY ministerio")
    resumo_ministerios = cursor.fetchall()
    conn.close()
    
    return render_template('ministerios.html', ministerios=resumo_ministerios)

@app.route('/historico')
def historico():
    if 'usuario_nome' not in session:
        return redirect(url_for('login'))
        
    conn = conectar_banco()
    cursor = conn.cursor()
    
    # Puxa os dízimos, ofertas e despesas para listar e permitir a exclusão
    cursor.execute("SELECT id, fiel, valor, ministerio, data FROM dizimos ORDER BY id DESC")
    dizimos = cursor.fetchall()
    
    cursor.execute("SELECT id, valor, culto, data FROM ofertas ORDER BY id DESC")
    ofertas = cursor.fetchall()
    
    cursor.execute("SELECT id, categoria, valor, descricao, data FROM despesas ORDER BY id DESC")
    despesas = cursor.fetchall()
    
    conn.close()
    return render_template('historico.html', dizimos=dizimos, ofertas=ofertas, despesas=despesas, cargo_usuario=session.get('usuario_cargo'))

@app.route('/excluir/<tipo>/<int:id_registro>')
def excluir_registro(tipo, id_registro):
    if 'usuario_nome' not in session:
        return redirect(url_for('login'))
        
    # Regra de Segurança: Apenas Administrador ou Tesoureira podem apagar dados
    if session.get('usuario_cargo') not in ['ADMINISTRADOR', 'TESOUREIRA']:
        flash("Erro: Você não tem permissão para apagar registros!")
        return redirect(url_for('historico'))
        
    conn = conectar_banco()
    cursor = conn.cursor()
    
    if tipo == 'dizimo':
        cursor.execute("DELETE FROM dizimos WHERE id = ?", (id_registro,))
    elif tipo == 'oferta':
        cursor.execute("DELETE FROM ofertas WHERE id = ?", (id_registro,))
    elif tipo == 'despesa':
        cursor.execute("DELETE FROM despesas WHERE id = ?", (id_registro,))
        
    conn.commit()
    conn.close()
    flash("Registro excluído com sucesso! O saldo foi recalculado.")
    return redirect(url_for('historico'))

if __name__ == '__main__':
    app.run(debug=True)

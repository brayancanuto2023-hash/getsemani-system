import os
import psycopg2

from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file

import pandas as pd

from reportlab.lib.pagesizes import letter

from reportlab.pdfgen import canvas

import io



app = Flask(__name__)

app.secret_key = "brayan_secret_key_getsemani_master"



def conectar_banco():
    url_conexao = os.environ.get('DATABASE_URL')
    return psycopg2.connect(url_conexao)


def inicializar_banco():

    conn = conectar_banco()

    cursor = conn.cursor()

    

    # Tabela de Utilizadores e Cargos (Admin, Pastor, Tesoureira, Membro)

    cursor.execute('''

        CREATE TABLE IF NOT EXISTS usuarios (

            id SERIAL PRIMARY KEY,

            username TEXT UNIQUE,

            senha TEXT,

            cargo TEXT

        )

    ''')

    

    # Tabela de Transações Financeiras (Entradas e Saídas)

    cursor.execute('''

        CREATE TABLE IF NOT EXISTS transacoes (

            id SERIAL PRIMARY KEY,

            tipo TEXT, -- 'Entrada' ou 'Saida'

            categoria TEXT, -- 'Dízimo', 'Oferta', 'Água', 'Luz', 'Internet', etc.

            valor REAL,

            membro TEXT, -- Nome se for dízimo, 'Anónimo' se for oferta

            descricao TEXT,

            mes_ano TEXT, -- Formato 'MM/AAAA' para fecho mensal

            data_registo TEXT

        )

    ''')

    

    # Tabela de Gestão de Património

    cursor.execute('''

        CREATE TABLE IF NOT EXISTS patrimonio (

            id SERIAL PRIMARY KEY,

            nome_equipamento TEXT,

            numero_serie TEXT,

            valor REAL,

            localizacao TEXT,

            data_registo TEXT

        )

    ''')

    

    conn.commit()

    

    # Criar Administrador Padrão (Brayan) se não existir

    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE username = 'brayan'")

    if cursor.fetchone()[0] == 0:

        cursor.execute("INSERT INTO usuarios (username, senha, cargo) VALUES ('brayan', 'admin123', 'Admin')")

        cursor.execute("INSERT INTO usuarios (username, senha, cargo) VALUES ('pastor', 'pastor123', 'Pastor')")

        cursor.execute("INSERT INTO usuarios (username, senha, cargo) VALUES ('tesoureira', 'tesour123', 'Tesoureira')")

        conn.commit()

        

    conn.close()



inicializar_banco()



@app.route('/')

def index():
busca = request.args.get('busca', '')
    if 'usuario' not in session:

        return redirect(url_for('login'))

    

    conn = conectar_banco()

    cursor = conn.cursor()

    

    mes_atual = datetime.now().strftime('%m/%Y')

    

    # Calcular Entradas e Saídas do Mês Atual

    cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'Entrada' AND mes_ano = %s", (mes_atual,))

    total_entradas = cursor.fetchone()[0] or 0.0

    

    cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'Saida' AND mes_ano = %s", (mes_atual,))

    total_saidas = cursor.fetchone()[0] or 0.0

    

    saldo_mes = total_entradas - total_saidas

    

    # Saldo Acumulado Total (Nunca zera)

    cursor.execute("SELECT SUM(CASE WHEN tipo = 'Entrada' THEN valor ELSE -valor END) FROM transacoes")

    saldo_geral_caixa = cursor.fetchone()[0] or 0.0

    

    # Listar Transações do Mês

    if busca:
        cursor.execute(
            "SELECT id, tipo, categoria, valor, membro, descricao, data_registo FROM transacoes WHERE mes_ano = %s AND (descricao ILIKE %s OR categoria ILIKE %s OR membro ILIKE %s) ORDER BY id DESC",
            (mes_atual, f"%{busca}%", f"%{busca}%", f"%{busca}%")
        )
    else:
        cursor.execute(
            "SELECT id, tipo, categoria, valor, membro, descricao, data_registo FROM transacoes WHERE mes_ano = %s ORDER BY id DESC",
            (mes_atual,)
        )
    transacoes = cursor.fetchall()

    

    # Listar Património

    cursor.execute("SELECT id, nome_equipamento, numero_serie, valor, localizacao FROM patrimonio")

    patrimonios = cursor.fetchall()

    

    # Listar Utilizadores

    cursor.execute("SELECT id, username, cargo FROM usuarios")

    usuarios = cursor.fetchall()

    

    conn.close()

    

    is_admin_ou_pastor = session.get('cargo') in ['Admin', 'Pastor', 'Tesoureira']

    

    return render_template('index.html', 

                           usuario=session.get('usuario'),
                           busca=busca,
                           cargo=session.get('cargo'),

                           total_entradas=total_entradas,

                           total_saidas=total_saidas,

                           saldo_mes=saldo_mes,

                           saldo_geral_caixa=saldo_geral_caixa,

                           transacoes=transacoes,

                           patrimonios=patrimonios,

                           usuarios=usuarios,

                           mes_atual=mes_atual,

                           is_admin_ou_pastor=is_admin_ou_pastor)



@app.route('/login', methods=['GET', 'POST'])

def login():

    if request.method == 'POST':

        username = request.form.get('username')

        senha = request.form.get('senha')

        

        conn = conectar_banco()

        cursor = conn.cursor()

        cursor.execute("SELECT cargo FROM usuarios WHERE username = %s AND senha = %s", (username, senha))

        user = cursor.fetchone()

        conn.close()

        

        if user:

            session['usuario'] = username

            session['cargo'] = user[0]

            flash('Sessão iniciada com sucesso no Getsêmani System!', 'success')

            return redirect(url_for('index'))

        else:

            flash('Utilizador ou senha incorretos!', 'danger')

            

    return render_template('login.html')



@app.route('/logout')

def logout():

    session.clear()

    return redirect(url_for('login'))



@app.route('/adicionar_transacao', methods=['POST'])

def adicionar_transacao():

    if 'usuario' not in session:

        return redirect(url_for('login'))

        

    tipo = request.form.get('tipo')

    categoria = request.form.get('categoria')

    valor = float(request.form.get('valor', 0))

    membro = request.form.get('membro', 'Anónimo') if tipo == 'Entrada' and categoria == 'Dízimo' else 'Anónimo'

    if tipo == 'Entrada' and categoria == 'Dízimo':

        membro = request.form.get('membro_nome', 'Membro Identificado')

        

    descricao = request.form.get('descricao', '')

    from datetime import timedelta
    fuso_brasil = timedelta(hours=-3)
    agora_br = datetime.now() + fuso_brasil
    
    mes_ano = agora_br.strftime('%m/%Y')
    data_registo = agora_br.strftime('%d/%m/%Y %H:%M')

    

    conn = conectar_banco()

    cursor = conn.cursor()

    cursor.execute("INSERT INTO transacoes (tipo, categoria, valor, membro, descricao, mes_ano, data_registo) VALUES (%s, %s, %s, %s, %s, %s, %s)",

                   (tipo, categoria, valor, membro, descricao, mes_ano, data_registo))

    conn.commit()

    conn.close()

    

    flash('Transação registada com sucesso!', 'success')

    return redirect(url_for('index'))



@app.route('/adicionar_patrimonio', methods=['POST'])

def adicionar_patrimonio():

    if 'usuario' not in session or session.get('cargo') != 'Admin':

        return redirect(url_for('login'))

        

    nome = request.form.get('nome_equipamento')

    serie = request.form.get('numero_serie')

    valor = float(request.form.get('valor', 0))

    local = request.form.get('localizacao')

    data_registo = datetime.now().strftime('%d/%m/%Y')

    

    conn = conectar_banco()

    cursor = conn.cursor()

    cursor.execute("INSERT INTO patrimonio (nome_equipamento, numero_serie, valor, localizacao, data_registo) VALUES (%s, %s, %s, %s, %s)",

                   (nome, serie, valor, local, data_registo))

    conn.commit()

    conn.close()

    

    flash('Património registado na ficha da igreja com sucesso!', 'success')

    return redirect(url_for('index'))



@app.route('/criar_usuario', methods=['POST'])

def criar_usuario():

    if 'usuario' not in session or session.get('cargo') != 'Admin':

        return redirect(url_for('login'))

        

    username = request.form.get('novo_user')

    senha = request.form.get('nova_senha')

    cargo = request.form.get('novo_cargo')

    

    conn = conectar_banco()

    cursor = conn.cursor()

    try:

        cursor.execute("INSERT INTO usuarios (username, senha, cargo) VALUES (?, ?, ?)", (username, senha, cargo))

        conn.commit()

        flash(f'Novo utilizador {username} criado com sucesso!', 'success')

    except:

        flash('Erro: Nome de utilizador já existe.', 'danger')

    conn.close()

    

    return redirect(url_for('index'))



@app.route('/gerar_relatorio_pdf')

def gerar_relatorio_pdf():

    if 'usuario' not in session:

        return redirect(url_for('login'))

        

    buffer = io.BytesIO()

    p = canvas.Canvas(buffer, pagesize=letter)

    p.drawString(100, 750, "GETSEMANI SYSTEM - PRESTAÇÃO DE CONTAS")

    p.drawString(100, 730, f"Emitido por: Admin Geral (brayan.sistemy)")

    p.drawString(100, 710, f"Data do Relatório: {datetime.now().strftime('%d/%m/%Y')}")

    

    conn = conectar_banco()

    cursor = conn.cursor()

    mes_atual = datetime.now().strftime('%m/%Y')

    

    cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'Entrada' AND mes_ano = %s", (mes_atual,))

    entradas = cursor.fetchone()[0] or 0.0

    

    cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'Saida' AND mes_ano = %s", (mes_atual,))

    saidas = cursor.fetchone()[0] or 0.0

    

    sobra = entradas - saidas

    

    p.drawString(100, 660, f"Mes de Referencia: {mes_atual}")

    p.drawString(100, 640, f"Total de Entradas (Receitas): R$ {entradas:.2f}")

    p.drawString(100, 620, f"Total de Saidas (Despesas): R$ {saidas:.2f}")

    p.drawString(100, 600, f"Saldo Líquido Restante (Sobras): R$ {sobra:.2f}")

    

    p.drawString(100, 540, "Sistema desenvolvido por brayan.system - Todos os direitos reservados.")

    p.showPage()

    p.save()

    

    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name=f"prestacao_contas_{mes_atual.replace('/', '-')}.pdf", mimetype='application/pdf')


@app.route('/excluir/<int:id>', methods=['POST'])
def excluir(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transacoes WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    
    flash('Registo excluído com sucesso!', 'success')
    return redirect(url_for('index'))
    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5000, debug=True)
   

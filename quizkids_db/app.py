import json
import os
import sqlite3
import time
from collections import defaultdict
from datetime import date
from functools import wraps
import random

from flask import (Flask, flash, g, redirect, render_template, request,
                   session, url_for)

app = Flask(__name__,
            static_folder='static',
            template_folder='templates')

app.secret_key = 'sua-chave-secreta-super-segura'
DATABASE = 'quizkids.db'

# --- FUNÇÕES DE CONEXÃO COM O BANCO DE DADOS ---

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# --- FUNÇÕES AUXILIARES ---

def calculate_age(birthdate_str):
    if not birthdate_str: return None
    try:
        today = date.today()
        birthdate = date.fromisoformat(birthdate_str)
        return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
    except (ValueError, TypeError):
        return None

# --- DECORATORS ---

def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                flash('Você precisa estar logado para acessar esta página.', 'danger')
                return redirect(url_for('login'))
            if role and session['user'].get('type') != role:
                flash('Você não tem permissão para acessar esta página.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or not session['user'].get('is_admin', False):
            flash('Acesso restrito a administradores.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROTAS PRINCIPAIS ---

@app.route('/')
def index():
    if 'user' in session:
        user_type = session['user'].get('type')
        if user_type == 'aluno': return redirect(url_for('portal_aluno'))
        elif user_type == 'professor': return redirect(url_for('painel_admin')) if session['user'].get('is_admin') else redirect(url_for('portal_professor'))

    fun_facts = [
        "Um polvo tem três corações.", "O mel nunca estraga.", "As girafas não têm cordas vocais.",
        "A Torre Eiffel pode ser 15 cm mais alta durante o verão.", "O primeiro telemóvel pesava mais de 1 quilo."
    ]
    fun_fact = random.choice(fun_facts)
    return render_template('index.html', fun_fact=fun_fact)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        db = get_db()
        reg_type = request.form.get('reg_type')

        def clean_cpf(cpf_string): return "".join(filter(str.isdigit, cpf_string))
        
        if reg_type == 'professor':
            cpf = clean_cpf(request.form.get('prof_cpf'))
            email = request.form.get('prof_email')
            if db.execute('SELECT id FROM users WHERE cpf = ? OR email = ?', (cpf, email)).fetchone():
                flash('CPF ou e-mail já cadastrado.', 'danger'); return redirect(url_for('register'))
            
            db.execute('INSERT INTO users (type, nome, cpf, email, escola, senha, status, is_admin) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', ('professor', request.form.get('prof_nome'), cpf, email, request.form.get('prof_escola'), request.form.get('prof_senha'), 'pendente', 0))
            db.commit()
            flash('Cadastro de professor realizado! Aguarde a aprovação do administrador.', 'success')
            return redirect(url_for('login'))

        elif reg_type == 'aluno':
            aluno_cpf = clean_cpf(request.form.get('aluno_cpf'))
            resp_cpf = clean_cpf(request.form.get('resp_cpf'))
            resp_email = request.form.get('resp_email')

            if aluno_cpf == resp_cpf: flash('CPF do aluno e do responsável não podem ser iguais.', 'danger'); return redirect(url_for('register'))
            if db.execute('SELECT id FROM users WHERE cpf IN (?, ?)', (aluno_cpf, resp_cpf)).fetchone():
                flash('Um dos CPFs informados já está em uso.', 'danger'); return redirect(url_for('register'))
            if db.execute('SELECT id FROM users WHERE email = ?', (resp_email,)).fetchone():
                flash('O e-mail do responsável já está em uso.', 'danger'); return redirect(url_for('register'))

            db.execute('''
                INSERT INTO users (type, nome, cpf, nascimento, escola, matricula, senha, pontuacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('aluno', request.form.get('aluno_nome'), aluno_cpf, request.form.get('aluno_nascimento'), request.form.get('aluno_escola'), request.form.get('aluno_matricula'), request.form.get('aluno_senha'), 0))
            db.commit()
            flash('Cadastro de aluno realizado com sucesso!', 'success')
            return redirect(url_for('login'))
            
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier_masked = request.form.get('identifier')
        password = request.form.get('password')
        identifier = "".join(filter(str.isdigit, identifier_masked))

        db = get_db()
        user_found = db.execute('SELECT * FROM users WHERE cpf = ? AND senha = ?', (identifier, password)).fetchone()

        if user_found:
            if user_found['type'] == 'professor' and user_found['status'] != 'aprovado':
                flash('Seu cadastro de professor ainda está pendente.', 'warning')
                return redirect(url_for('login'))
            
            session['user'] = dict(user_found)
            flash(f"Bem-vindo(a) de volta, {user_found['nome']}!", 'info')
            if user_found['type'] == 'aluno':
                return redirect(url_for('portal_aluno'))
            else:
                return redirect(url_for('painel_admin')) if user_found['is_admin'] else redirect(url_for('portal_professor'))

        flash('CPF ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('index'))

# --- ROTAS DO ALUNO ---

@app.route('/portal_aluno')
@login_required(role='aluno')
def portal_aluno():
    db = get_db()
    
    all_quizzes = db.execute('SELECT id, categoria FROM quizzes').fetchall()
    student_results = db.execute('SELECT quiz_id, quiz_categoria FROM results WHERE student_cpf = ?', (session['user']['cpf'],)).fetchall()
    
    progress_by_category = defaultdict(lambda: {'completed': 0, 'total': 0})
    for quiz in all_quizzes:
        progress_by_category[quiz['categoria']]['total'] += 1
    
    for result in student_results:
        progress_by_category[result['quiz_categoria']]['completed'] += 1
        
    progress_percentages = {}
    for cat, data in progress_by_category.items():
        if data['total'] > 0:
            progress_percentages[cat] = round((data['completed'] / data['total']) * 100)
        else:
            progress_percentages[cat] = 0

    return render_template('portal_aluno.html', progress=progress_percentages)

@app.route('/select_subject')
@login_required(role='aluno')
def select_subject():
    db = get_db()
    categories = db.execute('SELECT DISTINCT categoria FROM quizzes ORDER BY categoria').fetchall()
    return render_template('select_subject.html', categories=categories)

@app.route('/quizzes/<category>')
@login_required(role='aluno')
def quiz_list(category):
    db = get_db()
    
    if category == 'random':
        # CORREÇÃO: Garante que só seleciona quizzes que têm perguntas.
        all_quizzes = db.execute('SELECT * FROM quizzes WHERE id IN (SELECT DISTINCT quiz_id FROM perguntas)').fetchall()
        if all_quizzes:
            random_quiz = random.choice(all_quizzes)
            return redirect(url_for('quiz', quiz_id=random_quiz['id']))
        else:
            flash('Nenhum quiz disponível para o modo aleatório.', 'warning')
            return redirect(url_for('portal_aluno'))
            
    quizzes = db.execute('SELECT * FROM quizzes WHERE categoria = ?', (category,)).fetchall()
    results = db.execute('SELECT quiz_id FROM results WHERE student_cpf = ?', (session['user']['cpf'],)).fetchall()
    completed_quizzes_ids = {res['quiz_id'] for res in results}
    
    return render_template('quiz_list.html', quizzes=quizzes, category=category, completed_quizzes=completed_quizzes_ids)

@app.route('/quiz/<int:quiz_id>')
@login_required(role='aluno')
def quiz(quiz_id):
    db = get_db()
    quiz = db.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    if not quiz:
        flash('Quiz não encontrado.', 'danger')
        return redirect(url_for('portal_aluno'))
    
    perguntas_db = db.execute('SELECT * FROM perguntas WHERE quiz_id = ? ORDER BY id', (quiz_id,)).fetchall()
    
    # CORREÇÃO: Verifica se o quiz tem perguntas antes de o iniciar.
    if not perguntas_db:
        flash('Este quiz ainda não tem perguntas. Por favor, escolha outro.', 'warning')
        return redirect(url_for('select_subject'))

    perguntas = []
    for p in perguntas_db:
        p_dict = dict(p)
        p_dict['opcoes'] = json.loads(p['opcoes'])
        perguntas.append(p_dict)
        
    return render_template('quiz.html', quiz=quiz, perguntas=perguntas)

@app.route('/submit_quiz/<int:quiz_id>', methods=['POST'])
@login_required(role='aluno')
def submit_quiz(quiz_id):
    db = get_db()
    current_quiz = db.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    perguntas = db.execute('SELECT * FROM perguntas WHERE quiz_id = ?', (quiz_id,)).fetchall()
    user_cpf = session['user']['cpf']
    
    score = 0
    review_data = []
    total_score = len(perguntas) * 10
    
    for pergunta in perguntas:
        user_answer = request.form.get(f'pergunta_{pergunta["id"]}')
        is_correct = (str(user_answer).strip() == str(pergunta['resposta_correta']).strip())
        if is_correct:
            score += 10
        
        review_data.append({
            "texto": pergunta['texto'],
            "opcoes": json.loads(pergunta['opcoes']),
            "sua_resposta": user_answer,
            "resposta_correta": pergunta['resposta_correta'],
            "acertou": is_correct
        })
            
    # CORREÇÃO: A ordem de score e total_score estava trocada.
    db.execute('INSERT INTO results (student_cpf, quiz_id, quiz_tema, quiz_categoria, score, total_score, date) VALUES (?, ?, ?, ?, ?, ?, ?)',
               (user_cpf, quiz_id, current_quiz['tema'], current_quiz['categoria'], score, total_score, time.strftime("%Y-%m-%d %H:%M:%S")))
    db.execute('UPDATE users SET pontuacao = pontuacao + ? WHERE cpf = ?', (score, user_cpf))
    db.commit()
    
    session['last_score'] = score
    session['total_score'] = total_score
    session['review_data'] = review_data
    return redirect(url_for('resultado'))

@app.route('/resultado')
@login_required(role='aluno')
def resultado():
    score = session.get('last_score', 0)
    total_score = session.get('total_score', 0)
    review_data = session.get('review_data', [])
    return render_template('resultado.html', score=score, total_score=total_score, review_data=review_data)

@app.route('/ranking')
def ranking():
    db = get_db()
    ranking_list = db.execute("SELECT nome, pontuacao FROM users WHERE type = 'aluno' ORDER BY pontuacao DESC LIMIT 10").fetchall()
    return render_template('ranking.html', ranking=ranking_list)

# --- ROTAS DO PROFESSOR E ADMIN ---

@app.route('/portal_professor')
@login_required(role='professor')
def portal_professor():
    db = get_db()
    my_quizzes = db.execute('SELECT * FROM quizzes WHERE professor_cpf = ?', (session['user']['cpf'],)).fetchall()
    students_list = db.execute("SELECT * FROM users WHERE type = 'aluno'").fetchall()
    return render_template('portal_professor.html', quizzes=my_quizzes, students=students_list)

@app.route('/relatorio_aluno/<aluno_cpf>')
@login_required(role='professor')
def relatorio_aluno(aluno_cpf):
    db = get_db()
    student = db.execute('SELECT * FROM users WHERE cpf = ? AND type = "aluno"', (aluno_cpf,)).fetchone()
    if not student: return "Aluno não encontrado", 404
    
    student_results = db.execute('SELECT * FROM results WHERE student_cpf = ?', (aluno_cpf,)).fetchall()

    stats = {"total_quizzes": len(student_results), "total_score": student['pontuacao'], "geral_avg": 0, "category_performance": {}, "area_foco": "N/A"}
    if student_results:
        total_percent = sum((r['score'] / r['total_score']) * 100 for r in student_results if r['total_score'] > 0)
        stats['geral_avg'] = round(total_percent / len(student_results), 2) if student_results else 0
        
        category_scores = defaultdict(lambda: {'total': 0, 'count': 0})
        for res in student_results:
            cat = res['quiz_categoria']
            if res['total_score'] > 0:
                category_scores[cat]['total'] += (res['score'] / res['total_score']) * 100
                category_scores[cat]['count'] += 1
            
        category_avg = {cat: round(data['total'] / data['count'], 2) for cat, data in category_scores.items()}
        stats['category_performance'] = dict(sorted(category_avg.items()))
        if category_avg: stats['area_foco'] = min(category_avg, key=category_avg.get)

    return render_template('relatorio_aluno.html', student=student, stats=stats)


@app.route('/criar_quiz', methods=['GET', 'POST'])
@login_required(role='professor')
def criar_quiz():
    if request.method == 'POST':
        db = get_db()
        
        idade_min_str = request.form.get('idade_min', '0'); idade_max_str = request.form.get('idade_max', '0')
        idade_min = int(idade_min_str) if idade_min_str.isdigit() else 0
        idade_max = int(idade_max_str) if idade_max_str.isdigit() else 99

        cursor = db.execute('INSERT INTO quizzes (tema, dificuldade, categoria, professor_cpf, idade_min, idade_max) VALUES (?, ?, ?, ?, ?, ?)',
                            (request.form.get('tema'), request.form.get('dificuldade'), request.form.get('categoria', 'geral'), session['user']['cpf'], idade_min, idade_max))
        new_quiz_id = cursor.lastrowid
        
        for i in range(1, 6):
            texto_pergunta = request.form.get(f'pergunta{i}')
            if texto_pergunta:
                opcoes = [request.form.get(f'pergunta{i}_alt_a'), request.form.get(f'pergunta{i}_alt_b'), request.form.get(f'pergunta{i}_alt_c'), request.form.get(f'pergunta{i}_alt_d')]
                db.execute('INSERT INTO perguntas (quiz_id, texto, opcoes, resposta_correta) VALUES (?, ?, ?, ?)',
                           (new_quiz_id, texto_pergunta, json.dumps(opcoes), request.form.get(f'pergunta{i}_correta')))
        db.commit()
        flash('Quiz criado com sucesso!', 'success')
        return redirect(url_for('portal_professor'))
    return render_template('criar_quiz.html')

@app.route('/delete_quiz/<int:quiz_id>', methods=['POST'])
@login_required(role='professor')
def delete_quiz(quiz_id):
    db = get_db()
    quiz = db.execute('SELECT professor_cpf FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    if not quiz: flash('Quiz não encontrado.', 'danger'); return redirect(url_for('portal_professor'))
    if quiz['professor_cpf'] != session['user']['cpf'] and not session['user'].get('is_admin'):
        flash('Você não tem permissão para remover este quiz.', 'danger')
        return redirect(url_for('portal_professor'))

    db.execute('DELETE FROM perguntas WHERE quiz_id = ?', (quiz_id,))
    db.execute('DELETE FROM results WHERE quiz_id = ?', (quiz_id,))
    db.execute('DELETE FROM quizzes WHERE id = ?', (quiz_id,))
    db.commit()
    flash('Quiz removido com sucesso!', 'success')
    return redirect(url_for('portal_professor'))

@app.route('/admin')
@admin_required
def painel_admin():
    db = get_db()
    professors = db.execute("SELECT * FROM users WHERE type = 'professor'").fetchall()
    students = db.execute("SELECT * FROM users WHERE type = 'aluno'").fetchall()
    pending_professors = [p for p in professors if p['status'] == 'pendente']
    return render_template('painel_admin.html', pending_professors=pending_professors, all_professors=professors, all_students=students)

@app.route('/approve_professor/<cpf>', methods=['POST'])
@admin_required
def approve_professor(cpf):
    db = get_db()
    db.execute("UPDATE users SET status = 'aprovado' WHERE cpf = ?", (cpf,))
    db.commit()
    flash('Professor aprovado com sucesso!', 'success')
    return redirect(url_for('painel_admin'))

@app.route('/delete_professor/<cpf>', methods=['POST'])
@admin_required
def delete_professor(cpf):
    db = get_db()
    user = db.execute("SELECT is_admin FROM users WHERE cpf = ?", (cpf,)).fetchone()
    if user['is_admin']: flash('Não é possível remover a conta de administrador.', 'danger')
    else:
        db.execute("DELETE FROM users WHERE cpf = ?", (cpf,))
        db.commit()
        flash('Professor removido com sucesso.', 'success')
    return redirect(url_for('painel_admin'))

@app.route('/delete_student/<cpf>', methods=['POST'])
@admin_required
def delete_student(cpf):
    db = get_db()
    db.execute("DELETE FROM users WHERE cpf = ?", (cpf,))
    db.execute("DELETE FROM results WHERE student_cpf = ?", (cpf,))
    db.commit()
    flash('Aluno removido com sucesso.', 'success')
    return redirect(url_for('painel_admin'))

if __name__ == '__main__':
    if not os.path.exists('quizkids.db'):
        import init_db
        init_db.main()
    app.run(debug=True)
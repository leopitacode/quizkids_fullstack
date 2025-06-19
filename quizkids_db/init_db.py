import sqlite3
import json

def main():
    connection = sqlite3.connect('quizkids.db')

    with open('schema.sql') as f:
        connection.executescript(f.read())

    cursor = connection.cursor()

    # Inserir usuário Admin
    cursor.execute("INSERT INTO users (type, nome, cpf, email, escola, senha, status, is_admin) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ('professor', 'Admin', '00000000000', 'admin@quizkids.com', 'Escola Administradora', 'admin', 'aprovado', 1)
    )

    # Carregar quizzes do JSON e inserir no banco
    with open('data/quizzes.json', 'r', encoding='utf-8') as f:
        quizzes = json.load(f)

    for quiz in quizzes:
        cursor.execute("INSERT INTO quizzes (id, tema, dificuldade, categoria, professor_cpf, idade_min, idade_max) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (quiz['id'], quiz['tema'], quiz['dificuldade'], quiz['categoria'], quiz['professor_cpf'], quiz['idade_recomendada'][0], quiz['idade_recomendada'][1]))
        
        for p in quiz['perguntas']:
            cursor.execute("INSERT INTO perguntas (id, quiz_id, texto, opcoes, resposta_correta) VALUES (?, ?, ?, ?, ?)",
                        (p['id'], quiz['id'], p['texto'], json.dumps(p['opcoes']), p['correta']))


    connection.commit()
    connection.close()
    print("Banco de dados 'quizkids.db' criado e populado com sucesso.")

if __name__ == "__main__":
    main()
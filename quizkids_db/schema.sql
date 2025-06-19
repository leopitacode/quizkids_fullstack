DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS quizzes;
DROP TABLE IF EXISTS perguntas;
DROP TABLE IF EXISTS results;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('aluno', 'professor')),
    nome TEXT NOT NULL,
    cpf TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    escola TEXT,
    senha TEXT NOT NULL,
    status TEXT, -- para professores: pendente, aprovado
    is_admin INTEGER DEFAULT 0, -- 0 para não, 1 para sim
    -- Campos específicos do aluno
    nascimento TEXT,
    matricula TEXT,
    pontuacao INTEGER DEFAULT 0,
    -- Campos do responsável
    resp_nome TEXT,
    resp_cpf TEXT,
    resp_email TEXT,
    resp_telefone TEXT
);

CREATE TABLE quizzes (
    id INTEGER PRIMARY KEY,
    tema TEXT NOT NULL,
    dificuldade TEXT NOT NULL,
    categoria TEXT NOT NULL,
    professor_cpf TEXT NOT NULL,
    idade_min INTEGER,
    idade_max INTEGER
);

CREATE TABLE perguntas (
    id INTEGER PRIMARY KEY,
    quiz_id INTEGER NOT NULL,
    texto TEXT NOT NULL,
    opcoes TEXT NOT NULL, -- Armazenado como JSON string
    resposta_correta TEXT NOT NULL,
    FOREIGN KEY (quiz_id) REFERENCES quizzes (id)
);

CREATE TABLE results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_cpf TEXT NOT NULL,
    quiz_id INTEGER NOT NULL,
    quiz_tema TEXT,
    quiz_categoria TEXT,
    score INTEGER NOT NULL,
    total_score INTEGER NOT NULL,
    date TEXT NOT NULL
);
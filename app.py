from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from secretaria_manager import SecretariaManager
import psycopg2
import psycopg2.extras
import os
import uuid
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from functools import wraps
import uuid
from werkzeug.utils import secure_filename
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chave-secreta-troque-em-producao')

DB_CONFIG = {
    'host':     os.environ.get('DB_HOST', 'localhost'),
    'port':     os.environ.get('DB_PORT', '5432'),
    'database': os.environ.get('DB_NAME', 'newsdb'),
    'user':     os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', 'postgres'),
}

ADMIN_USER  = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS  = os.environ.get('ADMIN_PASS', 'admin123')

SMTP_HOST   = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT   = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER   = os.environ.get('SMTP_USER', '')
SMTP_PASS   = os.environ.get('SMTP_PASS', '')
SMTP_FROM   = os.environ.get('SMTP_FROM', SMTP_USER)

# ── Upload ────────────────────────────────────────────────────────────────────
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_IMAGES = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
ALLOWED_DOCS   = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods', 'zip', 'txt'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _ext(filename):
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


def salvar_arquivo(file_obj, allowed_exts):
    if not file_obj or not file_obj.filename:
        return None
    ext = _ext(file_obj.filename)
    if ext not in allowed_exts:
        return None
    nome = f"{uuid.uuid4().hex}.{ext}"
    file_obj.save(os.path.join(UPLOAD_FOLDER, nome))
    return f"/static/uploads/{nome}"


# ── SecretariaManager ────────────────────────────────────────────────────────
_sec_mgr: SecretariaManager | None = None

def get_sec_mgr() -> SecretariaManager:
    global _sec_mgr
    if _sec_mgr is None:
        _sec_mgr = SecretariaManager(DB_CONFIG)
    return _sec_mgr

SECRETARIAS = [
    'Gestão', 'Administração', 'Educação', 'Saúde', 'Obras', 'Finanças',
    'Meio Ambiente', 'Cultura', 'Esportes', 'Assistência Social', 'Planejamento',
]

STATUS_PROJETO = ['Planejamento', 'Em andamento', 'Concluído', 'Suspenso', 'Cancelado']


def get_db():
    return psycopg2.connect(**DB_CONFIG)


def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            # Notícias
            cur.execute("""
                CREATE TABLE IF NOT EXISTS noticias (
                    id               SERIAL PRIMARY KEY,
                    titulo           VARCHAR(255) NOT NULL,
                    subtitulo        VARCHAR(500),
                    conteudo         TEXT NOT NULL,
                    categoria        VARCHAR(100) DEFAULT 'Geral',
                    autor            VARCHAR(100) DEFAULT 'Redação',
                    publicado        BOOLEAN DEFAULT TRUE,
                    imagem_url       TEXT,
                    imagem_legenda   VARCHAR(500),
                    link_externo     TEXT,
                    link_label       VARCHAR(100),
                    documento_url    TEXT,
                    documento_nome   VARCHAR(200),
                    criado_em        TIMESTAMP DEFAULT NOW(),
                    atualizado_em    TIMESTAMP DEFAULT NOW()
                );
            """)
            for col_sql in [
                "ALTER TABLE noticias ADD COLUMN IF NOT EXISTS imagem_url      TEXT",
                "ALTER TABLE noticias ADD COLUMN IF NOT EXISTS imagem_legenda  VARCHAR(500)",
                "ALTER TABLE noticias ADD COLUMN IF NOT EXISTS link_externo    TEXT",
                "ALTER TABLE noticias ADD COLUMN IF NOT EXISTS link_label      VARCHAR(100)",
                "ALTER TABLE noticias ADD COLUMN IF NOT EXISTS documento_url   TEXT",
                "ALTER TABLE noticias ADD COLUMN IF NOT EXISTS documento_nome  VARCHAR(200)",
            ]:
                cur.execute(col_sql)
            # Eventos
            cur.execute("""
                CREATE TABLE IF NOT EXISTS eventos (
                    id          SERIAL PRIMARY KEY,
                    titulo      VARCHAR(255) NOT NULL,
                    descricao   TEXT,
                    local       VARCHAR(255),
                    cor         VARCHAR(20) DEFAULT '#4f5de8',
                    data_inicio DATE NOT NULL,
                    data_fim    DATE,
                    hora_inicio TIME,
                    hora_fim    TIME,
                    publicado   BOOLEAN DEFAULT TRUE,
                    url         TEXT,
                    url_label   VARCHAR(100),
                    secretaria  VARCHAR(100),
                    criado_em   TIMESTAMP DEFAULT NOW()
                );
            """)
            for col_sql in [
                "ALTER TABLE eventos ADD COLUMN IF NOT EXISTS url        TEXT",
                "ALTER TABLE eventos ADD COLUMN IF NOT EXISTS url_label  VARCHAR(100)",
                "ALTER TABLE eventos ADD COLUMN IF NOT EXISTS secretaria VARCHAR(100)",
            ]:
                cur.execute(col_sql)
            # Membros
            cur.execute("""
                CREATE TABLE IF NOT EXISTS membros (
                    id         SERIAL PRIMARY KEY,
                    nome       VARCHAR(255) NOT NULL,
                    email      VARCHAR(255) NOT NULL UNIQUE,
                    secretaria VARCHAR(100) NOT NULL,
                    cargo      VARCHAR(150),
                    ativo      BOOLEAN DEFAULT TRUE,
                    criado_em  TIMESTAMP DEFAULT NOW()
                );
            """)
            # Projetos
            cur.execute("""
                CREATE TABLE IF NOT EXISTS projetos (
                    id                        SERIAL PRIMARY KEY,
                    carimbo_data_hora        TIMESTAMP,
                    email                     VARCHAR(255),
                    nome_completo             VARCHAR(255),
                    cargo                     VARCHAR(150),
                    eixo                      VARCHAR(100),
                    secretaria               VARCHAR(100) NOT NULL,
                    publico_que_pretende_atingir TEXT,
                    faixa_etaria              VARCHAR(100),
                    genero                   VARCHAR(50),
                    publico                   VARCHAR(100),
                    nome_projeto             VARCHAR(255) NOT NULL,
                    data_inicio              DATE,
                    data_termino             DATE,
                    descricao_resumo         TEXT,
                    possui_prioritario       BOOLEAN DEFAULT FALSE,
                    publico_prioritario      TEXT,
                    estimativa_alcance        INTEGER,
                    regiao_administrativa    VARCHAR(100),
                    objetivos                TEXT,
                    grau_clareza_objetivos   INTEGER CHECK (grau_clareza_objetivos BETWEEN 1 AND 5),
                    metodologia              TEXT,
                    etapas                   TEXT,
                    cronograma_responsaveis  TEXT,
                    quantidade_pessoas       INTEGER,
                    frequencia_acompanhamento VARCHAR(100),
                    acompanhar_desenvolvimento TEXT,
                    documentos_links         TEXT,
                    nivel_maturidade         VARCHAR(50),
                    grau_eficacia_viabilidade INTEGER CHECK (grau_eficacia_viabilidade BETWEEN 1 AND 5),
                    status                   VARCHAR(50) DEFAULT 'Planejamento',
                    responsavel              VARCHAR(150),
                    orcamento               NUMERIC(15,2),
                    progresso               INTEGER DEFAULT 0,
                    criado_em               TIMESTAMP DEFAULT NOW(),
                    atualizado_em           TIMESTAMP DEFAULT NOW()
                );
            """)
            # Adicionar colunas adicionais para compatibilidade com o formato antigo
            for col_sql in [
                "ALTER TABLE projetos ADD COLUMN IF NOT EXISTS titulo          VARCHAR(255)",
                "ALTER TABLE projetos ADD COLUMN IF NOT EXISTS descricao        TEXT",
                "ALTER TABLE projetos ADD COLUMN IF NOT EXISTS data_inicio_old  DATE",
                "ALTER TABLE projetos ADD COLUMN IF NOT EXISTS data_fim_old     DATE",
            ]:
                cur.execute(col_sql)
            # Atualizações de projetos
            cur.execute("""
                CREATE TABLE IF NOT EXISTS projeto_updates (
                    id         SERIAL PRIMARY KEY,
                    projeto_id INTEGER REFERENCES projetos(id) ON DELETE CASCADE,
                    texto      TEXT NOT NULL,
                    autor      VARCHAR(150) DEFAULT 'Admin',
                    criado_em  TIMESTAMP DEFAULT NOW()
                );
            """)
            # Log de e-mails enviados
            cur.execute("""
                CREATE TABLE IF NOT EXISTS email_log (
                    id           SERIAL PRIMARY KEY,
                    assunto      VARCHAR(255),
                    destinatarios TEXT,
                    secretaria   VARCHAR(100),
                    enviado_em   TIMESTAMP DEFAULT NOW(),
                    sucesso      BOOLEAN DEFAULT TRUE,
                    erro         TEXT
                );
            """)
            # ── Seed inicial ──────────────────────────────────────────
            cur.execute("SELECT COUNT(*) FROM noticias;")
            if cur.fetchone()[0] == 0:
                cur.execute("""
                    INSERT INTO noticias (titulo, subtitulo, conteudo, categoria, autor)
                    VALUES (
                        'Bem-vindo ao Nexo News',
                        'Portal oficial de comunicação governamental',
                        'Este é o portal de notícias do Nexo News Governamental.\n\nAcesse o painel administrativo para publicar notícias, gerenciar projetos e enviar comunicados.',
                        'Institucional', 'Redação'
                    );
                """)
            cur.execute("SELECT COUNT(*) FROM membros;")
            if cur.fetchone()[0] == 0:
                cur.executemany("""
                    INSERT INTO membros (nome, email, secretaria, cargo, ativo)
                    VALUES (%s,%s,%s,%s,%s);
                """, [
                    ('Ana Paula Rocha',    'ana.rocha@gestao.gov.br',    'Gestão', 'Secretária de Gestão', True),
                    ('Carlos Mendes',      'carlos.mendes@gestao.gov.br', 'Gestão', 'Coordenador de TI',    True),
                    ('Beatriz Souza',      'beatriz.souza@gestao.gov.br', 'Gestão', 'Analista de Projetos', True),
                    ('Rafael Oliveira',    'rafael.oliveira@gestao.gov.br','Gestão', 'Assistente Administrativo', True),
                ])
            cur.execute("SELECT COUNT(*) FROM projetos;")
            if cur.fetchone()[0] == 0:
                cur.executemany("""
                    INSERT INTO projetos (titulo, descricao, secretaria, status, responsavel, orcamento, data_inicio, data_fim, progresso)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s);
                """, [
                    ('Modernização do Sistema de RH',
                     'Implantação de novo sistema integrado de gestão de recursos humanos, incluindo módulos de folha de pagamento, ponto eletrônico e avaliação de desempenho.',
                     'Gestão','Em andamento','Carlos Mendes',250000,'2025-01-10','2025-08-31',62),
                    ('Portal de Transparência',
                     'Desenvolvimento e publicação do novo portal de transparência com dados abertos, contratos, licitações e despesas em tempo real.',
                     'Gestão','Em andamento','Beatriz Souza',80000,'2025-02-01','2025-06-30',78),
                    ('Capacitação de Servidores 2025',
                     'Programa anual de treinamento e qualificação dos servidores públicos municipais, com cursos presenciais e EAD.',
                     'Gestão','Planejamento','Ana Paula Rocha',45000,'2025-05-01','2025-12-15',10),
                    ('Digitalização de Documentos',
                     'Digitalização e indexação do acervo documental da secretaria, abrangendo 12 anos de registros físicos.',
                     'Gestão','Concluído','Rafael Oliveira',32000,'2024-06-01','2025-01-31',100),
                ])
        conn.commit()


@app.context_processor
def inject_globals():
    categorias = []
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT categoria FROM noticias WHERE publicado=TRUE ORDER BY categoria;")
                categorias = [r[0] for r in cur.fetchall()]
    except Exception:
        pass
    return {
        'now': datetime.now(),
        'categorias': categorias,
        'categoria_ativa': request.args.get('categoria', ''),
        'busca': request.args.get('q', ''),
    }


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


def enviar_email(destinatarios, assunto, html, secretaria=''):
    """Envia e-mail via SMTP. Retorna (sucesso, erro)."""
    if not SMTP_USER or not SMTP_PASS:
        return False, 'SMTP não configurado (defina SMTP_USER e SMTP_PASS)'
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = assunto
        msg['From']    = SMTP_FROM
        msg['To']      = ', '.join(destinatarios)
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(SMTP_USER, SMTP_PASS)
            srv.sendmail(SMTP_FROM, destinatarios, msg.as_string())

        # Log
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO email_log (assunto,destinatarios,secretaria,sucesso) VALUES (%s,%s,%s,TRUE);",
                    (assunto, ', '.join(destinatarios), secretaria))
            conn.commit()
        return True, None
    except Exception as e:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO email_log (assunto,destinatarios,secretaria,sucesso,erro) VALUES (%s,%s,%s,FALSE,%s);",
                    (assunto, ', '.join(destinatarios), secretaria, str(e)))
            conn.commit()
        return False, str(e)


# ══════════════════════════════════════════════════════════════════════════════
# PÚBLICAS — NOTÍCIAS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    # Redireciona para a home page
    return redirect(url_for('home'))

@app.route('/home')
def home():
    # Retorna a página home personalizada
    return render_template('home.html')

@app.route('/sobre')
def sobre():
    # Retorna a página sobre
    return render_template('sobre.html')

@app.route('/noticias')
def noticias():
    """Rota para listar notícias (antiga rota principal)"""
    categoria = request.args.get('categoria', '')
    busca     = request.args.get('q', '')
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            query  = "SELECT * FROM noticias WHERE publicado=TRUE"
            params = []
            if categoria:
                query += " AND categoria=%s"; params.append(categoria)
            if busca:
                query += " AND (titulo ILIKE %s OR conteudo ILIKE %s)"; params += [f'%{busca}%']*2
            query += " ORDER BY criado_em DESC;"
            cur.execute(query, params)
            noticias = cur.fetchall()
    return render_template('index.html', noticias=noticias)


@app.route('/noticia/<int:id>')
def noticia(id):
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM noticias WHERE id=%s AND publicado=TRUE;", (id,))
            noticia = cur.fetchone()
            if not noticia:
                return render_template('404.html'), 404
            cur.execute("SELECT id,titulo,imagem_url,criado_em FROM noticias WHERE publicado=TRUE AND id<>%s AND categoria=%s ORDER BY criado_em DESC LIMIT 3;",
                        (id, noticia['categoria']))
            relacionadas = cur.fetchall()
    return render_template('noticia.html', noticia=noticia, relacionadas=relacionadas)


# ══════════════════════════════════════════════════════════════════════════════
# PÚBLICAS — CALENDÁRIO
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/calendario')
def calendario():
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM eventos WHERE publicado=TRUE ORDER BY data_inicio ASC;")
            eventos = cur.fetchall()
    eventos_json = [{
        'id': e['id'], 'title': e['titulo'],
        'start': e['data_inicio'].isoformat(),
        'end': e['data_fim'].isoformat() if e['data_fim'] else e['data_inicio'].isoformat(),
        'color': e['cor'],
        'extendedProps': {
            'descricao':   e['descricao'] or '',
            'local':       e['local'] or '',
            'secretaria':  e['secretaria'] or '',
            'url':         e['url'] or '',
            'url_label':   e['url_label'] or 'Ver mais',
            'hora_inicio': e['hora_inicio'].strftime('%H:%M') if e['hora_inicio'] else '',
            'hora_fim':    e['hora_fim'].strftime('%H:%M')    if e['hora_fim']    else '',
        }
    } for e in eventos]
    return render_template('calendario.html', eventos_json=eventos_json)


# ══════════════════════════════════════════════════════════════════════════════
# PÚBLICAS — PROJETOS POR SECRETARIA
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/secretarias')
def secretarias():
    mgr = get_sec_mgr()
    resumo = mgr.listar_com_resumo()
    return render_template('secretarias.html', resumo=resumo)


@app.route('/secretarias/<secretaria>')
def secretaria_detalhe(secretaria):
    # redireciona para visão geral
    return redirect(url_for('sec_visao_geral', secretaria=secretaria))


@app.route('/projetos/<int:id>')
def projeto_detalhe(id):
    mgr = get_sec_mgr()
    projeto = mgr.projeto_por_id(id)
    if not projeto:
        return render_template('404.html'), 404
    updates = mgr.projeto_updates(id)
    badge_class = mgr.badge_class
    progresso_cor = mgr.progresso_cor
    return render_template('projeto_detalhe.html', projeto=projeto,
                           updates=updates, badge_class=badge_class,
                           progresso_cor=progresso_cor)


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — AUTH
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        if request.form['usuario'] == ADMIN_USER and request.form['senha'] == ADMIN_PASS:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Usuário ou senha incorretos.', 'error')
    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('index'))


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin')
@login_required
def admin_dashboard():
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as n FROM noticias;")
            total_noticias = cur.fetchone()['n']
            cur.execute("SELECT COUNT(*) as n FROM noticias WHERE publicado=TRUE;")
            publicadas = cur.fetchone()['n']
            cur.execute("SELECT COUNT(*) as n FROM eventos;")
            total_eventos = cur.fetchone()['n']
            cur.execute("SELECT COUNT(*) as n FROM membros WHERE ativo=TRUE;")
            total_membros = cur.fetchone()['n']
            cur.execute("SELECT COUNT(*) as n FROM projetos;")
            total_projetos = cur.fetchone()['n']
            cur.execute("SELECT * FROM noticias ORDER BY criado_em DESC LIMIT 10;")
            noticias = cur.fetchall()
    return render_template('admin/dashboard.html',
                           noticias=noticias,
                           total=total_noticias, publicadas=publicadas,
                           total_eventos=total_eventos,
                           total_membros=total_membros,
                           total_projetos=total_projetos)


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — NOTÍCIAS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/noticias')
@login_required
def admin_noticias():
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM noticias ORDER BY criado_em DESC;")
            noticias = cur.fetchall()
    return render_template('admin/noticias.html', noticias=noticias)


@app.route('/admin/nova', methods=['GET', 'POST'])
@login_required
def admin_nova():
    if request.method == 'POST':
        titulo         = request.form['titulo'].strip()
        subtitulo      = request.form.get('subtitulo', '').strip()
        conteudo       = request.form['conteudo'].strip()
        categoria      = request.form.get('categoria', 'Geral').strip()
        autor          = request.form.get('autor', 'Redação').strip()
        publicado      = 'publicado' in request.form
        imagem_legenda = request.form.get('imagem_legenda', '').strip() or None
        link_externo   = request.form.get('link_externo', '').strip() or None
        link_label     = request.form.get('link_label', '').strip() or None
        imagem_url     = salvar_arquivo(request.files.get('imagem'), ALLOWED_IMAGES)
        doc_file       = request.files.get('documento')
        documento_url  = salvar_arquivo(doc_file, ALLOWED_DOCS)
        documento_nome = secure_filename(doc_file.filename) if doc_file and doc_file.filename else None
        if not titulo or not conteudo:
            flash('Título e conteúdo são obrigatórios.', 'error')
        else:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""INSERT INTO noticias
                        (titulo,subtitulo,conteudo,categoria,autor,publicado,
                         imagem_url,imagem_legenda,link_externo,link_label,documento_url,documento_nome)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);""",
                        (titulo,subtitulo,conteudo,categoria,autor,publicado,
                         imagem_url,imagem_legenda,link_externo,link_label,documento_url,documento_nome))
                conn.commit()
            flash('Notícia publicada!', 'success')
            return redirect(url_for('admin_noticias'))
    return render_template('admin/form.html', noticia=None, secretarias=get_secretarias_lista())


@app.route('/admin/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_editar(id):
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM noticias WHERE id=%s;", (id,))
            noticia = cur.fetchone()
    if not noticia:
        flash('Notícia não encontrada.', 'error')
        return redirect(url_for('admin_noticias'))
    if request.method == 'POST':
        titulo         = request.form['titulo'].strip()
        subtitulo      = request.form.get('subtitulo', '').strip()
        conteudo       = request.form['conteudo'].strip()
        categoria      = request.form.get('categoria', 'Geral').strip()
        autor          = request.form.get('autor', 'Redação').strip()
        publicado      = 'publicado' in request.form
        imagem_legenda = request.form.get('imagem_legenda', '').strip() or None
        link_externo   = request.form.get('link_externo', '').strip() or None
        link_label     = request.form.get('link_label', '').strip() or None
        nova_img = salvar_arquivo(request.files.get('imagem'), ALLOWED_IMAGES)
        if nova_img:
            imagem_url = nova_img
        elif 'remover_imagem' in request.form:
            imagem_url = None
        else:
            imagem_url = noticia['imagem_url']
        doc_file = request.files.get('documento')
        nova_doc = salvar_arquivo(doc_file, ALLOWED_DOCS)
        if nova_doc:
            documento_url  = nova_doc
            documento_nome = secure_filename(doc_file.filename)
        elif 'remover_documento' in request.form:
            documento_url  = None
            documento_nome = None
        else:
            documento_url  = noticia['documento_url']
            documento_nome = noticia['documento_nome']
        if not titulo or not conteudo:
            flash('Título e conteúdo são obrigatórios.', 'error')
        else:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""UPDATE noticias SET
                        titulo=%s,subtitulo=%s,conteudo=%s,categoria=%s,autor=%s,publicado=%s,
                        imagem_url=%s,imagem_legenda=%s,link_externo=%s,link_label=%s,
                        documento_url=%s,documento_nome=%s,atualizado_em=NOW()
                        WHERE id=%s;""",
                        (titulo,subtitulo,conteudo,categoria,autor,publicado,
                         imagem_url,imagem_legenda,link_externo,link_label,
                         documento_url,documento_nome,id))
                conn.commit()
            flash('Notícia atualizada!', 'success')
            return redirect(url_for('admin_noticias'))
    return render_template('admin/form.html', noticia=noticia, secretarias=get_secretarias_lista())


@app.route('/admin/excluir/<int:id>', methods=['POST'])
@login_required
def admin_excluir(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM noticias WHERE id=%s;", (id,))
        conn.commit()
    flash('Notícia excluída.', 'success')
    return redirect(url_for('admin_noticias'))


@app.route('/admin/toggle/<int:id>', methods=['POST'])
@login_required
def admin_toggle(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE noticias SET publicado = NOT publicado WHERE id=%s;", (id,))
        conn.commit()
    return redirect(url_for('admin_noticias'))


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — EVENTOS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/eventos')
@login_required
def admin_eventos():
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM eventos ORDER BY data_inicio DESC;")
            eventos = cur.fetchall()
    return render_template('admin/eventos.html', eventos=eventos)


@app.route('/admin/eventos/novo', methods=['GET', 'POST'])
@login_required
def admin_evento_novo():
    if request.method == 'POST':
        titulo=request.form['titulo'].strip(); descricao=request.form.get('descricao','').strip()
        local=request.form.get('local','').strip(); cor=request.form.get('cor','#c0392b')
        data_inicio=request.form['data_inicio']
        data_fim=request.form.get('data_fim') or None
        hora_inicio=request.form.get('hora_inicio') or None
        hora_fim=request.form.get('hora_fim') or None
        publicado='publicado' in request.form
        if not titulo or not data_inicio:
            flash('Título e data de início são obrigatórios.', 'error')
        url           = request.form.get('url', '').strip() or None
        url_label     = request.form.get('url_label', '').strip() or None
        secretaria_ev = request.form.get('secretaria', '').strip() or None
        if not titulo or not data_inicio:
            flash('Título e data de início são obrigatórios.', 'error')
        else:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""INSERT INTO eventos
                        (titulo,descricao,local,cor,data_inicio,data_fim,hora_inicio,hora_fim,
                         publicado,url,url_label,secretaria)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);""",
                        (titulo,descricao,local,cor,data_inicio,data_fim,hora_inicio,hora_fim,
                         publicado,url,url_label,secretaria_ev))
                conn.commit()
            flash('Evento criado!', 'success')
            return redirect(url_for('admin_eventos'))
    return render_template('admin/evento_form.html', evento=None, secretarias=get_secretarias_lista())


@app.route('/admin/eventos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_evento_editar(id):
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM eventos WHERE id=%s;", (id,))
            evento = cur.fetchone()
    if not evento:
        flash('Evento não encontrado.', 'error')
        return redirect(url_for('admin_eventos'))
    if request.method == 'POST':
        titulo=request.form['titulo'].strip(); descricao=request.form.get('descricao','').strip()
        local=request.form.get('local','').strip(); cor=request.form.get('cor','#c0392b')
        data_inicio=request.form['data_inicio']
        data_fim=request.form.get('data_fim') or None
        hora_inicio=request.form.get('hora_inicio') or None
        hora_fim=request.form.get('hora_fim') or None
        publicado='publicado' in request.form
        if not titulo or not data_inicio:
            flash('Título e data de início são obrigatórios.', 'error')
        url           = request.form.get('url', '').strip() or None
        url_label     = request.form.get('url_label', '').strip() or None
        secretaria_ev = request.form.get('secretaria', '').strip() or None
        if not titulo or not data_inicio:
            flash('Título e data de início são obrigatórios.', 'error')
        else:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""UPDATE eventos SET
                        titulo=%s,descricao=%s,local=%s,cor=%s,data_inicio=%s,data_fim=%s,
                        hora_inicio=%s,hora_fim=%s,publicado=%s,url=%s,url_label=%s,secretaria=%s
                        WHERE id=%s;""",
                        (titulo,descricao,local,cor,data_inicio,data_fim,hora_inicio,hora_fim,
                         publicado,url,url_label,secretaria_ev,id))
                conn.commit()
            flash('Evento atualizado!', 'success')
            return redirect(url_for('admin_eventos'))
    return render_template('admin/evento_form.html', evento=evento, secretarias=get_secretarias_lista())


@app.route('/admin/eventos/excluir/<int:id>', methods=['POST'])
@login_required
def admin_evento_excluir(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM eventos WHERE id=%s;", (id,))
        conn.commit()
    flash('Evento excluído.', 'success')
    return redirect(url_for('admin_eventos'))


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — MEMBROS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/membros')
@login_required
def admin_membros():
    secretaria = request.args.get('secretaria', '')
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if secretaria:
                cur.execute("SELECT * FROM membros WHERE secretaria=%s ORDER BY nome;", (secretaria,))
            else:
                cur.execute("SELECT * FROM membros ORDER BY secretaria, nome;")
            membros = cur.fetchall()
    return render_template('admin/membros.html', membros=membros,
                           secretarias=get_secretarias_lista(), secretaria_filtro=secretaria)


@app.route('/admin/membros/novo', methods=['GET', 'POST'])
@login_required
def admin_membro_novo():
    if request.method == 'POST':
        nome       = request.form['nome'].strip()
        email      = request.form['email'].strip().lower()
        secretaria = request.form['secretaria'].strip()
        cargo      = request.form.get('cargo', '').strip()
        ativo      = 'ativo' in request.form
        if not nome or not email or not secretaria:
            flash('Nome, e-mail e secretaria são obrigatórios.', 'error')
        else:
            try:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute("INSERT INTO membros (nome,email,secretaria,cargo,ativo) VALUES (%s,%s,%s,%s,%s);",
                                    (nome, email, secretaria, cargo, ativo))
                    conn.commit()
                flash('Membro cadastrado!', 'success')
                return redirect(url_for('admin_membros'))
            except psycopg2.errors.UniqueViolation:
                flash('E-mail já cadastrado.', 'error')
    return render_template('admin/membro_form.html', membro=None, secretarias=get_secretarias_lista())


@app.route('/admin/membros/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_membro_editar(id):
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM membros WHERE id=%s;", (id,))
            membro = cur.fetchone()
    if not membro:
        flash('Membro não encontrado.', 'error')
        return redirect(url_for('admin_membros'))
    if request.method == 'POST':
        nome       = request.form['nome'].strip()
        email      = request.form['email'].strip().lower()
        secretaria = request.form['secretaria'].strip()
        cargo      = request.form.get('cargo', '').strip()
        ativo      = 'ativo' in request.form
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE membros SET nome=%s,email=%s,secretaria=%s,cargo=%s,ativo=%s WHERE id=%s;",
                                (nome, email, secretaria, cargo, ativo, id))
                conn.commit()
            flash('Membro atualizado!', 'success')
            return redirect(url_for('admin_membros'))
        except psycopg2.errors.UniqueViolation:
            flash('E-mail já cadastrado por outro membro.', 'error')
    return render_template('admin/membro_form.html', membro=membro, secretarias=get_secretarias_lista())


@app.route('/admin/membros/excluir/<int:id>', methods=['POST'])
@login_required
def admin_membro_excluir(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM membros WHERE id=%s;", (id,))
        conn.commit()
    flash('Membro removido.', 'success')
    return redirect(url_for('admin_membros'))


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — E-MAIL
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/email', methods=['GET', 'POST'])
@login_required
def admin_email():
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM email_log ORDER BY enviado_em DESC LIMIT 30;")
            logs = cur.fetchall()
    secs_com_membros = get_secretarias_lista()

    if request.method == 'POST':
        assunto    = request.form['assunto'].strip()
        mensagem   = request.form['mensagem'].strip()
        secretaria = request.form.get('secretaria', '')  # vazio = todos

        if not assunto or not mensagem:
            flash('Assunto e mensagem são obrigatórios.', 'error')
        else:
            with get_db() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    if secretaria:
                        cur.execute("SELECT email,nome FROM membros WHERE ativo=TRUE AND secretaria=%s;", (secretaria,))
                    else:
                        cur.execute("SELECT email,nome FROM membros WHERE ativo=TRUE;")
                    dest = cur.fetchall()

            if not dest:
                flash('Nenhum membro ativo encontrado para envio.', 'error')
            else:
                emails = [r['email'] for r in dest]
                html = render_template('email_template.html',
                                       assunto=assunto, mensagem=mensagem,
                                       destinatarios=dest, secretaria=secretaria or 'Todos')
                ok, err = enviar_email(emails, assunto, html, secretaria or 'Todos')
                if ok:
                    flash(f'E-mail enviado para {len(emails)} destinatário(s)!', 'success')
                else:
                    flash(f'Erro ao enviar: {err}', 'error')
            return redirect(url_for('admin_email'))

    return render_template('admin/email.html',
                           secretarias=secs_com_membros, logs=logs,
                           smtp_ok=bool(SMTP_USER and SMTP_PASS))


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — PROJETOS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/projetos')
@login_required
def admin_projetos():
    secretaria = request.args.get('secretaria', '')
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            try:
                if secretaria:
                    cur.execute("SELECT *, COALESCE(nome_projeto, titulo) as nome_projeto_display FROM projetos WHERE secretaria=%s ORDER BY atualizado_em DESC;", (secretaria,))
                else:
                    cur.execute("SELECT *, COALESCE(nome_projeto, titulo) as nome_projeto_display FROM projetos ORDER BY atualizado_em DESC;")
                projetos = cur.fetchall()
            except psycopg2.errors.UndefinedColumn as e:
                # Fallback query if columns don't exist
                if secretaria:
                    cur.execute("SELECT *, COALESCE(titulo, 'Sem título') as nome_projeto_display FROM projetos WHERE secretaria=%s ORDER BY atualizado_em DESC;", (secretaria,))
                else:
                    cur.execute("SELECT *, COALESCE(titulo, 'Sem título') as nome_projeto_display FROM projetos ORDER BY atualizado_em DESC;")
                projetos = cur.fetchall()
    return render_template('admin/projetos.html', projetos=projetos,
                           secretarias=get_secretarias_lista(), secretaria_filtro=secretaria,
                           badge_class=SecretariaManager.badge_class,
                           progresso_cor=SecretariaManager.progresso_cor)


@app.route('/admin/projetos/novo', methods=['GET', 'POST'])
@login_required
def admin_projeto_novo():
    if request.method == 'POST':
        # Campos do formulário atualizado
        carimbo_data_hora = datetime.now()
        email = request.form.get('email','').strip()
        nome_completo = request.form.get('nome_completo','').strip()
        cargo = request.form.get('cargo','').strip()
        eixo = request.form.get('eixo','').strip()
        secretaria = request.form['secretaria'].strip()
        publico_que_pretende_atingir = request.form.get('publico_que_pretende_atingir','').strip()
        faixa_etaria = request.form.get('faixa_etaria','').strip()
        genero = request.form.get('genero','').strip()
        publico = request.form.get('publico','').strip()
        nome_projeto = request.form['nome_projeto'].strip()
        data_inicio = request.form.get('data_inicio') or None
        data_termino = request.form.get('data_termino') or None
        descricao_resumo = request.form.get('descricao_resumo','').strip()
        possui_prioritario = 'possui_prioritario' in request.form
        publico_prioritario = request.form.get('publico_prioritario','').strip()
        estimativa_alcance = request.form.get('estimativa_alcance') or None
        if estimativa_alcance:
            estimativa_alcance = int(estimativa_alcance)
        regiao_administrativa = request.form.get('regiao_administrativa','').strip()
        objetivos = request.form.get('objetivos','').strip()
        grau_clareza_objetivos = request.form.get('grau_clareza_objetivos') or None
        if grau_clareza_objetivos:
            grau_clareza_objetivos = int(grau_clareza_objetivos)
        metodologia = request.form.get('metodologia','').strip()
        etapas = request.form.get('etapas','').strip()
        cronograma_responsaveis = request.form.get('cronograma_responsaveis','').strip()
        quantidade_pessoas = request.form.get('quantidade_pessoas') or None
        if quantidade_pessoas:
            quantidade_pessoas = int(quantidade_pessoas)
        frequencia_acompanhamento = request.form.get('frequencia_acompanhamento','').strip()
        acompanhar_desenvolvimento = request.form.get('acompanhar_desenvolvimento','').strip()
        documentos_links = request.form.get('documentos_links','').strip()
        nivel_maturidade = request.form.get('nivel_maturidade','').strip()
        grau_eficacia_viabilidade = request.form.get('grau_eficacia_viabilidade') or None
        if grau_eficacia_viabilidade:
            grau_eficacia_viabilidade = int(grau_eficacia_viabilidade)

        # Campos legados para compatibilidade
        titulo = request.form.get('titulo','').strip() or nome_projeto
        descricao = request.form.get('descricao','').strip() or descricao_resumo
        status = request.form.get('status','Planejamento')
        responsavel = request.form.get('responsavel','').strip() or nome_completo
        orcamento = request.form.get('orcamento') or None
        progresso = int(request.form.get('progresso', 0))

        if not nome_projeto or not secretaria:
            flash('Nome do projeto e secretária são obrigatórios.', 'error')
        else:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""INSERT INTO projetos
                        (carimbo_data_hora, email, nome_completo, cargo, eixo, secretaria,
                        publico_que_pretende_atingir, faixa_etaria, genero, publico, nome_projeto,
                        data_inicio, data_termino, descricao_resumo, possui_prioritario, publico_prioritario,
                        estimativa_alcance, regiao_administrativa, objetivos, grau_clareza_objetivos,
                        metodologia, etapas, cronograma_responsaveis, quantidade_pessoas,
                        frequencia_acompanhamento, acompanhar_desenvolvimento, documentos_links,
                        nivel_maturidade, grau_eficacia_viabilidade, titulo, descricao, status,
                        responsavel, orcamento, progresso)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);""",
                        (carimbo_data_hora, email, nome_completo, cargo, eixo, secretaria,
                        publico_que_pretende_atingir, faixa_etaria, genero, publico, nome_projeto,
                        data_inicio, data_termino, descricao_resumo, possui_prioritario, publico_prioritario,
                        estimativa_alcance, regiao_administrativa, objetivos, grau_clareza_objetivos,
                        metodologia, etapas, cronograma_responsaveis, quantidade_pessoas,
                        frequencia_acompanhamento, acompanhar_desenvolvimento, documentos_links,
                        nivel_maturidade, grau_eficacia_viabilidade, titulo, descricao, status,
                        responsavel, orcamento, progresso))
                conn.commit()
            flash('Projeto criado!', 'success')
            return redirect(url_for('admin_projetos'))
    return render_template('admin/projeto_form.html', projeto=None,
                           secretarias=get_secretarias_lista(), status_list=STATUS_PROJETO)


@app.route('/admin/projetos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_projeto_editar(id):
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM projetos WHERE id=%s;", (id,))
            projeto = cur.fetchone()
            cur.execute("SELECT * FROM projeto_updates WHERE projeto_id=%s ORDER BY criado_em DESC;", (id,))
            updates = cur.fetchall()
    if not projeto:
        flash('Projeto não encontrado.', 'error')
        return redirect(url_for('admin_projetos'))
    if request.method == 'POST':
        action = request.form.get('action','save')
        if action == 'update':
            texto = request.form.get('update_texto','').strip()
            if texto:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute("INSERT INTO projeto_updates (projeto_id,texto) VALUES (%s,%s);", (id, texto))
                        cur.execute("UPDATE projetos SET atualizado_em=NOW() WHERE id=%s;", (id,))
                    conn.commit()
                flash('Atualização adicionada!', 'success')
        else:
            # Campos do formulário atualizado
            carimbo_data_hora = datetime.now()
            email = request.form.get('email','').strip()
            nome_completo = request.form.get('nome_completo','').strip()
            cargo = request.form.get('cargo','').strip()
            eixo = request.form.get('eixo','').strip()
            secretaria = request.form['secretaria'].strip()
            publico_que_pretende_atingir = request.form.get('publico_que_pretende_atingir','').strip()
            faixa_etaria = request.form.get('faixa_etaria','').strip()
            genero = request.form.get('genero','').strip()
            publico = request.form.get('publico','').strip()
            nome_projeto = request.form['nome_projeto'].strip()
            data_inicio = request.form.get('data_inicio') or None
            data_termino = request.form.get('data_termino') or None
            descricao_resumo = request.form.get('descricao_resumo','').strip()
            possui_prioritario = 'possui_prioritario' in request.form
            publico_prioritario = request.form.get('publico_prioritario','').strip()
            estimativa_alcance = request.form.get('estimativa_alcance') or None
            if estimativa_alcance:
                estimativa_alcance = int(estimativa_alcance)
            regiao_administrativa = request.form.get('regiao_administrativa','').strip()
            objetivos = request.form.get('objetivos','').strip()
            grau_clareza_objetivos = request.form.get('grau_clareza_objetivos') or None
            if grau_clareza_objetivos:
                grau_clareza_objetivos = int(grau_clareza_objetivos)
            metodologia = request.form.get('metodologia','').strip()
            etapas = request.form.get('etapas','').strip()
            cronograma_responsaveis = request.form.get('cronograma_responsaveis','').strip()
            quantidade_pessoas = request.form.get('quantidade_pessoas') or None
            if quantidade_pessoas:
                quantidade_pessoas = int(quantidade_pessoas)
            frequencia_acompanhamento = request.form.get('frequencia_acompanhamento','').strip()
            acompanhar_desenvolvimento = request.form.get('acompanhar_desenvolvimento','').strip()
            documentos_links = request.form.get('documentos_links','').strip()
            nivel_maturidade = request.form.get('nivel_maturidade','').strip()
            grau_eficacia_viabilidade = request.form.get('grau_eficacia_viabilidade') or None
            if grau_eficacia_viabilidade:
                grau_eficacia_viabilidade = int(grau_eficacia_viabilidade)

            # Campos legados para compatibilidade
            titulo = request.form.get('titulo','').strip() or nome_projeto
            descricao = request.form.get('descricao','').strip() or descricao_resumo
            status = request.form.get('status','Planejamento')
            responsavel = request.form.get('responsavel','').strip() or nome_completo
            orcamento = request.form.get('orcamento') or None
            progresso = int(request.form.get('progresso', 0))

            if not nome_projeto or not secretaria:
                flash('Nome do projeto e secretária são obrigatórios.', 'error')
            else:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""UPDATE projetos SET
                            carimbo_data_hora=%s, email=%s, nome_completo=%s, cargo=%s, eixo=%s, secretaria=%s,
                            publico_que_pretende_atingir=%s, faixa_etaria=%s, genero=%s, publico=%s, nome_projeto=%s,
                            data_inicio=%s, data_termino=%s, descricao_resumo=%s, possui_prioritario=%s, publico_prioritario=%s,
                            estimativa_alcance=%s, regiao_administrativa=%s, objetivos=%s, grau_clareza_objetivos=%s,
                            metodologia=%s, etapas=%s, cronograma_responsaveis=%s, quantidade_pessoas=%s,
                            frequencia_acompanhamento=%s, acompanhar_desenvolvimento=%s, documentos_links=%s,
                            nivel_maturidade=%s, grau_eficacia_viabilidade=%s, titulo=%s, descricao=%s, status=%s,
                            responsavel=%s, orcamento=%s, progresso=%s, atualizado_em=NOW()
                            WHERE id=%s;""",
                            (carimbo_data_hora, email, nome_completo, cargo, eixo, secretaria,
                            publico_que_pretende_atingir, faixa_etaria, genero, publico, nome_projeto,
                            data_inicio, data_termino, descricao_resumo, possui_prioritario, publico_prioritario,
                            estimativa_alcance, regiao_administrativa, objetivos, grau_clareza_objetivos,
                            metodologia, etapas, cronograma_responsaveis, quantidade_pessoas,
                            frequencia_acompanhamento, acompanhar_desenvolvimento, documentos_links,
                            nivel_maturidade, grau_eficacia_viabilidade, titulo, descricao, status,
                            responsavel, orcamento, progresso, id))
                    conn.commit()
                flash('Projeto atualizado!', 'success')
        return redirect(url_for('admin_projeto_editar', id=id))
    return render_template('admin/projeto_form.html', projeto=projeto, updates=updates,
                           secretarias=get_secretarias_lista(), status_list=STATUS_PROJETO)


@app.route('/admin/projetos/excluir/<int:id>', methods=['POST'])
@login_required
def admin_projeto_excluir(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM projetos WHERE id=%s;", (id,))
        conn.commit()
    flash('Projeto excluído.', 'success')
    return redirect(url_for('admin_projetos'))


# ══════════════════════════════════════════════════════════════════════════════
# PÚBLICAS — SECRETARIA (sub-páginas via SecretariaManager)
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/secretarias/<secretaria>/visao-geral')
def sec_visao_geral(secretaria):
    mgr = get_sec_mgr()
    return render_template('sec_visao_geral.html',
        secretaria=secretaria,
        stats=mgr.stats(secretaria),
        projetos_ativos=mgr.projetos_ativos(secretaria),
        updates_recentes=mgr.updates_recentes(secretaria),
        badge_class=mgr.badge_class,
        progresso_cor=mgr.progresso_cor,
    )


@app.route('/secretarias/<secretaria>/projetos')
def sec_projetos(secretaria):
    mgr = get_sec_mgr()
    status_filtro = request.args.get('status', '')
    return render_template('sec_projetos.html',
        secretaria=secretaria,
        projetos=mgr.projetos(secretaria, status_filtro),
        status_filtro=status_filtro,
        status_list=STATUS_PROJETO,
        badge_class=mgr.badge_class,
        progresso_cor=mgr.progresso_cor,
    )


@app.route('/secretarias/<secretaria>/membros')
def sec_membros(secretaria):
    mgr = get_sec_mgr()
    return render_template('sec_membros.html',
        secretaria=secretaria,
        membros=mgr.membros(secretaria),
        iniciais=mgr.iniciais,
    )


@app.route('/secretarias/<secretaria>/publicacoes')
def sec_publicacoes(secretaria):
    mgr = get_sec_mgr()
    return render_template('sec_publicacoes.html',
        secretaria=secretaria,
        noticias=mgr.publicacoes(secretaria),
    )


@app.route('/secretarias/<secretaria>/eventos')
def sec_eventos(secretaria):
    mgr = get_sec_mgr()
    eventos_json = []
    for e in mgr.todos_eventos():
        eventos_json.append({
            'id': e['id'], 'title': e['titulo'],
            'start': e['data_inicio'].isoformat(),
            'end': e['data_fim'].isoformat() if e['data_fim'] else e['data_inicio'].isoformat(),
            'color': e['cor'],
            'extendedProps': {
                'descricao':   e['descricao'] or '',
                'local':       e['local'] or '',
                'secretaria':  e.get('secretaria') or '',
                'url':         e.get('url') or '',
                'url_label':   e.get('url_label') or 'Ver mais',
                'hora_inicio': e['hora_inicio'].strftime('%H:%M') if e['hora_inicio'] else '',
                'hora_fim':    e['hora_fim'].strftime('%H:%M')    if e['hora_fim']    else '',
            }
        })
    proximos = mgr.eventos_proximos(limit=6)
    return render_template('sec_eventos.html',
        secretaria=secretaria,
        eventos_json=eventos_json,
        proximos=proximos,
    )



# ── helper dinâmico de secretarias ───────────────────────────────────────────

def get_secretarias_lista():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT nome FROM secretarias ORDER BY nome;")
                rows = cur.fetchall()
                return [r[0] for r in rows] if rows else list(SECRETARIAS)
    except Exception:
        return list(SECRETARIAS)


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — SECRETARIAS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/gerir-secretarias', methods=['GET', 'POST'])
@login_required
def admin_secretarias():
    if request.method == 'POST':
        action = request.form.get('action', '')
        nome   = request.form.get('nome', '').strip()
        sid    = request.form.get('id', '')
        if action == 'criar':
            if not nome:
                flash('Informe o nome da secretaria.', 'error')
            else:
                try:
                    with get_db() as conn:
                        with conn.cursor() as cur:
                            cur.execute("""CREATE TABLE IF NOT EXISTS secretarias (
                                id SERIAL PRIMARY KEY, nome VARCHAR(150) NOT NULL UNIQUE,
                                criado_em TIMESTAMP DEFAULT NOW());""")
                            cur.execute("INSERT INTO secretarias (nome) VALUES (%s);", (nome,))
                        conn.commit()
                    flash(f'Secretaria "{nome}" criada!', 'success')
                except Exception as e:
                    flash('Já existe uma secretaria com esse nome.' if 'unique' in str(e).lower() else str(e), 'error')
        elif action == 'excluir' and sid:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM secretarias WHERE id=%s;", (sid,))
                conn.commit()
            flash(f'Secretaria removida.', 'success')
        return redirect(url_for('admin_secretarias'))

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""CREATE TABLE IF NOT EXISTS secretarias (
                    id SERIAL PRIMARY KEY, nome VARCHAR(150) NOT NULL UNIQUE,
                    criado_em TIMESTAMP DEFAULT NOW());""")
                cur.execute("SELECT COUNT(*) FROM secretarias;")
                if cur.fetchone()[0] == 0:
                    for s in SECRETARIAS:
                        cur.execute("INSERT INTO secretarias (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING;", (s,))
            conn.commit()
        with get_db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT s.id, s.nome, s.criado_em,
                        (SELECT COUNT(*) FROM projetos p WHERE p.secretaria=s.nome) AS total_projetos,
                        (SELECT COUNT(*) FROM membros  m WHERE m.secretaria=s.nome AND m.ativo=TRUE) AS total_membros
                    FROM secretarias s ORDER BY s.nome;""")
                secretarias = cur.fetchall()
    except Exception as e:
        flash(f'Erro: {e}', 'error')
        secretarias = []
    return render_template('admin/secretarias.html', secretarias=secretarias)


if __name__ == '__main__':
    # init_db()  # Comentado para evitar erro no startup
    app.run(host='0.0.0.0', port=5000,
            debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
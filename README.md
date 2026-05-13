# Portal de Notícias — Flask + PostgreSQL

## Estrutura

```
news_app/
├── app.py                   # Aplicação principal
├── requirements.txt
└── templates/
    ├── base.html            # Layout base público
    ├── index.html           # Página inicial
    ├── noticia.html         # Página da notícia
    ├── 404.html
    └── admin/
        ├── login.html       # Login do administrador
        ├── dashboard.html   # Painel com lista de notícias
        └── form.html        # Formulário criar/editar
```

## Funcionalidades

**Portal público**
- Listagem de notícias com destaque principal
- Filtro por categoria
- Busca por título e conteúdo
- Página individual com notícias relacionadas

**Painel Admin** (`/admin`)
- Login protegido por usuário/senha
- Dashboard com contadores
- Criar, editar e excluir notícias
- Publicar / despublicar (rascunho)
- Categorias: Geral, Política, Economia, Tecnologia, Esportes, Saúde, Cultura, Institucional

## Instalação

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Criar banco no PostgreSQL
psql -U postgres -c "CREATE DATABASE newsdb;"

# 3. Configurar variáveis de ambiente (opcional)
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=newsdb
export DB_USER=postgres
export DB_PASSWORD=postgres

export ADMIN_USER=admin
export ADMIN_PASS=admin123          # TROQUE EM PRODUÇÃO
export SECRET_KEY=sua-chave-secreta # TROQUE EM PRODUÇÃO

# 4. Rodar
python app.py
```

Acesse: http://localhost:5000  
Admin:  http://localhost:5000/admin/login

## Credenciais padrão

| Campo   | Valor      |
|---------|------------|
| Usuário | `admin`    |
| Senha   | `admin123` |

> ⚠️ Altere as credenciais via variáveis de ambiente antes de colocar em produção.

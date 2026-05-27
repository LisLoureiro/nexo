import psycopg2
from psycopg2 import sql

# Configuração do banco
DB_CONFIG = {
    'host': 'db',
    'port': '5432',
    'database': 'newsdb',
    'user': 'postgres',
    'password': 'postgres'
}

def migrate_database():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Adicionar todas as colunas novas
    columns_to_add = [
        ("carimbo_data_hora", "TIMESTAMP"),
        ("email", "VARCHAR(255)"),
        ("nome_completo", "VARCHAR(255)"),
        ("cargo", "VARCHAR(150)"),
        ("eixo", "VARCHAR(100)"),
        ("publico_que_pretende_atingir", "TEXT"),
        ("faixa_etaria", "VARCHAR(100)"),
        ("genero", "VARCHAR(50)"),
        ("publico", "VARCHAR(100)"),
        ("nome_projeto", "VARCHAR(255)"),
        ("data_termino", "DATE"),
        ("descricao_resumo", "TEXT"),
        ("possui_prioritario", "BOOLEAN DEFAULT FALSE"),
        ("publico_prioritario", "TEXT"),
        ("estimativa_alcance", "INTEGER"),
        ("regiao_administrativa", "VARCHAR(100)"),
        ("objetivos", "TEXT"),
        ("grau_clareza_objetivos", "INTEGER CHECK (grau_clareza_objetivos BETWEEN 1 AND 5)"),
        ("metodologia", "TEXT"),
        ("etapas", "TEXT"),
        ("cronograma_responsaveis", "TEXT"),
        ("quantidade_pessoas", "INTEGER"),
        ("frequencia_acompanhamento", "VARCHAR(100)"),
        ("acompanhar_desenvolvimento", "TEXT"),
        ("documentos_links", "TEXT"),
        ("nivel_maturidade", "VARCHAR(50)"),
        ("grau_eficacia_viabilidade", "INTEGER CHECK (grau_eficacia_viabilidade BETWEEN 1 AND 5)"),
        ("titulo", "VARCHAR(255)"),
        ("data_inicio_old", "DATE"),
    ]

    for col_name, col_type in columns_to_add:
        try:
            cur.execute(sql.SQL("ALTER TABLE projetos ADD COLUMN IF NOT EXISTS {} {};").format(
                sql.Identifier(col_name),
                sql.SQL(col_type)
            ))
            print(f"Adicionada coluna: {col_name}")
        except Exception as e:
            print(f"Erro ao adicionar coluna {col_name}: {e}")

    # Atualizar dados existentes
    try:
        cur.execute("""
            UPDATE projetos SET
                carimbo_data_hora = criado_em,
                nome_projeto = COALESCE(nome_projeto, titulo),
                descricao_resumo = COALESCE(descricao_resumo, descricao),
                nome_completo = COALESCE(nome_completo, responsavel),
                data_termino = COALESCE(data_termino, data_fim),
                eixo = 'Administrativo'
            WHERE carimbo_data_hora IS NULL;
        """)
        print("Dados atualizados com sucesso!")
    except Exception as e:
        print(f"Erro ao atualizar dados: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print("Migração concluída!")

if __name__ == "__main__":
    migrate_database()
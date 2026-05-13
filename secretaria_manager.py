"""
SecretariaManager
─────────────────
Classe responsável por toda a lógica de dados das secretarias.
Centraliza queries, stats e helpers — os blueprints/rotas apenas chamam
os métodos desta classe e passam os dados para os templates.
"""
import psycopg2
import psycopg2.extras
from datetime import date


class SecretariaManager:

    def __init__(self, db_config: dict):
        self._cfg = db_config

    # ── conexão ────────────────────────────────────────────────────────────────

    def _conn(self):
        return psycopg2.connect(**self._cfg)

    def _fetch(self, sql: str, params=(), many=True):
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                return cur.fetchall() if many else cur.fetchone()

    def _scalar(self, sql: str, params=()):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                return row[0] if row else 0

    # ── lista de secretarias cadastradas ──────────────────────────────────────

    def listar_com_resumo(self) -> list:
        """Retorna todas as secretarias que têm projetos, com contadores."""
        return self._fetch("""
            SELECT
                secretaria,
                COUNT(*)                                              AS total_projetos,
                SUM(CASE WHEN status='Em andamento' THEN 1 ELSE 0 END) AS em_andamento,
                SUM(CASE WHEN status='Concluído'    THEN 1 ELSE 0 END) AS concluidos,
                SUM(CASE WHEN status='Planejamento' THEN 1 ELSE 0 END) AS planejamento,
                ROUND(AVG(progresso))                                  AS progresso_medio
            FROM projetos
            GROUP BY secretaria
            ORDER BY secretaria;
        """)

    # ── stats de uma secretaria ────────────────────────────────────────────────

    def stats(self, secretaria: str) -> dict:
        sc = secretaria
        return {
            'total_projetos':  self._scalar("SELECT COUNT(*) FROM projetos WHERE secretaria=%s;", (sc,)),
            'em_andamento':    self._scalar("SELECT COUNT(*) FROM projetos WHERE secretaria=%s AND status='Em andamento';", (sc,)),
            'concluidos':      self._scalar("SELECT COUNT(*) FROM projetos WHERE secretaria=%s AND status='Concluído';", (sc,)),
            'planejamento':    self._scalar("SELECT COUNT(*) FROM projetos WHERE secretaria=%s AND status='Planejamento';", (sc,)),
            'total_membros':   self._scalar("SELECT COUNT(*) FROM membros  WHERE secretaria=%s AND ativo=TRUE;", (sc,)),
            'publicacoes':     self._scalar("SELECT COUNT(*) FROM noticias WHERE categoria=%s AND publicado=TRUE;", (sc,)),
            'eventos':         self._scalar("SELECT COUNT(*) FROM eventos  WHERE publicado=TRUE;"),   # global p/ simplificar
            'orcamento_total': self._scalar("SELECT COALESCE(SUM(orcamento),0) FROM projetos WHERE secretaria=%s;", (sc,)),
        }

    # ── projetos ───────────────────────────────────────────────────────────────

    def projetos(self, secretaria: str, status: str = '') -> list:
        sql = """
            SELECT * FROM projetos WHERE secretaria=%s
            {where}
            ORDER BY
                CASE status
                    WHEN 'Em andamento' THEN 1
                    WHEN 'Planejamento' THEN 2
                    WHEN 'Suspenso'     THEN 3
                    WHEN 'Concluído'    THEN 4
                    ELSE 5
                END, atualizado_em DESC;
        """
        if status:
            return self._fetch(sql.format(where="AND status=%s"), (secretaria, status))
        return self._fetch(sql.format(where=''), (secretaria,))

    def projeto_por_id(self, id: int):
        return self._fetch("SELECT * FROM projetos WHERE id=%s;", (id,), many=False)

    def projeto_updates(self, projeto_id: int) -> list:
        return self._fetch(
            "SELECT * FROM projeto_updates WHERE projeto_id=%s ORDER BY criado_em DESC;",
            (projeto_id,))

    def projetos_ativos(self, secretaria: str, limit: int = 5) -> list:
        return self._fetch("""
            SELECT * FROM projetos
            WHERE secretaria=%s AND status='Em andamento'
            ORDER BY progresso DESC LIMIT %s;
        """, (secretaria, limit))

    # ── membros ────────────────────────────────────────────────────────────────

    def membros(self, secretaria: str) -> list:
        return self._fetch(
            "SELECT * FROM membros WHERE secretaria=%s ORDER BY ativo DESC, nome;",
            (secretaria,))

    def membros_ativos(self, secretaria: str) -> list:
        return self._fetch(
            "SELECT * FROM membros WHERE secretaria=%s AND ativo=TRUE ORDER BY nome;",
            (secretaria,))

    # ── publicações (notícias) ─────────────────────────────────────────────────

    def publicacoes(self, secretaria: str, limit: int = 50) -> list:
        return self._fetch("""
            SELECT * FROM noticias
            WHERE publicado=TRUE AND (categoria=%s OR categoria ILIKE %s)
            ORDER BY criado_em DESC LIMIT %s;
        """, (secretaria, f'%{secretaria}%', limit))

    # ── eventos ────────────────────────────────────────────────────────────────

    def eventos_proximos(self, limit: int = 10) -> list:
        return self._fetch("""
            SELECT * FROM eventos
            WHERE publicado=TRUE AND data_inicio >= CURRENT_DATE
            ORDER BY data_inicio ASC LIMIT %s;
        """, (limit,))

    def todos_eventos(self) -> list:
        return self._fetch("""
            SELECT * FROM eventos WHERE publicado=TRUE ORDER BY data_inicio DESC;
        """)

    # ── timeline de atualizações ───────────────────────────────────────────────

    def updates_recentes(self, secretaria: str, limit: int = 8) -> list:
        return self._fetch("""
            SELECT pu.*, p.titulo AS projeto_titulo, p.status AS projeto_status
            FROM projeto_updates pu
            JOIN projetos p ON p.id = pu.projeto_id
            WHERE p.secretaria = %s
            ORDER BY pu.criado_em DESC LIMIT %s;
        """, (secretaria, limit))

    # ── helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def badge_class(status: str) -> str:
        return {
            'Em andamento': 'badge-blue',
            'Concluído':    'badge-green',
            'Planejamento': 'badge-yellow',
            'Suspenso':     'badge-red',
            'Cancelado':    'badge-gray',
        }.get(status, 'badge-gray')

    @staticmethod
    def progresso_cor(pct: int) -> str:
        if pct >= 80: return '#1a8a5a'
        if pct >= 50: return '#4f5de8'
        if pct >= 25: return '#f0a500'
        return '#c0392b'

    @staticmethod
    def iniciais(nome: str) -> str:
        partes = nome.strip().split()
        if len(partes) >= 2:
            return (partes[0][0] + partes[-1][0]).upper()
        return nome[:2].upper()

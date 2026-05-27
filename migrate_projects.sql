-- Migration to update projetos table structure
-- Add new columns from Excel form

-- First, add all new columns to the existing table
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS carimbo_data_hora TIMESTAMP;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS email VARCHAR(255);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS nome_completo VARCHAR(255);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS cargo VARCHAR(150);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS eixo VARCHAR(100);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS publico_que_pretende_atingir TEXT;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS faixa_etaria VARCHAR(100);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS genero VARCHAR(50);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS publico VARCHAR(100);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS nome_projeto VARCHAR(255);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS data_termino DATE;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS descricao_resumo TEXT;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS possui_prioritario BOOLEAN DEFAULT FALSE;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS publico_prioritario TEXT;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS estimativa_alcance INTEGER;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS regiao_administrativa VARCHAR(100);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS objetivos TEXT;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS grau_clareza_objetivos INTEGER CHECK (grau_clareza_objetivos BETWEEN 1 AND 5);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS metodologia TEXT;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS etapas TEXT;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS cronograma_responsaveis TEXT;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS quantidade_pessoas INTEGER;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS frequencia_acompanhamento VARCHAR(100);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS acompanhar_desenvolvimento TEXT;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS documentos_links TEXT;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS nivel_maturidade VARCHAR(50);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS grau_eficacia_viabilidade INTEGER CHECK (grau_eficacia_viabilidade BETWEEN 1 AND 5);

-- Add compatibility columns
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS titulo VARCHAR(255);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS data_inicio_old DATE;

-- Update existing records with default values where needed
UPDATE projetos SET
    carimbo_data_hora = criado_em,
    nome_projeto = COALESCE(nome_projeto, titulo),
    descricao_resumo = COALESCE(descricao_resumo, descricao),
    nome_completo = COALESCE(nome_completo, responsavel),
    data_inicio = COALESCE(data_inicio, data_inicio_old)
WHERE carimbo_data_hora IS NULL OR nome_projeto IS NULL;

-- Create index for better performance
CREATE INDEX IF NOT EXISTS idx_projetos_secretaria ON projetos(secretaria);
CREATE INDEX IF NOT EXISTS idx_projetos_status ON projetos(status);
CREATE INDEX IF NOT EXISTS idx_projetos_eixo ON projetos(eixo);

-- Print completion message
SELECT 'Migration completed successfully!' as status;
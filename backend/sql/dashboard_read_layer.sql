-- Camada de leitura para dashboard
-- Banco alvo: PostgreSQL 14+
-- Objetivo: descarregar consultas analíticas do banco transacional.

BEGIN;

CREATE SCHEMA IF NOT EXISTS analytics;

-- 1) VIEW base de eventos operacionais (join padronizado)
CREATE OR REPLACE VIEW analytics.vw_operacao_base AS
SELECT
    o.id AS os_id,
    o.status AS os_status,
    o.opened_at AT TIME ZONE 'UTC' AS os_opened_at_utc,
    o.closed_at AT TIME ZONE 'UTC' AS os_closed_at_utc,
    o.setor_id,
    o.colaborador_id,
    o.tipo_servico_id,
    o.seguradora_id,
    o.budget_id AS orcamento_id,
    b.status AS orcamento_status,
    b.enviado_at AT TIME ZONE 'UTC' AS orcamento_enviado_at_utc,
    b.aprovado_at AT TIME ZONE 'UTC' AS orcamento_aprovado_at_utc,
    b.valor_total AS orcamento_valor_total,
    f.id AS fatura_id,
    f.valor AS fatura_valor,
    f.issued_at AT TIME ZONE 'UTC' AS fatura_emitida_at_utc,
    f.paid_at AT TIME ZONE 'UTC' AS fatura_paga_at_utc
FROM ordens_servico o
LEFT JOIN orcamentos b ON b.id = o.budget_id
LEFT JOIN faturas f ON f.os_id = o.id;

-- 2) MATERIALIZED VIEW: fatos diários para operação
CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.mv_kpi_operacao_diario AS
SELECT
    DATE_TRUNC('day', os_opened_at_utc)::date AS data_ref,
    setor_id,
    colaborador_id,
    tipo_servico_id,
    seguradora_id,
    COUNT(DISTINCT os_id) FILTER (WHERE os_status IN ('ABERTA','EM_EXECUCAO','AGUARDANDO_PECA','EM_QUALIDADE')) AS os_abertas_qtd,
    AVG(EXTRACT(EPOCH FROM (os_closed_at_utc - os_opened_at_utc))/3600.0)
        FILTER (WHERE os_closed_at_utc IS NOT NULL) AS lead_time_os_horas,
    COUNT(DISTINCT orcamento_id) FILTER (WHERE orcamento_status = 'APROVADO') AS orcamentos_aprovados_qtd,
    COUNT(DISTINCT orcamento_id) FILTER (WHERE orcamento_status IN ('APROVADO','REJEITADO','EXPIRADO')) AS orcamentos_decididos_qtd,
    SUM(orcamento_valor_total) FILTER (WHERE orcamento_status = 'APROVADO') AS valor_aprovado_total
FROM analytics.vw_operacao_base
GROUP BY 1,2,3,4,5;

CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_kpi_operacao_diario
    ON analytics.mv_kpi_operacao_diario (data_ref, setor_id, colaborador_id, tipo_servico_id, seguradora_id);

-- 3) MATERIALIZED VIEW: fatos financeiros diários
CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.mv_kpi_financeiro_diario AS
SELECT
    DATE_TRUNC('day', fatura_emitida_at_utc)::date AS data_ref,
    setor_id,
    seguradora_id,
    SUM(fatura_valor) AS faturamento_bruto,
    AVG(EXTRACT(EPOCH FROM (fatura_paga_at_utc - fatura_emitida_at_utc))/86400.0)
        FILTER (WHERE fatura_paga_at_utc IS NOT NULL) AS tempo_medio_pagamento_dias,
    SUM(fatura_valor) FILTER (
        WHERE fatura_paga_at_utc IS NULL
          AND fatura_emitida_at_utc::date <= (CURRENT_DATE - INTERVAL '30 days')
    ) AS valor_vencido_30d
FROM analytics.vw_operacao_base
GROUP BY 1,2,3;

CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_kpi_financeiro_diario
    ON analytics.mv_kpi_financeiro_diario (data_ref, setor_id, seguradora_id);

-- 4) VIEW final de consumo para dashboard (métricas derivadas)
CREATE OR REPLACE VIEW analytics.vw_dashboard_kpis AS
SELECT
    op.data_ref,
    op.setor_id,
    op.colaborador_id,
    op.tipo_servico_id,
    op.seguradora_id,
    op.os_abertas_qtd,
    op.lead_time_os_horas,
    CASE
        WHEN op.orcamentos_decididos_qtd = 0 THEN NULL
        ELSE (op.orcamentos_aprovados_qtd::numeric / op.orcamentos_decididos_qtd::numeric) * 100
    END AS taxa_aprovacao_orcamento_pct,
    CASE
        WHEN op.orcamentos_aprovados_qtd = 0 THEN NULL
        ELSE op.valor_aprovado_total / op.orcamentos_aprovados_qtd
    END AS ticket_medio_aprovado,
    fin.faturamento_bruto,
    fin.tempo_medio_pagamento_dias,
    CASE
        WHEN fin.faturamento_bruto IS NULL OR fin.faturamento_bruto = 0 THEN NULL
        ELSE (fin.valor_vencido_30d / fin.faturamento_bruto) * 100
    END AS inadimplencia_30d_pct
FROM analytics.mv_kpi_operacao_diario op
LEFT JOIN analytics.mv_kpi_financeiro_diario fin
  ON fin.data_ref = op.data_ref
 AND fin.setor_id = op.setor_id
 AND fin.seguradora_id = op.seguradora_id;

COMMIT;

-- Rotina sugerida de refresh (agendar no orchestrator):
-- REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.mv_kpi_operacao_diario;
-- REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.mv_kpi_financeiro_diario;

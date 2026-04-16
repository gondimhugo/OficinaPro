# Dicionário de Métricas e Modelo de Leitura para Dashboard

## 1) Dicionário de métricas (nome, fórmula, granularidade, atualização, owner)

| Métrica | Fórmula (definição operacional) | Granularidade | Atualização | Owner |
|---|---|---|---|---|
| `tempo_medio_primeiro_atendimento_min` | `AVG(TIMESTAMP_DIFF(first_response_at, opened_at, MINUTE))` para atendimentos com primeira resposta | Dia, setor, colaborador | Tempo real (incremental a cada evento) | Operações de Atendimento |
| `sla_primeiro_atendimento_pct` | `COUNT(first_response_at <= sla_deadline_at) / COUNT(*) * 100` | Dia, setor | Tempo real (janela deslizante) | Operações de Atendimento |
| `orcamentos_emitidos_qtd` | `COUNT(DISTINCT orcamento_id)` com status `ENVIADO` | Dia, setor, colaborador | Tempo real | Comercial |
| `taxa_aprovacao_orcamento_pct` | `COUNT(status='APROVADO') / COUNT(status IN ('APROVADO','REJEITADO','EXPIRADO')) * 100` | Dia, setor, seguradora | Batch (D+0 horário) | Comercial |
| `ticket_medio_aprovado` | `SUM(valor_aprovado) / NULLIF(COUNT(orcamento_aprovado),0)` | Dia, setor, tipo de serviço, seguradora | Batch (D+0 horário) | Comercial |
| `os_abertas_qtd` | `COUNT(os_id WHERE status IN ('ABERTA','EM_EXECUCAO','AGUARDANDO_PECA','EM_QUALIDADE'))` | Snapshot horário, setor | Tempo real | Operações Técnicas |
| `lead_time_os_horas` | `AVG(TIMESTAMP_DIFF(closed_at, opened_at, HOUR))` para OS encerradas | Dia, setor, tipo de serviço | Batch (D+1) | Operações Técnicas |
| `taxa_retrabalho_pct` | `COUNT(os_reaberta)/COUNT(os_encerrada)*100` | Semana, setor, colaborador | Batch (D+1) | Qualidade |
| `faturamento_bruto` | `SUM(valor_fatura_emitida)` | Dia, setor, seguradora | Batch (intradiário a cada 30 min) | Financeiro |
| `inadimplencia_30d_pct` | `SUM(valor_vencido_30d)/SUM(valor_emitido_vencido)*100` | Dia, setor, seguradora | Batch diário (madrugada) | Financeiro |
| `tempo_medio_pagamento_dias` | `AVG(DATE_DIFF(data_pagamento, data_emissao, DAY))` | Dia, seguradora | Batch diário | Financeiro |

---

## 2) Classificação dos KPIs: transacionais vs analíticos

### KPIs transacionais (tempo real)
- `tempo_medio_primeiro_atendimento_min`
- `sla_primeiro_atendimento_pct`
- `orcamentos_emitidos_qtd`
- `os_abertas_qtd`

**Critério:** métricas diretamente ligadas a operação em andamento, usadas para ação imediata e com baixa latência (
~segundos/minutos).

### KPIs analíticos (batch)
- `taxa_aprovacao_orcamento_pct`
- `ticket_medio_aprovado`
- `lead_time_os_horas`
- `taxa_retrabalho_pct`
- `faturamento_bruto`
- `inadimplencia_30d_pct`
- `tempo_medio_pagamento_dias`

**Critério:** métricas que exigem consolidação histórica, regras de fechamento ou reconciliação financeira/operacional.

---

## 3) Padronização de dimensões

### Dimensão `tempo`
- Chaves: `date_key` (`YYYYMMDD`), `month_key` (`YYYYMM`), `week_key` (ISO week), `hour_key` (`0-23`).
- Fusos: armazenar eventos em UTC e expor conversão para `America/Sao_Paulo` no read model.
- Campos recomendados: `event_date`, `event_month`, `event_week`, `event_hour`, `is_business_day`.

### Dimensão `setor`
- Chave substituta: `setor_sk`.
- Chave natural: `setor_id` operacional.
- Atributos: `setor_nome`, `unidade_id`, `unidade_nome`, `gestor_setor_id`.
- Regra SCD: Tipo 2 para mudanças organizacionais relevantes.

### Dimensão `colaborador`
- Chave substituta: `colaborador_sk`.
- Chave natural: `colaborador_id`.
- Atributos: `colaborador_nome`, `cargo`, `setor_id`, `ativo_flag`.
- Regra SCD: Tipo 2 para troca de setor/cargo.

### Dimensão `tipo_servico`
- Chave substituta: `tipo_servico_sk`.
- Chave natural: `tipo_servico_id`.
- Atributos: `categoria`, `subcategoria`, `criticidade`, `tempo_padrao_min`.

### Dimensão `seguradora`
- Chave substituta: `seguradora_sk`.
- Chave natural: `seguradora_id`.
- Atributos: `seguradora_nome`, `canal`, `prazo_medio_pagamento_dias`, `status_parceria`.

### Regras de governança de dimensão
- Evitar texto livre em fatos; usar sempre chaves de dimensão.
- Adotar nomenclatura única para IDs (`*_id`) e surrogate keys (`*_sk`).
- Definir owner por dimensão:
  - `tempo`: Engenharia de Dados
  - `setor` e `colaborador`: RH/Operações
  - `tipo_servico`: Operações Técnicas
  - `seguradora`: Comercial + Financeiro

---

## 4) Camada de leitura para dashboard

Para reduzir carga no banco transacional:

1. Criar **views de integração leve** para padronizar joins de múltiplas tabelas operacionais.
2. Criar **materialized views** para KPIs de alta consulta e baixa mutabilidade.
3. Atualizar em janelas controladas (`REFRESH MATERIALIZED VIEW CONCURRENTLY`) com orquestração por scheduler.
4. Expor apenas a camada de leitura para o BI/dashboard.

Implementação proposta no arquivo SQL: `backend/sql/dashboard_read_layer.sql`.

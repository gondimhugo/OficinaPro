# Plano de fases (MVP 1, 2 e 3)

Este documento define, por fase, os mínimos técnicos, NFRs alvo, riscos/dependências, critérios de pronto para produção e a arquitetura de transição até a arquitetura alvo.

## Princípios de evolução (para evitar retrabalho)

- **Contrato primeiro**: todos os eventos e APIs entre contextos devem ser versionados (`*.v1`, `*.v2`) e retrocompatíveis.
- **Estrangulamento incremental**: sair do monólito modular para serviços por domínio apenas quando houver dor operacional clara (escala, autonomia de times, SLAs distintos).
- **Observabilidade desde o MVP 1**: logs estruturados, métricas e tracing com `correlationId` são requisitos de base para todas as fases.
- **Consistência explícita**: processos críticos (estoque/compras/consumo OS/financeiro) com idempotência, reconciliação e trilha de auditoria.

---

## MVP 1 — Fundação operacional integrada

### 1) Capacidades técnicas mínimas

- **Auth**
  - Login com usuário/senha + JWT de curta duração.
  - RBAC mínimo por perfil (atendimento, comercial, técnico, compras, financeiro, gerente, admin).
  - Escopo por unidade (multi-filial básica).
- **Auditoria**
  - Log imutável de ações críticas: criação/edição/aprovação/cancelamento de orçamento, OS, compra e lançamento financeiro.
  - Capturar `who`, `when`, `before`, `after`, `reason`, `correlationId`.
- **Notificações**
  - Notificação in-app e e-mail para eventos críticos: orçamento enviado/aprovado/rejeitado, OS bloqueada/pronta, fatura emitida/paga.
  - Retentativa simples com fila interna.
- **Storage de fotos**
  - Upload de fotos de atendimento e OS para object storage (bucket único por ambiente).
  - URL assinada de leitura; metadados no banco (hash, tamanho, autor, `os_id`/`atendimento_id`).

### 2) NFRs alvo

- **Latência**
  - `P95 < 400ms` para consultas operacionais.
  - `P95 < 700ms` para comandos transacionais sem anexos.
  - Upload de foto: confirmação em até `2s` para arquivos até 10 MB.
- **Disponibilidade**
  - `99,5%` mensal (janela de manutenção planejada fora de horário comercial).
- **Backup**
  - Backup full diário + incremental a cada 4h.
  - Teste de restore mensal.
- **RPO/RTO**
  - `RPO <= 4h`.
  - `RTO <= 8h`.

### 3) Riscos e dependências

- Aprovação de orçamento depende de regras comerciais estáveis e versionadas.
- Execução de OS depende de transição de estados centralizada (evitar bypass por endpoint).
- Compras depende de visão minimamente confiável de saldo em estoque.
- Financeiro depende de eventos de OS finalizada sem duplicidade (idempotência).
- Risco de baixa rastreabilidade se auditoria não for obrigatória por middleware.

### 4) Critérios de pronto para produção

- **Monitoramento**
  - Dashboard com: erros por endpoint, latência P95/P99, fila de notificações, taxa de falha de upload.
- **Alarmes**
  - Erro 5xx > 2% em 5 min.
  - Fila de eventos pendentes acima de limite por 10 min.
  - Falha de backup ou restore test.
- **Testes críticos**
  - Fluxo E2E: atendimento → orçamento → aprovação → OS → finalização → faturamento.
  - Testes de transição inválida de estado.
  - Testes de autorização (RBAC + escopo de unidade).

### 5) Arquitetura de transição (MVP 1)

- **Monólito modular** com bounded contexts lógicos (Atendimento, Comercial, Execução, Estoque/Compras, Financeiro, Portal).
- Banco relacional único com separação por schema lógico.
- Outbox table para publicação assíncrona de eventos de domínio.
- Worker interno para notificações e tarefas de reconciliação básica.

### 6) Arquitetura alvo ao final do MVP 1

- Monólito modular consolidado + contratos de integração estáveis (`v1`).
- Observabilidade padronizada e trilha de auditoria cobrindo fluxos críticos.

---

## MVP 2 — Consistência de estoque/compras e resiliência

### 1) Capacidades técnicas mínimas

- **Auth**
  - Refresh token rotativo.
  - ABAC complementar para alçada de aprovação e SoD (separação de funções).
- **Auditoria**
  - Assinatura de eventos críticos (hash encadeado) para evidência de integridade.
  - Painel de auditoria com filtros por entidade e `correlationId`.
- **Notificações**
  - Orquestração por filas (DLQ + retentativa exponencial).
  - Templates versionados por canal (e-mail/WhatsApp/SMS, se habilitado).
- **Storage de fotos**
  - Ciclo de vida de objetos (quente/frio), antivírus em upload e deduplicação por hash.
  - Política de retenção por tipo de documento.

### 2) NFRs alvo

- **Latência**
  - `P95 < 300ms` consultas.
  - `P95 < 600ms` comandos principais.
- **Disponibilidade**
  - `99,9%` mensal para APIs operacionais.
- **Backup**
  - Replicação contínua + snapshots de banco por hora.
  - Restore validado quinzenalmente em ambiente isolado.
- **RPO/RTO**
  - `RPO <= 1h`.
  - `RTO <= 2h`.

### 3) Riscos e dependências

- **Compras depende de estoque consistente** (reserva/baixa/recebimento com ordenação por chave de negócio).
- OS em aguardando peça depende de SLA de integração compras↔estoque.
- Risco de dead-letter crescer sem operação de reprocessamento assistido.
- Financeiro pode gerar títulos incorretos se reconciliação de consumo não ocorrer antes do fechamento.

### 4) Critérios de pronto para produção

- **Monitoramento**
  - Métricas por domínio: lead time de compra, taxa de reconciliação, mensagens em DLQ, eventos duplicados descartados.
- **Alarmes**
  - Divergência estoque físico x sistema acima da tolerância.
  - Crescimento de DLQ > limiar por 15 min.
  - Falha em jobs de reconciliação/fechamento.
- **Testes críticos**
  - Testes de concorrência para reserva e baixa de estoque.
  - Testes de idempotência de eventos e reprocessamento.
  - Testes de desastre (restore + replay de eventos outbox).

### 5) Arquitetura de transição (MVP 2)

- Monólito modular + **serviços adjacentes** para capacidades transversais:
  - Notification Service.
  - Media Service (fotos).
- Broker de mensagens obrigatório para integrações assíncronas.
- Read models para Portal e painéis operacionais.

### 6) Arquitetura alvo ao final do MVP 2

- Núcleo transacional ainda no monólito modular.
- Estoque/Compras operando com consistência reforçada (locks, idempotência, reconciliação).
- Serviços de mídia e notificação desacoplados e escaláveis.

---

## MVP 3 — Escala, alta disponibilidade e autonomia por domínio

### 1) Capacidades técnicas mínimas

- **Auth**
  - SSO corporativo (OIDC/SAML) opcional + MFA para perfis sensíveis.
  - Políticas centralizadas (policy engine) com RBAC+ABAC versionado.
- **Auditoria**
  - Trilha inviolável (WORM/log append-only externo).
  - Relatórios de conformidade e trilha de aprovação por alçada.
- **Notificações**
  - Preferência por cliente, janelas de silêncio e fallback multicanal.
  - Métrica de entrega fim-a-fim por canal e motivo de falha.
- **Storage de fotos**
  - Multi-bucket por tenant/unidade, criptografia com KMS e replicação cross-region.
  - CDN com redimensionamento sob demanda e política de acesso por escopo.

### 2) NFRs alvo

- **Latência**
  - `P95 < 200ms` consultas frequentes.
  - `P95 < 450ms` comandos críticos.
- **Disponibilidade**
  - `99,95%` mensal para operações críticas.
- **Backup**
  - Estratégia multi-região com cópia imutável.
  - Exercício de DR trimestral com relatório formal.
- **RPO/RTO**
  - `RPO <= 15 min`.
  - `RTO <= 30 min`.

### 3) Riscos e dependências

- Separação prematura em microserviços pode aumentar custo/complexidade sem ganho real.
- Consistência distribuída entre Execução, Estoque e Financeiro exige saga e compensação bem definidas.
- Dependência de maturidade SRE/observabilidade para sustentar 99,95%.
- Risco de lock-in em provedores de mensageria/storage sem abstrações mínimas.

### 4) Critérios de pronto para produção

- **Monitoramento**
  - SLOs por domínio com error budget e burn rate.
  - Tracing distribuído cobrindo chamadas síncronas e assíncronas.
- **Alarmes**
  - Burn-rate alert (rápido/lento), saturação de filas e degradação de dependências externas.
  - Alarme de quebra de contrato de evento/API.
- **Testes críticos**
  - Chaos engineering em componentes não críticos + game days.
  - Teste de failover regional e rollback por versão de contrato.
  - Testes de performance sustentada e picos sazonais.

### 5) Arquitetura de transição (MVP 3)

- Extração gradual dos domínios com maior necessidade de escala/autonomia:
  1. Estoque/Compras.
  2. Financeiro.
  3. Execução/OS (se justificar).
- API Gateway + service mesh (quando volume/complexidade exigir).
- Estratégia de saga para processos interdomínio longos.

### 6) Arquitetura alvo ao final do MVP 3

- Arquitetura orientada a domínio com serviços independentes por capacidade crítica.
- Eventos como integração principal; consultas compostas via read models/materialized views.
- Plataforma operacional madura: observabilidade, segurança, DR e governança de contratos.

---

## Mapa de evolução arquitetural consolidado

| Fase | Arquitetura de transição | Arquitetura alvo da fase | Decisão anti-retrabalho |
|---|---|---|---|
| MVP 1 | Monólito modular + outbox + worker interno | Monólito modular com contratos `v1` e observabilidade base | Definir contratos e auditoria antes de separar serviços |
| MVP 2 | Monólito modular + broker + serviços de notificação/mídia | Núcleo transacional estável + capacidades transversais desacopladas | Isolar primeiro o que é transversal e de alta volumetria |
| MVP 3 | Extração progressiva por domínio + saga + gateway | Serviços por domínio crítico com SLOs e DR avançado | Extrair por evidência de gargalo, não por moda arquitetural |

## Gate de passagem entre fases

- **MVP 1 → MVP 2**
  - Contratos `v1` sem mudanças quebrantes em produção por 2 ciclos.
  - Auditoria ativa em 100% das operações críticas.
- **MVP 2 → MVP 3**
  - Reconciliação de estoque com taxa de divergência dentro da meta acordada.
  - DLQ sob controle operacional e reprocessamento com playbook validado.
  - Indicadores de escala/latência justificando extração de domínios.

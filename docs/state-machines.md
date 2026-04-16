# Diagrama de estados e regras de transição

## 1) Orçamento

```mermaid
stateDiagram-v2
    [*] --> RASCUNHO
    RASCUNHO --> ENVIADO: enviar_orcamento
    ENVIADO --> APROVADO: aprovar_orcamento
    ENVIADO --> REJEITADO: rejeitar_orcamento
    ENVIADO --> EXPIRADO: expirar_orcamento
    APROVADO --> CONVERTIDO: converter_em_os
```

### Matriz de transições de Orçamento

| De | Para | Evento disparador | Perfis autorizados | Pré-condições | Pós-condições | Side effects |
|---|---|---|---|---|---|---|
| RASCUNHO | ENVIADO | `enviar_orcamento` | atendimento, vendedor, admin | itens e valores válidos; cliente vinculado | status atualizado; registro de histórico | notificar cliente; atualizar portal |
| ENVIADO | APROVADO | `aprovar_orcamento` | cliente, atendimento, admin | orçamento vigente; sem bloqueio comercial | status atualizado; registro de auditoria | notificar equipe interna; atualizar portal |
| ENVIADO | REJEITADO | `rejeitar_orcamento` | cliente, atendimento, admin | orçamento vigente | status atualizado; registro de motivo | notificar responsável comercial; atualizar portal |
| ENVIADO | EXPIRADO | `expirar_orcamento` | sistema, admin | data de validade atingida | status atualizado; auditoria automática | notificar atendimento; atualizar portal |
| APROVADO | CONVERTIDO | `converter_em_os` | atendimento, planejador, admin | orçamento aprovado | OS criada e vinculada; auditoria de conversão | notificar operação; atualizar portal |

## 2) Ordem de Serviço (OS)

```mermaid
stateDiagram-v2
    [*] --> ABERTA
    ABERTA --> EM_EXECUCAO: iniciar_execucao
    ABERTA --> CANCELADA: cancelar_os

    EM_EXECUCAO --> BLOQUEADA: bloquear_os
    EM_EXECUCAO --> AGUARDANDO_PECA: aguardar_peca
    EM_EXECUCAO --> EM_QUALIDADE: enviar_para_qualidade
    EM_EXECUCAO --> CANCELADA: cancelar_os

    BLOQUEADA --> EM_EXECUCAO: desbloquear_os
    BLOQUEADA --> CANCELADA: cancelar_os

    AGUARDANDO_PECA --> EM_EXECUCAO: peca_recebida
    AGUARDANDO_PECA --> CANCELADA: cancelar_os

    EM_QUALIDADE --> PRONTA: aprovar_qualidade
    EM_QUALIDADE --> EM_EXECUCAO: reprovar_qualidade

    PRONTA --> ENTREGUE: entregar_os
    ENTREGUE --> ENCERRADA: encerrar_os
```

### Matriz de transições de OS

| De | Para | Evento disparador | Perfis autorizados | Pré-condições | Pós-condições | Side effects |
|---|---|---|---|---|---|---|
| ABERTA | EM_EXECUCAO | `iniciar_execucao` | tecnico, supervisor, admin | orçamento vinculado aprovado; recursos alocados | status atualizado; histórico de início | notificar cliente (opcional); atualizar portal |
| ABERTA | CANCELADA | `cancelar_os` | supervisor, admin | sem execução iniciada | status atualizado; motivo registrado | notificar cliente; atualizar portal |
| EM_EXECUCAO | BLOQUEADA | `bloquear_os` | tecnico, supervisor, admin | bloqueio justificado | status atualizado; pendência registrada | notificar operação; atualizar portal |
| EM_EXECUCAO | AGUARDANDO_PECA | `aguardar_peca` | tecnico, compras, supervisor, admin | peça pendente identificada | status atualizado; item pendente registrado | notificar compras e cliente; atualizar portal |
| EM_EXECUCAO | EM_QUALIDADE | `enviar_para_qualidade` | tecnico, supervisor, admin | checklist técnico concluído | status atualizado; histórico de envio | notificar qualidade; atualizar portal |
| EM_EXECUCAO | CANCELADA | `cancelar_os` | supervisor, admin | justificativa aprovada | status atualizado; auditoria de cancelamento | notificar cliente; atualizar portal |
| BLOQUEADA | EM_EXECUCAO | `desbloquear_os` | supervisor, admin | impedimento removido | status atualizado; registro de desbloqueio | notificar time técnico; atualizar portal |
| BLOQUEADA | CANCELADA | `cancelar_os` | supervisor, admin | justificativa aprovada | status atualizado; auditoria de cancelamento | notificar cliente; atualizar portal |
| AGUARDANDO_PECA | EM_EXECUCAO | `peca_recebida` | compras, supervisor, admin | peça recebida em estoque | status atualizado; vínculo com recebimento | notificar técnico; atualizar portal |
| AGUARDANDO_PECA | CANCELADA | `cancelar_os` | supervisor, admin | justificativa aprovada | status atualizado; auditoria de cancelamento | notificar cliente; atualizar portal |
| EM_QUALIDADE | PRONTA | `aprovar_qualidade` | qualidade, supervisor, admin | inspeção aprovada | status atualizado; laudo anexado | notificar atendimento; atualizar portal |
| EM_QUALIDADE | EM_EXECUCAO | `reprovar_qualidade` | qualidade, supervisor, admin | inspeção reprovada | status atualizado; não conformidade registrada | notificar técnico; atualizar portal |
| PRONTA | ENTREGUE | `entregar_os` | atendimento, supervisor, admin | agendamento de entrega confirmado | status atualizado; comprovante registrado | notificar cliente; atualizar portal |
| ENTREGUE | ENCERRADA | `encerrar_os` | atendimento, financeiro, admin | documentação e faturamento concluídos | status atualizado; encerramento auditado | atualizar portal; disparar pesquisa de satisfação |

## 3) Estratégia de validação central no backend

- Criar um componente único de domínio (ex.: `TransitionValidator`) para validar **toda** alteração de status.
- API não altera estado diretamente: ela chama o validador com `(entidade, estado_atual, estado_destino, evento, perfil, contexto)`.
- O validador bloqueia transições inválidas quando:
  - par `(estado_atual, estado_destino)` não existe na matriz;
  - evento não corresponde à transição esperada;
  - perfil não autorizado;
  - pré-condição não satisfeita.
- Em caso de sucesso:
  - aplica mudança de status;
  - executa pós-condições;
  - registra auditoria/histórico;
  - dispara side effects de notificação e atualização de portal.

Esse padrão centraliza regra de negócio e evita inconsistências entre diferentes endpoints da API.

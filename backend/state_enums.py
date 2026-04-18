"""Enums formais de estado para Atendimento, Orçamento e Ordem de Serviço."""

from __future__ import annotations

from enum import Enum


class AtendimentoState(str, Enum):
    """Estados válidos de um Atendimento."""

    ABERTO = "aberto"
    EM_AVALIACAO = "em_avaliacao"
    CONVERTIDO = "convertido"
    CANCELADO = "cancelado"


class OrcamentoState(str, Enum):
    """Estados válidos de um Orçamento."""

    RASCUNHO = "rascunho"
    ENVIADO = "enviado"
    APROVADO = "aprovado"
    REJEITADO = "rejeitado"
    EXPIRADO = "expirado"
    CONVERTIDO = "convertido"


class OSState(str, Enum):
    """Estados válidos de uma Ordem de Serviço."""

    ABERTA = "aberta"
    EM_EXECUCAO = "em_execucao"
    BLOQUEADA_PECA = "bloqueada_peca"
    QUALIDADE = "qualidade"
    PRONTA_ENTREGA = "pronta_entrega"
    ENTREGUE = "entregue"
    ENCERRADA = "encerrada"


class EntityKind(str, Enum):
    """Tipos de entidade suportados pela máquina de estados de domínio."""

    ATENDIMENTO = "atendimento"
    ORCAMENTO = "orcamento"
    OS = "os"


ATENDIMENTO_TRANSITIONS: dict[tuple[AtendimentoState, AtendimentoState], str] = {
    (AtendimentoState.ABERTO, AtendimentoState.EM_AVALIACAO): "iniciar_avaliacao",
    (AtendimentoState.EM_AVALIACAO, AtendimentoState.CONVERTIDO): "converter_em_orcamento",
    (AtendimentoState.ABERTO, AtendimentoState.CANCELADO): "cancelar_atendimento",
    (AtendimentoState.EM_AVALIACAO, AtendimentoState.CANCELADO): "cancelar_atendimento",
}


ORCAMENTO_TRANSITIONS: dict[tuple[OrcamentoState, OrcamentoState], str] = {
    (OrcamentoState.RASCUNHO, OrcamentoState.ENVIADO): "enviar_orcamento",
    (OrcamentoState.ENVIADO, OrcamentoState.APROVADO): "aprovar_orcamento",
    (OrcamentoState.ENVIADO, OrcamentoState.REJEITADO): "rejeitar_orcamento",
    (OrcamentoState.ENVIADO, OrcamentoState.EXPIRADO): "expirar_orcamento",
    (OrcamentoState.APROVADO, OrcamentoState.CONVERTIDO): "converter_em_os",
}


OS_TRANSITIONS: dict[tuple[OSState, OSState], str] = {
    (OSState.ABERTA, OSState.EM_EXECUCAO): "iniciar_execucao",
    (OSState.EM_EXECUCAO, OSState.BLOQUEADA_PECA): "bloquear_por_peca",
    (OSState.BLOQUEADA_PECA, OSState.EM_EXECUCAO): "retomar_apos_peca",
    (OSState.EM_EXECUCAO, OSState.QUALIDADE): "enviar_para_qualidade",
    (OSState.QUALIDADE, OSState.EM_EXECUCAO): "reprovar_qualidade",
    (OSState.QUALIDADE, OSState.PRONTA_ENTREGA): "aprovar_qualidade",
    (OSState.PRONTA_ENTREGA, OSState.ENTREGUE): "entregar_os",
    (OSState.ENTREGUE, OSState.ENCERRADA): "encerrar_os",
}


TERMINAL_STATES: dict[EntityKind, frozenset[str]] = {
    EntityKind.ATENDIMENTO: frozenset({
        AtendimentoState.CONVERTIDO.value,
        AtendimentoState.CANCELADO.value,
    }),
    EntityKind.ORCAMENTO: frozenset({
        OrcamentoState.REJEITADO.value,
        OrcamentoState.EXPIRADO.value,
        OrcamentoState.CONVERTIDO.value,
    }),
    EntityKind.OS: frozenset({OSState.ENCERRADA.value}),
}

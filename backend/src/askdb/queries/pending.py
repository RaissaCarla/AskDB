import threading
import time

from askdb.queries.errors import ApplicationError
from askdb.queries.models import SqlProposal


class PendingSqlRegistry:
    def __init__(self, *, ttl_seconds: float = 600, clock=time.monotonic):
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._items: dict[str, tuple[SqlProposal, float]] = {}
        self._lock = threading.Lock()

    def register(self, proposal: SqlProposal) -> str:
        if proposal.validation.status != "approved":
            raise ApplicationError("proposal_not_approved", "Uma proposta bloqueada não pode aguardar execução.")
        with self._lock:
            self._items = {key: item for key, item in self._items.items()
                           if item[1] > self.clock() and item[0].session_id != proposal.session_id}
            if proposal.id in self._items:
                raise ApplicationError("proposal_unavailable", "O identificador da proposta já foi utilizado.")
            self._items[proposal.id] = (proposal.model_copy(deep=True), self.clock() + self.ttl_seconds)
        return proposal.id

    def _lookup(self, proposal_id: str, connection_id: str, session_id: str) -> SqlProposal:
        item = self._items.get(proposal_id)
        if item is None or item[1] <= self.clock():
            self._items.pop(proposal_id, None)
            raise ApplicationError("proposal_unavailable", "A proposta não existe, expirou ou já foi consumida.")
        proposal = item[0]
        if proposal.connection_id != connection_id or proposal.session_id != session_id:
            raise ApplicationError("connection_mismatch", "A proposta pertence a outra conexão ou sessão.")
        return proposal

    def get(self, proposal_id: str, connection_id: str, session_id: str) -> SqlProposal:
        with self._lock:
            return self._lookup(proposal_id, connection_id, session_id).model_copy(deep=True)

    def consume(self, proposal_id: str, connection_id: str, session_id: str) -> SqlProposal:
        with self._lock:
            proposal = self._lookup(proposal_id, connection_id, session_id)
            self._items.pop(proposal_id)
            return proposal.model_copy(deep=True)

    def invalidate_session(self, session_id: str):
        with self._lock:
            self._items = {key: item for key, item in self._items.items() if item[0].session_id != session_id}

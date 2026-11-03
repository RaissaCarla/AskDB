class ApplicationError(Exception):
    """Erro público com mensagem fixa; detalhes externos não são propagados."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

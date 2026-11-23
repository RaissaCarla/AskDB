from pydantic import SecretStr

from askdb.llm.http import completion_content, request_json, usage_counts
from askdb.llm.models import LLMContext, LLMProfile, LLMResponse
from askdb.queries.errors import ApplicationError


class OpenAILLMClientAdapter:
    def __init__(self, profile: LLMProfile, api_key: SecretStr, *, timeout=120.0,
                 connect_timeout=5.0, transport=None):
        if profile.provider != "openai" or not isinstance(api_key, SecretStr) or not api_key.get_secret_value().strip():
            raise ApplicationError("configuration_error", "Confira o perfil OpenAI e sua chave em execução.")
        self.profile = profile
        self._api_key = api_key
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.transport = transport

    def generate(self, context: LLMContext) -> LLMResponse:
        payload = {"model": self.profile.model, "messages": context.messages, "stream": False,
                   "max_completion_tokens": self.profile.output_reserve, "store": False}
        result = request_json(self.profile.endpoint + "/chat/completions", payload,
                              headers={"Authorization": "Bearer " + self._api_key.get_secret_value()},
                              timeout=self.timeout, connect_timeout=self.connect_timeout, transport=self.transport)
        sql = completion_content(result)
        input_tokens, output_tokens = usage_counts(result)
        return LLMResponse(sql=sql, input_tokens=input_tokens, output_tokens=output_tokens)

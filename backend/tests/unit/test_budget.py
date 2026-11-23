import hashlib
import json
import os
from pathlib import Path
import zipfile

import pytest

from askdb.knowledge.budget import TokenBudgetPolicy, utf8_upper_bound
from askdb.llm.models import LLMContext, LLMProfile
from askdb.queries.errors import ApplicationError


def test_budget_boundaries_and_unknown_model():
    context = LLMContext(messages=[{"role": "user", "content": "pergunta"}])
    policy = TokenBudgetPolicy(LLMProfile())
    checked = policy.validate("a" * 8000, context)
    assert checked.memory_tokens_estimate == 8000
    with pytest.raises(ApplicationError) as error:
        policy.validate("a" * 8001, context)
    assert error.value.code == "context_limit_exceeded"
    large = LLMContext(messages=[{"role": "system", "content": "x" * 16000}])
    with pytest.raises(ApplicationError):
        policy.validate("", large)
    smaller = TokenBudgetPolicy(LLMProfile(context_window=2200, output_reserve=2048))
    with pytest.raises(ApplicationError):
        smaller.validate("", context)
    with pytest.raises(ApplicationError) as error:
        TokenBudgetPolicy(LLMProfile(model="unknown")).validate("", context)
    assert error.value.code == "context_budget_unavailable"
    assert utf8_upper_bound("ação🙂") > len("ação🙂")


def test_exact_input_threshold_includes_envelope():
    context = LLMContext(messages=[{"role": "user", "content": "x"}])
    expected = utf8_upper_bound(json.dumps(context.messages, ensure_ascii=False, separators=(",", ":"))) + 576
    profile = LLMProfile(context_window=4096, output_reserve=4096 - expected)
    assert TokenBudgetPolicy(profile).validate("", context).input_tokens_estimate == expected
    with pytest.raises(ApplicationError):
        TokenBudgetPolicy(profile).validate("", LLMContext(messages=[{"role": "user", "content": "xx"}]))


def test_official_tokenizers_are_bounded_when_artifacts_available():
    folder = os.getenv("ASKDB_TOKENIZER_FIXTURES")
    if not folder:
        pytest.skip("Validação offline opcional: defina ASKDB_TOKENIZER_FIXTURES para os artefatos oficiais.")
    from tokenizers import Tokenizer
    manifest = json.loads((Path(__file__).parents[1] / "fixtures/tokenizer-manifest.json").read_text(encoding="utf-8"))
    corpus = ["", "Quais são os produtos mais vendidos?", "SELECT nome, SUM(quantidade) FROM produtos GROUP BY nome;",
              "ação, coração, João, São Paulo", "中文 日本語 العربية 🙂🚀", "\n\t\x00" * 100,
              "é" * 8000, "a" * 8000, "{}[]<>|;\\\"'" * 500,
              "".join(chr(n) for n in range(1, 2048))]
    for item in manifest["artifacts"]:
        raw = (Path(folder) / item["filename"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item["sha256"]
        if "zip_member" in item:
            with zipfile.ZipFile(Path(folder) / item["filename"]) as package:
                raw = package.read(item["zip_member"])
        tokenizer = Tokenizer.from_str(raw.decode("utf-8"))
        for text in corpus:
            assert len(tokenizer.encode(text, add_special_tokens=False).ids) <= utf8_upper_bound(text)


def test_openai_tokenizer_is_bounded_when_cache_available():
    if not os.getenv("ASKDB_TOKENIZER_FIXTURES"):
        pytest.skip("Validação offline opcional do tokenizador OpenAI.")
    import tiktoken
    tokenizer = tiktoken.encoding_for_model("gpt-4.1-mini")
    corpus = ["Quais são os produtos mais vendidos?", "SELECT nome FROM produtos;", "ação🙂中文",
              "\x00\n\t" * 100, "é" * 8000, "".join(chr(n) for n in range(1,2048))]
    for text in corpus:
        assert len(tokenizer.encode(text, disallowed_special=())) <= utf8_upper_bound(text)

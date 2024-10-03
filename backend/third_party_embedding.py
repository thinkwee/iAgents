from llama_index.embeddings.dashscope import (
    DashScopeEmbedding,
    DashScopeTextEmbeddingModels,
    DashScopeTextEmbeddingType,
)
import yaml
import os
import emoji
from typing import Any, List
from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.embeddings import BaseEmbedding
from zhipuai import ZhipuAI
import re
from unidecode import unidecode

file_path = os.path.dirname(__file__)
project_path = os.path.dirname(file_path)
global_config = yaml.safe_load(open(os.path.join(project_path, "config/global.yaml"), "r"))

QWEN_API_KEY = global_config.get("backend").get("qwen_api_key")
os.environ["DASHSCOPE_API_KEY"] = QWEN_API_KEY
GLM_API_KEY = global_config.get("backend").get("glm_api_key")
os.environ["ZHIPU_API_KEY"] = GLM_API_KEY

dashscope_embedder = DashScopeEmbedding(
    model_name=DashScopeTextEmbeddingModels.TEXT_EMBEDDING_V2,
    text_type=DashScopeTextEmbeddingType.TEXT_TYPE_DOCUMENT,
)


class ZhipuEmbeddings(BaseEmbedding):
    _model: ZhipuAI = PrivateAttr()
    _instruction: str = PrivateAttr()

    def __init__(
        self,
        instruction: str = "",
        instructor_model_name: str = "zhipu/embedding-3",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._instruction = instruction
        self._client = ZhipuAI(api_key=GLM_API_KEY) 

    @classmethod
    def class_name(cls) -> str:
        return "zhipu"

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return self._get_text_embedding(text)

    def _clean_text(self, text: str) -> str:
        text = re.sub(r'[\x00-\x1f\x7f-\x9f\u200b-\u200d\uFEFF]', '', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', '', text)
        text = emoji.replace_emoji(text, replace='')
        return text.strip()

    def _get_query_embedding(self, query: str) -> List[float]:
        clean_query = self._clean_text(query)
        response = self._client.embeddings.create(
            model="embedding-3",
            input=[clean_query],
            dimensions=256
        )
        return response.data[0].embedding

    def _get_text_embedding(self, text: str) -> List[float]:
        clean_text = self._clean_text(text)
        response = self._client.embeddings.create(
            model="embedding-3",
            input=[clean_text],
            dimensions=256
        )
        return response.data[0].embedding

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        clean_texts = [self._clean_text(text) for text in texts]
        response = self._client.embeddings.create(
            model="embedding-3",
            input=clean_texts,
            dimensions=256
        )
        return [data.embedding for data in response.data]

import os

from llama_index.llms.ollama import Ollama
import yaml
from tenacity import retry
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential

file_path = os.path.dirname(__file__)
project_path = os.path.dirname(file_path)
global_config = yaml.safe_load(open(os.path.join(project_path, "config/global.yaml"), "r"))

MAX_RETRY_TIMES = global_config.get("agent").get("max_query_retry_times", 10)
OLLAMA_MODEL_NAME = global_config.get("backend").get("ollama_model_name", "qwen2:0.5b")

model = Ollama(model=OLLAMA_MODEL_NAME, request_timeout=100.0)


@retry(wait=wait_exponential(min=10, max=300), stop=stop_after_attempt(MAX_RETRY_TIMES))
def query_ollama(prompt):
    return model.complete(prompt).text
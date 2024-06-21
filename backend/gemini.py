import os

import google.generativeai as genai
import yaml
from tenacity import retry
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential

file_path = os.path.dirname(__file__)
project_path = os.path.dirname(file_path)
global_config = yaml.safe_load(open(os.path.join(project_path, "config/global.yaml"), "r"))

MAX_RETRY_TIMES = global_config.get("agent").get("max_query_retry_times", 10)
GOOGLE_API_KEY = global_config.get("backend").get("google_api_key")

genai.configure(api_key=GOOGLE_API_KEY)

model_10 = genai.GenerativeModel('gemini-1.0-pro-latest', generation_config={"max_output_tokens": 2048})
model_15 = genai.GenerativeModel('gemini-1.5-pro-latest', generation_config={"max_output_tokens": 8192})


@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(MAX_RETRY_TIMES))
def query_gemini(q):
    try:
        response = model_10.generate_content(q)
        return response.text
    except ValueError as e:
        if hasattr(e, 'response'):
            response = e.response
            response_text = ""
            for candidate in response.candidates:
                response_text += " ".join([part.text for part in candidate.content.parts])
            return response_text
        else:
            raise e

@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(MAX_RETRY_TIMES))
def query_gemini_15(q):
    try:
        response = model_15.generate_content(q)
        return response.text
    except ValueError as e:
        if hasattr(e, 'response'):
            response = e.response
            response_text = ""
            for candidate in response.candidates:
                response_text += " ".join([part.text for part in candidate.content.parts])
            return response_text
        else:
            raise e

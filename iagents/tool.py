import json
import logging
import os
import re
from abc import ABC
from time import sleep
import faiss
import numpy as np
import pandas as pd

import yaml

from iagents.sql import *
from iagents.util import iAgentsLogger
from openai import OpenAI

from tenacity import retry
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential

file_path = os.path.dirname(__file__)
project_path = os.path.dirname(file_path)
global_config = yaml.safe_load(open(os.path.join(project_path, "config/global.yaml"), "r"))
OPENAI_API_KEY = global_config.get("backend").get("openai_api_key")
BASE_URL = global_config.get("backend").get("base_url", None)
max_tool_retry_times = global_config.get("agent").get("max_tool_retry_times")
MAX_RETRY_TIMES = global_config.get("agent").get("max_query_retry_times", 10)


class Tool(ABC):
    """base class for tool,
    defines the max retry times
    """

    def __init__(self, tool_name) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.max_tool_retry_times = max_tool_retry_times
        with open(os.path.join(project_path, "prompts", "tool_prompt.json"), "r") as f:
            self.tool_prompt = json.load(f)


class FaissTool(Tool):
    """faiss retrieval
    """

    def __init__(self, memory_file_path, tool_name="faiss") -> None:
        super().__init__(tool_name)
        self.emb_client = OpenAI(api_key=OPENAI_API_KEY, base_url=BASE_URL)
        self.memory_file_path = memory_file_path
        self.exist_memory = True
        if os.path.exists(self.memory_file_path):
            raw_emb_df = pd.read_csv(self.memory_file_path, sep='\t')
            self.emb_memory = np.array(
                raw_emb_df['emb'].apply(lambda x: np.fromstring(x[1:-1], sep=',')).tolist())
            self.text_memory = raw_emb_df['text'].to_list()
            self.emb_memory /= np.linalg.norm(self.emb_memory, axis=1)[:, np.newaxis]
            self.index = faiss.IndexFlatIP(256)
            self.index.add(self.emb_memory)
        else:
            self.exist_memory = False

    @retry(wait=wait_exponential(min=10, max=300), stop=stop_after_attempt(MAX_RETRY_TIMES))
    def _get_embedding_v2(self, text, model="text-embedding-ada-002"):
        if not text or len(text) == 0:
            text = "None"
        text = text.replace("\n", " ")
        return self.emb_client.embeddings.create(model=model, input=text,
                                                 encoding_format="float").data[0].embedding[:256]

    @retry(wait=wait_exponential(min=10, max=300), stop=stop_after_attempt(MAX_RETRY_TIMES))
    def _get_embedding(self, text, model="text-embedding-3-small"):
        if not text or len(text) == 0:
            text = "None"
        text = text.replace("\n", " ")
        return self.emb_client.embeddings.create(input=[text], model=model, dimensions=256).data[0].embedding

    def query(self, text, topk=3):
        # return distances, indices and text, all in the shape of [topk]
        ret_dis = []
        ret_indices = []
        ret_text = []
        topk = max(1, topk)

        if self.exist_memory:
            query_emb = self._get_embedding(text)
            query = np.asarray([query_emb])
            query /= np.linalg.norm(query)
            distances, indices = self.index.search(query, topk)

            for i in range(topk):
                ret_dis.append(distances[0][i])
                ret_indices.append(indices[0][i])
                ret_text.append(self.text_memory[indices[0][i]])

        iAgentsLogger.log(text, "\n".join(["{}: {}".format(dis, ans) for dis, ans in zip(ret_dis, ret_text)]),
                         "Executing Faiss")

        return ret_dis, ret_indices, ret_text


class SqlTool(Tool):

    def __init__(self, tool_name="chat_history_sql") -> None:
        super().__init__(tool_name)

    def get_context_bykeyword_current(self, keyword, sender, receiver, limit=40, window=2):
        sql_command = """
            WITH relevant_messages AS (
                SELECT id, timestamp, sender, receiver, message
                FROM chats
                WHERE message LIKE %s
            ),
            context AS (
                SELECT id, timestamp, sender, receiver, message
                FROM chats
                WHERE 
                    ((sender = %s AND receiver = %s) OR (sender = %s AND receiver = %s))
                    AND 
                    (sender NOT LIKE '%Agent%' AND receiver NOT LIKE '%Agent%')
            ),
            relevant_ids AS (
                SELECT id,
                    LAG(id, %s, id) OVER (ORDER BY id) AS prev_id,
                    LEAD(id, %s, id) OVER (ORDER BY id) AS next_id
                FROM context
            ),
            relevant_context_ids AS (
                SELECT DISTINCT r.id AS message_id, r.timestamp AS message_timestamp, r.sender AS message_sender, r.receiver AS message_receiver, r.message AS message_content,
                                c.id AS context_id, c.timestamp AS context_timestamp, c.sender AS context_sender, c.receiver AS context_receiver, c.message AS context_message
                FROM relevant_messages r
                JOIN relevant_ids ri ON r.id = ri.id
                JOIN context c ON c.id BETWEEN ri.prev_id AND ri.next_id
            )
            SELECT context_id AS id, context_timestamp AS timestamp, context_sender AS sender, context_receiver AS receiver, context_message AS message
            FROM relevant_context_ids
            ORDER BY message_id
            LIMIT %s;
        """
        window = max(window, 1)
        limit = max(limit, 10)
        params = ("%" + keyword + "%", sender, receiver, receiver, sender, window, window, limit)

        sql_execute_results = self.execute_sql(sql_command, params)
        return sql_execute_results

    def get_context_bykeyword(self, keyword, sender, receiver, limit=40, window=2):
        sql_command = """
            WITH relevant_messages AS (
                SELECT id, timestamp, sender, receiver, message
                FROM chats
                WHERE message LIKE %s
            ),
            context AS (
                SELECT id, timestamp, sender, receiver, message
                FROM chats
                WHERE 
                    ((sender = %s AND receiver != %s) OR (sender != %s AND receiver = %s))
                    AND 
                    (sender NOT LIKE '%Agent%' AND receiver NOT LIKE '%Agent%')
            ),
            relevant_ids AS (
                SELECT id,
                    LAG(id, %s, id) OVER (ORDER BY id) AS prev_id,
                    LEAD(id, %s, id) OVER (ORDER BY id) AS next_id
                FROM context
            ),
            relevant_context_ids AS (
                SELECT DISTINCT r.id AS message_id, r.timestamp AS message_timestamp, r.sender AS message_sender, r.receiver AS message_receiver, r.message AS message_content,
                                c.id AS context_id, c.timestamp AS context_timestamp, c.sender AS context_sender, c.receiver AS context_receiver, c.message AS context_message
                FROM relevant_messages r
                JOIN relevant_ids ri ON r.id = ri.id
                JOIN context c ON c.id BETWEEN ri.prev_id AND ri.next_id
            )
            SELECT context_id AS id, context_timestamp AS timestamp, context_sender AS sender, context_receiver AS receiver, context_message AS message
            FROM relevant_context_ids
            ORDER BY message_id
            LIMIT %s;
        """
        window = max(window, 1)
        limit = max(limit, 10)
        params = ("%" + keyword + "%", sender, receiver, receiver, sender, window, window, limit)

        sql_execute_results = self.execute_sql(sql_command, params)
        return sql_execute_results

    def get_friends(self, master):
        sql_command = """
        SELECT users.name
            FROM friendships
            JOIN users ON friendships.friend_id = users.id
            WHERE friendships.user_id = (
                SELECT id FROM users WHERE name = %s
            )
        """
        params = (master,)
        sql_execute_results = self.execute_sql(sql_command, params)
        return sql_execute_results

    def get_current_chat_history(self, sender, receiver, limit=20):
        sql_command = """
            SELECT timestamp, sender, receiver, message 
            FROM chats 
            WHERE 
                (sender = %s AND receiver = %s) OR (sender = %s AND receiver = %s) 
            ORDER BY id DESC
            LIMIT %s
        """
        limit = max(limit, 10)
        params = (sender, receiver, receiver, sender, limit)
        sql_execute_results = self.execute_sql(sql_command, params)
        return sql_execute_results

    def get_other_chat_history(self, sender, receiver, limit=30):
        sql_command = """
            SELECT timestamp, sender, receiver, message
            FROM chats 
            WHERE 
                ((sender = %s AND receiver != %s) OR (sender != %s AND receiver = %s))
                AND 
                (sender NOT LIKE '%Agent%' AND receiver NOT LIKE '%Agent%') 
            ORDER BY id DESC
            LIMIT %s
        """

        limit = max(limit, 10)
        params = (sender, receiver, receiver, sender, limit)
        sql_execute_results = self.execute_sql(sql_command, params)
        return sql_execute_results

    def execute_sql(self, sql_command, params=None):
        full_sql_command = "SQL COMMAND:\n{}\nPARAMS:\n{}\n".format(str(sql_command), str(params))
        sql_results = exec_sql(sql_command=sql_command, params=params)
        iAgentsLogger.log(full_sql_command, "\n".join([str(item) for item in sql_results]), "Executing SQL")
        return sql_results


class JsonFormatTool(Tool):

    def __init__(self, query_func, tool_name="json_format") -> None:
        super().__init__(tool_name)
        self.query_func = query_func

    def json_check(self, text, json_format) -> bool:
        """check if the text is aligned with the json_format

        Args:
            text (str): text
            json_format (dict): json_format
        """
        try:
            text_json = eval(text)
            for key in json_format:
                assert isinstance(text_json[key], type(json_format[key]))
        except Exception as e:
            return False
        return True

    def json_reformat(self, text, json_format) -> str:
        """retry and ask llm to rewrite the text in json format

        Args:
            text (str): text
            json_format (dict): json_format

        Returns:
            str: llm response in json format
        """
        if not text:
            return str(json_format)
        json_format_str = str(json_format)
        reformat_prompt = "\n".join(self.tool_prompt['json_reformat'])
        try_idx = 0
        while try_idx < self.max_tool_retry_times:
            text = text.replace("null", '"Error"')
            text = text.replace("None", '"Error"')
            text = text.replace("```json", "")
            text = text.replace("```", "")
            try_idx += 1
            if self.json_check(text, json_format):
                return text
            input_text = reformat_prompt.format(text=text, json_format=json_format_str)
            text = self.query_func(input_text)
            iAgentsLogger.log(input_text, text, "Trial {}. on reformatting json text".format(str(try_idx)))
            sleep(1)
        if self.json_check(text, json_format):
            return text
        else:
            # for key in json_format:
            #     json_format[key] = "Error"
            return str(json_format)

    def json_reformat_woreference(self, text):
        """similar to json_reformat but reference-free
        """
        reformat_prompt = "\n".join(self.tool_prompt['json_reformat_woreference'])
        try_idx = 0
        if not text:
            return str(dict())
        while try_idx < self.max_tool_retry_times:
            text = text.replace("null", '"Error"')
            text = text.replace("None", '"Error"')
            text = text.replace("```json", "")
            text = text.replace("```", "")
            try_idx += 1
            if self.json_check(text, dict()):
                return text
            input_text = reformat_prompt.format(text=text)
            text = self.query_func(input_text)
            iAgentsLogger.log(input_text, text, "Trial {} on reformatting json text".format(str(try_idx)))
            sleep(1)
        if self.json_check(text, dict()):
            return text
        else:
            return str(dict())


class MindFillTool(Tool):
    """The tool for listing and updating the pinned facts in mindmap
    """

    def __init__(self, query_func, tool_name="mind_fill") -> None:
        super().__init__(tool_name)
        self.query_func = query_func
        self.json_tool = JsonFormatTool(query_func)
        self.infonav_plan = ""
        self.know_facts = dict()
        self.unknown_facts = set()

    def set_infonav(self, text):
        self.infonav_plan = text

    def set_unknown_facts(self, text):
        matches = re.findall(r'\[([^\[\]]+)\]', text)
        self.unknown_facts = set(matches)

    def get_known_facts(self):
        ret = []
        for fact in self.know_facts:
            ret.append("known fact: {} --> {}".format(fact, self.know_facts[fact]))
        return "\n".join(ret)

    def get_unknown_facts(self):
        ret = []
        for fact in self.unknown_facts:
            ret.append("unknown fact: {}".format(fact))
        return "\n".join(ret)

    def fill_mind(self, infonav, filled_json_text):
        filled_json = self.json_tool.json_reformat_woreference(filled_json_text)
        filled_json = eval(filled_json)
        for key in filled_json:
            if "[{}]".format(key) in infonav and key in self.unknown_facts:
                infonav = infonav.replace("[{}]".format(key),
                                          "[{}](Solved, which is {})".format(key, str(filled_json[key])))
                iAgentsLogger.log(
                    instruction="[update pinned facts]: {} --> {}".format(key, str(filled_json[key])))
                if "unknown" not in str(filled_json[key]).lower():
                    self.unknown_facts.remove(key)
                self.know_facts[key] = str(filled_json[key])
        return infonav
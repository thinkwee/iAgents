import json
import os
import re
from abc import ABC, abstractmethod
import yaml

from backend.gemini import query_gemini
from backend.gpt import query_claude, query_gpt, query_gpt4
from backend.third_party import *
from iagents.tool import FaissTool, JsonFormatTool, MindFillTool, SqlTool
from iagents.util import iAgentsLogger
from iagents.llamaindex import LlamaIndexer

# Load global config
file_path = os.path.dirname(__file__)
project_path = os.path.dirname(file_path)

try:
    with open(os.path.join(project_path, "config/global.yaml"), "r") as f:
        global_config = yaml.safe_load(f)
except FileNotFoundError:
    raise FileNotFoundError("Config file not found.")
except yaml.YAMLError as exc:
    raise yaml.YAMLError(f"Error in configuration file: {exc}")

class Agent(ABC):
    """The Base class for Agent.
    It defines the backend LLM of agent and how to assemble the prompt of agents.    
    """

    def __init__(self, master: str, backend: str, task: str, is_assistant: bool = False) -> None:
        """Initialize the Agent.

        Args:
            master (str): Name of the human master of agent (username in the chat database).
            backend (str): Name of the backend LLM (gemini/gpt/gpt4).
            task (str): Task prompt.
            is_assistant (bool, optional): The agent who raises task is the instructor, the other is the assistant. Defaults to False.
        """
        super().__init__()
        self.master = master
        self.task = task
        self.agent_chat_history = []
        self.backend = backend
        self.query_func = self._get_query_func(backend)
        self.is_assistant = is_assistant

        prompt_path = os.path.join(project_path, "prompts")
        system_prompt_filepath = os.path.join(prompt_path, "assistant_system_prompt.json" if is_assistant else "instructor_system_prompt.json")
        with open(system_prompt_filepath, "r") as f:
            self.system_prompt = json.load(f)

        with open(os.path.join(project_path, "prompts", "tool_prompt.json"), "r") as f:
            self.tool_prompt = json.load(f)

        self.sql_tool = SqlTool()
        self.json_tool = JsonFormatTool(self.query_func)
        self.mindfill_tool = MindFillTool(self.query_func)

    def _get_query_func(self, backend: str):
        """Get the query function based on the backend LLM.

        Args:
            backend (str): Name of the backend LLM.

        Returns:
            function: Query function for the specified backend.

        Raises:
            ValueError: If the backend is not implemented.
        """
        if backend == "gemini":
            return query_gemini
        elif backend == "gpt":
            return query_gpt
        elif backend == "gpt4":
            return query_gpt4
        elif backend == "claude":
            return query_claude
        elif backend == "ollama":
            from backend.ollama import query_ollama
            return query_ollama
        elif backend == "deepseek":
            return query_deepseek
        elif backend == "qwen":
            return query_qwen
        elif backend == "ernie":
            return query_ernie
        elif backend == "glm":
            return query_glm
        elif backend == "hunyuan":
            return query_hunyuan
        elif backend == "spark":
            return query_spark
        else:
            raise ValueError(f"{backend} backend not implemented")

    def set_master(self, master: str) -> None:
        """Set the master of the agent.

        Args:
            master (str): Name of the human master of agent.
        """
        self.master = master

    @abstractmethod
    def get_other_chat_history(self, receiver: str, communication_history: list[str] = None) -> str:
        """Get the context from chatting with other friends.

        Args:
            receiver (str): The name of user in current chatting.
            communication_history (list[str], optional): The chat history between two agents. Defaults to None.

        Returns:
            str: Retrieved chat history as the context for assembling the query prompt.
        """
        pass

    @abstractmethod
    def get_current_chat_history(self, receiver: str, communication_history: list[str]) -> str:
        """Get the context from current chatting.

        Args:
            receiver (str): The name of user in current chatting.
            communication_history (list[str]): The chat history between two agents.

        Returns:
            str: Retrieved chat history as the context for assembling the query prompt.
        """
        pass

    def assemble_prompt(self, receiver: str, communication_history: list[str]) -> str:
        """Assemble the query prompt.

        Args:
            receiver (str): The name of user in current chatting.
            communication_history (list[str]): The chat history between two agents.

        Returns:
            str: Assembled prompt.
        """
        current_chat_history = self.get_current_chat_history(receiver, communication_history)
        other_chat_history = self.get_other_chat_history(receiver, communication_history)
        agent_profile_prompt = self.sql_tool.get_agent_profile_prompt(self.master)

        system_prompt = "\n".join([
            agent_profile_prompt,
            "\n".join(self.system_prompt['role']).format(master=self.master, contact=receiver),
            "\n".join(self.system_prompt['chat_history']).format(master=self.master, contact=receiver, current_chat_history=current_chat_history, other_chat_history=other_chat_history),
            "\n".join(self.system_prompt['task']).format(contact=receiver, task=self.task),
            "\n".join(self.system_prompt['agent_chat_history']).format(contact=receiver, agent_chat_history="\n".join(communication_history), master=self.master),
            "\n".join(self.system_prompt['return_format']),
        ])

        return system_prompt

    def _query(self, receiver: str, communication_history: list[str]) -> str:
        """Send the query to backend LLM.

        Args:
            receiver (str): The name of user in current chatting.
            communication_history (list[str]): The chat history between two agents.

        Returns:
            str: LLM response.
        """
        query_str = self.assemble_prompt(receiver, communication_history)
        response = self.query_func(query_str)
        iAgentsLogger.log(query_str, response, f"Query to generate message from {self.master} to {receiver}")
        return response

    def query(self, receiver: str, communication_history: list[str]) -> str:
        """Wrap on the _query method to ensure the return format is correct.

        Args:
            receiver (str): The name of user in current chatting.
            communication_history (list[str]): The chat history between two agents.

        Returns:
            str: LLM response in JSON string.
        """
        raw_response = self._query(receiver, communication_history)
        response = raw_response
        iAgentsLogger.log(instruction=f"response generated from {self.master} to {receiver}\nthe reformatted message:\n{response}")
        return response

    def conclusion(self, communication_history: list[str]) -> str:
        """Summarize the agents' communication and give the final answer to the task.

        Args:
            communication_history (list[str]): The chat history between two agents.

        Returns:
            str: Final answer to the task.
        """
        query_str = "\n".join(self.tool_prompt['conclusion']).format(agent_communication="\n".join(communication_history), task=self.task)
        response = self.query_func(query_str)
        iAgentsLogger.log(query_str, response, "[Conclusion]")
        return response

    def get_friends(self) -> str:
        """Get all friends of one user.

        Returns:
            str: Friend list.
        """
        result_str = "\n"
        sql_execute_results = self.sql_tool.get_friends(self.master)
        for message in sql_execute_results:
            result_str += f"{message[0]}\n"
        return result_str


class VanillaAgent(Agent):
    """VanillaAgent uses SQL tool to get context."""

    def get_other_chat_history(self, receiver: str, communication_history: list[str] = None) -> str:
        result_str = "\n"
        sql_execute_results = self.sql_tool.get_other_chat_history(self.master, receiver)
        for message in sql_execute_results:
            result_str += f"from {message[1]} to {message[2]}: {message[3]}\n"
        return result_str

    def get_current_chat_history(self, receiver: str, communication_history: list[str]) -> str:
        result_str = "\n"
        sql_execute_results = self.sql_tool.get_current_chat_history(self.master, receiver)
        for message in sql_execute_results:
            result_str += f"from {message[1]} to {message[2]}: {message[3]}\n"
        return result_str


class ThinkAgent(VanillaAgent):
    """ThinkAgent inherits from VanillaAgent and utilizes InfoNav mechanism to manage the communication."""

    def __init__(self, master: str, backend: str, task: str, is_assistant: bool = False) -> None:
        super().__init__(master, backend, task, is_assistant)
        self.infonav_plan = None
        self.infonav_status = 0  # 0 for init plan; 1 for mark the unknown rationales in the plan; 2 for update the unknown rationales to known rationales

    def assemble_prompt_think(self, receiver: str, communication_history: list[str]) -> str:
        """InfoNav assembles the prompt for initializing/updating the plan.

        Args:
            receiver (str): The name of user in current chatting.
            communication_history (list[str]): The chat history between two agents.

        Returns:
            str: Assembled query prompt.
        """
        if self.infonav_status == 0:
            prompt_infonav = "\n".join(self.tool_prompt['infonav_init'])
            system_prompt = "\n".join([
                "\n".join(self.system_prompt['role']).format(master=self.master, contact=receiver),
                "\n".join(self.system_prompt['task']).format(contact=receiver, task=self.task), prompt_infonav
            ])
            self.infonav_status += 1
        elif self.infonav_status == 1:
            prompt_infonav = "\n".join(self.tool_prompt['infonav_mark'])
            system_prompt = "\n".join([
                "\n".join(self.system_prompt['role']).format(master=self.master, contact=receiver),
                prompt_infonav.format(task=self.task, infonav=self.infonav_plan)
            ])
            self.infonav_status += 1
        else:
            prompt_infonav = "\n".join(self.tool_prompt['infonav_update']).format(infonav=self.infonav_plan,
                                                                                  known_facts=self.mindfill_tool.get_known_facts(),
                                                                                  unknown_facts=self.mindfill_tool.get_unknown_facts())
            system_prompt = "\n".join([
                "\n".join(self.system_prompt['role']).format(master=self.master, contact=receiver),
                "\n".join(self.system_prompt['task']).format(contact=receiver, task=self.task),
                "\n".join(self.system_prompt['agent_chat_history']).format(contact=receiver, 
                                                                           agent_chat_history="\n".join(communication_history),
                                                                           master=self.master), prompt_infonav])

        return system_prompt

    def assemble_prompt(self, receiver: str, communication_history: list[str], current_chat_history: str, other_chat_history: str) -> str:
        agent_profile_prompt = self.sql_tool.get_agent_profile_prompt(self.master)
        system_prompt = "\n".join([
            agent_profile_prompt,
            "\n".join(self.system_prompt['role']).format(master=self.master, contact=receiver),
            "\n".join(self.system_prompt['chat_history']).format(master=self.master, contact=receiver, current_chat_history=current_chat_history, other_chat_history=other_chat_history),
            "\n".join(self.system_prompt['task']).format(contact=receiver, task=self.task),
            "\n".join(self.system_prompt['agent_chat_history']).format(contact=receiver, agent_chat_history="\n".join(communication_history), master=self.master),
            "\n".join(self.system_prompt['return_format_withinfonav']).format(infonav=self.infonav_plan, unknown_facts=self.mindfill_tool.get_unknown_facts()),
        ])

        return system_prompt

    def _query(self, receiver: str, communication_history: list[str]) -> str:
        """First update/init the infonav, then incorporate the infonav plan in the final query prompt.

        Args:
            receiver (str): The name of user in current chatting.
            communication_history (list[str]): The chat history between two agents.

        Returns:
            str: LLM response.
        """
        current_chat_history = self.get_current_chat_history(receiver, communication_history)
        other_chat_history = self.get_other_chat_history(receiver, communication_history)

        if self.infonav_status < 2:
            query_think = self.assemble_prompt_think(receiver, communication_history)
            self.infonav_plan = self.query_func(query_think)
            iAgentsLogger.log(query_think, self.infonav_plan, f"[Init infonav from {self.master} to {receiver}:]")

            query_think = self.assemble_prompt_think(receiver, communication_history)
            self.infonav_plan = self.query_func(query_think)
            iAgentsLogger.log(query_think, self.infonav_plan, f"[Mark infonav from {self.master} to {receiver}:]")

            self.mindfill_tool.set_unknown_facts(self.infonav_plan)

        else:
            query_think = self.assemble_prompt_think(receiver, communication_history)
            updated_facts = self.query_func(query_think)
            iAgentsLogger.log(query_think, updated_facts, f"[Updated facts from {self.master} to {receiver}:]")
            self.infonav_plan = self.mindfill_tool.fill_mind(self.infonav_plan, updated_facts)

        query_action = self.assemble_prompt(receiver, communication_history, current_chat_history, other_chat_history)
        response = self.query_func(query_action)
        iAgentsLogger.log(query_action, response, f"[Query to generate message from {self.master} to {receiver}]")
        return response


class MemoryAgent(ThinkAgent):
    """MemoryAgent inherits from ThinkAgent and has the mixed memory mechanism which reactively adjusts the query for distinct (SQL) memory retrieval and fuzzy (FAISS) memory retrieval."""

    def __init__(self, master: str, backend: str, task: str, is_assistant: bool = False, enable_distinct_memory: bool = True, enable_fuzzy_memory: bool = False, memory_name: str = "") -> None:
        super().__init__(master, backend, task, is_assistant)

        self.previous_sql_result = "None"
        self.previous_sql_params = "None"
        self.previous_sql_result_cur = "None"
        self.previous_sql_params_cur = "None"
        self.previous_faiss_params = "None"
        self.previous_faiss_result = "None"

        # by default it only enables distinct memory, for enabling fuzzy memory, first generates the memory (TODO: general memory generation script) and set enable_fuzzy_memory=True
        self.enable_distinct_memory = enable_distinct_memory
        self.enable_fuzzy_memory = enable_fuzzy_memory

        # load memory file for fuzzy memory TODO: general memory file loading script
        self.memory_name = memory_name
        assert self.enable_distinct_memory or self.enable_fuzzy_memory, "For MemoryAgent, either distinct memory or fuzzy memory should be enabled"
        self.memory_file_path = os.path.join(project_path, "memory", self.memory_name, master + ".tsv")
        self.faiss_tool = FaissTool(self.memory_file_path)
        self.stopwords = set()
        with open(os.path.join(project_path, "iagents", "stopwords.txt"), "r") as f:
            for line in f:
                self.stopwords.add(line.strip())
        
        # load llama indexer for RAG
        self.llamaindexer = LlamaIndexer(self.master)


    def set_master(self, master: str) -> None:
        """Set the master of the agent.

        Args:
            master (str): Name of the human master of agent.
        """
        self.master = master
        self.memory_file_path = os.path.join(project_path, "memory", self.memory_name, master + ".tsv")
        self.faiss_tool = FaissTool(self.memory_file_path)

    def get_current_chat_history(self, receiver: str, communication_history: list[str]) -> str:
        """Get the context from current chatting.

        Args:
            receiver (str): The name of user in current chatting.
            communication_history (list[str]): The chat history between two agents.

        Returns:
            str: Retrieved chat history as the context for assembling the query prompt.
        """
        result_str = "\n\n"

        # add distinct memory
        if self.enable_distinct_memory:
            response_json_format = {"keyword": "ring/alice/steal", "window": 3, "limit": 10}
            system_prompt = "\n".join([
                "\n".join(self.system_prompt['role']).format(master=self.master, contact=receiver),
                "\n".join(self.system_prompt['task']).format(contact=receiver, task=self.task)
            ])
            query_prompt = system_prompt + "\n".join(self.tool_prompt['sql_react']).format(condition="current session (between {} and {})".format(self.master, receiver),
                                                                                           example_json=str(response_json_format),
                                                                                           previous_params=self.previous_sql_params_cur,
                                                                                           previous_sql_result=self.previous_sql_result_cur,
                                                                                           agent_communication="\n".join(communication_history))
            response = self.query_func(query_prompt)
            iAgentsLogger.log(query_prompt, response, "[generate sql query by {}:]".format(self.master))
            response_json = self.json_tool.json_reformat(response, response_json_format)
            response_json = eval(response_json)
            sql_keywords = set(re.split("/| |'|\"", response_json['keyword'].lower())) - self.stopwords
            iAgentsLogger.log(instruction="[SQL Keywords Set:] {}".format(str(sql_keywords)))
            distinct_memories = []
            for keyword in sql_keywords:
                sql_execute_results = self.sql_tool.get_context_bykeyword_current(keyword=keyword, 
                                                                                  sender=self.master, 
                                                                                  receiver=receiver, 
                                                                                  limit=response_json['limit'], 
                                                                                  window=response_json['window'])
                distinct_memories += sql_execute_results
            # TODO: Total Messages Limit
            for message in distinct_memories[:30]:
                result_str += f"from {message[2]} to {message[3]}: {message[4]}\n"
            self.previous_sql_result_cur = result_str
            self.previous_sql_params_cur = str(response_json)
            iAgentsLogger.log(
                instruction="[Distinct Memory (with current contact) Retrieved results of {}:] \n{}".format(self.master, result_str))

        return result_str

    def get_other_chat_history(self, receiver: str, communication_history: list[str]) -> str:
        """Get the context from chatting with other friends.

        Args:
            receiver (str): The name of user in current chatting.
            communication_history (list[str]): The chat history between two agents.

        Returns:
            str: Retrieved chat history as the context for assembling the query prompt.
        """
        result_str = ""

        # add distinct memory
        if self.enable_distinct_memory:
            result_str += "<context messages related to task starts>\n"
            response_json_format = {"keyword": "ring/alice/steal", "window": 3, "limit": 10}
            system_prompt = "\n".join([
                "\n".join(self.system_prompt['role']).format(master=self.master, contact=receiver),
                "\n".join(self.system_prompt['task']).format(contact=receiver, task=self.task)
            ])
            query_prompt = system_prompt + "\n".join(self.tool_prompt['sql_react']).format(condition="sessions among {} and {}'s other friends (except {})".format(self.master, self.master, receiver),
                                                                                           example_json=str(response_json_format),
                                                                                           previous_params=self.previous_sql_params,
                                                                                           previous_sql_result=self.previous_sql_result,
                                                                                           agent_communication="\n".join(communication_history))
            response = self.query_func(query_prompt)
            iAgentsLogger.log(query_prompt, response, "[sql query prompt to {}:]".format(self.master))
            response_json = self.json_tool.json_reformat(response, response_json_format)
            response_json = eval(response_json)
            sql_keywords = set(re.split("/| |'|\"", response_json['keyword'].lower())) - self.stopwords
            iAgentsLogger.log(instruction="[SQL Keywords Set:] {}".format(str(sql_keywords)))
            distinct_memories = []
            for keyword in sql_keywords:
                sql_execute_results = self.sql_tool.get_context_bykeyword(keyword, self.master, receiver,
                                                                          response_json['limit'],
                                                                          response_json['window'])
                distinct_memories += sql_execute_results
            # TODO: Total Max Limit
            for message in distinct_memories[:30]:
                result_str += f"from {message[2]} to {message[3]}: {message[4]}\n"
            result_str += "\n<context messages related to task ends>\n"
            self.previous_sql_result = result_str
            self.previous_sql_params = str(response_json)
            iAgentsLogger.log(
                instruction="[Distinct Memory Retrieved results of {}:] \n{}".format(self.master, result_str))

        # add fuzzy memory
        if self.enable_fuzzy_memory:
            result_str += "<context summary related to task starts>\n"
            response_json_format = {"query": "{}".format(self.task), "topk": 3}
            system_prompt = "\n".join([
                "\n".join(self.system_prompt['role']).format(master=self.master, contact=receiver),
                "\n".join(self.system_prompt['task']).format(contact=receiver, task=self.task)
            ])
            query_prompt = system_prompt + "\n".join(self.tool_prompt['faiss_react']).format(example_json=str(response_json_format),
                                                                                             task=self.task,
                                                                                             previous_params=self.previous_faiss_params,
                                                                                             previous_faiss_result=self.previous_faiss_result,
                                                                                             agent_communication="\n".join(communication_history))
            response = self.query_func(query_prompt)
            iAgentsLogger.log(query_prompt, response, "[faiss query prompt to {}:]".format(self.master))
            response_json = self.json_tool.json_reformat(response, response_json_format)
            response_json = eval(response_json)
            query = response_json['query']
            topk = response_json['topk']
            ret_dis, ret_indices, ret_text = self.faiss_tool.query(query, topk)
            result_str += "\n\n{}".format("\n".join(ret_text))
            result_str += "\n<context summary related to task ends>\n"
            iAgentsLogger.log(instruction="[Fuzzy Memory Retrieved results of {}:] \n{}".format(self.master, "\n".join(ret_text)))
            self.previous_faiss_params = str(response_json)
            self.previous_faiss_result = "\n".join(ret_text)
        
        # add llamaindex for memory
        if global_config.get("agent").get("use_llamaindex"):
            response = self.llamaindexer.query(self.task)
            result_str += "<file information related to task starts>\n"
            result_str += "\n{}".format(response)
            result_str += "\n<file information related to task ends>\n"
            iAgentsLogger.log(instruction="[Llama Index Memory Retrieved results of {}:] \n{}".format(self.master, response))

        return result_str
from iagents.agent import *
from iagents.communication import *
import logging

# load global config
file_path = os.path.dirname(__file__)
project_path = os.path.dirname(file_path)


class Mode():
    """class for holding different settings

        ModeName                 InfoNav     MultiCommunication      Memory
    1.  Base                      Double        --                    Distinct
    2.  RAG                       Double        --                    LlamaIndex


    For those with MultiCommunication enabled,
    The mode used in the raised new third-party communication is the same as invoker mode,
    but no multicommunication enabled (so no nested communication),
    It is automatically handled by MultiCommunication Class

    """

    def __init__(self, sender, receiver, task, global_config, user_directory_root=None, rewrite_prompt=True) -> None:
        self.sender = sender
        self.receiver = receiver
        self.task = task
        self.raw_task = task
        self.global_config = global_config
        self.mode_name = self.global_config.get("mode").get("mode")
        self.backend = self.global_config.get('backend').get('provider')
        self.rewrite_prompt = self.global_config.get('agent').get('rewrite_prompt')
        self.user_directory_root = user_directory_root

        # load backend
        if self.backend == "gemini":
            self.query_func = query_gemini
        elif self.backend == "gpt":
            self.query_func = query_gpt
        elif self.backend == "gpt4":
            self.query_func = query_gpt4
        elif self.backend == "claude":
            self.query_func = query_claude
        elif self.backend == "ollama":
            self.query_func = query_ollama
        elif self.backend == "deepseek":
            self.query_func = query_deepseek
        elif self.backend == "qwen":
            self.query_func = query_qwen
        elif self.backend == "ernie":
            self.query_func = query_ernie
        elif self.backend == "glm":
            self.query_func = query_glm
        elif self.backend == "hunyuan":
            self.query_func = query_hunyuan
        elif self.backend == "spark":
            self.query_func = query_spark
        else:
            raise ValueError("{} backend not implemented".format(self.backend))

        # load tool prompts
        with open(os.path.join(project_path, "prompts", "tool_prompt.json"), "r") as f:
            self.tool_prompt = json.load(f)

        # rewrite the task
        if self.rewrite_prompt:
            query_prompt = "\n".join(self.tool_prompt['rewrite_task']).format(sender=sender,
                                                                              receiver=receiver,
                                                                              task=self.task)
            self.task = self.query_func(query_prompt)
            iAgentsLogger.log(query_prompt, self.task, "[rewrite task]")

        self.realized_modes = {"Base", "RAG"}
        assert self.mode_name in self.realized_modes, "{} not realized, iagents now supports: {}".format(
            self.mode_name, str(self.realized_modes))

        # log some global config
        global_config_str = ""
        global_config_str += "Global LLM Config:\n{}".format(str(self.global_config.get("backend").get("provider"))) + "\n"
        global_config_str += "Global Agent Config:\n{}".format(str(self.global_config.get("agent"))) + "\n"
        global_config_str += "Global Mode Config:\n{}".format(str(self.global_config.get("mode"))) + "\n"
        global_config_str += "Global Database Config:\n{}".format(str(self.global_config.get("mysql").get("database"))) + "\n"
        iAgentsLogger.log(instruction=global_config_str)

    def get_instructor_agent(self):
        if self.mode_name in {'Base'}:
            return ThinkAgent(master=self.sender, backend=self.backend, task=self.task)
        elif self.mode_name in {'RAG'}:
            return MemoryAgent(master=self.sender, backend=self.backend, task=self.task)

    def get_assistant_agent(self):
        if self.mode_name in {'Base'}:
            return ThinkAgent(master=self.receiver, backend=self.backend, task=self.task, is_assistant=True)
        elif self.mode_name in {'RAG'}:
            return MemoryAgent(master=self.receiver, backend=self.backend, task=self.task, is_assistant=True)

    def get_communication(self, is_offline=False):
        """choose communication

        some combinations:
        1. whether offline
        2. whether Multi-Party Communication
        3. whether consensus conclusion
        4. whether OfflineLoad conclusions from Multi-Party Communication
        5. whether use llamaindex to retrieve external memory

        Args:
            is_offline (bool, optional): whether offline. Defaults to False.

        Returns:
            Communication: constructed communication based on the mode
        """
        instructor_agent = self.get_instructor_agent()
        assistant_agent = self.get_assistant_agent()

        if self.mode_name in {'Base', 'RAG'}:
            if is_offline:
                comm = OfflineCommunication(
                    instructor=instructor_agent,
                    assistant=assistant_agent,
                    max_round=global_config.get("agent").get("max_communication_turns"),
                    is_consensus_conclusion=True)
            else:
                comm = VanillaCommunication(
                    instructor=instructor_agent,
                    assistant=assistant_agent,
                    max_round=global_config.get("agent").get("max_communication_turns"),
                    is_consensus_conclusion=True)

        # print the rewritten task
        # if self.rewrite_prompt:
        #     comm.send_message_agent(
        #         comm.instructor, comm.assistant,
        #         "[rewrite task prompt]: from '{}' --> '{}'".format(self.raw_task, self.task))

        return comm
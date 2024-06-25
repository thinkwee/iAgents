import json
import os
from abc import ABC, abstractmethod
from datetime import datetime
import inspect
from iagents.agent import *
from iagents.sql import *
import sys

sys.path.append("..")

file_path = os.path.dirname(__file__)
project_path = os.path.dirname(file_path)

try:
    with open(os.path.join(project_path, "config/global.yaml"), "r") as f:
        global_config = yaml.safe_load(f)
except FileNotFoundError:
    print("Config file not found.")
    raise
except yaml.YAMLError as exc:
    print("Error in configuration file:", exc)
    raise

class BaseCommunication(ABC):
    """The base class of communication
    A communication class hold the process of dialogue between two agents,
    and how the message was sent to the web UI
    """

    def __init__(self, instructor, assistant, max_round) -> None:
        """init

        Args:
            instructor (Agent): the instructor agent with the Agent base class
            assistant (Agent): the assistant agent with the Agent base class
            max_round (_type_): the max round limit of communication
        """
        super().__init__()
        self.instructor = instructor
        self.assistant = assistant
        self.max_round = max_round
        self.communication_history = ['']
        assert isinstance(self.instructor, Agent) and isinstance(self.assistant, Agent), "instructor and assistant must be Agent instances"
        assert self.instructor.task == self.assistant.task, "Tasks of instructor and assistant must match"
        self.task = instructor.task

        try:
            with open(os.path.join(project_path, "prompts", "tool_prompt.json"), "r") as f:
                self.tool_prompt = json.load(f)
        except FileNotFoundError:
            print("Tool prompt file not found.")
            raise
        except json.JSONDecodeError as exc:
            print("Error decoding JSON file:", exc)
            raise

    @abstractmethod
    def communicate(self) -> str:
        """the core method in Communication class, which defines all the steps in the communication 

        Returns:
            str: the output conclusion of this communication
        """
        pass

    @abstractmethod
    def send_message_agent(self, sender, receiver, message):
        """send the message of agent to the UI (online) or log (offline)

        Args:
            sender (Agent): the agent who sent this message
            receiver (Agent): the agent who receive this message
            message (str): the message
        """
        pass

    @abstractmethod
    def format_agent_history(self, sender, receiver, message):
        """organize the messages between agents in chat history-like format

        Args:
            sender (Agent): the agent who sent this message
            receiver (Agent): the agent who receive this message
            message (str): the message
        """
        pass

    def get_time(self):
        current_time = datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
        return formatted_time


class VanillaCommunication(BaseCommunication):
    """VanillaCommunication realizes the basic communication between two agents, it is a simple back-and-forth dialogue,
    where the instructor and assistant agent take turns to send messages to each other.
    It is notable that instructor agent is the one who raise the communication, but both agents are able to send instructions(questions) to each other.
    """

    def __init__(self, instructor, assistant, max_round, is_consensus_conclusion=False) -> None:
        """_summary_

        Args:
            instructor (Agent): the instructor agent with the Agent base class
            assistant (Agent): the assistant agent with the Agent base class
            max_round (int): the max round limit of communication
            is_consensus_conclusion (bool, optional): use consensus conclusion to summarize two infonav plans from agents. Defaults to False.
        """
        super().__init__(instructor, assistant, max_round)
        self.is_consensus_conclusion = is_consensus_conclusion
        if self.is_consensus_conclusion:
            assert isinstance(self.instructor, ThinkAgent) and isinstance(self.assistant, ThinkAgent), "Consensus Conclusion is only avaiable when two agents are ThinkAgent"

    def communicate(self) -> str:
        round_index = 0
        while round_index < self.max_round:
            iAgentsLogger.log(instruction="[Comm Round: {}]".format(round_index))
            round_index += 1

            if round_index == 1:
                # add the task prompt at the start of agent's communication
                self.send_message_agent(self.instructor, 
                                        self.assistant,
                                        "[Trigger Agents Communication for Task Solving, Task Prompt]: " + self.task)

            # instructor sends message to assistant
            instructor_response = self.instructor.query(self.assistant.master, 
                                                        self.communication_history)
            self.communication_history.append(self.format_agent_history(self.instructor, 
                                                                        self.assistant, 
                                                                        instructor_response))
            self.send_message_agent(self.instructor, self.assistant, instructor_response)

            # assistant sends message to instructor
            assistant_response = self.assistant.query(self.instructor.master, 
                                                      self.communication_history)
            self.communication_history.append(self.format_agent_history(self.assistant, 
                                                                        self.instructor, 
                                                                        assistant_response))
            self.send_message_agent(self.assistant, self.instructor, assistant_response)

        # get conclusion
        if self.is_consensus_conclusion:
            conclusion = self.consensus_conclusion(self.communication_history, 
                                                   self.instructor.infonav_plan,
                                                   self.assistant.infonav_plan)
        else:
            conclusion = self.instructor.conclusion(self.communication_history)
        iAgentsLogger.log(instruction="[conclusion]:\n{}".format(conclusion))
        return conclusion

    def send_message_agent(self, sender, receiver, message):
        sender = sender.master + "'s Agent"
        receiver = receiver.master + "'s Agent"
        _ = exec_sql("INSERT INTO chats (sender, receiver, message, communication_history) VALUES (%s, %s, %s, %s)",
                     params=(sender, receiver, message, ""),
                     mode="write")

    def format_agent_history(self, sender, receiver, message):
        message = "from {} to {}: {}".format(sender.master + "'s Agent", 
                                             receiver.master + "'s Agent",
                                             message)
        return message

    def consensus_conclusion(self, communication_history, infonav_instructor, infonav_assistant):
        """given the infonav plans from agents, 
        the communication class holds the responsibility to extract the consensus in infonav plans,
        and reason to get the final conclusion.
        TODO: explicitly extracts the consensus rationale and ignores the conflict rationales instead of just prompting.

        Args:
            communication_history (list[str]): the chat history between two agents
            infonav_instructor (str): infonav plan from instructor agent
            infonav_assistant (str): infonav plan from assistant agent
        """

        query_str = "\n".join(self.tool_prompt['consensus_conclusion']).format(
            task=self.task,
            agent_communication="\n".join(communication_history),
            infonav_instructor=infonav_instructor,
            infonav_assistant=infonav_assistant)
        response = self.instructor.query_func(query_str)

        iAgentsLogger.log(query_str, response, "[consensus_conclusion]")
        return response


class MultiPartyCommunication(VanillaCommunication):
    """Communication with multi-party commmunication feature activated.
    It means agents can recursively raise new communication within the current communication.
    """

    def __init__(self, instructor, assistant, max_round, is_consensus_conclusion=False) -> None:
        super().__init__(instructor, assistant, max_round, is_consensus_conclusion)

    def get_agent_params(self, agent):
        signature = inspect.signature(agent.__init__)
        args = [param for param in signature.parameters.keys() if param != 'self']
        init_params = {}
        for param_name in args:
            param_value = getattr(agent, param_name)
            init_params[param_name] = param_value
        return init_params

    def raise_new_comm(self, agent, current_talking_agent):
        """make the agent to actively start a new communication with other agents

        Args:
            agent (Agent): the agent who wants to raise new communication
            current_talking_agent (Agent): the agent of current chat partner
        """
        friends_set = set(agent.get_friends().split("\n"))
        if current_talking_agent.master in friends_set:
            friends_set.remove(current_talking_agent.master)
        if agent.master in friends_set:
            friends_set.remove(agent.master)
        friends_set.remove("")
        friends_set = {item.lower() for item in friends_set}
        friends = ",".join(friends_set)

        query_friends = "\n".join(self.tool_prompt['raise_new_communication']).format(
            task=self.task, friends=friends, yourself=agent.master, contact=current_talking_agent.master)

        chosen_friend = agent.query_func(query_friends)
        if not chosen_friend:
            chosen_friend = "None"
        chosen_friend = chosen_friend.lower().strip()
        iAgentsLogger.log(query_friends, chosen_friend,
                         "choose third-party friends from {}".format(agent.master))

        if chosen_friend not in friends_set:
            iAgentsLogger.log(instruction="Failed to find third-party for {}".format(agent.master))
            self.send_message_agent(
                agent, current_talking_agent,
                "[Trigger {}'s Agents Raising New Communication with {}]".format(agent.master, "None"))
            return "None", "None"
        else:
            iAgentsLogger.log(instruction="Found third-party for {}, {}".format(agent.master, chosen_friend))
            self.send_message_agent(
                agent, current_talking_agent,
                "[Trigger {}'s Agents Raising New Communication with {}]".format(agent.master, chosen_friend))
            # inspect the Agent type of instructor and assistant, apply the same agent type with different master
            # the raised new communication is a normal communication (not MultiCommunication)
            agent_type_instructor = type(self.instructor)
            agent_type_assistant = type(self.assistant)
            agent_params_instructor = self.get_agent_params(self.instructor)
            agent_params_assistant = self.get_agent_params(self.assistant)

            agent_instructor = agent_type_instructor(**agent_params_instructor)
            agent_assistant = agent_type_assistant(**agent_params_assistant)
            agent_instructor.set_master(agent.master)
            agent_assistant.set_master(chosen_friend)

            communication = VanillaCommunication(
                instructor=agent_instructor,
                assistant=agent_assistant,
                max_round=global_config.get("agent").get("max_communication_turns"),
                is_consensus_conclusion=True)
            response = communication.communicate()
            return chosen_friend, response

    def communicate(self) -> str:
        round_index = 0
        while round_index < self.max_round:
            iAgentsLogger.log(instruction="[MultiComm Round: {}]".format(round_index))
            round_index += 1

            if round_index == 1:
                # add the task prompt at the start of agent's communication
                self.send_message_agent(
                    self.instructor, self.assistant,
                    "[Trigger Agents Communication for Task Solving, Task Prompt]: " + self.task)

                # instructor starts the new communication
                chosen_friend_instructor, new_comm_instructor_conclusion = self.raise_new_comm(
                    self.instructor, self.assistant)
                self.communication_history.append(
                    self.format_agent_history(
                        self.instructor, self.assistant,
                        "Discussion with {}'s Agents: {} ".format(chosen_friend_instructor,
                                                                  new_comm_instructor_conclusion)))
                self.send_message_agent(
                    self.instructor, self.assistant,
                    "[Discussion with {}'s Agents]: {} ".format(chosen_friend_instructor,
                                                                new_comm_instructor_conclusion))

                # assistant star∂ts the new communication
                chosen_friend_assistant, new_comm_assistant_conclusion = self.raise_new_comm(
                    self.assistant, self.instructor)
                self.communication_history.append(
                    self.format_agent_history(
                        self.assistant, self.instructor,
                        "Discussion with {}'s Agents: {} ".format(chosen_friend_assistant,
                                                                  new_comm_assistant_conclusion)))
                self.send_message_agent(
                    self.assistant, self.instructor,
                    "[Discussion with {}'s Agents]: {} ".format(chosen_friend_assistant,
                                                                new_comm_assistant_conclusion))
            else:
                instructor_response = self.instructor.query(self.assistant.master, self.communication_history)
                self.communication_history.append(
                    self.format_agent_history(self.instructor, self.assistant, instructor_response))
                self.send_message_agent(self.instructor, self.assistant, instructor_response)

                assistant_response = self.assistant.query(self.instructor.master, self.communication_history)
                self.communication_history.append(
                    self.format_agent_history(self.assistant, self.instructor, assistant_response))
                self.send_message_agent(self.assistant, self.instructor, assistant_response)

        if self.is_consensus_conclusion:
            conclusion = self.consensus_conclusion(self.communication_history, 
                                                   self.instructor.infonav_plan,
                                                   self.assistant.infonav_plan)
        else:
            conclusion = self.instructor.conclusion(self.communication_history)
        iAgentsLogger.log(instruction="[conclusion]:\n{}".format(conclusion))
        return conclusion


class OfflineCommunication(VanillaCommunication):
    """Offline communication class of batch evaluation

    The only difference lies in that for offline we do not interact with database,
    but only record the communication in the log.
    the communication history between agents is still maintained in self.communication_history for prompt assemble
    """

    def __init__(self, instructor, assistant, max_round, is_consensus_conclusion=False) -> None:
        super().__init__(instructor, assistant, max_round, is_consensus_conclusion)

    def send_message_agent(self, sender, receiver, message):
        sender = sender.master + "'s Agent"
        receiver = receiver.master + "'s Agent"
        iAgentsLogger.log(instruction="from {} to {}: {}".format(sender, receiver, message))

    def format_agent_history(self, sender, receiver, message):
        message = "from {} to {}: {}".format(sender.master + "'s Agent", receiver.master + "'s Agent",
                                             message)
        return message


class OfflineMultiPartyCommunication(MultiPartyCommunication):
    """offline version for multi-party communications, no need to send message to frontend

    Args:
        MultiPartyCommunication (_type_): _description_
    """

    def __init__(self, instructor, assistant, max_round, is_consensus_conclusion=False) -> None:
        super().__init__(instructor, assistant, max_round, is_consensus_conclusion)

    def send_message_agent(self, sender, receiver, message):
        pass


class OfflineLoadMultiPartyCommunication(VanillaCommunication):
    """similar to VanillaCommunication, but load multi-party communication conclusions from file and add it to self.communication_history

    Args:
        VanillaCommunication (_type_): _description_
    """

    def __init__(self, instructor, assistant, max_round, is_consensus_conclusion=False) -> None:
        super().__init__(instructor, assistant, max_round, is_consensus_conclusion)

    def send_message_agent(self, sender, receiver, message):
        pass

    def set_communication_history(self, messages):
        self.communication_history += messages
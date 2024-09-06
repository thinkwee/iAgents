import requests
import json
import csv
import re
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.gpt import query_gpt4

def schedule_dict_2_str(name, schedule_dict):
    """
    Convert a schedule dictionary to a formatted string.

    Args:
        name (str): The name of the person whose schedule is being converted.
        schedule_dict (dict): A dictionary containing schedule information.

    Returns:
        str: A formatted string representation of the schedule.
    """
    schedule_str = ''
    sorted_schedule = dict(sorted(schedule_dict.items(), key=lambda item: item[1]['start']))
    for activity, details in sorted_schedule.items():
        start_hour = details['start'] // 2
        start_minute = '00' if details['start'] % 2 == 0 else '30'
        end_hour = details['end'] // 2
        end_minute = '00' if details['end'] % 2 == 0 else '30'
        participants = ' and '.join([p for p in details['participants_list'] if p != name])
        if details['type'] == 0:
            schedule_str += f"{start_hour}:{start_minute}-{end_hour}:{end_minute} {activity[:-1]}\n"
        else:
            schedule_str += f"{start_hour}:{start_minute}-{end_hour}:{end_minute} {activity[:-1]} with {participants}\n"
    return schedule_str

def write_one_sample(schedule_dict, writer):
    """
    Generate and write dialogue samples based on schedules.

    Args:
        schedule_dict (dict): A dictionary containing schedule information for multiple agents.
        writer (csv.writer): A CSV writer object to write the generated dialogue.
    """
    agent_sorted_pool = sorted(schedule_dict.keys(), key=lambda x: (int(x[1:]), x[0]))
    i = 0
    total_people = 6
    while i < len(agent_sorted_pool):
        for j in range(1, total_people // 2):
            input_text = '''
The following is {person1}'s and {person2}'s schedule for tomorrow.
Please design the conversations between them so that they understand each other's schedules. Notice,
1. When {person1} and {person2} have activities that they participate in together, the names of the participants in the joint activities can be mentioned in the conversation;
2. If either party {person1} or {person2} does not participate in an activity, the participating party cannot mention the names of other participants in the activity;
3. Please follow this format when generating dialogue. For example: when {person1} talks to {person2}, the format is ‘{person1} to {person2}: ‘.
{person1}'s schedule:
{person1_schedule}
{person2}'s schedule:
{person2_schedule}
            '''.format(person1=agent_sorted_pool[i],
                       person2=agent_sorted_pool[i+j],
                       person1_schedule=schedule_dict_2_str(agent_sorted_pool[i], schedule_dict[agent_sorted_pool[i]]),
                       person2_schedule=schedule_dict_2_str(agent_sorted_pool[i+j], schedule_dict[agent_sorted_pool[i+j]]))
            print(f'inputtext: {input_text}')
            generated_text = query_gpt4(input_text).strip()
            print("Generated text")
            print(generated_text)
            messages = generated_text.strip().split('\n')
            for message in messages:
                match = re.match(r'(\w+) to (\w+): "(.*)"', message)
                if match:
                    sender, receiver, message_text = match.groups()
                    writer.writerow([sender, receiver, message_text])
        i += total_people // 2

def main():
    """
    Main function to process schedule data and generate dialogue.
    """
    with open('dialogue.csv', 'a', newline='') as fw:
        writer = csv.writer(fw)
        writer.writerow(["sender", "receiver", "message"])

        with open("./schedule_data_list.jsonl", 'r') as f:
            for line in f:
                schedule_dict = json.loads(line.strip())
                write_one_sample(schedule_dict, writer)

if __name__ == "__main__":
    main()
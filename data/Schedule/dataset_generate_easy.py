import json
import csv

# number of samples to generate
scale = 1

def generate_names(total_people):
    """
    Generate a list of names for the given number of people.
    
    Args:
    total_people (int): The number of people to generate names for.
    
    Returns:
    list: A list of generated names.
    """
    names = []
    for idx in range(scale):
        for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:total_people]:
            names.append(char + str(idx))
    return names

def write_jsonl(data_list, filename):
    """
    Write data to a JSONL file.
    
    Args:
    data_list (list): List of data to write.
    filename (str): Name of the file to write to.
    """
    with open(filename, 'w') as f:
        for entry in data_list:
            json.dump(entry, f)
            f.write('\n')

def read_jsonl(filename):
    """
    Read data from a JSONL file.
    
    Args:
    filename (str): Name of the file to read from.
    
    Returns:
    list: List of data read from the file.
    """
    data_list = []
    with open(filename, 'r') as f:
        for line in f:
            data_list.append(json.loads(line.strip()))
    return data_list

def find_least_delete_span(schedule_dict):
    """
    Find the minimum number of activities that need to be deleted to avoid overlaps.
    
    Args:
    schedule_dict (dict): Dictionary containing schedule information.
    
    Returns:
    int: Minimum number of activities to delete.
    """
    intervals = []
    for agent in schedule_dict.keys():
        if "A" not in agent and "D" not in agent:
            continue
        for activity in schedule_dict[agent].keys():
            if "Sleep" in activity:
                continue
            intervals.append([schedule_dict[agent][activity]['start'], schedule_dict[agent][activity]['end']])
    if not intervals:
        return 0
    
    intervals.sort()
    n = len(intervals)
    f = [1]

    for i in range(1, n):
        f.append(max((f[j] for j in range(i) if intervals[j][1] <= intervals[i][0]), default=0) + 1)

    return n - max(f)

def schedule_dict_2_str(name, schedule_dict):
    """
    Convert a schedule dictionary to a string representation.
    
    Args:
    name (str): Name of the person whose schedule is being converted.
    schedule_dict (dict): Dictionary containing schedule information.
    
    Returns:
    list: List of schedule entries as strings.
    """
    schedule_list = []
    sorted_schedule = dict(sorted(schedule_dict.items(), key=lambda item: item[1]['start']))
    for activity, details in sorted_schedule.items():
        start_hour = details['start'] // 2
        start_minute = '00' if details['start'] % 2 == 0 else '30'
        end_hour = details['end'] // 2
        end_minute = '00' if details['end'] % 2 == 0 else '30'
        participants = ' and '.join([p for p in details['participants_list'] if p != name])
        if details['type'] == 0:
            schedule_list.append(f"{start_hour}:{start_minute}-{end_hour}:{end_minute} {activity[:-1]}")
        else:
            schedule_list.append(f"{start_hour}:{start_minute}-{end_hour}:{end_minute} {activity[:-1]} with {participants}")
    return schedule_list

def main():
    """
    Main function to generate the dataset.
    """
    total_people = 6
    write_data_list = []
    name_pool = generate_names(total_people)
    schedule_list = read_jsonl('schedule_data_list.jsonl')

    for i in range(scale):
        name_begin_p = i * total_people
        name_group = name_pool[name_begin_p:name_begin_p + total_people]

        schedule_nl = []
        for name in name_group:
            schedule_nl.append({name: schedule_dict_2_str(name, schedule_list[i][name])})

        tmp_all = {
            'id': i + 1,
            'schedule': schedule_list[i],
            'schedule_nl': schedule_nl,
            'message': [],
            'QA agents': [name_group[0], name_group[total_people // 2]],
            'question': f'Please resolve the following math problems: calculate how many activities need to be deleted at least so that there are no overlapping activities on the schedule of A{i} and D{i}. Note that any activity except sleeping can be deleted and you don\'t have to decide which activity need to be deleted, just give the minimum number.',
            'answer': ''
        }

        with open('dialogue.csv', 'r') as file:
            reader = csv.reader(file)
            next(reader)  # Skip header
            for sender, receiver, message in reader:
                if sender in name_group and receiver in name_group:
                    tmp_all['message'].append(f"from {sender} to {receiver} : {message}")

        least_delete = find_least_delete_span(schedule_list[i])
        tmp_all['answer'] = str(least_delete)
        write_data_list.append(tmp_all)
        print(least_delete)

    write_jsonl(write_data_list, 'dataset_easy.jsonl')

if __name__ == "__main__":
    main()

import json
import csv

# number of samples to generate
scale = 1

def generate_names(total_people):
    """Generate a list of names for the given number of people."""
    names = []
    for idx in range(scale):
        for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:total_people]:
            names.append(char + str(idx))
    return names

def write_jsonl(data_list, filename):
    """Write data to a JSONL file."""
    with open(filename, 'w') as f:
        for entry in data_list:
            json.dump(entry, f)
            f.write('\n')

def read_jsonl(filename):
    """Read data from a JSONL file."""
    data_list = []
    with open(filename, 'r') as f:
        for line in f:
            data_list.append(json.loads(line.strip()))
    return data_list

def generate_time_vec(schedule_dict):
    """Generate time vectors for all agents in the schedule."""
    all_time_vector_list = []
    for agent in schedule_dict.keys():
        time_vec = [1] * 48
        for activity in schedule_dict[agent].keys():
            start, end = schedule_dict[agent][activity]['start'], schedule_dict[agent][activity]['end']
            time_vec[start:end] = [0] * (end - start)
        all_time_vector_list.append(time_vec)
    return all_time_vector_list

def find_common_free_time(all_time_vector_list):
    """Find common free time slots from all time vectors."""
    common_free_time = [all(vectors) for vectors in zip(*all_time_vector_list)]
    result = []
    start = None
    for i, is_free in enumerate(common_free_time):
        if is_free:
            if start is None:
                start = i
        elif start is not None:
            result.append((start, i - 1))
            start = None
    
    if start is not None:
        result.append((start, len(common_free_time) - 1))

    return [f"{start//2}:{start%2*30:02d}-{(end+1)//2}:{(end+1)%2*30:02d}" 
            for start, end in result]

def schedule_dict_2_str(name, schedule_dict):
    """Convert schedule dictionary to a list of formatted strings."""
    schedule_list = []
    sorted_schedule = dict(sorted(schedule_dict.items(), key=lambda item: item[1]['start']))
    for activity, details in sorted_schedule.items():
        start_hour, start_minute = divmod(details['start'], 2)
        end_hour, end_minute = divmod(details['end'], 2)
        participants = ' and '.join([p for p in details['participants_list'] if p != name])
        activity_str = f"{start_hour:02d}:{start_minute*30:02d}-{end_hour:02d}:{end_minute*30:02d} {activity[:-1]}"
        if details['type'] != 0:
            activity_str += f" with {participants}"
        schedule_list.append(activity_str)
    return schedule_list

def main():
    """Main function to generate the dataset."""
    total_people = 6
    write_data_list = []
    name_pool = generate_names(total_people)
    schedule_list = read_jsonl('schedule_data_list.jsonl')

    for i in range(scale):
        name_group = name_pool[i*total_people:(i+1)*total_people]
        schedule_nl = [{name: schedule_dict_2_str(name, schedule_list[i][name])} for name in name_group]

        tmp_all = {
            'id': i + 1,
            'schedule': schedule_list[i],
            'schedule_nl': schedule_nl,
            'message': [],
            'QA agents': [name_group[0], name_group[total_people // 2]],
            'question': 'Please find out when all your friends can join together today, which means you may need to find out all free time spans between 00:00 and 24:00 that does not have any activity for anybody. List all free time spans in the format like HH:MM-HH:MM.'
        }

        with open('dialogue.csv', 'r') as file:
            reader = csv.reader(file)
            next(reader)  # Skip header
            for sender, receiver, message in reader:
                if sender in name_group and receiver in name_group:
                    tmp_all['message'].append(f"from {sender} to {receiver} : {message}")

        all_time_vector = generate_time_vec(schedule_list[i])
        common_free_time = find_common_free_time(all_time_vector)
        tmp_all['answer'] = common_free_time
        write_data_list.append(tmp_all)
        print(common_free_time)

    write_jsonl(write_data_list, 'dataset_hard.jsonl')

if __name__ == "__main__":
    main()

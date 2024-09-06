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

def find_longest_activity_name(schedule_dict):
    """Find the longest activity name(s) in the schedule."""
    ans = 0
    ret = set()
    for agent in schedule_dict.keys():
        for activity in schedule_dict[agent].keys():
            if "Sleep" in activity:
                continue
            ans = max(ans, (schedule_dict[agent][activity]['end'] - schedule_dict[agent][activity]['start']))
    for agent in schedule_dict.keys():
        for activity in schedule_dict[agent].keys():
            if "Sleep" in activity:
                continue
            if (schedule_dict[agent][activity]['end'] - schedule_dict[agent][activity]['start']) == ans:
                ret.add(activity[:-1])
    return ret

def schedule_dict_2_str(name, schedule_dict):
    """Convert schedule dictionary to a list of formatted strings."""
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
    """Main function to generate the dataset."""
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
            'question': 'Please find out the activity with longest duration (except sleep) on the schedule of all people you had communication with. You two may known different people and you need to gather all of them. If there are multiple activity with the same longest duration, list all of them.'
        }

        with open('dialogue.csv', 'r') as file:
            reader = csv.reader(file)
            next(reader)  # Skip header
            for sender, receiver, message in reader:
                if sender in name_group and receiver in name_group:
                    tmp_all['message'].append(f"from {sender} to {receiver} : {message}")

        activity_set = find_longest_activity_name(schedule_list[i])
        tmp_all['answer'] = str(activity_set)
        write_data_list.append(tmp_all)
        print(activity_set)

    write_jsonl(write_data_list, 'dataset_medium.jsonl')

if __name__ == "__main__":
    main()

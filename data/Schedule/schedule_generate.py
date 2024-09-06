import random
import requests
import json

# number of samples to generate
scale = 1

single_activities = {
    "Breakfast": {"duration": 1, "is_available": 1},
    "Lunch": {"duration": 1, "is_available": 1},
    "Dinner": {"duration": 1, "is_available": 1},
    "Sleep": {"duration": 16, "is_available": 0},
    "Exercise": {"duration": 1, "is_available": 1},
    "Work": {"duration": 2, "is_available": 0},
    "Housekeeping": {"duration": 3, "is_available": 1},
    "Meditation": {"duration": 4, "is_available": 1},
    "Yoga": {"duration": 1, "is_available": 1},
    "Grocery Shopping": {"duration": 2, "is_available": 1},
    "Reading": {"duration": 3, "is_available": 1},
    "Watching TV": {"duration": 4, "is_available": 1},
    "Listening to music": {"duration": 1, "is_available": 1},
    "Playing video games": {"duration": 2, "is_available": 1},
    "Doing board games": {"duration": 3, "is_available": 1},
    "Walking the dog": {"duration": 4, "is_available": 1},
    "Gardening": {"duration": 1, "is_available": 1},
    "Laundry": {"duration": 2, "is_available": 1},
    "Online Shopping": {"duration": 3, "is_available": 1}
}

shared_activities = {
    "Team Meeting": {"duration": 1, "is_available": 0, "participants": 2, "start_set": [20, 40]},
    "Group Exercise": {"duration": 2, "is_available": 0, "participants": 2, "start_set": [14, 40]},
    "Conference Call": {"duration": 3, "is_available": 0, "participants": 2, "start_set": [16, 36]},
    "Movie Night": {"duration": 4, "is_available": 0, "participants": 2, "start_set": [36, 44]},
    "Group Study": {"duration": 1, "is_available": 0, "participants": 2, "start_set": [16, 40]},
    "Business Presentation": {"duration": 2, "is_available": 0, "participants": 2, "start_set": [16, 36]},
    "Camping Trip": {"duration": 3, "is_available": 0, "participants": 2, "start_set": [14, 34]},
    "Cooking Class": {"duration": 4, "is_available": 0, "participants": 2, "start_set": [20, 40]},
    "Book Club Meeting": {"duration": 1, "is_available": 0, "participants": 2, "start_set": [20, 40]}
}

persona_pool = ['current None'] * (scale * 10)

routine_set = {
    "Breakfast": [12, 13, 14, 15, 16, 17, 18],
    "Lunch": [22, 23, 24, 25, 26],
    "Dinner": [34, 35, 36, 37, 38],
    "Sleep": [44, 45, 46]
}

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

def generate_names(total_people, idx):
    """Generate names for people."""
    return [char + str(idx) for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:total_people]]

class Person:
    """Represents a person with a schedule."""

    def __init__(self, name, persona):
        self.name = name
        self.persona = persona
        self.time_vector = [0] * 48
        self.activity_willing_dict = {}
        self.activity_count = {}
        self.schedule = {}

    def schedule_print(self):
        """Print the person's schedule."""
        print('------------------------')
        print(f"{self.name}'s schedule:")
        sorted_schedule = dict(sorted(self.schedule.items(), key=lambda item: item[1]['start']))
        for activity, details in sorted_schedule.items():
            start_hour, start_minute = divmod(details['start'], 2)
            end_hour, end_minute = divmod(details['end'], 2)
            start_minute = '00' if start_minute == 0 else '30'
            end_minute = '00' if end_minute == 0 else '30'
            participants = ' and '.join([p for p in details['participants_list'] if p != self.name])
            if details['type'] == 0:
                print(f"{start_hour}:{start_minute}-{end_hour}:{end_minute} {activity}")
            else:
                print(f"{start_hour}:{start_minute}-{end_hour}:{end_minute} {activity} with {participants}")

    def clear_current_schedule(self):
        """Clear the current schedule."""
        self.time_vector = [0] * 48
        self.schedule_list = ['Not assigned'] * 48
        self.schedule = {}

    def generate_random_activity_vector(self, single_activities, shared_activities):
        """Generate a random activity vector."""
        all_activities = list(single_activities.keys()) + list(shared_activities.keys())
        self.activity_willing_dict = {activity: random.choice([0, 1]) for activity in all_activities}
        self.activity_willing_dict['Sleep'] = 1
        self.activity_willing_dict['Lunch'] = 1

    def add_schedule(self, start, end, activity_name, type, participants_list=[]):
        """Add an activity to the schedule."""
        if activity_name in self.activity_count:
            last_activity = self.schedule[f"{activity_name}{self.activity_count[activity_name]}"]
            if participants_list == last_activity['participants_list'] and start == last_activity['end']:
                last_activity['end'] = end
                return
            elif start != last_activity['end']:
                self.activity_count[activity_name] += 1
        else:
            self.activity_count[activity_name] = 1

        self.schedule[f"{activity_name}{self.activity_count[activity_name]}"] = {
            'start': start,
            'end': end,
            'type': type,
            'participants_list': participants_list
        }

    def generate_routine(self):
        """Generate routine activities."""
        for routine in ['Sleep', 'Lunch']:
            for _ in range(5):
                start = random.choice(routine_set[routine])
                if self.time_vector[start] == 0:
                    end = start + single_activities[routine]['duration']
                    if end > 48:
                        end_after = end % 48
                        self.time_vector[0:end_after] = [1] * end_after
                        self.time_vector[start:48] = [1] * (48 - start)
                        self.add_schedule(0, end_after, routine, 0, [self.name])
                        self.add_schedule(start, 48, routine, 0, [self.name])
                    else:
                        self.time_vector[start:end] = [1] * (end - start)
                        self.add_schedule(start, end, routine, 0, [self.name])
                    break

    def generate_schedule(self):
        """Generate the person's schedule."""
        skip_available_prob = 0.1
        for _ in range(5):
            start = 0
            while start < 48:
                while start < 48 and self.time_vector[start] != 0:
                    start += 1
                if start >= 48:
                    break
                end = start + 1
                while end < 48 and self.time_vector[end] != 1:
                    end += 1
                time_span = end - start
                for _ in range(5):
                    if time_span > 4:
                        selected_activity = random.choice([key for key in single_activities.keys() if single_activities[key]['duration'] >= 4 and key not in ['Lunch', 'Sleep']])
                        end = start + single_activities[selected_activity]['duration']
                        self.time_vector[start:end] = [1] * (end - start)
                        if random.random() < skip_available_prob:
                            self.add_schedule(start, end, selected_activity, 0, [self.name])
                        break
                    else:
                        selected_activity = random.choice([key for key in single_activities.keys() if key not in ['Lunch', 'Sleep']])
                        if single_activities[selected_activity]['duration'] <= time_span and (self.activity_willing_dict[selected_activity] == 1 or _ == 4):
                            end = start + single_activities[selected_activity]['duration']
                            self.time_vector[start:end] = [1] * (end - start)
                            if random.random() < skip_available_prob:
                                self.add_schedule(start, end, selected_activity, 0, [self.name])
                            break
                start = end

def main():
    """Main function to generate schedules."""
    total_people = 6
    schedule_data_list = []

    for i in range(scale):
        name_pool = generate_names(total_people, i)
        agent_pool = {name: Person(name, persona) for name, persona in zip(name_pool, persona_pool)}

        activity_willing_dict = {}
        for agent in agent_pool.values():
            agent.clear_current_schedule()
            agent.generate_random_activity_vector(single_activities, shared_activities)
            activity_willing_dict[agent.name] = agent.activity_willing_dict

        for agent in agent_pool.values():
            agent.clear_current_schedule()
            agent.activity_willing_dict = activity_willing_dict[agent.name]

        shared_activities_num = random.randint(1, total_people // 3)
        extracted_shared_activities = dict(random.sample(shared_activities.items(), shared_activities_num))

        shared_activities_info = {}
        for activity, details in extracted_shared_activities.items():
            participants = random.sample(name_pool, details['participants'])
            start = random.choice(details['start_set'])
            end = start + details['duration']
            shared_activities_info[activity] = {
                'participants_list': participants,
                'start': start,
                'end': end
            }

        for activity, info in shared_activities_info.items():
            for name in info['participants_list']:
                agent_pool[name].add_schedule(info['start'], info['end'], activity, 1, info['participants_list'])
                agent_pool[name].time_vector[info['start']:info['end']] = [1] * (info['end'] - info['start'])

        schedule_dict = {}
        for agent in agent_pool.values():
            agent.generate_routine()
            agent.generate_schedule()
            schedule_dict[agent.name] = agent.schedule
            agent.schedule_print()
        schedule_data_list.append(schedule_dict)

    write_jsonl(schedule_data_list, 'schedule_data_list.jsonl')

if __name__ == "__main__":
    main()
import os
import sys
import logging
from datetime import datetime, timedelta
import pandas as pd
sys.path.append("../..")
from backend.gpt import query_gpt4

def setup_logging(output_path):
    """Set up logging configuration."""
    logging.basicConfig(
        filename=os.path.join(output_path, "data_generation.log"),
        level=logging.INFO,
        format='[%(asctime)s]\n%(message)s',
        datefmt='%Y-%d-%m %H:%M:%S',
        encoding="utf-8"
    )

def create_output_folder(season_num, episode_num):
    """Create output folder for the episode."""
    output_path = f"./s{season_num}/e{episode_num}"
    try:
        os.makedirs(output_path)
        print(f"Output to {output_path}")
    except FileExistsError:
        print(f"{output_path} created, output will be overwritten")
    except OSError as e:
        print(f"Failed to create output path {output_path}: {e}")
        sys.exit(1)
    return output_path

def load_and_filter_data(season_num, episode_num):
    """Load and filter data for the specified episode."""
    df = pd.read_csv('Friends.csv', delimiter=',', header=0)
    df = df.applymap(lambda x: x.lower() if isinstance(x, str) else x)
    sample = df[df['Season'].str.contains(f"season-{season_num}")]
    sample = sample[sample['Episode'].str.contains(f"episode-{episode_num}")].dropna().reset_index(drop=True)
    return sample

def norm_name(name):
    """Normalize character names."""
    name = name.strip()
    orig = name
    replacements = {
        "phoe": "phoebe",
        "rach": "rachel",
        "mnca": "monica",
        "chan": "chandler"
    }
    for abbr, full in replacements.items():
        if name == abbr or any(f"{abbr}{suffix}" in name for suffix in ["'s", ",", "/", " "]):
            name = name.replace(abbr, full)
    if orig != name:
        logging.info(f"{orig} --> {name}")
    return name

def locate_scenes(sample):
    """Locate scene boundaries in the script."""
    scene_indexs = []
    for idx, data in sample.iterrows():
        if "[scene" in data["Speaker"] or "scene" in data["Speaker"]:
            scene_indexs.append(idx)
    
    if not scene_indexs:
        scene_indexs = list(range(len(sample)))[::len(sample) // 10]
        logging.info("No explicit scene info, evenly divided into 10 scenes")
        return scene_indexs, False
    
    return scene_indexs, True

def write_scene_info(sample, scene_indexs, scene_flag, output_path):
    """Write scene information to a CSV file."""
    scene_pd = []
    for idx in scene_indexs:
        try:
            if scene_flag:
                scene_pd.append([idx, sample.iloc[idx+1]['Text']])
            else:
                scene_pd.append([idx, sample.iloc[idx]['Text']])
        except IndexError:
            continue
    scene_pd = pd.DataFrame(scene_pd, columns=['index','text'])
    scene_pd.to_csv(os.path.join(output_path, "scene_info.csv"))

def process_scene(sample, scene_indexs, scene_idx, scene_flag, output_path, season_num, episode_num):
    """Process a single scene and generate labeled data."""
    start_index = scene_indexs[scene_idx]
    end_index = len(sample) if scene_idx == len(scene_indexs) - 1 else scene_indexs[scene_idx + 1]
    
    if scene_flag:
        scene_info = sample.iloc[start_index]['Speaker'] + str(scene_idx+1)
        background_info = sample.iloc[start_index]['Text']
        episode_info = sample.iloc[start_index]['Episode']
        season_info = sample.iloc[start_index]['Season']
        start_index += 1
    else:
        scene_info = ""
        background_info = ""
        episode_info = sample.iloc[start_index]['Episode']
        season_info = sample.iloc[start_index]['Season']
    
    logging.info(f"Scene {scene_idx + 1}")
    logging.info(f"From {start_index} to {end_index} in scripts, {end_index - start_index + 1} lines")
    
    scene_part = sample.iloc[start_index:end_index].reset_index(drop=True)
    content = ["Index\tUtterance\tSpeaker"]
    content.extend([f"{i+1}\t{line['Text']}\t{line['Speaker']}" for i, (_, line) in enumerate(scene_part.iterrows())])
    content = "\n".join(content)
    
    query_prompt = """this is a script of {} in the popular tv series Friends, {} in {}. 
the background of this scene is {}. Here is the script:

{}

each line is the index and utterance with the speaker of this utterance.
you need to annotate the listener for each utterance based on the context of dialogue and scene description.
the utterances are not organized in speaker-listener-speaker mode, there may be multiple consecutive queries from multiple speakers to the same listener.
so you must annotate based on the content of dialogue.
if there are multiple listener for one utterance, annotate in the format of "name1/name2/name3"
if all character in this scene are the listeners for one utterance, annotate it with "ALL"
if there exist pronouns and references, you need to annotate precise attribution, e.g, "father" should be annotate as "someone's father"
you have to give answer. if you are not sure, annotate the listener as "ALL"
the returned index and speaker should be exactly the same as the given script, all you need to do is only add the listener
return in the format like:
index, speaker, listener
1, the name of speaker, the name of listener""".format(scene_info, episode_info, season_info, background_info, content)

    ans = query_gpt4(query_prompt)
    ans_list = [line.split(",") for line in ans.lower().split("\n") if "Utterance" not in line]
    
    final_list = []
    for idx, line in enumerate(ans_list):
        try:
            utterance_index = int(line[0])
        except ValueError:
            logging.info(f"Bad Generated utterance, skip")
            continue
        speaker_input = scene_part.iloc[utterance_index - 1]['Speaker'].strip()
        speaker_output = line[1].strip()
        listener = line[2].strip()
        
        if speaker_input != speaker_output:
            logging.info(f"{utterance_index}: {speaker_input}[Input Speaker] != {speaker_output}[Output Speaker]")
            logging.info(f"Original Input: {scene_part.iloc[utterance_index - 1]}")
            logging.info(f"Full Output: {line}")
            logging.info("Model output will be used as speaker")
            if speaker_output:
                speaker_input = speaker_output
        
        if len(line) != 3:
            logging.info(f"len({utterance_index}) != 3: Bad Generated utterance, skip")
            continue
        
        final_list.append(f"{norm_name(speaker_input)}\t{norm_name(listener)}\t{scene_part.iloc[utterance_index - 1]['Text']}")
    
    with open(f"{output_path}/s{season_num}e{episode_num}_scene{scene_idx + 1}.tsv", "w") as f:
        for data in final_list:
            f.write(f"{data}\n")

def process_df(df):
    """Process and clean the GPT-labeled dataset."""
    global current_time
    all_people = set()
    for item in set(df[0]) - set(["all"]):
        item = item.replace("the ", "")
        all_people.update(item.replace(" & ", "/").replace(" and ", "/").replace("+", "/").split("/"))
    
    if len(all_people) <= 2:
        all_people = set(["rachel", "monica", "phoebe", "ross", "joey", "chandler"])
    
    ret = []
    for _, line in df.iterrows():
        mysql_timestamp = current_time.strftime('%Y-%m-%d %H:%M:%S')
        current_time += timedelta(seconds=1)
        sender = line[0].strip().replace("the ", "").replace(" and ", "/").replace("+", "/").replace(" & ", "/")
        receiver = line[1].strip().replace("the ", "").replace(" and ", "/").replace("+", "/").replace(" & ", "/")
        
        if "all" in receiver:
            receiver = receiver.replace("all", "/".join(all_people - set(sender.split("/"))))
        if "all" in sender:
            sender = sender.replace("all", "/".join(all_people - set(receiver.split("/"))))

        sender = sender.strip()
        receiver = receiver.strip()
        for character_sender in sender.split("/"):
            for character_receiver in receiver.split("/"):
                ret.append([character_sender, character_receiver, line[2], mysql_timestamp])
    return pd.DataFrame(ret)

def main():
    season_num, episode_num = sys.argv[1], sys.argv[2]
    output_path = create_output_folder(season_num, episode_num)
    setup_logging(output_path)
    
    sample = load_and_filter_data(season_num, episode_num)
    logging.info("Picked Episode")
    logging.info(sample)
    
    scene_indexs, scene_flag = locate_scenes(sample)
    logging.info("Index of each scene in the script")
    logging.info(scene_indexs)
    
    write_scene_info(sample, scene_indexs, scene_flag, output_path)
    
    for scene_idx in range(len(scene_indexs)):
        process_scene(sample, scene_indexs, scene_idx, scene_flag, output_path, season_num, episode_num)
    
    # Process and combine all scene files
    file_name_prefix = f"{output_path}/s{season_num}e{episode_num}_scene"
    df_list = []
    for idx in range(1, len(scene_indexs) + 1):
        try:
            df = pd.read_csv(f"{file_name_prefix}{idx}.tsv", delimiter='\t', header=None)
            df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
            df_list.append(process_df(df))
        except pd.errors.EmptyDataError:
            logging.info(f"Empty tsv: {file_name_prefix}{idx}.tsv skipped")
    
    concat_df = pd.concat(df_list, axis=0, ignore_index=True)
    all_character = set(concat_df[0]) | set(concat_df[1])
    logging.info("All characters in this episode")
    logging.info(all_character)
    concat_df.to_csv(f"{output_path}/s{season_num}e{episode_num}_labeled.csv")
    logging.info("Final cleaned data")
    logging.info(concat_df)

if __name__ == "__main__":
    start_time = datetime(1994, 9, 22, 0, 0, 0) # it doesn't matter what date we choose, 1994.9.22 is the day friends tv series premiered
    current_time = start_time
    main()
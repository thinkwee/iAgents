import json
import sys
import re
from pprint import pprint
from collections import defaultdict
from itertools import combinations

import pandas as pd
import jsonlines

sys.path.append("../..")
from backend.gpt import query_gpt4

# Helper function to normalize text
def norm(text):
    return text.lower().strip().replace(" ", "")

# Load QA datasets
def load_qa_data(file_path):
    with open(file_path, "r") as f:
        return json.load(f)

FriendsQAData = load_qa_data("path_to_FriendsQA/dat/friendsqa_trn.json")

# Load labeled dialogue dataset
concat_df = pd.read_csv("s01.csv")
utterance2character = defaultdict(set)
for _, line in concat_df.iterrows():
    utterance2character[norm(line['message'])].add(line['sender'])
    utterance2character[norm(line['message'])].add(line['receiver'])

# Open output file
output_file = jsonlines.open("./FriendsComQA.jsonl", "a")

good_case = []

# Process each scene in season 1
for data in FriendsQAData['data']:
    if "s01" not in data['title']:
        continue
    
    for paragraph in data['paragraphs']:
        qas_list = paragraph['qas']
        utterances_list = paragraph['utterances:']
        dialogue = [f"{'/'.join(item['speakers'])}: {item['utterance']}" for item in utterances_list]

        # Skip scenes with only two participants
        all_participants = set().union(*[set(item['speakers']) for item in utterances_list])
        if len(all_participants) == 2:
            continue

        # Create mappings for QA pairs and utterances
        uid2qas = defaultdict(list)
        idx2qa = {}
        idx2speaker = {}
        idx2uid = {}

        for qidx, qas in enumerate(qas_list):
            for idx, answer in enumerate(qas['answers']):
                qa_id = f"Q_{qidx}_A_{idx}"
                uid2qas[answer['utterance_id']].append(qa_id)
                idx2uid[qa_id] = answer['utterance_id']
                idx2speaker[qa_id] = utterances_list[answer['utterance_id']]['speakers'][0].lower().split(" ")[0]
                idx2qa[qa_id] = f"{qas['question']}: {answer['answer_text']}"
        
        # Count rationale utterances with multiple participants
        count = sum(1 for idx, item in enumerate(utterances_list) if len(uid2qas[idx]) > 0 and len(utterance2character[norm(item['utterance'])]) >= 2)

        if count >= 2:
            print("\n" * 3)
            print(data['title'])
            print('-' * 10)

            rationale_list = []
            rationale_list_print = []
            qas_set = set()

            # Process each utterance
            for idx, item in enumerate(utterances_list):
                if len(uid2qas[idx]) > 0 and len(utterance2character[norm(item['utterance'])]) >= 2:
                    rationale_list_print.append(f"[{item['uid']}] {'/'.join(item['speakers'])}: {item['utterance']} \t {uid2qas[idx]} \t {utterance2character[norm(item['utterance'])]}")
                    rationale_list.append({
                        "rationale_uid": item['uid'],
                        "speaker": item['speakers'],
                        "rationale_utterance": item['utterance'],
                        "related_qas": uid2qas[idx],
                        "related_character": list(utterance2character[norm(item['utterance'])])
                    })
                    qas_set.update(uid2qas[idx])
            
            # Process QA pair combinations
            for comb in combinations(qas_set, 2):
                if comb[0].split("_")[1] != comb[1].split("_")[1]:  # Different questions
                    # Skip if there are no differences between rationales
                    if not (utterance2character[norm(utterances_list[idx2uid[comb[0]]]['utterance'])] ^ utterance2character[norm(utterances_list[idx2uid[comb[1]]]['utterance'])]):
                        continue

                    print("-" * 20)
                    query_prompt = """
Here is a conversation:
{}
Here is a question-answer pair on this conversation:
{}
Here is another question-answer pair on this conversation:
{}
Please generate a new question-answer pair based on the given two question-answer pairs.
The new question-answer pair must satisfies the following requirements:
a. You can only ask one question in the new generated question.
b. The new question can be answered only if both answers of the given two questions are known. Both answers are directly necessary for solving the new question.
c. The answer to this new question is simple, certain and unambiguous, usually only one word or phrase, which can be easily solved once the two answers to the above questions are known.
d. The new question should contain as much detailed description on the context/event/situation as possible but not leaking any answers.

Here are some good cases for generating the new questions

{}


Return in the format of:         
1. the new question
2. explain in detail that why it must needs answers to the given first questions to solve, and how it be solved
3. explain in detail that why it must needs answers to the given second questions to solve, and how it be solved
4. the answer to the new question
5. how to induce/deduce the answer to the new question from the answers of given two questions, which are "{}" and "{}"
"""
                    query_prompt = query_prompt.format("\n".join(dialogue), idx2qa[comb[0]], idx2qa[comb[1]], "\n".join(good_case), idx2qa[comb[0]].split(": ")[1], idx2qa[comb[1]].split(": ")[1])
                    print(query_prompt)
                    print("-" * 20)
                    print("QA Combination: ", comb)
                    print("QA1: ", idx2qa[comb[0]])
                    print("QA2: ", idx2qa[comb[1]])
                    involve_speakers = set([idx2speaker[comb[0]], idx2speaker[comb[1]]])

                    print("QA1 Speaker&Participants: ", idx2speaker[comb[0]], utterance2character[norm(utterances_list[idx2uid[comb[0]]]['utterance'])])
                    print("QA2 Speaker&Participants: ", idx2speaker[comb[1]], utterance2character[norm(utterances_list[idx2uid[comb[1]]]['utterance'])])

                    if len(utterance2character[norm(utterances_list[idx2uid[comb[0]]]['utterance'])] - utterance2character[norm(utterances_list[idx2uid[comb[1]]]['utterance'])] - involve_speakers) == 0:
                        continue
                    if not (utterance2character[norm(utterances_list[idx2uid[comb[1]]]['utterance'])] - utterance2character[norm(utterances_list[idx2uid[comb[0]]]['utterance'])] - involve_speakers):
                        continue
                    
                    # Display QA information
                    show_df = []
                    for i in range(2):
                        q, a = idx2qa[comb[i]].split(": ")
                        speaker = idx2speaker[comb[i]]
                        unique_participants = utterance2character[norm(utterances_list[idx2uid[comb[i]]]['utterance'])] - utterance2character[norm(utterances_list[idx2uid[comb[1-i]]]['utterance'])] - involve_speakers
                        rationale_uid = idx2uid[comb[i]]
                        show_df.append([q, a, speaker, unique_participants, rationale_uid])
                    
                    show_df = pd.DataFrame(show_df, columns=['Question', 'Answer', 'Speaker', 'Unique Participants', "Rationale Uid"])
                    print("*" * 10)
                    print(show_df)
                    print("*" * 10)

                    print("Rationale Utterance:")
                    print("\n".join(rationale_list_print))

                    # User input for continuing or skipping
                    s = input("Please check if it is a suitable scene for generating combined questions, y for continue, n for refuse, s for skip this scene\n")
                    if s == "n":
                        continue
                    elif s == "s":
                        break

                    print(">" * 10)
                    response = query_gpt4(query_prompt, temperature=0.1)
                    matches = re.findall(r'\d+\.\s*(.*)', response)
                    response_list = [match.strip() for match in matches]
                    print(response)
                    print()

                    # User input for accepting or refusing generated question
                    s = input("Please check if the generated question is good, y for accept, n for refuse, s for skip this scene, g for accept and saving this good case as in-context examples\n")
                    if s in ["y", "g"]:
                        ret_dict = {
                            "episode": data['title'],
                            "context": dialogue,
                            "rationale_list": rationale_list,
                            "QA1": {"idx": comb[0], "content": idx2qa[comb[0]]},
                            "QA2": {"idx": comb[1], "content": idx2qa[comb[1]]},
                            "generated_question": response_list[0],
                            "reason1": response_list[1],
                            "reason2": response_list[2],
                            "answer": response_list[3],
                            "QA1_third_party": list(utterance2character[norm(utterances_list[idx2uid[comb[0]]]['utterance'])] - involve_speakers),
                            "QA2_third_party": list(utterance2character[norm(utterances_list[idx2uid[comb[1]]]['utterance'])] - involve_speakers),
                        }
                        pprint(ret_dict)
                        output_file.write(ret_dict)
                        if s == "g":
                            good_case.append(f"{idx2qa[comb[0]]} + {idx2qa[comb[1]]} --> {response_list[0]}: {response_list[3]}, why is a good combination: {response_list[4]}")
                        input("finished, write to file, enter to continue")
                    elif s == "s":
                        break

# Close output file
output_file.close()

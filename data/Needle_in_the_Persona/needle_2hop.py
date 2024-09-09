import random
import sys
import jsonlines
from datasets import load_dataset
from backend.gpt import query_gpt4

sys.path.append("../..")

# Constants
NUM_SAMPLES = 100
DATASET_PATH = "google/Synthetic-Persona-Chat"
OUTPUT_FILE = "./dataset_2hop.jsonl"

def load_persona_dataset():
    """
    Load the Synthetic-Persona-Chat dataset and extract relevant information.
    
    Returns:
        list: A list of samples, each containing personas and conversations.
    """
    dataset = load_dataset(DATASET_PATH)
    samples = dataset['train']
    samples_list = [
        [sample['user 1 personas'], sample['user 2 personas'], sample['Best Generated Conversation']]
        for sample in samples
    ]
    print(f"Loaded {len(samples_list)} samples from persona dataset")
    return samples_list

def norm_name(text, person_a_name, person_b_name):
    """
    Normalize names in the conversation text.
    
    Args:
        text (str): The conversation text.
        person_a_name (str): Name of the first person.
        person_b_name (str): Name of the second person.
    
    Returns:
        str: Normalized conversation text.
    """
    text = text.lower().replace("user 1", person_a_name).replace("user 2", person_b_name).replace("'s name", "").replace(" name", "")
    ret = []
    for utterance in text.split("\n"):
        if "name" in utterance or "username" in utterance:
            norm_utterance_prompt = """
I will give a utterance in the conversation between {} and {}
please replace the name or username in the text with the correct name based on role and utterance.
You should identify whether each placeholder ([name]/[username]) should be filled with its own name or the other person's name
for example, if bob is talking with alice 
"bob: my name is [name]." should be replaced to "bob: my name is [bob].".
or
"bob: nice to meet you, username." should be replaced to "nice to meet you, alice".
here is the conversation:
{}
please only return the replaced text without adding anything else, just replace and return.
            """.format(person_a_name, person_b_name, utterance)
            utterance = query_gpt4(norm_utterance_prompt)
        ret.append(utterance)
    text = "\n".join(ret)
    for name in [person_a_name, person_b_name]:
        text = text.replace(f"({name})", name).replace(f"[{name}]", name)
    return text

def generate_sample(samples_list, idx):
    """
    Generate a single sample for the dataset.
    
    Args:
        samples_list (list): List of all samples from the original dataset.
        idx (int): Index of the current sample being generated.
    
    Returns:
        dict: A dictionary containing the generated sample data.
    """
    # Select random conversations and personas
    ab = random.choice(samples_list)
    cd = random.choice(samples_list)
    insert_needle = random.choice(random.choice(samples_list)[0].split("."))
    
    # Ensure unique conversations
    while ab[-1] == cd[-1] or insert_needle in ab[0] or insert_needle in cd[1]:
        ab = random.choice(samples_list)
        cd = random.choice(samples_list)
        insert_needle = random.choice(random.choice(samples_list)[0].split("."))
    
    persona, personb, personc, persond = ab[0], ab[1], cd[0], cd[1]
    chatab = norm_name(ab[-1], "alice", "bob")
    chatcd = norm_name(cd[-1], "charlie", "dave")

    print("Normalized conversations complete")
    print(f"Persona of Alice\n{persona}")
    print(f"Persona of Bob\n{personb}")
    print(f"Persona of Charlie\n{personc}")
    print(f"Persona of Dave\n{persond}")

    # Generate common persona
    add_persona_prompt = """
Personas are aspects of the user's character that provide insights into their personality, motivations, and behaviors.
A taxonomy of persona can be:
1. Demographics (Location, Employment, School, Family Status, Possession, Marital Status, Age, Gender)
2. Psychographics (Preference, Hobby, Personal Characteristics)
3. Wellness (Disease, Symptom)

here is the persona of alice:

{}

here is the persona of dave:

{}

now you need to try to create a new persona by adding some details on an existing persona, '{}'.
this new persona can be added to both alice and dave, but in either same or different ways.
1. If it was added in the same way, both alice and dave have this persona.
2. If it was added in different way, either alice or dave will have this persona, and the other will dislike/against/posses different kind of this persona.
Now you choose to add this persona in {} way.
The new persona should be
1. specific (It cannot be a description that is too common or too abstract, such as go outdoor)
2. full of imagination.
YOU SHOULD ONLY return 
1. the introduction of the persona with a short phase or short sentence.
2. and how it was added to alice and dave's personality.
    """.format(persona, persond, insert_needle, "same" if idx % 2 == 0 else "different")
    common_persona = query_gpt4(add_persona_prompt)
    print(common_persona)

    # Generate question for common persona
    explain_persona_prompt = """
here is the persona of alice:

{}

here is the persona of dave:

{}

here is the new persona of alice and dave and how it was added to alice and dave:

{}


try to describe the new persona with a simple and interesting question.
the question should be as short as possible, but at the same time this question is sufficient to identify this newly added persona.
for example,
if the new persona is "Alice and Dave often go biking", then the question may be "what is the common sport interest of alice and bob?"
if the new persona is "Alice love fish soup while Dave hate it", then the question may be "what is the thing that alice loves while dave hates?"
if the new persona is "Alice is a math teacher and Dave is a science teacher", then the question may be "What subject is Alice good at but Bob is not good at?"
YOU SHOULD ONLY RETURN THE QUESTION.
    """.format(persona, persond, common_persona)
    common_persona_question = query_gpt4(explain_persona_prompt)
    print(common_persona_question)

    # Modify conversations to include new persona
    add_persona_ab_prompt = """
here is a conversation between alice and bob:

{}

here is the persona of alice:

{}

here is the persona of bob:

{}

here is a new persona about alice and dave:

{}

modify only one or two utterance of the conversation to ONLY include the alice part of the new persona.
you should make the modified conversation natural, fluent and coherent.
you can not modify the original persona.
you can not delete or ignore the personas mentioned in the original conversation
you can add some details to the conversation to make it longer, at least 20 turns of dialogue
YOU SHOULD ONLY RETURN THE modified conversation without omitting any utterance
    """
    modified_alice_bob_conversation = query_gpt4(add_persona_ab_prompt.format(chatab, persona, personb, common_persona))

    add_persona_cd_prompt = """
here is a conversation between charlie and dave:

{}

here is the persona of charlie:

{}

here is the persona of dave:

{}

here is a new persona about alice and dave:

{}

modify only one or two utterance of the conversation to ONLY include the dave part of the new persona.
you should make the modified conversation natural, fluent and coherent.
you can not modify the original persona.
you can not delete or ignore the personas mentioned in the original conversation.
you can add some details to the conversation to make it longer, at least 20 turns of dialogue
YOU SHOULD ONLY RETURN THE modified conversation without omitting any utterance
    """
    modified_charlie_dave_conversation = query_gpt4(add_persona_cd_prompt.format(chatcd, personc, persond, common_persona))

    # Generate conversation between Bob and Charlie
    generate_conversation_bc_prompt = """
here is the persona of bob:

{}

here is the persona of charlie:

{}

now you need generate a conversation between bob and charlie.
the generated conversation should obey their persona.
you can add some details to the conversation to make it longer, at least 20 turns of dialogue
YOU SHOULD ONLY return the generated conversation between bob and charlie
    """
    generated_bob_charlie = query_gpt4(generate_conversation_bc_prompt.format(personb, personc))

    # Normalize the answer
    norm_answer_prompt = """
here is the context:

{}

here is the question:

{}

please return the answer to the question in one word or one phrase
    """
    answer = query_gpt4(norm_answer_prompt.format(common_persona, common_persona_question))

    return {
        'id': str(idx),
        'modified_alice_bob_conversation': modified_alice_bob_conversation,
        'modified_charlie_dave_conversation': modified_charlie_dave_conversation,
        'chat_bob_charlie': generated_bob_charlie,
        'task_prompt': common_persona_question,
        'answer': answer,
        'needle_detail': common_persona
    }

def main():
    """
    Main function to generate and save samples.
    """
    samples_list = load_persona_dataset()
    
    with jsonlines.open(OUTPUT_FILE, "a") as fw:
        for idx in range(NUM_SAMPLES):
            sample = generate_sample(samples_list, idx)
            fw.write(sample)

if __name__ == "__main__":
    main()
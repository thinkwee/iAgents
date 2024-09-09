import random
import jsonlines
from datasets import load_dataset
from backend.gpt import query_gpt4

# Constants
NUM_SAMPLES = 100
OUTPUT_FILE = "./dataset_1hop.jsonl"

def load_persona_dataset():
    """Load and process the Synthetic-Persona-Chat dataset."""
    dataset = load_dataset("google/Synthetic-Persona-Chat")
    samples = dataset['train']
    samples_list = [[sample['user 1 personas'], sample['user 2 personas'], sample['Best Generated Conversation']] for sample in samples]
    print(f"Loaded {len(samples_list)} samples from persona dataset")
    return samples_list

def norm_name(text, person_a_name, person_b_name):
    """Normalize names in the conversation text."""
    text = text.lower().replace("user 1", person_a_name).replace("user 2", person_b_name).replace("'s name", "").replace(" name", "")
    ret = []
    for utterance in text.split("\n"):
        if "name" in utterance or "username" in utterance:
            norm_utterance_prompt = f"""
I will give a utterance in the conversation between {person_a_name} and {person_b_name}
please replace the name or username in the text with the correct name based on role and utterance.
You should identify whether each placeholder ([name]/[username]) should be filled with its own name or the other person's name
for example, if bob is talking with alice 
"bob: my name is [name]." should be replaced to "bob: my name is [bob].".
or
"bob: nice to meet you, username." should be replaced to "nice to meet you, alice".
here is the conversation:
{utterance}
please only return the replaced text without adding anything else, just replace and return.
            """
            utterance = query_gpt4(norm_utterance_prompt)
            print(utterance)
        ret.append(utterance)
    text = "\n".join(ret)
    for name in [person_a_name, person_b_name]:
        text = text.replace(f"({name})", name).replace(f"[{name}]", name)
    return text

def generate_fact(conversation, persona):
    """Generate a fact about a person based on their conversation and persona."""
    prompt = f"""
here is a conversation between alice and bob:
{conversation}
here is some facts about alice:
{persona}
now you need to choose a fact.
the fact can be deduced from the conversation between alice and bob.

YOU MUST ONLY RETURN THE fact.
"""
    return query_gpt4(prompt)

def generate_question(conversation, fact):
    """Generate a question based on a conversation and a chosen fact."""
    prompt = f"""
here is a conversation between alice and bob:
{conversation}
here is a chosen fact which can be deduced from the conversation between alice and bob.
{fact}
Now you need to generate a detailed question asking about alice, and the answer to this question is the chosen fact.
for example, 'what is the sport interest of alice' or 'how old is alice'.
the answer to this question, which is the chosen fact, should be unambiguous.

YOU MUST ONLY RETURN THE question.
"""
    return query_gpt4(prompt)

def generate_conversation(persona_b, persona_c):
    """Generate a conversation between two personas."""
    prompt = f"""
here is the persona of bob:

{persona_b}

here is the persona of charlie:

{persona_c}

now you need generate a conversation between bob and charlie.
the generated conversation should obey their persona.
you can add some details to the conversation to make it longer, at least 20 turns of dialogue
YOU SHOULD ONLY return the generated conversation between bob and charlie
    """
    return query_gpt4(prompt)

def main():
    samples_list = load_persona_dataset()
    
    with jsonlines.open(OUTPUT_FILE, "w") as fw:
        for idx in range(NUM_SAMPLES):
            # Randomly sample conversations
            ab = random.choice(samples_list)
            cd = random.choice(samples_list)
            assert ab[-1] != cd[-1]
            
            # Extract personas
            persona_a, persona_b, chat_ab = ab
            persona_c, persona_d, chat_cd = cd

            # Normalize conversations
            chat_ab_norm = norm_name(chat_ab, "alice", "bob")
            chat_cd_norm = norm_name(chat_cd, "charlie", "dave")
            print("Normalized conversations complete")

            # Generate fact and question
            fact = generate_fact(chat_ab_norm, persona_a)
            question = generate_question(chat_ab_norm, fact)

            # Generate conversation between Bob and Charlie
            chat_bc = generate_conversation(persona_b, persona_c)

            # Prepare sample data
            sample = {
                'id': str(idx),
                'modified_alice_bob_conversation': chat_ab_norm,
                'modified_charlie_dave_conversation': chat_cd_norm,
                'chat_bob_charlie': chat_bc,
                'task_prompt': question,
                'answer': fact
            }
            fw.write(sample)

if __name__ == "__main__":
    main()
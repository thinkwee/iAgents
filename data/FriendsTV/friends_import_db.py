import os
import sys
import mysql.connector
import yaml
import pandas as pd

# Load global config
file_path = os.path.dirname(__file__)
project_path = os.path.dirname(os.path.dirname(file_path))
with open(os.path.join(project_path, "config/global.yaml"), "r") as config_file:
    global_config = yaml.safe_load(config_file)

# Database configuration
DATABASE = "FRIENDSTV"
DATABASE_USER = global_config["mysql"]["username"]
DATABASE_PASSWD = global_config["mysql"]["password"]
HOST = global_config["mysql"]["host"]

db_config = {'host': HOST, 'user': DATABASE_USER, 'password': str(DATABASE_PASSWD)}

# Establish MySQL connection
conn = mysql.connector.connect(**db_config)
cursor = conn.cursor(buffered=True)

def create_database(cursor):
    """Create the database if it doesn't exist."""
    try:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DATABASE}")
        print(f"Database '{DATABASE}' created successfully")
    except mysql.connector.Error as err:
        print(f"Error creating database '{DATABASE}':", err)

def create_users_table(cursor):
    """Create the users table if it doesn't exist."""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL
            )
        """)
        print("Table 'users' created successfully")
    except mysql.connector.Error as err:
        print("Error creating table 'users':", err)

def create_friendships_table(cursor):
    """Create the friendships table if it doesn't exist."""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS friendships (
                user_id INT,
                friend_id INT,
                PRIMARY KEY (user_id, friend_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (friend_id) REFERENCES users(id)
            )
        """)
        print("Table 'friendships' created successfully")
    except mysql.connector.Error as err:
        print("Error creating table 'friendships':", err)

def create_chats_table(cursor):
    """Create the chats table if it doesn't exist."""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sender VARCHAR(255) NOT NULL,
                receiver VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("Table 'chats' created successfully")
    except mysql.connector.Error as err:
        print("Error creating table 'chats':", err)

def insert_chat(cursor, sender, receiver, message):
    """Insert a new chat message into the chats table."""
    try:
        query = """
            INSERT INTO chats (sender, receiver, message, communication_history) 
            VALUES (%s, %s, %s, %s)
        """
        data = (sender, receiver, message, "")
        cursor.execute(query, data)
        print(f"Chat inserted successfully: {sender}, {receiver}")
    except mysql.connector.Error as err:
        print("Error inserting chat:", err)

def insert_friendship_data(cursor, user_id, friend_id):
    """Insert a new friendship into the friendships table."""
    try:
        cursor.execute(
            """
            INSERT INTO friendships (user_id, friend_id)
            VALUES (%s, %s)
        """, (user_id, friend_id))
        print(f"Friendship data inserted successfully: {user_id}, {friend_id}")
    except mysql.connector.Error as err:
        print("Error inserting Friendship data:", err)

def insert_user_data(cursor, id, name, password):
    """Insert a new user into the users table."""
    try:
        cursor.execute(
            """
            INSERT INTO users (id, name, password)
            VALUES (%s, %s, %s)
        """, (id, name, password))
        print(f"User data inserted successfully: {id}, {name}, {password}")
    except mysql.connector.Error as err:
        print("Error inserting user data:", err)

# Main execution
if __name__ == "__main__":
    # Create database and tables
    create_database(cursor)
    cursor.execute(f"USE {DATABASE}")
    create_users_table(cursor)
    create_friendships_table(cursor)
    create_chats_table(cursor)

    # Load and process data
    concat_df = pd.read_csv("s01.csv")
    all_characters = set(concat_df['sender']) | set(concat_df['receiver'])
    
    # Create character to ID mappings
    id2cha = {user_id + 1000: character for user_id, character in enumerate(all_characters)}
    cha2id = {character: user_id + 1000 for user_id, character in enumerate(all_characters)}

    # Initialize counters
    count_user = 0
    count_relationship = 0
    count_utterance = 0

    # Insert users
    for id, character in id2cha.items():
        insert_user_data(cursor, id, character, character)
        count_user += 1
    conn.commit()

    # Insert friendships and messages
    exist_friendship = set()
    for _, line in concat_df.iterrows():
        insert_chat(cursor, line['sender'], line['receiver'], line['message'])
        count_utterance += 1
        
        id_a = cha2id[line['sender']]
        id_b = cha2id[line['receiver']]
        
        if f"{id_a}_{id_b}" not in exist_friendship:
            exist_friendship.add(f"{id_a}_{id_b}")
            exist_friendship.add(f"{id_b}_{id_a}")
            insert_friendship_data(cursor, id_a, id_b)
            count_relationship += 1
            if id_a != id_b:
                insert_friendship_data(cursor, id_b, id_a)
    
    conn.commit()

    # Print summary
    print(all_characters)
    print(f"Totally {count_user} characters with {count_relationship} relationships and {count_utterance} utterances")

    # Close connections
    cursor.close()
    conn.close()
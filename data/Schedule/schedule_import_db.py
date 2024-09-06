import os
import mysql.connector
import yaml
import pandas as pd

def load_config():
    """Load global configuration from YAML file."""
    file_path = os.path.dirname(__file__)
    project_path = os.path.dirname(os.path.dirname(file_path))
    global_config = yaml.safe_load(open(os.path.join(project_path, "config/global.yaml"), "r"))
    return global_config

def get_db_connection(config):
    """Establish and return a MySQL database connection."""
    db_config = {
        'host': config['mysql']['host'],
        'user': config['mysql']['username'],
        'password': str(config['mysql']['password'])
    }
    return mysql.connector.connect(**db_config)

def create_database(cursor, database):
    """Create a database if it doesn't exist."""
    try:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database}")
        print(f"Database '{database}' created successfully")
    except mysql.connector.Error as err:
        print(f"Error creating database '{database}':", err)

def create_table(cursor, table_name, query):
    """Create a table if it doesn't exist."""
    try:
        cursor.execute(query)
        print(f"Table '{table_name}' created successfully")
    except mysql.connector.Error as err:
        print(f"Error creating table '{table_name}':", err)

def insert_data(cursor, query, data):
    """Insert data into a table."""
    try:
        cursor.execute(query, data)
        print("Data inserted successfully")
    except mysql.connector.Error as err:
        print("Error inserting data:", err)

def print_table_summary(cursor, table_name):
    """Print a summary of the table structure and sample data."""
    try:
        cursor.execute(f"DESCRIBE {table_name}")
        print(f"\nTable Structure for '{table_name}':")
        for row in cursor.fetchall():
            print(row)
        
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
        print(f"\nSample Data for '{table_name}':")
        for row in cursor.fetchall():
            print(row)
        print("-" * 50)
    except mysql.connector.Error as err:
        print(f"Error printing table summary for '{table_name}':", err)

def main():
    """Main function to import schedule data into MySQL database."""
    config = load_config()
    conn = get_db_connection(config)
    cursor = conn.cursor(buffered=True)

    DATABASE = "Schedule"
    create_database(cursor, DATABASE)
    cursor.execute(f"USE {DATABASE}")

    # Create tables
    create_table(cursor, "users", """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL
        )
    """)

    create_table(cursor, "friendships", """
        CREATE TABLE IF NOT EXISTS friendships (
            user_id INT,
            friend_id INT,
            PRIMARY KEY (user_id, friend_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (friend_id) REFERENCES users(id)
        )
    """)

    create_table(cursor, "chats", """
        CREATE TABLE IF NOT EXISTS chats (
            id INT AUTO_INCREMENT PRIMARY KEY,
            sender VARCHAR(255) NOT NULL,
            receiver VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    conn.commit()

    # Process CSV data
    concat_df = pd.read_csv('dialogue.csv')
    all_characters = set(concat_df['sender']) | set(concat_df['receiver'])
    id2cha = {user_id + 1000: character for user_id, character in enumerate(all_characters)}
    cha2id = {character: user_id + 1000 for user_id, character in enumerate(all_characters)}

    # Insert user data
    for user_id, character in id2cha.items():
        insert_data(cursor, "INSERT INTO users (id, name, password) VALUES (%s, %s, %s)", 
                    (user_id, character, character))

    # Insert friendship and chat data
    exist_friendship = set()
    for _, line in concat_df.iterrows():
        insert_data(cursor, "INSERT INTO chats (sender, receiver, message) VALUES (%s, %s, %s)", 
                    (line['sender'], line['receiver'], line['message']))
        
        id_a, id_b = cha2id[line['sender']], cha2id[line['receiver']]
        if f"{id_a}_{id_b}" not in exist_friendship:
            exist_friendship.add(f"{id_a}_{id_b}")
            exist_friendship.add(f"{id_b}_{id_a}")
            insert_data(cursor, "INSERT INTO friendships (user_id, friend_id) VALUES (%s, %s)", (id_a, id_b))
            if id_a != id_b:
                insert_data(cursor, "INSERT INTO friendships (user_id, friend_id) VALUES (%s, %s)", (id_b, id_a))

    conn.commit()

    print("All characters in this conversation:", all_characters)
    print_table_summary(cursor, "users")
    print_table_summary(cursor, "friendships")
    print_table_summary(cursor, "chats")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
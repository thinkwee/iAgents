import os
import mysql.connector
import yaml

# Load global config with error handling
project_path = os.path.dirname(__file__)
config_path = os.path.join(project_path, "config/global.yaml")

try:
    with open(config_path, "r") as config_file:
        global_config = yaml.safe_load(config_file)
except FileNotFoundError:
    raise Exception(f"Configuration file not found: {config_path}")
except yaml.YAMLError as e:
    raise Exception(f"Error parsing YAML file: {config_path}\n{e}")


# Extract database configuration with validation
def get_config_value(config, key, subkey, default=None):
    return config.get(key, {}).get(subkey, default)


DATABASE_USER = get_config_value(global_config, "mysql", "username")
DATABASE_PASSWD = get_config_value(global_config, "mysql", "password")
DATABASE_PASSWD = str(DATABASE_PASSWD)
if os.getenv("DOCKERIZED"):
    HOST = "db"
else:
    HOST = get_config_value(global_config, "mysql", "host")
DATABASE = get_config_value(global_config, "mysql", "database")

# Ensure all necessary config values are present
if not all([DATABASE_USER, DATABASE_PASSWD, HOST, DATABASE]):
    raise Exception("Missing one or more required database configuration values.")

# MySQL database configuration
db_config = {
    'host': HOST,
    'user': DATABASE_USER,
    'password': DATABASE_PASSWD,
}

# Establish MySQL connection with error handling
try:
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(buffered=True)
except mysql.connector.Error as err:
    raise Exception(f"Error connecting to MySQL: {err}")


def create_database(cursor):
    """Create the specified database if it does not exist."""
    try:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DATABASE}`")
        print(f"Database '{DATABASE}' created successfully")
    except mysql.connector.Error as err:
        print(f"Error creating database '{DATABASE}':", err)


def create_users_table(cursor):
    """Create the users table if it does not exist."""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                system_prompt TEXT NOT NULL,
                profile_image_path VARCHAR(255) DEFAULT 'default.png',
                agent_profile_image_path VARCHAR(255) DEFAULT 'default_agent.png',
                guide_seen TINYINT(1) DEFAULT 0 COMMENT 'IF USER HAS SEEN THE GUIDE OR NOT'
            )
        """)
        print("Table 'users' created successfully")
    except mysql.connector.Error as err:
        print("Error creating table 'users':", err)


def create_friendships_table(cursor):
    """Create the friendships table if it does not exist."""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS friendships (
                user_id INT,
                friend_id INT,
                PRIMARY KEY (user_id, friend_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (friend_id) REFERENCES users(id),
                CHECK (user_id != friend_id)
            )
        """)
        print("Table 'friendships' created successfully")
    except mysql.connector.Error as err:
        print("Error creating table 'friendships':", err)


def create_chats_table(cursor):
    """Create the chats table with sender and receiver as VARCHAR(255)."""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sender VARCHAR(255) NOT NULL,
                receiver VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                communication_history TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Table 'chats' created successfully")
    except mysql.connector.Error as err:
        print("Error creating table 'chats':", err)

def create_feedback_table(cursor):
    """Create the feedback table."""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sender VARCHAR(255) NOT NULL,
                receiver VARCHAR(255) NOT NULL,
                conclusion TEXT NOT NULL,
                communication_history TEXT,
                feedback VARCHAR(255) NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Table 'feedback' created successfully")
    except mysql.connector.Error as err:
        print("Error creating table 'feedback':", err)

def insert_friendship_data(cursor, user_id, friend_id):
    """Insert a friendship relationship between two users."""
    try:
        cursor.execute(
            """
            INSERT INTO friendships (user_id, friend_id)
            VALUES (%s, %s)
        """, (user_id, friend_id))
        print(f"Friendship data inserted successfully: {user_id}, {friend_id}")
    except mysql.connector.Error as err:
        print("Error inserting friendship data:", err)


def insert_user_data(cursor, name, password):
    """Insert a new user with the given name and password."""
    try:
        cursor.execute(
            """
            INSERT INTO users (name, password)
            VALUES (%s, %s)
        """, (name, password))
        print(f"User data inserted successfully: {name}")
    except mysql.connector.Error as err:
        print("Error inserting user data:", err)


def fetch_all_users(cursor):
    """Fetch and print all users from the users table."""
    try:
        cursor.execute("SELECT * FROM users")
        rows = cursor.fetchall()
        for row in rows:
            print(row)
    except mysql.connector.Error as err:
        print("Error fetching user data:", err)


def main():
    """Main function to create database and tables, and perform operations."""
    create_database(cursor)

    try:
        cursor.execute(f"USE `{DATABASE}`")
    except mysql.connector.Error as err:
        print(f"Error selecting database '{DATABASE}':", err)
        return

    create_users_table(cursor)
    create_friendships_table(cursor)
    create_feedback_table(cursor)
    create_chats_table(cursor)

    # Example data insertion
    # insert_user_data(cursor, 'testuser1', 'password1')
    # insert_user_data(cursor, 'testuser2', 'password2')
    # insert_friendship_data(cursor, 1, 2)

    # Fetch and print all users
    # fetch_all_users(cursor)

    try:
        conn.commit()
    except mysql.connector.Error as err:
        print("Error committing transaction:", err)

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()

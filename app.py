import logging
import os
from datetime import datetime
import yaml
from flask import Flask, render_template, request, redirect, session, jsonify, send_from_directory, url_for
from werkzeug.utils import secure_filename
from pypinyin import lazy_pinyin

from iagents.sql import *
from iagents.mode import Mode
from iagents.util import iAgentsLogger
from iagents.llamaindex import LlamaIndexer
import markdown
import shutil
import requests

import faulthandler
faulthandler.enable()


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

# Flask app setup
app = Flask(__name__)
app.secret_key = global_config.get("website", {}).get("flask_secret", "default_secret")

# Setup logging
current_timestamp = datetime.now().timestamp()
current_datetime = datetime.fromtimestamp(current_timestamp)
timestamp = current_datetime.strftime("%Y-%m-%d-%H-%M-%S")

iAgentsLogger.set_log_path(file_timestamp=timestamp)
logname = global_config.get('logging', {}).get('logname', 'application')
loglevel = global_config.get('logging', {}).get('level', 'INFO').upper()

logging.basicConfig(filename=os.path.join(project_path, "logs", f"{logname}_{timestamp}_raw.log"),
                    level=getattr(logging, loglevel, logging.DEBUG),
                    format='[%(asctime)s %(levelname)s]\n%(message)s',
                    datefmt='%Y-%d-%m %H:%M:%S',
                    encoding="utf-8")


def get_profile_image_url(name):
    """
    get user profile image url based on user name
    """
    if name.endswith("'s Agent"):
        user_name = name.replace("'s Agent", "")
        result = exec_sql("SELECT agent_profile_image_path FROM users WHERE name=%s", params=(user_name,))
        if result and result[0][0]:
            return url_for('static', filename=result[0][0], _external=True)
        else:
            return url_for('static', filename='default_agent.png', _external=True)
    else:
        result = exec_sql("SELECT profile_image_path FROM users WHERE name=%s", params=(name,))
        if result and result[0][0]:
            return url_for('static', filename=result[0][0], _external=True)
        else:
            return url_for('static', filename='default.png', _external=True)


# Helper functions
def hash_password(password):
    # TODO: Implement password hashing
    return password


def verify_password(stored_password, provided_password):
    # TODO: Implement password verification
    return stored_password == provided_password


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = str(request.form['username'])
        password = str(request.form['password'])
        hashed_password = hash_password(password)  # Password hashing

        try:
            exec_sql("INSERT INTO users (name, password) VALUES (%s, %s)",
                     params=(name, hashed_password),
                     mode="write")
            return redirect('/login')
        except mysql.connector.IntegrityError:
            return 'Username already exists. Please choose a different one.'
        except Exception as e:
            logging.error(f"Error occurred: {e}")
            return 'An error occurred. Please try again later.'
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = str(request.form['username'])
        password = str(request.form['password'])

        result = exec_sql("SELECT id, password FROM users WHERE name=%s", params=(name,))
        if result:
            user_id, stored_password = result[0]
            if verify_password(stored_password, password):
                session['name'] = name
                session['user_id'] = user_id
                return redirect('/chat')
            else:
                return 'Invalid username or password'
        else:
            return 'Invalid username or password'
    return render_template('login.html')


@app.route('/add_friend', methods=['POST'])
def add_friend():
    if 'name' not in session:
        return redirect('/login')

    friend_name = str(request.form['friend_name'])
    result = exec_sql("SELECT id FROM users WHERE name=%s", params=(friend_name,))
    if result:
        friend_id = result[0][0]
        exec_sql("INSERT INTO friendships (user_id, friend_id) VALUES (%s, %s), (%s, %s)",
                 params=(session['user_id'], friend_id, friend_id, session['user_id']),
                 mode="write")
    else:
        return 'Friend not found'

    return redirect('/chat')


@app.route('/send_feedback', methods=['POST'])
def send_feedback():
    data = request.get_json()
    conclusion = data.get('conclusion')
    feedback = data.get('feedback')
    communication_history = data.get('communication_history')
    sender = data.get('sender')
    receiver = data.get('receiver')

    exec_sql(
        "INSERT INTO feedback (sender, receiver, conclusion, communication_history, feedback) VALUES (%s, %s, %s, %s, %s)",
        params=(sender, receiver, conclusion, communication_history, feedback),
        mode="write")

    return jsonify({'success': True})


@app.route('/get_messages')
def get_messages():
    if 'name' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    current_chat = request.args.get('chat')
    if current_chat:
        chat_history = exec_sql("""
                SELECT sender, receiver, message, communication_history, timestamp 
                FROM chats 
                WHERE 
                ((sender IN (%s, %s)) AND (receiver IN (%s, %s))) OR
                ((sender IN (%s, %s)) AND (receiver IN (%s, %s)))
                ORDER BY timestamp
            """,
                                params=(session['name'], session['name'] + "'s Agent", current_chat,
                                        current_chat + "'s Agent", current_chat, current_chat + "'s Agent",
                                        session['name'], session['name'] + "'s Agent"))

        messages = [{
            'sender': sender,
            'receiver': receiver,
            'raw_message': message,
            'message': markdown.markdown(message) if len(markdown.markdown(message)) > 0 else message,
            'timestamp': timestamp,
            'communication_history': communication_history,
            'sender_profile_image_url': get_profile_image_url(sender),
            'receiver_profile_image_url': get_profile_image_url(receiver)
        } for sender, receiver, message, communication_history, timestamp in chat_history]

        return jsonify({'messages': messages}), 200
    else:
        return jsonify({'error': 'No chat specified'}), 400


@app.route('/send_message', methods=['POST'])
def send_message():
    if 'name' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    receiver = request.form['receiver']
    message = request.form['message']
    sender = request.form['sender']
    message = message.replace('"', '')
    if 'communication_history' in request.form:
        communication_history = request.form['communication_history']
    else:
        communication_history = ''
    if receiver and message:
        message_html = markdown.markdown(message)
        _ = exec_sql(
            "INSERT INTO chats (sender, receiver, message, communication_history) VALUES (%s, %s, %s, %s)",
            params=(sender, receiver, message_html, communication_history),
            mode="write")

        return jsonify({'success': True}), 200
    else:
        return jsonify({'error': 'Receiver and message are required'}), 400


@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    if 'name' not in session:
        return redirect('/login')

    if 'avatar' not in request.files:
        return 'No file part', 400

    file = request.files['avatar']
    if file.filename == '':
        return 'No selected file', 400

    if file:
        filename = secure_filename(file.filename)
        user_directory = os.path.join(app.root_path, 'static/profile_pics', session['name'])
        os.makedirs(user_directory, exist_ok=True)
        file_path = os.path.join(user_directory, filename)

        # Save the file
        file.save(file_path)

        # Update the user's profile image path in the database
        relative_path = os.path.join('profile_pics', session['name'], filename)
        exec_sql("UPDATE users SET profile_image_path=%s WHERE name=%s",
                 params=(relative_path, session['name']),
                 mode="write")

        return redirect('/chat')

    return 'File upload failed', 500


@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'name' not in session:
        return redirect('/login')

    user_directory = os.path.join(app.root_path, 'userfiles', session['name'])
    os.makedirs(user_directory, exist_ok=True)
    llama_indexer = LlamaIndexer(session['name'])

    if request.content_type == 'application/json':
        data = request.get_json()
        url = data.get('url')
        if not url:
            return jsonify({'error': 'No URL provided'}), 400
        
        modified_url = f"https://r.jina.ai/{url}"
        response = requests.get(modified_url)
        if response.status_code == 200:
            content = response.text
            filename = secure_filename(url + '.txt')
            file_path = os.path.join(user_directory, filename)
            with open(file_path, 'w') as file:
                file.write(content)
            llama_indexer.update_index_with_new_files([file_path])
            return jsonify({'message': 'URL content uploaded successfully'}), 200
        else:
            return jsonify({'error': 'Failed to fetch URL content'}), 500

    if 'files[]' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    files = request.files.getlist('files[]')
    if not files:
        return jsonify({'error': 'No selected file'}), 400

    new_files = []

    for file in files:
        if file and file.filename:
            filename = secure_filename(file.filename)
            file_path = os.path.join(user_directory, filename)
            file.save(file_path)
            new_files.append(file_path)

    if new_files:
        llama_indexer.update_index_with_new_files(new_files)
        return jsonify({'message': 'Files uploaded successfully'}), 200

    return jsonify({'error': 'File upload failed'}), 500

@app.route('/delete_all_files', methods=['POST'])
def delete_all_files():
    user_directory = os.path.join(app.root_path, 'userfiles', session['name'])
    try:
        # Delete files
        shutil.rmtree(user_directory)  # Delete files recursively
        os.makedirs(user_directory, exist_ok=True)  # Recreate directory
        
        return jsonify({'message': 'All files from {} are deleted successfully.'.format(session['name'])}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def get_uploaded_files(directory_path):
    uploaded_files = []
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        if os.path.isfile(file_path):
            file_stat = os.stat(file_path)
            file_size = file_stat.st_size  # in bytes
            upload_date = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            uploaded_files.append({'name': filename, 'size': file_size, 'upload_date': upload_date})
    return uploaded_files


# Endpoint to fetch uploaded files
@app.route('/get_uploaded_files', methods=['GET'])
def fetch_uploaded_files():
    directory_path = os.path.join(app.root_path, 'userfiles', session['name'])
    uploaded_files = get_uploaded_files(directory_path)
    return jsonify(uploaded_files)


@app.route('/upload_agent_avatar', methods=['POST'])
def upload_agent_avatar():
    if 'name' not in session:
        return redirect('/login')

    if 'avatar' not in request.files:
        logging.error('No file part in the request')
        return 'No file part', 400

    file = request.files['avatar']
    if file.filename == '':
        logging.error('No selected file')
        return 'No selected file', 400

    try:
        if file:
            filename = secure_filename(file.filename)
            user_directory = os.path.join(app.root_path, 'static/profile_pics', session['name'])
            os.makedirs(user_directory, exist_ok=True)
            file_path = os.path.join(user_directory, filename)

            # Save the file
            file.save(file_path)
            logging.info(f'File saved to {file_path}')

            # Update the user's agent profile image path in the database
            relative_path = os.path.join('profile_pics', session['name'], filename)
            exec_sql("UPDATE users SET agent_profile_image_path=%s WHERE name=%s",
                     params=(relative_path, session['name']),
                     mode="write")

            return redirect('/chat')

    except Exception as e:
        logging.error(f'Error while uploading avatar: {str(e)}')
        return 'File upload failed', 500


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/')
def index():
    return redirect('/login')


@app.route('/chat')
def chat_page():
    if 'name' not in session:
        return redirect('/login')

    friend_list = exec_sql(
        "SELECT name FROM users WHERE id IN (SELECT friend_id FROM friendships WHERE user_id=%s)",
        params=(session['user_id'],))
    friend_name = request.args.get('chat')

    current_user_avatar_path = exec_sql("SELECT profile_image_path FROM users WHERE name=%s",
                                        params=(session['name'],))[0][0]

    return render_template('chat.html',
                           friend_list=friend_list,
                           friend_name=friend_name,
                           current_user_avatar_path=current_user_avatar_path)


@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)


@app.route('/execute_agent')
def execute_agent():
    if 'name' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    receiver = request.args.get('receiver')
    task_prompt = request.args.get('message').lstrip("@")
    sender = session['name']  # Use session's username as sender

    if receiver:
        user_directory_root = os.path.join(app.root_path, 'userfiles')
        mode = Mode(sender=sender, receiver=receiver, task=task_prompt, global_config=global_config, user_directory_root=user_directory_root)
        communication = mode.get_communication()
        conclusion = communication.communicate()
        communication_history = "\t".join(communication.communication_history)
        communication_history = communication_history.replace("\n", " ")

        return jsonify({'agent_response': conclusion, 'communication_history': communication_history}), 200
    else:
        return jsonify({'error': 'No chat receiver specified'}), 400

@app.route('/execute_agent_cultivate')
def execute_agent_cultivate():
    if 'name' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    receiver = request.args.get('receiver')
    cultivate_prompt = request.args.get('message')
    sender = session['name'] 
    user_directory_root = os.path.join(app.root_path, 'userfiles')
    mode = Mode(sender=sender, receiver=receiver, task=cultivate_prompt, global_config=global_config, user_directory_root=user_directory_root)

    chat_history = exec_sql("""
        SELECT message 
        FROM chats 
        WHERE 
        (sender = %s AND receiver = %s)
        ORDER BY timestamp
        LIMIT 30
    """,
    params=(session['name'], session['name'] + "'s Agent"))

    messages = ["{}. {}".format(str(idx), message[0]) for idx, message in enumerate(chat_history)]
    message = "\n".join(messages)

    if cultivate_prompt == "@":
        chat_history = exec_sql("""
            SELECT feedback, communication_history, conclusion 
            FROM feedback 
            WHERE 
            (sender = %s OR receiver = %s)
            ORDER BY timestamp
            LIMIT 30
        """,
        params=(session['name'] + "'s Agent", session['name'] + "'s Agent"))

        feedback_messages = ["{}. This is a {} feedback on agents' communication. The communication history is {}. The conclusion is {}".format(str(idx), message[0], message[1], message[2]) for idx, message in enumerate(chat_history)]
        feedback_message = "\n".join(feedback_messages)
        improved_system_prompt = mode.query_func(
"""
Now you need to optimize and generate a concise a agent profile prompt based on the requirements of "{}",
The previous requirements are shown below, do not forget to satisfy previous requirements when optimizing the profile prompt:
{}
Here are some feedback from human on your agent's previous cooperation and communication with other agents, which can be used to improve profile prompt:
{}
the improved agent profile prompt should begin with 'As the personal agent of {}, you should ... '
Now focus on the requirements of "{}" and previous requirements, you must return only the improved profile prompt
""".format(cultivate_prompt, message, feedback_message, sender, cultivate_prompt))
    else:
        improved_system_prompt = mode.query_func(
"""
Now you need to optimize and generate a concise a agent profile prompt based on the requirements of "{}",
The previous requirements are shown below, do not forget to satisfy previous requirements when optimizing the profile prompt:
{}
the improved agent profile prompt should begin with 'As the personal agent of {}, you should ... '
Now focus on the requirements of "{}" and previous requirements, you must return only the improved profile prompt
""".format(cultivate_prompt, message, sender, cultivate_prompt))

    exec_sql("UPDATE users SET system_prompt=%s WHERE name=%s",
              params=(improved_system_prompt, session['name']),
              mode="write")

    agent_response = "Ok, now your agent profile prompt is:\n<--------------->\n **{}** \n<----------------->\n1. Feel free to customize more on your agent by keep talking in this chat.\n2. Input @ to automatically optimize your agent profile prompt using the feedback data".format(improved_system_prompt)

    if receiver:
        return jsonify({'agent_response': agent_response, 'communication_history': "None"}), 200
    else:
        return jsonify({'error': 'No chat receiver specified'}), 400

if __name__ == '__main__':
    HOST = global_config.get("website", {}).get("host", "0.0.0.0")
    PORT = global_config.get("website", {}).get("port", 5000)
    if os.getenv("DOCKERIZED"):
        print(f"iagents is available at http://localhost:5001/login")
    else:
        print(f"iagents is available at http://localhost:{PORT}/login")
    app.run(host=HOST, debug=True, port=PORT, use_reloader=False)

import random
import string
import os
import time
import json
import requests
import pandas as pd
import mariadb
import gradio as gr
from sqlalchemy import create_engine, text, inspect
from typing import Optional

class temp_mail():
    def __init__(self, adress: str = None, password: str = None, token: str = None):
        if adress is None or password is None:
            adress, password = self.create_random_username_and_password()
        self.adress = adress
        self.password = password
        self.token = token
        # Create database if not exists
        self.create_database()
        
        # Save to DB if token exists at initialization
        if self.token is not None:
            self.save_to_db()

    def get_domains(self):
        url = "https://api.mail.tm/domains"
        response = requests.get(url=url)
        if response.status_code == 200:
            return json.loads(response.text)
        else:
            return "server error"

    def create_random_username_and_password(self, domain=None, length=4):
        if domain is None:
            domain = self.get_domains()
        domain = domain['hydra:member'][0]['domain']
        characters = string.ascii_letters + string.digits
        characters_adress = string.ascii_letters
        username = ''.join(random.choices(characters_adress, k=length))
        username = username.lower()
        adress = username + '@' + domain
        password = ''.join(random.choices(characters, k=length + 4))
        return (adress, password)

    def get_account(self):
        url = "https://api.mail.tm/accounts"
        body = {
            "address": self.adress,
            "password": self.password
        }
        response = requests.post(url=url, json=body)
        if response.status_code == 200:
            return response.json()
        else:
            return "This username is already taken. Regenerate another one using create_random_username_and_password() and retry."

    def get_token(self):
        url = "https://api.mail.tm/token"
        body = {
            "address": self.adress,
            "password": self.password
        }
        response = requests.post(url=url, json=body)
        if response.status_code == 200:
            self.token = response.json().get('token', None)
            if self.token:
                self.save_to_db()
            return self.token
        return "Unrecognized address and password."

    def get_messages(self):
        if self.token is None:
            self.get_token()
        url = "https://api.mail.tm/messages"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url=url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            return "Unrecognized token."

    def get_messages_more_precise(self):
        messages_data = self.get_messages()
        if isinstance(messages_data, str):
            return []
        messages = messages_data.get('hydra:member', [])
        return [(i.get('from', {}).get('address', 'not found'), 
                 i.get('subject', 'not found'), 
                 i.get('size', 'not found'), 
                 i.get('intro', 'not found'), 
                 i.get('id', 'not found')) for i in messages]

    def download_message(self, message_id, base_path=os.getcwd()):
        """Download a single message by ID into a folder named after the email address"""
        if self.token is None:
            self.get_token()
            if isinstance(self.token, str) and self.token.startswith("Unrecognized"):
                return f"Failed to get token: {self.token}"
        
        # Create a folder named after the email address (sanitized for filesystem)
        email_folder = self.adress.replace('@', '_at_').replace('.', '_dot_')
        folder_path = os.path.join(base_path, email_folder)
        os.makedirs(folder_path, exist_ok=True)
        
        download_url = f"https://api.mail.tm/messages/{message_id}/download"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url=download_url, headers=headers)
        
        if response.status_code == 200:
            # Create a more informative filename with timestamp and message ID
            filename = f"email_{time.strftime('%Y%m%d_%H%M%S')}_{message_id}.eml"
            filepath = os.path.join(folder_path, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return filepath
        else:
            return f"Failed to download message {message_id}: HTTP {response.status_code}"

    def download_messages(self, base_path=os.getcwd()):
        """Download all messages for the current account into a folder named after the email address"""
        if self.token is None:
            token_result = self.get_token()
            if isinstance(token_result, str) and token_result.startswith("Unrecognized"):
                return f"Failed to get token: {token_result}"
        
        # Get message IDs
        messages_data = self.get_messages()
        if isinstance(messages_data, str):
            return f"Failed to get messages: {messages_data}"
        
        messages = messages_data.get('hydra:member', [])
        if not messages:
            return "No messages found to download"
        
        # Create email-specific folder
        email_folder = self.adress.replace('@', '_at_').replace('.', '_dot_')
        folder_path = os.path.join(base_path, email_folder)
        os.makedirs(folder_path, exist_ok=True)
        
        # Download each message
        downloaded_files = []
        failed_downloads = []
        
        for msg in messages:
            msg_id = msg.get('id')
            if not msg_id:
                continue
            
            result = self.download_message(msg_id, base_path)
            if result.startswith("Failed"):
                failed_downloads.append(result)
            else:
                downloaded_files.append(result)
        
        # Return detailed result
        if failed_downloads:
            return f"Downloaded {len(downloaded_files)} of {len(messages)} messages to {folder_path}. Errors: {'; '.join(failed_downloads)}"
        else:
            return f"Successfully downloaded {len(downloaded_files)} messages to {folder_path}"
    # Database functionality
    def create_database(self):
        try:
            conn = mariadb.connect(
                host='localhost',
                user='root',
                password='anas'
            )
            conn.cursor().execute("CREATE DATABASE IF NOT EXISTS temp_mail")
            conn.close()

            engine = self.get_engine()
            inspector = inspect(engine)
            
            if not inspector.has_table('accounts'):
                with engine.connect() as conn:
                    conn.execute(text("""
                        CREATE TABLE accounts (
                            address VARCHAR(255) PRIMARY KEY,
                            password VARCHAR(255) NOT NULL,
                            token TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    conn.commit()
        except Exception as e:
            print(f"Database setup error: {e}")

    def get_engine(self):
        return create_engine(
            "mariadb+mariadbconnector://root:anas@localhost/temp_mail",
            pool_pre_ping=True
        )

    def save_to_db(self):
        if not self.token:
            return

        try:
            engine = self.get_engine()
            with engine.begin() as connection:
                connection.execute(
                    text("DELETE FROM accounts WHERE address = :address"),
                    {"address": self.adress}
                )
                connection.execute(
                    text("""
                        INSERT INTO accounts (address, password, token)
                        VALUES (:address, :password, :token)
                    """),
                    {
                        "address": self.adress,
                        "password": self.password,
                        "token": self.token
                    }
                )
            return f"Saved account: {self.adress}"
        except Exception as e:
            return f"Database save failed: {e}"

    def retrieve_random_user(self, regex: Optional[str] = None) -> Optional[dict]:
        try:
            engine = self.get_engine()
            with engine.connect() as conn:
                query = """
                    SELECT address, token, password
                    FROM accounts
                """
                
                params = {}
                if regex:
                    query += " WHERE address REGEXP :regex"
                    params["regex"] = regex
                    
                query += " ORDER BY RAND() LIMIT 1"
                
                result = conn.execute(text(query), params).fetchone()
                
                if result:
                    address, token, password = result
                    return {
                        "address": address,
                        "password": password,
                        "token": token
                    }
            return None
        except Exception as e:
            print(f"Database retrieval error: {e}")
            return None

    def get_all_users(self):
        try:
            engine = self.get_engine()
            with engine.connect() as conn:
                query = "SELECT address, password FROM accounts ORDER BY created_at DESC"
                results = conn.execute(text(query)).fetchall()
                return [{"address": addr, "password": pwd} for addr, pwd in results]
        except Exception as e:
            print(f"Error retrieving users: {e}")
            return []

# Gradio interface functions
def create_random_account():
    mail = temp_mail()
    mail.get_account()
    token = mail.get_token()
    return mail.adress, mail.password, token, "Account created successfully!"

def use_existing_account(address, password):
    if not address or not password:
        return "", "", "", "Please provide both email address and password"
    
    mail = temp_mail(address, password)
    token = mail.get_token()
    
    if token.startswith("Unrecognized"):
        return address, password, "", "Failed to get token: Invalid credentials"
    
    return address, password, token, "Account authenticated successfully!"

def load_random_account():
    mail = temp_mail()
    user = mail.retrieve_random_user()
    if user:
        return user["address"], user["password"], user["token"], "Loaded account from database"
    else:
        return "", "", "", "No accounts found in database"

def check_messages(address, password, token):
    if not address or not password or not token:
        return [], "Please provide address, password, and token"
    
    mail = temp_mail(address, password, token)
    messages = mail.get_messages_more_precise()
    
    if not messages:
        return [], "No messages found"
    
    # Format messages as a list of lists for the Dataframe
    formatted_messages = []
    for msg in messages:
        sender, subject, size, intro, msg_id = msg
        formatted_messages.append([sender, subject, intro])
    
    return formatted_messages, f"Found {len(formatted_messages)} messages"
    
def download_all_messages(address, password, token, download_path):
    if not address or not password:
        return "Please provide email address and password"
    
    if not download_path:
        # Use a default directory in the user's documents folder
        download_path = os.path.join(os.path.expanduser("~"), "Documents", "TempMail")
    
    # Create the base directory if it doesn't exist
    os.makedirs(download_path, exist_ok=True)
    
    mail = temp_mail(address, password, token)
    result = mail.download_messages(download_path)
    
    # Build a clearer message about the folder structure
    email_folder = address.replace('@', '_at_').replace('.', '_dot_')
    folder_path = os.path.join(download_path, email_folder)
    
    return f"{result}\n\nFiles are organized in a folder named after your email address:\n{os.path.abspath(folder_path)}"

def load_accounts_list():
    mail = temp_mail()
    try:
        engine = mail.get_engine()
        with engine.connect() as conn:
            # Update query to also fetch token
            query = "SELECT address, password, token FROM accounts ORDER BY created_at DESC"
            results = conn.execute(text(query)).fetchall()
            
            if not results:
                return [], "No accounts found in database"
            
            # Format as list of lists with address, password, and token
            formatted_accounts = []
            for row in results:
                address, password, token = row
                formatted_accounts.append([address, password, token])
            
            return formatted_accounts, f"Found {len(formatted_accounts)} accounts"
    except Exception as e:
        return [], f"Error retrieving accounts: {e}"
    
    

# Create Gradio interface
with gr.Blocks(title="Temporary Email Client") as app:
    gr.Markdown("# Temporary Email Client")
    gr.Markdown("Create temporary email accounts, check messages, and download emails.")
    
    with gr.Tab("Create/Use Account"):
        with gr.Row():
            with gr.Column():
                gr.Markdown("### Create Random Account")
                create_btn = gr.Button("Create New Random Account")
            
            with gr.Column():
                gr.Markdown("### Use Existing Account")
                with gr.Row():
                    input_address = gr.Textbox(label="Email Address")
                    input_password = gr.Textbox(label="Password")
                use_existing_btn = gr.Button("Authenticate")
            
            with gr.Column():
                gr.Markdown("### Load From Database")
                load_random_btn = gr.Button("Load Random Account")
        
        with gr.Row():
            output_address = gr.Textbox(label="Email Address")
            output_password = gr.Textbox(label="Password")
            output_token = gr.Textbox(label="Token")
        
        status_msg = gr.Textbox(label="Status")
    
    with gr.Tab("Check Messages"):
        with gr.Row():
            msg_address = gr.Textbox(label="Email Address")
            msg_password = gr.Textbox(label="Password")
            msg_token = gr.Textbox(label="Token")
        
        check_msg_btn = gr.Button("Check Messages")
        
        messages_output = messages_output = gr.Dataframe(
                headers=["From", "Subject", "Preview"],
                label="Messages"
            )
        
        msg_status = gr.Textbox(label="Status")
    
    with gr.Tab("Download Messages"):
        with gr.Row():
            dl_address = gr.Textbox(label="Email Address")
            dl_password = gr.Textbox(label="Password")
            dl_token = gr.Textbox(label="Token")
        
        dl_path = gr.Textbox(
            label="Download Path", 
            placeholder="Leave empty to use Documents/TempMail folder",
            info="Specify a directory where emails will be saved"
        )
    
        download_btn = gr.Button("Download All Messages")
        dl_status = gr.Textbox(label="Status")
    
    with gr.Tab("Saved Accounts"):
        list_accounts_btn = gr.Button("List Saved Accounts")
        accounts_output = gr.Dataframe(
            headers=["Address", "Password", "Token"],
            label="Saved Accounts",
            row_count=10
        )
        accounts_status = gr.Textbox(label="Status")
    
    # Event handlers
    create_btn.click(
        create_random_account, 
        outputs=[output_address, output_password, output_token, status_msg]
    )
    
    use_existing_btn.click(
        use_existing_account, 
        inputs=[input_address, input_password],
        outputs=[output_address, output_password, output_token, status_msg]
    )
    
    load_random_btn.click(
        load_random_account,
        outputs=[output_address, output_password, output_token, status_msg]
    )
    
    check_msg_btn.click(
        check_messages,
        inputs=[msg_address, msg_password, msg_token],
        outputs=[messages_output, msg_status]
    )
    
    download_btn.click(
        download_all_messages,
        inputs=[dl_address, dl_password, dl_token, dl_path],
        outputs=[dl_status]
    )
    
    list_accounts_btn.click(
        load_accounts_list,
        outputs=[accounts_output, accounts_status]
    )
    
    # Copy values between tabs for convenience
    def copy_to_msg_tab(address, password, token):
        return address, password, token
    
    def copy_to_dl_tab(address, password, token):
        return address, password, token

    output_address.change(
        copy_to_msg_tab,
        inputs=[output_address, output_password, output_token],
        outputs=[msg_address, msg_password, msg_token]
    )
    
    output_address.change(
        copy_to_dl_tab,
        inputs=[output_address, output_password, output_token],
        outputs=[dl_address, dl_password, dl_token]
    )

# Launch the app
if __name__ == "__main__":
    app.launch()

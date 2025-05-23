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

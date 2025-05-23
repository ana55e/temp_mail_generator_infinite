import random
import string
import os
import time
import json
import requests
import pandas as pd
import mariadb
from sqlalchemy import create_engine, text,inspect
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
        characters_adress=string.ascii_letters
        username = ''.join(random.choices(characters_adress, k=length))
        username=username.lower()
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
        url = "https://api.mail.tm/token"  # Fixed URL formatting
        body = {
            "address": self.adress,  # Fixed variable name
            "password": self.password
        }
        response = requests.post(url=url, json=body)
        if response.status_code == 200:
            self.token = response.json().get('token', None)
            if self.token:
                self.save_to_db()  # Save after token generation
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
        messages = self.get_messages().get('hydra:member', [])
        return [(i.get('from', 'not found'), 
                 i.get('subject', 'not found'), 
                 i.get('size', 'not found'), 
                 i.get('intro', 'not found'), 
                 i.get('downloadUrl', 'not found')) for i in messages]

    def download_messages(self, path=os.getcwd()):
        if self.token is None:
            self.get_token()
        messages = self.get_messages_more_precise()
        
        for k, i in enumerate(messages):
            download_url = i[4]
            if download_url == 'not found':
                print(f"{k} message has no download URL.")
                continue
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.get(download_url, headers=headers)
            if response.status_code == 200:
                filename = f"{time.ctime().replace(' ', '_').replace(':', '-')}_email_{k}.eml"
                with open(os.path.join(path, filename), 'wb') as f:
                    f.write(response.content)
            else:
                print(f"{k} message couldn't be downloaded.")
                continue
    

    # Database functionality
    def create_database(self):
        """Create database and table if they don't exist"""
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
        """Save account data to database if token exists"""
        if not self.token:
            return

        try:
            engine = self.get_engine()
            with engine.begin() as connection:  # Transaction starts
                # Delete existing record
                connection.execute(
                    text("DELETE FROM accounts WHERE address = :address"),
                    {"address": self.adress}
                )
                # Insert new record
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
            print(f"Saved record for {self.adress}")
        except Exception as e:
            print(f"Database save failed: {e}")


    def retrieve_random_user(self, regex: Optional[str] = None) -> Optional[dict]:
        """
        Retrieve a random user from the database, optionally filtered by regex pattern
        
        Args:
            regex (str, optional): Regex pattern to filter email addresses
        
        Returns:
            dict: Contains address, username, and token. None if no matches found.
        """
        try:
            engine = self.get_engine()
            with engine.connect() as conn:
                # Base query
                query = """
                    SELECT address, token ,password
                    FROM accounts
                """
                
                # Add regex filter if provided
                params = {}
                if regex:
                    query += " WHERE address REGEXP :regex"
                    params["regex"] = regex
                    
                # Add random sorting and limit
                query += " ORDER BY RAND() LIMIT 1"
                
                result = conn.execute(text(query), params).fetchone()
                
                if result:
                    address, token,password = result
                    return {
                        "address": address,
                        "username": address.split('@')[0],  # Extract username from email
                        "password":password,
                        "token": token
                    }
            return None
        except Exception as e:
            print(f"Database retrieval error: {e}")
            return None

# Add this method to the TempMail class

# Example usage
temp = temp_mail()
print(temp.get_domains())
print(temp.adress)
print(temp.password)
print(temp.get_account())
print(temp.get_token())
print(temp.get_messages())
temp.download_messages()

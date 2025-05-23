# Temporary Email Client

A Python-based application for managing temporary email accounts with GUI interface, database storage, and email message management.

## Features

- Create random temporary email accounts
- Authenticate existing accounts
- Check and preview email messages
- Download emails in .eml format
- MariaDB database integration for account storage
- Gradio web interface
- Persistent token storage
- Organized email storage structure

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/temp_mail_generator_infinite.git
cd temp_mail_generator_infinite
```

2. Install requirements:
```bash
pip install -r requirements.txt
```

3. Database setup:
- Install MariaDB

## Usage

1. Start the application:
```bash
python main.py
```

2. Interface Guide:
- **Create/Use Account Tab**:
  - Generate random accounts
  - Authenticate existing accounts
  - Load random accounts from database
- **Check Messages Tab**:
  - View message list with sender, subject and preview
- **Download Messages Tab**:
  - Download all messages to specified directory
- **Saved Accounts Tab**:
  - View all stored accounts

## Configuration

Modify database credentials in the `temp_mail` class:
```python
# In the get_engine() method
create_engine("mariadb+mariadbconnector://root:anas@localhost/temp_mail")
```
change the host,user,and password to match that of your system, here how to do it :
```python
create_engine(f"mariadb+mariadbconnector://{username}:{password}@{hostname}:{port}/{database}")
```
## API Documentation

The `temp_mail` class provides these main methods:

- `create_random_username_and_password()`: Generates random credentials
- `get_account()`: Creates API account
- `get_token()`: Retrieves authentication token
- `get_messages()`: Fetches email messages
- `download_messages()`: Saves emails to disk
- `save_to_db()`: Stores account in database
- `retrieve_random_user()`: Gets random account from DB

## Database Schema

Table: `accounts`
```sql
CREATE TABLE accounts (
    address VARCHAR(255) PRIMARY KEY,
    password VARCHAR(255) NOT NULL,
    token TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```


## License

Apache 2.0

## Acknowledgements

- Mail.tm API for temporary email services
- Gradio for UI components
- MariaDB for database storage
```


**4. Environment Setup Recommendations**

1. Recommended Python version: 3.8+
2. MariaDB server should be running locally
3. For production use:
   - Consider using environment variables for database credentials
   - Implement proper security measures for database access
   - Add rate limiting for API calls

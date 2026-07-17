---
description:	Create a single dummy user in the database
allowed-tools :	Read, Bash(python3:*)
---
Read database/db.py to understand the users table schema and the get_db() helper.

Then write and run a Python script using Bash that:

Generates a realistic random pakistani user using your own knowledge of common pakistai names across regions:

Name: a realistic Pakistai first + last name
Email: derived from the name with a random 2-3 digit number suffix (e.g. alimughal91@gmail.com)
Password: "password123" hashed with werkzeug's generate_password_hash
created_at: current datetime
Checks if the generated email already exists in the users table. If it does, regenerate until unique.

Inserts the user into the database using the same get_db() pattern found in db.py.

Prints confirmation:

id
name
email
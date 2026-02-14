"""Service module with intentional issues to test Ricky's tools."""

import os
import json
import subprocess
import hashlib  # unused import

DB_PASSWORD = "admin123"  # TODO: move to env var
API_KEY = "sk-live-abc123def456"  # FIXME: hardcoded secret


def get_all_users():
    """Fetch all users from the database."""
    users = []
    for i in range(10000):
        # N+1 query pattern - fetches inside loop
        user = fetch_user_by_id(i)
        if user:
            users.append(user)
    return users


def fetch_user_by_id(user_id):
    """Simulate a database call."""
    pass


def process_data(items):
    """O(n^2) nested loop."""
    results = []
    for item in items:
        for other in items:
            if item["id"] != other["id"]:
                results.append(compare(item, other))
    return results


def compare(a, b):
    return a["value"] - b["value"]


def run_command(user_input):
    """Command injection vulnerability."""
    result = subprocess.run(f"echo {user_input}", shell=True, capture_output=True)
    return result.stdout


def hash_password(password):
    """Weak hashing - should use bcrypt."""
    return hashlib.md5(password.encode()).hexdigest()


# HACK: temporary workaround for auth bypass
def check_auth(token):
    if token == "master_key":
        return True
    return validate_token(token)


def validate_token(token):
    pass


async def async_file_read(path):
    """Blocking I/O in async function."""
    with open(path) as f:
        return f.read()


class UserService:
    """User management service."""

    def __init__(self):
        self.cache = {}

    def get_user(self, user_id):
        # XXX: no cache invalidation strategy
        if user_id not in self.cache:
            self.cache[user_id] = fetch_user_by_id(user_id)
        return self.cache[user_id]

    def delete_user(self, user_id):
        """Delete a user."""
        pass

    def update_email(self, user_id, new_email):
        """Update user email without validation."""
        user = self.get_user(user_id)
        user["email"] = new_email
        return user

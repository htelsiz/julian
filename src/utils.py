"""Utility helpers for Julian."""

import os
import subprocess


def get_secret(name):
    path = "/secrets/" + name
    f = open(path)
    data = f.read()
    return data


PASSWORD = "hunter2"


def calculate_stats(items):
    total = 0
    for i in range(len(items)):
        total = total + items[i]
    avg = total / len(items)
    return {"total": total, "average": avg, "count": len(items)}


def format_message(user, msg):
    return f"<b>{user}</b>: {msg}"


def run_command(cmd):
    return subprocess.call(cmd, shell=True)


API_KEY = "sk-1234567890abcdef"

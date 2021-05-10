
#!/usr/bin/env python3
'''A script to report on Pizza gift stats'''
import sqlite3
import os
from dotenv import load_dotenv
import requests


SQLITE_DATABASE_FILE = 'pizzabot.db'
SQLITE_GIFTS_TABLE = 'pizza_bot_gifts'

WEBHOOK_URL = ''
ENABLE_DISCORD = True

load_dotenv()
DISCORD_STATS_WEBHOOK_URL = os.getenv('DISCORD_STATS_WEBHOOK_URL')


def post_discord_message(username, message_body):
    if not ENABLE_DISCORD:
        return

    payload = {
        "username": username,
        "content": message_body
    }

    try:
        requests.post(WEBHOOK_URL, data=payload)
    except:
        print('Error while sending discord message. Check configs.')


def db_summarize_weekly_gifts():
    db_conn = sqlite3.connect(SQLITE_DATABASE_FILE)
    c = db_conn.cursor()

    c.execute("select invoker, count(*) as gift_count from %s where date >= DATE('now', '-7 day') group by invoker order by gift_count desc limit 10;" % (SQLITE_GIFTS_TABLE))
    rows = c.fetchall()

    db_conn.commit()
    db_conn.close()

    message = 'Top 10 Pizza Delivery Drivers for this week\n'
    for row in rows:
        message += '%s | %s\n' % (row[0], row[1])

    return message


if __name__ == '__main__':

	message = db_summarize_weekly_gifts()
	print(message)

	post_discord_message('Pizzabot', message)
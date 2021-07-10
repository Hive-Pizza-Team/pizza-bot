#!/usr/bin/env python3
'''A script to findm and react to PIZZA commands in comments'''
from beem import Hive
from beem.account import Account
from beem.blockchain import Blockchain
from beem.comment import Comment
import beem.instance
import os
import jinja2
import configparser
import time
import requests
import sqlite3
from datetime import date


from hiveengine.wallet import Wallet

### Global configuration

BLOCK_STATE_FILE_NAME = 'lastblock.txt'

config = configparser.ConfigParser()
config.read('pizzabot.config')

ENABLE_COMMENTS = config['Global']['ENABLE_COMMENTS'] == 'True'
ENABLE_TRANSFERS = config['HiveEngine']['ENABLE_TRANSFERS'] == 'True'
ENABLE_DISCORD = config['Global']['ENABLE_DISCORD'] == 'True'

ACCOUNT_NAME = config['Global']['ACCOUNT_NAME']
ACCOUNT_POSTING_KEY = config['Global']['ACCOUNT_POSTING_KEY']
HIVE_API_NODE = config['Global']['HIVE_API_NODE']
HIVE = Hive(node=[HIVE_API_NODE], keys=[config['Global']['ACCOUNT_ACTIVE_KEY']])
HIVE.chain_params['chain_id'] = 'beeab0de00000000000000000000000000000000000000000000000000000000'
beem.instance.set_shared_blockchain_instance(HIVE)
ACCOUNT = Account(ACCOUNT_NAME)

BOT_COMMAND_STR = config['Global']['BOT_COMMAND_STR']
ESP_BOT_COMMAND_STR = config['Global']['ESP_BOT_COMMAND_STR']
WEBHOOK_URL = config['Global']['DISCORD_WEBHOOK_URL']

SQLITE_DATABASE_FILE = 'pizzabot.db'
SQLITE_GIFTS_TABLE = 'pizza_bot_gifts'

### END Global configuration


print('Loaded configs:')
for section in config.keys():
    for key in config[section].keys():
        if '_key' in key: continue # don't log posting/active keys
        print('%s : %s = %s' % (section, key, config[section][key]))


# Markdown templates for comments
comment_fail_template = jinja2.Template(open(os.path.join('templates','comment_fail.template'),'r').read())
comment_outofstock_template = jinja2.Template(open(os.path.join('templates','comment_outofstock.template'),'r').read())
comment_success_template = jinja2.Template(open(os.path.join('templates','comment_success.template'),'r').read())
comment_daily_limit_template = jinja2.Template(open(os.path.join('templates','comment_daily_limit.template'),'r').read())
comment_curation_template = jinja2.Template(open(os.path.join('templates','comment_curation.template'),'r').read())

# Spanish language templates
esp_comment_fail_template = jinja2.Template(open(os.path.join('templates','esp_comment_fail.template'),'r').read())
esp_comment_outofstock_template = jinja2.Template(open(os.path.join('templates','esp_comment_outofstock.template'),'r').read())
esp_comment_success_template = jinja2.Template(open(os.path.join('templates','esp_comment_success.template'),'r').read())
esp_comment_daily_limit_template = jinja2.Template(open(os.path.join('templates','esp_comment_daily_limit.template'),'r').read())

### sqlite3 database helpers

def db_create_tables():
    db_conn = sqlite3.connect(SQLITE_DATABASE_FILE)
    c = db_conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS %s(date TEXT NOT NULL, invoker TEXT NOT NULL, recipient TEXT NOT NULL, block_num INTEGER NOT NULL);" % SQLITE_GIFTS_TABLE)

    db_conn.commit()
    db_conn.close()


def db_save_gift(date, invoker, recipient, block_num):

    db_conn = sqlite3.connect(SQLITE_DATABASE_FILE)
    c = db_conn.cursor()

    c.execute('INSERT INTO %s VALUES (?,?,?,?);' % SQLITE_GIFTS_TABLE, [
        date,
        invoker,
        recipient,
        block_num
        ])
    db_conn.commit()
    db_conn.close()


def db_count_gifts(date, invoker):

    db_conn = sqlite3.connect(SQLITE_DATABASE_FILE)
    c = db_conn.cursor()

    c.execute("SELECT count(*) FROM %s WHERE date = '%s' AND invoker = '%s';" % (SQLITE_GIFTS_TABLE,date,invoker))
    row = c.fetchone()

    db_conn.commit()
    db_conn.close()

    return row[0]

def get_account_posts(account):
    acc = Account(account)
    account_history = acc.get_account_history(-1, 5000)
    account_history = [x for x in account_history if x['type'] == 'comment' and not x['parent_author']]

    return account_history


def get_account_details(account):
    acc = Account(account)
    return acc.json()


def get_block_number():

    if not os.path.exists(BLOCK_STATE_FILE_NAME):
        return None

    with open(BLOCK_STATE_FILE_NAME, 'r') as infile:
        block_num = infile.read()
        block_num = int(block_num)
        return block_num


def set_block_number(block_num):

    with open(BLOCK_STATE_FILE_NAME, 'w') as outfile:
        outfile.write('%d' % block_num)


def has_already_replied(post):

    for reply in post.get_replies():
        if reply.author == ACCOUNT_NAME:
            return True

    return False


def post_comment(parent_post, author, comment_body):
    if ENABLE_COMMENTS:
        print('Commenting!')
        parent_post.reply(body=comment_body, author=author)
        # sleep 3s before continuing
        time.sleep(3)
    else:
        print('Debug mode comment:')
        print(comment_body)

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



def daily_limit_reached(invoker_name, level=1):

    today = str(date.today())
    today_gift_count = db_count_gifts(today, invoker_name)

    print(today_gift_count)

    access_level = 'AccessLevel%d' % level

    if today_gift_count >= int(config[access_level]['MAX_DAILY_GIFTS']):
        return True

    return False


def get_invoker_level(invoker_name, invoker_balance, invoker_stake):
    # does invoker meet level 2 requirements?
    min_balance = float(config['AccessLevel2']['MIN_TOKEN_BALANCE'])
    min_staked = float(config['AccessLevel2']['MIN_TOKEN_STAKED'])

    if invoker_balance >= min_balance and invoker_stake >= min_staked:
        return 2

    # does invoker meet level 1 requirements?
    min_balance = float(config['AccessLevel1']['MIN_TOKEN_BALANCE'])
    min_staked = float(config['AccessLevel1']['MIN_TOKEN_STAKED'])

    if invoker_balance >= min_balance and invoker_stake >= min_staked:
        return 1

    return 0


def can_gift(invoker_name, invoker_balance, invoker_stake):

    if invoker_name in config['HiveEngine']['GIFT_ALLOW_LIST']:
        return True

    level = get_invoker_level(invoker_name, invoker_balance, invoker_stake)

    if level == 0:
        return False

    if not daily_limit_reached(invoker_name, level):
        return True

    return False


def hive_posts_stream():

    db_create_tables()

    blockchain = Blockchain(node=[HIVE_API_NODE])

    start_block = get_block_number()

    for op in blockchain.stream(opNames=['comment','vote'], start=start_block, threading=False, thread_num=1):

        set_block_number(op['block_num'])

        if 'type' in op.keys() and op['type'] == 'vote':
            if 'voter' in op.keys() and op['voter'] == config['VoteWatcher']['FOLLOW_ACCOUNT']:
                print('%s -> %s' % (op['voter'], op['author']))

                # skip downvotes
                if op['weight'] < 0:
                    print('Downvote')
                    continue

                author_account = op['voter']
                parent_author = op['author']
                # we reply to post instead of a comment
                reply_identifier = '@%s/%s' % (parent_author,op['permlink'])

                print('Found curation vote in block # %s - https://peakd.com/%s' % (op['block_num'],reply_identifier)) 

            else:
                # skip votes from other accounts
                continue

        else:
            # it's a comment or post

            # how are there posts with no author?
            if 'author' not in op.keys():
                continue

            author_account = op['author']
            parent_author = op['parent_author']
            reply_identifier = '@%s/%s' % (author_account,op['permlink'])

            if parent_author == ACCOUNT_NAME:
                message_body = '%s replied with: %s' % (author_account,op['body'])
                post_discord_message(ACCOUNT_NAME, message_body)

            # skip comments that don't include the bot's command prefix
            if BOT_COMMAND_STR not in op['body'] and ESP_BOT_COMMAND_STR not in op['body']:
                continue
            else:
                debug_message = 'Found %s command: https://peakd.com/%s in block %s' % (BOT_COMMAND_STR, reply_identifier, op['block_num'])
                print(debug_message)


        if not parent_author:
            continue

        # no self-tipping
        if author_account == parent_author:
            continue

        # check if spanish language comment templates should be used
        use_spanish_templates = ESP_BOT_COMMAND_STR in op['body']

        message_body = '%s asked to send a slice to %s' % (author_account, parent_author)
        post_discord_message(ACCOUNT_NAME, message_body)

        try:
            post = Comment(reply_identifier)
        except beem.exceptions.ContentDoesNotExistsException:
            print('post not found!')
            continue

        # if we already commented on this post, skip
        if has_already_replied(post):
            print("We already replied!")
            continue


        # check how much TOKEN the invoker has
        TOKEN_NAME = config['HiveEngine']['TOKEN_NAME']
        wallet_token_info = Wallet(author_account).get_token(TOKEN_NAME)

        if not wallet_token_info:
            invoker_balance = 0
            invoker_stake = 0
        else:
            invoker_balance = float(wallet_token_info['balance'])
            invoker_stake = float(wallet_token_info['stake'])

        invoker_level = get_invoker_level(author_account, invoker_balance, invoker_stake)

        if not can_gift(author_account, invoker_balance, invoker_stake):

            print('Invoker doesnt meet minimum requirements')

            min_balance = float(config['AccessLevel1']['MIN_TOKEN_BALANCE'])
            min_staked = float(config['AccessLevel1']['MIN_TOKEN_STAKED'])

            if invoker_level > 0 and daily_limit_reached(author_account):
                max_daily_gifts = config['AccessLevel%s' % invoker_level]['MAX_DAILY_GIFTS']

                if use_spanish_templates:
                    comment_body = esp_comment_daily_limit_template.render(token_name=TOKEN_NAME,
                                                          target_account=author_account,
                                                          max_daily_gifts=max_daily_gifts)
                else:
                    comment_body = comment_daily_limit_template.render(token_name=TOKEN_NAME,
                                                                      target_account=author_account,
                                                                      max_daily_gifts=max_daily_gifts)
                message_body = '%s tried to send PIZZA but reached the daily limit.' % (author_account)
            else:
                if use_spanish_templates:
                    comment_body = esp_comment_fail_template.render(token_name=TOKEN_NAME,
                                                                target_account=author_account,
                                                                min_balance=min_balance,
                                                                min_staked=min_staked)
                else:
                    comment_body = comment_fail_template.render(token_name=TOKEN_NAME,
                                                                target_account=author_account,
                                                                min_balance=min_balance,
                                                                min_staked=min_staked)
                message_body = '%s tried to send PIZZA but didnt meet requirements.' % (author_account)

            post_comment(post, ACCOUNT_NAME, comment_body)
            print(message_body)
            post_discord_message(ACCOUNT_NAME, message_body)

            continue

        # check how much TOKEN the bot has
        TOKEN_GIFT_AMOUNT = float(config['HiveEngine']['TOKEN_GIFT_AMOUNT'])
        bot_balance = float(Wallet(ACCOUNT_NAME).get_token(TOKEN_NAME)['balance'])
        if bot_balance < TOKEN_GIFT_AMOUNT:

            message_body = 'Bot wallet has run out of %s' % TOKEN_NAME
            print(message_body)
            post_discord_message(ACCOUNT_NAME, message_body)

            if use_spanish_templates:
                comment_body = esp_comment_outofstock_template.render(token_name=TOKEN_NAME)
            else:
                comment_body = comment_outofstock_template.render(token_name=TOKEN_NAME)
            post_comment(post, ACCOUNT_NAME, comment_body)

            continue

        # transfer

        if ENABLE_TRANSFERS:
            print('[*] Transfering %f %s from %s to %s' % (TOKEN_GIFT_AMOUNT, TOKEN_NAME, ACCOUNT_NAME, parent_author))

            wallet = Wallet(ACCOUNT_NAME, steem_instance=HIVE)
            wallet.transfer(parent_author, TOKEN_GIFT_AMOUNT, TOKEN_NAME, memo=config['HiveEngine']['TRANSFER_MEMO'])

            today = str(date.today())
            db_save_gift(today, author_account, parent_author, op['block_num'])

            message_body = 'I sent %f %s to %s' % (TOKEN_GIFT_AMOUNT, TOKEN_NAME, parent_author)
            print(message_body)
            post_discord_message(ACCOUNT_NAME, message_body)
        else:
            print('[*] Skipping transfer of %f %s from %s to %s' % (TOKEN_GIFT_AMOUNT, TOKEN_NAME, ACCOUNT_NAME, parent_author))

        # Leave a comment to nofify about the transfer
        if 'type' in op.keys() and op['type'] == 'vote':
            comment_body = comment_curation_template.render(token_name=TOKEN_NAME, target_account=parent_author, token_amount=TOKEN_GIFT_AMOUNT, author_account=author_account)
        else:
            today = str(date.today())
            today_gift_count = db_count_gifts(today, author_account)
            max_daily_gifts = config['AccessLevel%s' % invoker_level]['MAX_DAILY_GIFTS']

            if use_spanish_templates:
                # use Spanish template
                comment_body = esp_comment_success_template.render(token_name=TOKEN_NAME, target_account=parent_author, token_amount=TOKEN_GIFT_AMOUNT, author_account=author_account,  today_gift_count=today_gift_count, max_daily_gifts=max_daily_gifts)
            else:
                comment_body = comment_success_template.render(token_name=TOKEN_NAME, target_account=parent_author, token_amount=TOKEN_GIFT_AMOUNT, author_account=author_account,  today_gift_count=today_gift_count, max_daily_gifts=max_daily_gifts)
        post_comment(post, ACCOUNT_NAME, comment_body)

        #break

if __name__ == '__main__':

    hive_posts_stream()

#!/usr/bin/env python3
'''A script to findm and react to PIZZA commands in comments'''
from beem import Steem
from beem.account import Account
from beem.blockchain import Blockchain
from beem.comment import Comment
import beem.instance
import os
import jinja2
import configparser
import time
import requests

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

print('Loaded configs:')
for key in config['Global'].keys():
    print(key + ' = ' + config['Global'][key])
for key in config['HiveEngine'].keys():
    print(key + ' = ' + config['HiveEngine'][key])


# Markdown templates for comments
comment_fail_template = jinja2.Template(open('comment_fail.template','r').read())
comment_outofstock_template = jinja2.Template(open('comment_outofstock.template','r').read())
comment_success_template = jinja2.Template(open('comment_success.template','r').read())

PIZZA_GIFS = ['![I Sent You Some Pizza GIF-downsized.gif](https://files.peakd.com/file/peakd-hive/pizzabot/24243uENGsh6uW4qKCGujxK4BvoMKN5RcN7sfaEJ5NKJtep8rt9afWsVtg3Kvjtq1pDjS.gif)',
'![Mmmpizza GIF-downsized.gif](https://files.peakd.com/file/peakd-hive/pizzabot/23zGqBEBBrndd2a4j4sFd7pfokJbPP78MUeXbhTF7tpkm68TDPNKpyEQx6SyXfw2TvxCc.gif)',
'![Out If Pizza GIF-downsized.gif](https://files.peakd.com/file/peakd-hive/pizzabot/23xouo4FKcHyERYKyiEm4x425LXY5UZsLSbwPtftnNGdqpGPpP9TwJ6k3WfLGw7dRi8ix.gif)',
'![Pizza Bro GIF-downsized.gif](https://files.peakd.com/file/peakd-hive/pizzabot/23wqthb5pRQCesbcTuqXfTcNtjLsRRRTpEUfTaMAqm1h8jVmEgYikZjf2edLHrRcoDriQ.gif)',
'![Pizza Delivery 2 GIF-downsized.gif](https://files.peakd.com/file/peakd-hive/pizzabot/23yd8DEejLwG8jbK6yiHPUqaQqC2rWNvVjANJcC5J5LQM3NKz9SHZZqCy9Lzg1YsnoR5W.gif)',
'![Pizza Tickle GIF-downsized.gif](https://files.peakd.com/file/peakd-hive/pizzabot/242DXLG4DJojrUAscw229UnyJkGma6C1QoCQjngcVG2LFbkaTdN4oJw9WgLLxV3N2oWLc.gif)',
'![Slice GIF-downsized.gif](https://files.peakd.com/file/peakd-hive/pizzabot/23sdt4qbqaFxwbYhkYuviGR8kBeGLTYeaveqjXiwGSRUbxyV5J5rusMoXD1AGk2JhpDsi.gif)',
'![Smell The Pizza GIF-downsized_large.gif](https://files.peakd.com/file/peakd-hive/pizzabot/23wX5M8YHK92Kzmr8gAE1mZRePnsG96StjiPPnDYGcdq6BD3BkmMb7jLrCiPVrGRKsbBi.gif)',
'![Sweet Pizza GIF-downsized.gif](https://files.peakd.com/file/peakd-hive/pizzabot/23xL35bVpiQbPTwnuBMMPsEpSbApf598uVE9fMXq8SKj5Hzh2ik4CnHYWcRNBriXkk5gQ.gif)',
'![Wanna Slice GIF-downsized_large.gif](https://files.peakd.com/file/peakd-hive/pizzabot/242DQXTLyKebw5oUNSqsNPvoqPDXCgPKafnoB2zE7bBqyfCAKxKL44r4SarskWCmYY4Lc.gif)',
'![What No Pizza 2 GIF-downsized.gif](https://files.peakd.com/file/peakd-hive/pizzabot/242s64cMzwVBDgMuApdLgtJrj4G4Qt3dTjJuKWFb4MXCvwiXAorV25iTUMFjU4gPm1azQ.gif)',
'![Yes Pizza GIF-downsized.gif](https://files.peakd.com/file/peakd-hive/pizzabot/23y92ccQqXL7ixb1AYUg8T6yHRAEiLptBYhuoahFeh8uU8FXt1WFhJBwLysktbFdC46Gc.gif)',
'![Yum Pizza GIF-downsized (1).gif](https://files.peakd.com/file/peakd-hive/pizzabot/242Nt1WKYcjivqc1FPyfqwQ6vkTs7sznxWKYagPhc7TQ4v8VSYNA46NEswjkZeiSxuRAC.gif)',
'![Eat Pizza GIF-downsized_large.gif](https://files.peakd.com/file/peakd-hive/pizzabot/23xKxeFC2EKESp2cQ3MrPHcAHEaFtvf2mekStgrqqSxYS5rL7PnfmNwoWVQbdJwJS6zQt.gif)',
'![Hands Off My Pizza GIF-downsized_large.gif](https://files.peakd.com/file/peakd-hive/pizzabot/242hfEv5oigYcb19z6ZDEPANTmAn1rWub84KKSJqdbtenEWhPxK2H1tqwanWzTrXZC3LQ.gif)',
'![Hungry For Pizza GIF-downsized_large.gif](https://files.peakd.com/file/peakd-hive/pizzabot/23xerFt4yJKoK1hhVdzVEYpKMKbGUHaW9SR3g7os8UmqAZLsnhs5QgWGeD9NNk72FNGxC.gif)',
'![Love Pizza GIF-downsized_large (1).gif](https://files.peakd.com/file/peakd-hive/pizzabot/243Bpw3x8jfheRpNACEc9fjrrLvn2Qtw8KQwhwscRjLc8BNfhxktPjuLDvnjTv7wCeLVi.gif)',
'![Pizza GIF-downsized_large.gif](https://files.peakd.com/file/peakd-hive/pizzabot/23xAcRA5z5PG8aNLzq3jcDrSwP6eVYAagSSooGTzWQ4TZHPvNH8Ccc16zwtP6y3fkgX1e.gif)',
'![Share The Pizza GIF-downsized_large.gif](https://files.peakd.com/file/peakd-hive/pizzabot/23zGkxUGqyXMTN7rVm2EPkLr6dsnk4T4nFyrEBejS9WB2VbKpJ3P356EcQjcrMF6gRTbz.gif)',
'![What No Pizza GIF-downsized.gif](https://files.peakd.com/file/peakd-hive/pizzabot/23x17QUuztsLf64Mav8m59nuRF4B9k3RAV6QGrtpvmc3hA9bxSJ2URkW7fuYSfaRLKAq2.gif)',
'![No Pizza Left GIF-downsized_large.gif](https://files.peakd.com/file/peakd-hive/pizzabot/23wC5ZpMMfnFCsLS4MLF3N6XZ2aMQ1Fjnw6QGrZtpJqQmiH4xtsUEgjjCD5VU3ccjoRet.gif)']


### END Global configuration

HIVE = Steem(node=[HIVE_API_NODE], keys=[ACCOUNT_POSTING_KEY])
beem.instance.set_shared_blockchain_instance(HIVE)
ACCOUNT = Account(ACCOUNT_NAME)

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

    WEBHOOK_URL = config['Global']['DISCORD_WEBHOOK_URL']
    payload = {
        "username": username,
        "content": message_body
    }

    try:
        requests.post(WEBHOOK_URL, data=payload)
    except:
        print('Error while sending discord message. Check configs.')

def hive_posts_stream():

    blockchain = Blockchain(node=[HIVE_API_NODE])

    start_block = get_block_number()

    for op in blockchain.stream(opNames=['comment'], start=start_block, threading=False, thread_num=1):

        set_block_number(op['block_num'])

        # how are there posts with no author?
        if 'author' not in op.keys():
            continue

        author_account = op['author']
        parent_author = op['parent_author']

        if not parent_author:
            continue

        # no self-tipping
        if author_account == parent_author:
            continue

        reply_identifier = '@%s/%s' % (author_account,op['permlink'])

        BOT_COMMAND_STR = config['Global']['BOT_COMMAND_STR']

        if BOT_COMMAND_STR not in op['body']:
            continue
        else:
            message_body = 'Found %s command: https://peakd.com/%s in block %s' % (BOT_COMMAND_STR, reply_identifier, op['block_num'])
            print(message_body)
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
        invoker_balance =float(wallet_token_info['balance'])
        invoker_stake = float(wallet_token_info['stake'])

        min_balance = float(config['HiveEngine']['MIN_TOKEN_BALANCE'])
        min_staked = float(config['HiveEngine']['MIN_TOKEN_STAKED'])

        if invoker_balance < min_balance or invoker_stake < min_staked:

            print('Invoker doesnt meet minimum requirements')

            comment_body = comment_fail_template.render(token_name=TOKEN_NAME, target_account=author_account, min_balance=min_balance, min_staked=min_staked)
            post_comment(post, ACCOUNT_NAME, comment_body)

            message_body = '%s tried to send PIZZA but didnt meet requirements: https://peakd.com/%s' % (author_account, reply_identifier)
            print(message_body)
            post_discord_message(ACCOUNT_NAME, message_body)

            continue

        # check how much TOKEN the bot has
        TOKEN_GIFT_AMOUNT = float(config['HiveEngine']['TOKEN_GIFT_AMOUNT'])
        bot_balance = float(Wallet(author_account).get_token(TOKEN_NAME)['balance'])
        if bot_balance < TOKEN_GIFT_AMOUNT:

            message_body = 'Bot wallet has run out of %s' % TOKEN_NAME
            print(message_body)
            post_discord_message(ACCOUNT_NAME, message_body)

            comment_body = comment_outofstock_template.render(token_name=TOKEN_NAME)
            post_comment(post, ACCOUNT_NAME, comment_body)

            continue

        # transfer
        if ENABLE_TRANSFERS:
            print('[*] Transfering %f %s from %s to %s' % (TOKEN_GIFT_AMOUNT, TOKEN_NAME, ACCOUNT_NAME, parent_author))
            stm = Steem(keys=[config['Global']['ACCOUNT_ACTIVE_KEY']])
            wallet = Wallet(ACCOUNT_NAME, steem_instance=stm)
            wallet.transfer(parent_author, TOKEN_GIFT_AMOUNT, TOKEN_NAME, memo="")

            message_body = 'I sent %f %s to %s' % (TOKEN_GIFT_AMOUNT, TOKEN_NAME, parent_author)
            print(message_body)
            post_discord_message(ACCOUNT_NAME, message_body)
        else:
            print('[*] Skipping transfer of %f %s from %s to %s' % (TOKEN_GIFT_AMOUNT, TOKEN_NAME, ACCOUNT_NAME, parent_author))

        # Leave a comment to nofify about the transfer
        comment_body = comment_success_template.render(token_name=TOKEN_NAME, target_account=parent_author, token_amount=TOKEN_GIFT_AMOUNT, pizza_gifs=PIZZA_GIFS)
        post_comment(post, ACCOUNT_NAME, comment_body)

        #break

if __name__ == '__main__':

    hive_posts_stream()

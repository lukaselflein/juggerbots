#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This program is dedicated to the public domain under the CC0 license.
"""
Telegram bot for keeping the scores in a jugger team.
"""

import logging
import json 
import os
import time
import pandas as pd

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


# A dataframe that goes like
# Date PersonA PersonB PointsA PointsB
# 10.5 Max     Lu      10      8
sparring_df = pd.DataFrame(columns=['time', 'person_a', 'person_b', 
                                        'points_a', 'points_b']) 


# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update, context):
    """Send a message when the command /start is issued."""
    update.message.reply_text('Hi Rigor!')


def help(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Help!')


def parse(update, context):
    """Parse text for commands."""
    global sparring_df

    text = update.message.text.lower()
    if text is None:
        update.message.reply_text('Empty Message.')

    words = text.split(' ')
    # e.g., Ludo Günther 10-6
    if len(words) > 2:
        names = [words[0], words[1]]

    # e.g., Ludo Günther 10-6
    if len(words) == 3:
        score = words[2]
        # allow more score formats like 5/10, 5:10
        for seperator in ['-', ':', '/']:
            if seperator in score:
                print(seperator, ' in ', score)
                points = score.split(seperator)
                print(points)
                if len(points) != 2:
                    update.message.reply_text(f'Bad score format: {score}')
                    return

    new_row = {'time': pd.Timestamp.now(), 'person_a':words[0], 'person_b': words[1], 
               'points_a': points[0], 'points_b': points[1]}
    print(new_row)

    sparring_df = sparring_df.append(new_row, ignore_index=True)


    update.message.reply_text(f'added {words[0]} {words[1]} {points[0]}:{points[1]}')


def stats(update, context):
    text = update.message.text.lower()
    words = text.split(' ')
    # Command is just /stats
    if len(words) == 1:
        update.message.reply_text(f'{str(sparring_df)}')

    elif len(words) == 2:
        matches = sparring_df[sparring_df.person_a == words[1]]
        output = matches[['person_a', 'person_b', 'points_a', 'points_b']]
        # TODO: append cases where search name is second pos
        update.message.reply_text(f'{str(matches)}')

    elif len(words) == 3:
        matches = sparring_df[sparring_df.person_a == words[1]]
        matches = matches[sparring_df.person_b == words[2]]
        update.message.reply_text(f'{str(matches)}')


def read_secrets(path=None, token_name='pompfbot_token'):
    __location__ = os.path.realpath(
        os.path.join(os.getcwd(), os.path.dirname(__file__)))
    absolute_path = os.path.join(__location__, path)

    with open(path, 'r') as infile:
        json_dict = json.load(infile)
    api_token = json_dict[token_name]
    return api_token


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    """Start the bot."""
    token = read_secrets(path='./secrets.json')

    # Create the Updater and pass it your bot's token.
    updater = Updater(token, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("help", help))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.text, parse))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()

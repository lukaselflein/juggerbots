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

def save_table(df):
    filename = './data/scores.csv'
    df.to_csv(filename)

def init_table():

    # make sure data folder exists
    if not os.path.exists('./data/'):
        os.mkdir('./data/')

    # check if df for scores already exists
    filename = './data/scores.csv'
    if os.path.exists(filename):
        sparring_df = pd.read_csv(filename)
        return sparring_df

    else:
        # Initiate a dataframe like
        # Date        person_a person_b points_a points_b
        # 2020-10-..3 Max      Lu       10       8
        # ....
        sparring_df = pd.DataFrame(columns=['time', 'person_a', 'person_b', 
                                                'points_a', 'points_b']) 
        save_table(sparring_df)
        return sparring_df

sparring_df = init_table()



def delete_table():
    filename = './data/scores.csv'
    os.rename(filename, filename + '_bk_' + str(time.time()))


def clear(update, context):
    delete_table()
    global sparring_df
    sparring_df = init_table()
    update.message.reply_text('Deleted all entries.')


def start(update, context):
    """Send a message when the command /start is issued."""
    update.message.reply_text('Hi Rigor!')


def help(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Help!')


def parse(update, context):
    """Parse text input, extract names and points."""
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

    # e.g., Ludo Günther 10 6
    if len(words) == 4:
        points = [words[2], words[3]]

    print(words, points)

    # convert points to int
    try:
        points[0], points[1] = int(points[0]), int(points[1])
    except:
        update.message.reply_text(f'Bad score format: {score}')

    # Leave everything if ordered
    if words[0] < words[1]:
        first_person = words[0]
        first_score = points[0]
        second_person = words[1]
        second_score = points[1]

    # Swap scores and persons if not alphabetically ordered
    elif words[0] > words[1]:
        first_person = words[1]
        first_score = points[1]
        second_person = words[0]
        second_score = points[0]
    
    else:
        raise(ValueError, f'Persons must be different')

    new_row = {'time': pd.Timestamp.now(), 
               'person_a': first_person, 'person_b': second_person, 
               'points_a': first_score, 'points_b': second_score}

    sparring_df = sparring_df.append(new_row, ignore_index=True)
    save_table(sparring_df)

    update.message.reply_text(f'added {first_person} {second_person} {first_score}:{second_score}')


def stats(update, context):
    text = update.message.text.lower()
    words = text.split(' ')
    print(words)
    # Command is just /stats
    if len(words) == 1:
        update.message.reply_text(f'{str(sparring_df)}')

    # Command is like /stats lu
    elif len(words) == 2:
        matches = sparring_df[(sparring_df.person_a == words[1]) | (sparring_df.person_b == words[1])]

    # Command is like /stats lu max
    elif len(words) == 3:
        # todo a != b
        filtered_1 = sparring_df[(sparring_df.person_a == words[1]) | (sparring_df.person_a == words[1])]
        matches = filtered_1[(sparring_df.person_a == words[2]) | (sparring_df.person_b == words[2])]

    # Malformed command like '/stats a b c' or double spaces
    else:
        update.message.reply_text(f'Could not parse {text}.')
        return
        
    output = matches.groupby(['person_a', 'person_b']).agg('sum')
    output['ratio'] = round(100 * output.points_a / (output.points_b + output.points_a), 0)
    output = output.reset_index()


    # Output formatting
    max_len_a = output.person_a.map(lambda x: len(x)).max()
    asci_table = ''
    for index, row in output.iterrows():
        asci_table += f'{row.person_a}:{row.person_b}\t {row.points_a}:{row.points_b}\t {int(row.ratio)}%\n'
        

    update.message.reply_text(f'{asci_table}')
    return


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
    dp.add_handler(CommandHandler("s", stats))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("clear", clear))

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

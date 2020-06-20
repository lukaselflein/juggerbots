#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This program is dedicated to the public domain under the CC0 license.
"""
Telegram bot for keeping the scores in a jugger team.
"""

import argparse
import logging
import json 
import time
import os
import re
import pandas as pd

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import telegram

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


def parse_cli():
    parser = argparse.ArgumentParser(description='Run a telegram bot for keeping stats.')
    parser.add_argument('--keyname', default='pompfbot_token',
                        help='Name of the secret API key for the bot')
    args = parser.parse_args()
    return args.keyname

def start(update, context):
    """Send a message when the command /start is issued."""
    update.message.reply_text('Hi Rigor!')


def help(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Help!')


def handle_data(text, update, context):
    """Extract names and scores from telegram input."""

    # eliminate double spaces
    clean_text = re.sub('\s+', ' ', text)

    words = clean_text.split(' ')
    # e.g., "Ludo Günther"
    if len(words) >= 2:
        names = [words[0], words[1]]
        # Check if names are unique, no self-matches possible
        if names[0] == names[1]:
            update.message.reply_text(f'Names must be unequal: "{text}"')
            return

    # e.g., Ludo Günther 5-10
    if len(words) == 3:
        score = words[2]
        # allow more score formats like 5/10, 5:10
        for seperator in ['-', ':', '/']:
            if seperator in score:
                points = score.split(seperator)
                if len(points) != 2:
                    update.message.reply_text(f'Bad score format: {score}')
                    return

    # e.g., Ludo Günther 10 6
    if len(words) == 4:
        points = [words[2], words[3]]

    # validate that the score consists of natural numbers
    try:
        points[0], points[1] = int(points[0]), int(points[1])
    except:
        update.message.reply_text(f'Bad score format: {points}')
        return

    player_points, opponent_points = points[0], points[1]
    player_name, opponent_name = names[0], names[1]
    # Add a new data row like
    # 2020-20-6 max lu 4 10
    data = [[pd.Timestamp.now(), player_name, opponent_name, 
             player_points, opponent_points]]
    # Append a duplicate where player and opponent are swapped, for easier filtering, like
    # 2020-20-6 lu max 10 4
    data += [[pd.Timestamp.now(), opponent_name, player_name, 
              opponent_points, player_points]]

    columns = ['time', 'player', 'opponent', 'player_points', 'opponent_points']
    df = pd.DataFrame(data, columns=columns)
    return df


def parse(update, context):
    """Parse text input, extract names and points."""

    text = update.message.text.lower()
    if text is None:
        update.message.reply_text('Error: Empty Message.')
        return

    # Sanity checks against overflows
    message_maxlen = 25000  # 1000 lines a 25 chars
    line_maxlen = 30  # names: 20 chars, + 5 chars for result
    if len(text) > message_maxlen:
        update.message.reply_text('Error: Message longer than {message_maxlen}.')
        return

    # Split the message into lines by
    lines = text.split('\n')
    for line in lines:
        if len(line) > line_maxlen:
            update.message.reply_text(f'Error: Line longer than {line_maxlen}.')
            return

        # Do the actual processing     
        df = handle_data(line, update, context)

        # Only use output if no error was encountered
        if df is not None:
            data = save_entry(df)

    return


def save_entry(df, path='./data/scores.csv'):
    """Append pandas dataframe to csv at rest."""

    # Load old data
    rest_data = read_db(path=path, update=None, context=None)

    if rest_data is not None:
        # If we have old data on disk, append the new data
        new_data = pd.concat([rest_data, df], ignore_index=True)
    else:
        # Otherwise, the new stuff is all we have 
        new_data = df

    new_data.to_csv(path, index=False)
    return new_data


def read_db(update=None, context=None, path='./data/scores.csv'):
    """Output the currently stored data as pandas dataframe"""
    try:
        # Check if we already have a file
        rest_data = pd.read_csv(path)
    except:
        rest_data = None
    return rest_data


def delete_db(update=None, context=None, path='./data/scores.csv'):
    """Backup & delete the database."""
    backup_path = path + '_bk_' + str(int(time.time()))
    os.rename(path, backup_path)
    update.message.reply_text('All scores deleted.')


def push_db():
    """Push the local database to the online google docs sheet."""


def pull_db():
    """Get the most recent version of the google docs table."""

def stats(update, context):
    """Output aggregated statistics"""
    # Parse & clean
    text = update.message.text.lower()
    clean_text = re.sub('\s+', ' ', text)
    words = text.split(' ')

    data = read_db()
    if data is None:
        update.message.reply_text(f'No data on disk.')
        return

    # Command is just "/stats"
    if len(words) == 1:
        filtered_data = data

    # Command is like "/stats max"
    elif len(words) == 2:
        player = words[1]
        filtered_data = data[data.player == player]

    # Command is like "/stats lu max"
    elif len(words) == 3:
        player, opponent = words[1], words[2]
        player_filtered_data = data[data.player == player]
        filtered_data = player_filtered_data[data.opponent == opponent]

    # Malformed command like '/stats a b c' or double spaces
    else:
        update.message.reply_text(f'Invalid command: \n"{text}".')
        return
        
    output = filtered_data.groupby(['player', 'opponent']).agg('sum')
    output['ratio'] = round(100 * output.player_points 
                            / (output.player_points + output.opponent_points),
                            0)
    output = output.reset_index()

    # Output formatting
    asci_table = ''
    for index, row in output.iterrows():
        asci_table += f'{row.player:10}{row.opponent:10}' 
        asci_table += f'{row.player_points:2}:{row.opponent_points:2}'
        asci_table += f' \t{int(row.ratio)}%\n'
        

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

    keyname = parse_cli()
    
    token = read_secrets(path='./secrets.json', token_name=keyname)
    print(token)
    exit()

    # Create the Updater and pass it your bot's token.
    updater = Updater(token, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("s", stats))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("clear", delete_db))
    dp.add_handler(CommandHandler("delete", delete_db))

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

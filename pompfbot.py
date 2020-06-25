#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This program is dedicated to the public domain under the MIT license.
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
import pickle
import telegram

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from utility import GoogleSheet, read_secrets, check_connection, handle_data 

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


def parse(update, context):
    """Parse text input, extract names and points."""

    if not check_connection(update, context):
        start(update, context)
        if not check_connection(update, context):
            update.message.reply_text('Error: Google sheet could not be found.')


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
            data = save_entry(update, context, df)

    return

def start(update, context):
    """Send a message when the command /start is issued."""
    # Set up a Google Sheet document as a database
    g_sheet = GoogleSheet(sheet_id='1Qmrj-YI5RokrKkfXf9wNubt2oezTGmb8bL-KCUyWf7o', 
                          sheet_range='Data!A1:E')
    context.bot_data['google_sheet'] = g_sheet
    update.message.reply_text('Google Sheet initialized.')


def help(update, context):
    """Send a message when the command /help is issued."""
    text = 'Usage:\n'
    text += 'lu linus 9 10 - add a new duel score\n'
    text += '/stats - all aggregate statistics\n'
    text += '/stats lu - Lu\'s statistics\n'
    text += '/stats lu linus - Lu-vs-Linus statistics\n'
    update.message.reply_text(text)


def save_entry(update, context, df, path='./data/scores.csv'):
    """Append pandas dataframe to csv at rest."""

    google_sheet = context.bot_data['google_sheet']
    # Convert pandas Dataframe -> numpy array -> nested list
    nested_list = df.values.tolist()
    return_status = google_sheet.append(nested_list)
    update.message.reply_text(f'Upload: {return_status}')


def read_db(update, context, path='./data/scores.csv'):
    """Output the currently stored data as pandas dataframe"""

    if not check_connection(update, context):
        start(update, context)

    google_sheet = context.bot_data['google_sheet']
    # Google sheets database
    data = google_sheet.read()
    # Transform list to pandas DataFrame
    df  = pd.DataFrame(data[1:], columns=data[0]) 
    # Cast points from str to int
    df.player_points = df.player_points.astype('int32')
    df.opponent_points = df.opponent_points.astype('int32')

    return df


def stats(update, context):
    """Output aggregated statistics"""
    # Parse & clean
    text = update.message.text.lower()
    clean_text = re.sub('\s+', ' ', text)
    words = text.split(' ')

    data = read_db(update, context)  # Google api returns list
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


def timechart(update, context):
    pass


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    """Start the bot."""


    # Read Command line interface parameters
    keyname = parse_cli()
    
    # Read Telegram secrets file
    token = read_secrets(path='./secrets.json', token_name=keyname)

    # Create the Updater and pass it your bot's token.
    updater = Updater(token, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("s", stats))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("timechart", timechart))
    dp.add_handler(CommandHandler("t", timechart))

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

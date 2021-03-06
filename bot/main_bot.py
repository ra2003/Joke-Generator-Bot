import logging
import os
import sys
from functools import wraps
from configparser import ConfigParser

import telegram
from joke_generator import JokeGenerator, TestABGenerator, RussianModelWrapper
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ChatAction
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

"""
Basic example for a bot that uses inline keyboards.
"""
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO,
                    handlers=[
                        logging.FileHandler("run.log"),
                        logging.StreamHandler(sys.stdout),
                    ])
logger = logging.getLogger(__name__)

cfg = ConfigParser()
cfg.read(os.path.join(os.path.dirname(__file__), 'bot.cfg'))

model_cfg = cfg['model']
model_paths = model_cfg['model_paths'].split(',')
dataset_paths = model_cfg['dataset_paths'].split(',')
model_args = {
    'max_len': int(model_cfg['max_joke_len']),
    'buffer_size': int(model_cfg['buffer_size']),
    'device': model_cfg['device']
}
if cfg['bot']['ab_test'].lower() == 'true':
    joke_generator = TestABGenerator(dataset_paths=dataset_paths,
                                     model_paths=model_paths,
                                     config=model_args
                                     )
else:
    joke_generator = JokeGenerator(model_path=model_paths[0], config=model_args)

if model_cfg.get('rus_model_path'):
    joke_generator = RussianModelWrapper(eng_model=joke_generator,
                                         rus_model_path=model_cfg.get('rus_model_path'),
                                         config=model_args
                                        )

splitter = "::"
pos = "1"
neg = "2"

GREETING_MESSAGE = "Welcome to the _Joke Generator Bot_."

HELP_MESSAGE = "Use `/joke` to generate a joke. " + \
               "Or, if you want a joke on some specific topic from me, " + \
               "just write me a question and I'll answer it in a playful form." + \
               "\n\nTo help me learn, please sent feedback on jokes through the 👍/👎 buttons."

DISCLAIMER_MESSAGE = "*DISCLAIMER*: This bot is still very dumb and " + \
                     "produces a lot of dark and racist humor. " + \
                     "Don't judge him, he learned them from the people"


def send_typing_action(func):
    """Sends typing action while processing func command."""

    @wraps(func)
    def command_func(update, context, *args, **kwargs):
        context.bot.send_chat_action(chat_id=update.effective_message.chat_id,
                                     action=ChatAction.TYPING)
        return func(update, context,  *args, **kwargs)

    return command_func


@send_typing_action
def joke_command_handler(update, context):
    general_joke_handler(update, context, promt_text="")


@send_typing_action
def text_handler(update, context):
    question = update.message.text
    general_joke_handler(update, context, question)


def general_joke_handler(update, context, promt_text=""):
    joke = joke_generator.generate_joke(promt=promt_text)
    joke_id = joke.id

    keyboard = [[InlineKeyboardButton("👍", callback_data=f'{joke_id}{splitter}{pos}'),
                 InlineKeyboardButton("👎", callback_data=f'{joke_id}{splitter}{neg}')]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(joke.text, reply_markup=reply_markup,
                              parse_mode=telegram.ParseMode.MARKDOWN)


def button_handler(update, context):
    query = update.callback_query
    data = query.data
    (joke_id, rating) = data.rsplit(splitter, 1)
    user_id = query.message.chat.id
    if rating == pos:
        joke_generator.positive_grade(user_id=user_id, joke_id=joke_id)
    elif rating == neg:
        joke_generator.negative_grade(user_id=user_id, joke_id=joke_id)
    context.bot.answer_callback_query(query.id, "Thank you for your feedback")


def start_handler(update, context):
    update.message.reply_text(GREETING_MESSAGE + '\n\n'
                              + HELP_MESSAGE + '\n\n' +
                              DISCLAIMER_MESSAGE, parse_mode=telegram.ParseMode.MARKDOWN)


def help_handler(update, context):
    update.message.reply_text(HELP_MESSAGE + '\n\n' + DISCLAIMER_MESSAGE,
                              parse_mode=telegram.ParseMode.MARKDOWN)


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(cfg['bot']['token'], use_context=True)

    updater.dispatcher.add_handler(CommandHandler('joke', joke_command_handler))
    updater.dispatcher.add_handler(CallbackQueryHandler(button_handler))
    updater.dispatcher.add_handler(CommandHandler('start', start_handler))
    updater.dispatcher.add_handler(CommandHandler('help', help_handler))
    updater.dispatcher.add_handler(CallbackQueryHandler(text_handler))
    updater.dispatcher.add_error_handler(error)
    updater.dispatcher.add_handler(MessageHandler(Filters.text, text_handler))

    # Start the Bot
    updater.start_polling()

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()


if __name__ == '__main__':
    main()
